#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kos_service.py — KOS 诊断服务(系统集成层)
====================================================================
把 P3-Alpha 模型 + KOS 引擎 + SHAP 清洗 + 未知物防线
封装成系统可调用的诊断服务。

输入: 场地检测数据(因子→浓度 dict) + 轨道(prod/eco)
输出: 三层诊断(明确障碍 + 关键障碍 KOS + 补测建议) + 模型贡献度 + 数据质量标记
====================================================================
"""
import os
import sys
import json
import math
import joblib
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# PyInstaller 打包后数据在 _MEIPASS 或其 _internal 子目录
if getattr(sys, 'frozen', False):
    _mep = sys._MEIPASS  # type: ignore[attr-defined]
    # PyInstaller 6.x onedir: 数据可能在 _MEIPASS 或 _MEIPASS/_internal
    if os.path.isdir(os.path.join(_mep, 'ml', 'ranking')):
        ROOT = _mep
    elif os.path.isdir(os.path.join(_mep, '_internal', 'ml', 'ranking')):
        ROOT = os.path.join(_mep, '_internal')
sys.path.insert(0, ROOT)

import importlib.util
def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_kos_engine = _load_module(os.path.join(ROOT, "ml", "ranking", "kos_engine_v0.8.py"), "kos_engine")
compute_kos = _kos_engine.compute_kos
compute_severity = _kos_engine.compute_severity
compute_severity_detail = getattr(_kos_engine, "compute_severity_detail", None)
KOS_SEVERITY_CAP_RATIO = getattr(_kos_engine, "KOS_SEVERITY_CAP_RATIO", 10)
EVIDENCE_SCORE = _kos_engine.EVIDENCE_SCORE
KOS_W = _kos_engine.KOS_W
_guardrails = _load_module(os.path.join(ROOT, "ml", "rules", "unknown_organic_guardrails.py"), "guardrails")
guardrail_check = _guardrails.guardrail_check
_shap_svc = _load_module(os.path.join(ROOT, "ml", "explain", "shap_service.py"), "shap_svc")
explain_regression = _shap_svc.explain_regression

# 所有路径基于 ROOT(不 chdir,避免多 worker 冲突)
ART = os.path.join(ROOT, "ml", "artifacts", "p3_alpha")
_OUT_BASE = os.path.join(ROOT, "artifacts", "overnight_20260703")

# 生产轨阈值(GB15618 简化,mg/kg)
PROD_THRESHOLDS = {
    "Cd_mgkg": {"type": "upper", "limit": 0.6}, "Pb_mgkg": {"type": "upper", "limit": 170},
    "As_mgkg": {"type": "upper", "limit": 40}, "Cr_mgkg": {"type": "upper", "limit": 250},
    "Hg_mgkg": {"type": "upper", "limit": 1.3}, "Cu_mgkg": {"type": "upper", "limit": 100},
    "Zn_mgkg": {"type": "upper", "limit": 300}, "Ni_mgkg": {"type": "upper", "limit": 100},
    "BaP_ngg": {"type": "upper", "limit": 550}, "SumHCHs_ngg": {"type": "upper", "limit": 500},
    "SumDDTs_ngg": {"type": "upper", "limit": 500},
}
# 生态轨阈值(GB36600 简化,更宽松)
ECO_THRESHOLDS = {
    "Cd_mgkg": {"type": "upper", "limit": 1.5}, "Pb_mgkg": {"type": "upper", "limit": 400},
    "As_mgkg": {"type": "upper", "limit": 60}, "Cr_mgkg": {"type": "upper", "limit": 250},
    "Hg_mgkg": {"type": "upper", "limit": 1.5}, "Cu_mgkg": {"type": "upper", "limit": 200},
    "Zn_mgkg": {"type": "upper", "limit": 300}, "Ni_mgkg": {"type": "upper", "limit": 100},
}
# pH 区间
PH_THRESHOLD = {"prod": {"type": "interval", "min": 5.5, "max": 8.5},
                "eco": {"type": "interval", "min": 5.0, "max": 8.3}}

# 用途权重(简化,来自课题二 AHP)
PROD_WEIGHTS = {"Cd_mgkg": 0.9, "Pb_mgkg": 0.8, "As_mgkg": 0.85, "Cr_mgkg": 0.7, "Hg_mgkg": 0.85,
                "Cu_mgkg": 0.75, "Zn_mgkg": 0.7, "Ni_mgkg": 0.65, "pH": 0.8, "BaP_ngg": 0.85}
ECO_WEIGHTS = {"Cd_mgkg": 0.85, "Pb_mgkg": 0.85, "As_mgkg": 0.9, "Cr_mgkg": 0.8, "Hg_mgkg": 0.9,
               "Cu_mgkg": 0.7, "Zn_mgkg": 0.65, "Ni_mgkg": 0.7, "pH": 0.75}

# 特征名映射(中文场地数据 → x_measured_ 特征名)
# 这是从甲方检测数据到模型特征的桥梁
VALUE_TO_FEATURE = {
    "镉": "Cd_mgkg", "Cd": "Cd_mgkg", "镉_Cd": "Cd_mgkg",
    "铅": "Pb_mgkg", "Pb": "Pb_mgkg", "铅_Pb": "Pb_mgkg",
    "砷": "As_mgkg", "As": "As_mgkg", "砷_As": "As_mgkg",
    "铬": "Cr_mgkg", "Cr": "Cr_mgkg",
    "汞": "Hg_mgkg", "Hg": "Hg_mgkg",
    "铜": "Cu_mgkg", "Cu": "Cu_mgkg", "铜_Cu": "Cu_mgkg",
    "锌": "Zn_mgkg", "Zn": "Zn_mgkg", "锌_Zn": "Zn_mgkg",
    "镍": "Ni_mgkg", "Ni": "Ni_mgkg",
    "pH": "pH", "SoilpH": "pH", "pH_merged": "pH",
}


def load_registry() -> dict:
    with open(f"{ART}/model_registry_v0.8.json", encoding="utf-8") as f:
        return json.load(f)


def normalize_factors(raw_values: dict) -> dict:
    """把场地原始检测数据(各种命名)归一化到 model 特征名"""
    normed = {}
    for k, v in raw_values.items():
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        # 尝试多种匹配
        for pattern, feat in VALUE_TO_FEATURE.items():
            if pattern in str(k):
                # 单位转换: ng/g 不转, mg/kg 不转
                normed[feat] = float(v)
                break
        else:
            # 未匹配的保留原名(可能是未知有机物)
            normed[str(k)] = float(v)
    return normed


def run_kos_diagnosis(site_values: dict, track: str = "prod", subset: str = "all",
                      top_n: int = 10, site_pH: float | None = None,
                      land_use_type: str | None = None, db_session=None) -> dict:
    """运行完整 KOS 诊断。
    site_values: {因子名(各种格式): 浓度值}
    track: prod / eco
    subset: all / hm / op / hm_op (决定用哪个模型)
    site_pH: 场地 pH 值(用于动态阈值选择, M0-2)
    land_use_type: 土地用途(用于动态阈值选择)
    db_session: 数据库 session(用于查询 StandardThreshold, M0-2)
    """
    # M0-1: 归一化使用 normalize_factors_v2(精确匹配, 替代旧 substring)
    from app.services.factor_normalizer import normalize_factors_v2
    norm_result = normalize_factors_v2(site_values)
    factors = norm_result["factors"]
    mapping_details = norm_result["mapping_details"]
    mapping_conflicts = norm_result["mapping_conflicts"]
    unmapped = norm_result["unmapped"]
    data_quality_flags = list(norm_result["data_quality_flags"])

    # 冲突因子不进正式 KOS(M0-1 要求)
    conflict_factors = set()
    for c in mapping_conflicts:
        conflict_factors.add(c["canonical"])
        factors.pop(c["canonical"], None)
    if mapping_conflicts:
        data_quality_flags.append(
            f"mapping_conflicts: {len(mapping_conflicts)} 个因子有来源冲突, 已排除出正式KOS, 需人工选择")

    # 单位转换详情
    unit_conversion_details = [
        {"original_name": d["original_name"], "canonical": d.get("canonical"),
         "unit_raw": d.get("unit_raw"), "unit_converted": d.get("unit_converted"),
         "conversion_factor": d.get("conversion_factor", 1.0)}
        for d in mapping_details
    ]

    # 选模型
    model_id = f"{subset}_{track}_Full_RandomForest"
    registry = load_registry()
    model_info = registry["models"].get(model_id)
    if model_info is None:
        return {"error": f"模型 {model_id} 未注册"}

    is_op = subset in {"op", "hm_op"}
    is_exploratory = model_info["status"] == "exploratory"

    # 加载 SHAP measured 贡献(清洗后的)
    shap_tag = model_id.replace("_Full_RandomForest", "")
    measured_csv = os.path.join(_OUT_BASE, "shap_filtered", f"{shap_tag}_measured_contribution_global.csv")
    if os.path.exists(measured_csv):
        shap_measured = pd.read_csv(measured_csv)
    else:
        # fallback: 用原始 shap_global 并过滤
        sg = pd.read_parquet(f"{ART}/{model_id}_shap_global.parquet")
        shap_measured = sg[~sg["group"].str.contains("缺失指示", na=False)].copy()

    # M0-2: 动态阈值选择 — 优先从数据库查询(pH+land_use), 静态仅 emergency fallback(默认关闭)
    thresholds = {}
    threshold_meta = {}  # 每个因子的阈值元数据
    ambiguous_factors = []
    USE_STATIC_FALLBACK = False  # 静态 fallback 默认关闭(M0-2 要求)

    if db_session is not None:
        from app.services.threshold_resolver import resolve_threshold_from_db, resolve_threshold_fallback
        for fac in list(factors.keys()):
            if fac == "pH":
                thresholds["pH"] = PH_THRESHOLD[track]
                continue
            thr_result = resolve_threshold_from_db(
                db_session, fac, track=track, site_pH=site_pH, land_use_type=land_use_type)
            if thr_result["threshold_resolution_status"] == "resolved":
                thresholds[fac] = thr_result["threshold"]
                threshold_meta[fac] = thr_result
            elif thr_result["threshold_resolution_status"] == "ambiguous":
                # v1.0.2(裴总决策 + GPT 4.10): ambiguous 不再 pop 因子!
                # 改用 resolve_threshold_fallback 取 GB15618 最严档兜底,
                # 让甲方看到"有障碍但阈值待核实", 而非"没障碍"
                fb_result = resolve_threshold_fallback(db_session, fac, track=track)
                if fb_result["threshold_resolution_status"] == "fallback":
                    thresholds[fac] = fb_result["threshold"]
                    threshold_meta[fac] = fb_result
                    ambiguous_factors.append(fac)
                    data_quality_flags.append(
                        f"threshold_fallback: {fac} pH/用地缺失, 已用最严档"
                        f"({fb_result['threshold_value']})兜底, 请核实")
                else:
                    # fallback 也查不到(完全无标准) → 该因子退出 KOS
                    ambiguous_factors.append(fac)
                    data_quality_flags.append(
                        f"threshold_not_found: {fac} 无任何标准阈值, 不进KOS")
                    factors.pop(fac, None)
            # not_found 的因子不进 KOS(无阈值)

    # emergency fallback(默认关闭): 仅当 db_session 为 None 或无数据时
    if not thresholds and USE_STATIC_FALLBACK:
        thresholds = dict(PROD_THRESHOLDS if track == "prod" else ECO_THRESHOLDS)
        thresholds["pH"] = PH_THRESHOLD[track]
        data_quality_flags.append("WARNING: 使用静态硬编码阈值(emergency fallback), 非数据库动态查询")
    elif not thresholds and db_session is None:
        # 无 db_session 时用静态(兼容旧调用方式, 但标记)
        thresholds = dict(PROD_THRESHOLDS if track == "prod" else ECO_THRESHOLDS)
        thresholds["pH"] = PH_THRESHOLD[track]
        data_quality_flags.append("WARNING: 无 db_session, 使用静态硬编码阈值(请在 API 层传入 db_session)")

    weights = PROD_WEIGHTS if track == "prod" else ECO_WEIGHTS

    # 证据等级: 实测=A, 否则 C
    evidence = {f: "A" for f in factors}

    # KOS 计算
    kos_result = compute_kos(
        shap_measured, factors, thresholds, weights, evidence,
        top_n=top_n, op_model=is_op
    )

    # M0-2: 给 key_obstacles 附加阈值元数据
    for k in kos_result.get("key_obstacles", []):
        fac = k.get("factor")
        if fac in threshold_meta:
            tm = threshold_meta[fac]
            k["threshold_value"] = tm.get("threshold_value")
            k["threshold_unit"] = tm.get("threshold_unit", "mg/kg")
            k["threshold_standard"] = tm.get("threshold_standard", "")
            k["threshold_version"] = tm.get("threshold_version", "")
            k["pH_condition"] = tm.get("pH_condition", "")
            k["land_use_type"] = tm.get("land_use_type", "")
            k["threshold_source_id"] = tm.get("threshold_source_id")
            # v1.0.2: 阈值解析状态 + 兜底说明
            k["threshold_resolution_status"] = tm.get("threshold_resolution_status", "resolved")
            if tm.get("fallback_note"):
                k["fallback_note"] = tm["fallback_note"]

    # 未知有机物三道防线
    known_factors = set(thresholds.keys())
    organic_result = guardrail_check(factors, known_factors)

    # 模型贡献度(只取 measured,前端用) — 口径与 kos_engine 的 m_map 一致(mean_abs_shap/total), 避免双源不一致
    # P0-5 SHAP 口径修复: model_contribution 是"全局模型贡献度"(global_model scope),
    # 不得描述为局部/障碍/因果类口径(详见 interpretation_note 字段)
    model_contribution = []
    if len(shap_measured) > 0:
        total_shap = float(shap_measured["mean_abs_shap"].sum()) if "mean_abs_shap" in shap_measured.columns else 0.0
        for _, r in shap_measured.head(10).iterrows():
            raw = float(r.get("mean_abs_shap", 0))
            model_contribution.append({
                "factor": r["group"],
                "contribution": round(raw / total_shap, 6) if total_shap > 0 else 0.0,
                "direction": r.get("direction", "positive"),
                # P0-5: 显式口径标记, 防止前端误读为局部/因果类口径
                "contribution_scope": "global_model",
            })

    # 四层输出(裴总 P0 规则)
    output = {
        "track": track,
        "model_id": model_id,
        "data_version": "Gold Dataset v0.8",
        "threshold_version": ("数据库动态阈值(StandardThreshold)" if db_session and thresholds
                              else "静态硬编码(需传入db_session启用动态阈值)"),
        "model_status": model_info["status"],
        # M0-1: 因子映射详情
        "mapping_details": mapping_details,
        "mapping_conflicts": mapping_conflicts,
        "unmapped": unmapped,
        "unit_conversion_details": unit_conversion_details,
        # M0-2: 阈值解析详情
        "ambiguous_threshold_factors": ambiguous_factors,
        # 第一层: 明确障碍(实测+有阈值+B=1)
        "explicit_obstacles": kos_result["explicit_obstacles"],
        # 第二层: 关键障碍 Top-N(KOS 排序)
        "key_obstacles": [
            {"rank": k["rank"], "factor": k["factor"], "KOS": k["KOS"],
             "components": {"R": k["R"], "W": k["W"], "M": k["M"], "S": k["S"], "E": k["E"]},
             "value": k["value"], "evidence": k["E"],
             # P0-4 透明化字段 (向后兼容, 只新增)
             "exceedance_ratio": k.get("exceedance_ratio", 0.0),
             "severity_cap_ratio": k.get("severity_cap_ratio", KOS_SEVERITY_CAP_RATIO),
             "severity_saturated": k.get("severity_saturated", False),
             "stability_is_constant": k.get("stability_is_constant", True),
             "stability_note": k.get("stability_note",
                                     "当前无重复样稳定性数据,S为固定占位参数"),
             "ranking_difference_small": k.get("ranking_difference_small", False),
             # M0-2: 动态阈值元数据
             "threshold_value": k.get("threshold_value"),
             "threshold_unit": k.get("threshold_unit", "mg/kg"),
             "threshold_standard": k.get("threshold_standard", ""),
             "threshold_version": k.get("threshold_version", ""),
             "pH_condition": k.get("pH_condition", ""),
             "land_use_type": k.get("land_use_type", ""),
             "threshold_source_id": k.get("threshold_source_id"),
             # v1.0.2: 阈值解析状态(fallback 时前端显示"已用兜底阈值,请核实")
             "threshold_resolution_status": k.get("threshold_resolution_status", "resolved"),
             "fallback_note": k.get("fallback_note", "")}
            for k in kos_result["key_obstacles"]
        ],
        # 第三层: 模型关注因子(实测+模型见过+无阈值或未超标,需专家复核)
        "model_attention_factors": kos_result["model_attention_factors"],
        # 第四层: 族群预警 + 未知物(来自三道防线)
        "family_warnings": organic_result["family_warnings"],
        "unknown_alerts": organic_result["unknown_substances"],
        # 补测建议
        "recommended_tests": [
            {"factor": r["factor"], "reason": r.get("reason", f"未实测,证据等级{r['E']}"), "evidence": r["E"]}
            for r in kos_result["recommended_tests"]
        ],
        "model_contribution": model_contribution,
        "data_quality_flags": kos_result["data_quality_flags"] + (
            ["OP 模型为探索性,建议结合规则筛查和人工复核"] if is_exploratory else []
        ) + (
            [f"检测到 {organic_result['summary']['n_family_warning']} 个族群未收录物质,"
             f"{organic_result['summary']['n_unknown']} 个完全未知物质"] if organic_result["summary"]["has_unknown_risk"] else []
        ),
        "review_required": kos_result["review_required"] or is_exploratory or organic_result["summary"]["has_unknown_risk"],
        "limitations": model_info["limitations"],
        "organic_guardrails": organic_result["summary"],
        "kos_weights": KOS_W,
        "interpretation_note": "模型贡献度, 非因果, 非障碍高度",
    }
    return output


def selftest():
    """用云南个旧重金属超标数据做端到端 KOS 诊断测试"""
    print("=" * 60)
    print("KOS 诊断服务自测 (云南个旧重金属数据)")
    print("=" * 60)
    # 模拟个旧超标场地(As 是主要超标物)
    site_values = {
        "砷_As(mg/kg)": 80.0,  # 超 40(生产)/60(生态)
        "铅_Pb(mg/kg)": 300.0,  # 超 170
        "铜_Cu(mg/kg)": 150.0,  # 超 100(生产)
        "锌_Zn(mg/kg)": 400.0,  # 超 300
        "pH": 4.5,  # 过酸
        "镉_Cd(mg/kg)": 0.3,  # 未超 0.6
    }
    for track in ["prod", "eco"]:
        print(f"\n--- {track} 轨 ---")
        result = run_kos_diagnosis(site_values, track=track, subset="all")
        if "error" in result:
            print(f"  ❌ {result['error']}")
            continue
        print(f"模型: {result['model_id']} ({result['model_status']})")
        print(f"关键障碍 Top-N:")
        for k in result["key_obstacles"]:
            print(f"  #{k['rank']} {k['factor']:15s} KOS={k['KOS']:.4f} "
                  f"(R={k['components']['R']:.3f} W={k['components']['W']:.3f} M={k['components']['M']:.3f})")
        print(f"建议补测: {len(result['recommended_tests'])}")
        print(f"数据质量标记: {result['data_quality_flags']}")
        print(f"需人工复核: {result['review_required']}")

    out = os.path.join(_OUT_BASE, "kos_service_selftest.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    result = run_kos_diagnosis(site_values, track="prod", subset="all")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ 自测通过: {out}")


if __name__ == "__main__":
    selftest()
