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
                "Cu_mgkg": 0.75, "Zn_mgkg": 0.7, "Ni_mgkg": 0.65, "pH": 0.8, "BaP_ngg": 0.85,
                # v1.0.1 L4 扩展重金属(启发式权重, 低于核心重金属)
                "Mn_mgkg": 0.55, "Co_mgkg": 0.55, "Mo_mgkg": 0.5, "Sb_mgkg": 0.6,
                "Tl_mgkg": 0.65, "Be_mgkg": 0.6, "Ba_mgkg": 0.5, "V_mgkg": 0.55, "Fe_mgkg": 0.45,
                # v1.0.1 L4 有机物(按毒性/持久性赋权, PAH/OCP 高于 VOC)
                "PAH_Benzo[a]pyrene": 0.85, "PAH_total": 0.8, "PAH_Naphthalene": 0.65,
                "PAH_Pyrene": 0.65, "PAH_Fluoranthene": 0.65, "PAH_Phenanthrene": 0.6,
                "PAH_Anthracene": 0.6, "PAH_Fluorene": 0.55, "PAH_Indeno": 0.75,
                "PAH_Benzo[a]anthracene": 0.7, "PAH_Benzo[b]fluoranthene": 0.7,
                "OCP_DDT": 0.85, "OCP_HCH": 0.8, "PCB_total": 0.85, "PFAS_total": 0.8,
                "TPH_C10C40": 0.65,
                "VOC_Tetrachloroethylene": 0.7, "VOC_Trichloroethylene": 0.65,
                "VOC_CarbonTetrachloride": 0.7, "Aniline": 0.65, "Nitrobenzene": 0.6,
                "Cyanide": 0.7, "Phenol_Pentachlorophenol": 0.7,
                "BTEX_Styrene": 0.55, "BTEX_Toluene": 0.55, "BTEX_Ethylbenzene": 0.6,
                "BTEX_Xylene": 0.55}
ECO_WEIGHTS = {"Cd_mgkg": 0.85, "Pb_mgkg": 0.85, "As_mgkg": 0.9, "Cr_mgkg": 0.8, "Hg_mgkg": 0.9,
               "Cu_mgkg": 0.7, "Zn_mgkg": 0.65, "Ni_mgkg": 0.7, "pH": 0.75,
               # v1.0.1 L4 生态轨(生态用地对重金属更敏感, 权重略高)
               "Mn_mgkg": 0.6, "Co_mgkg": 0.6, "Tl_mgkg": 0.7, "Be_mgkg": 0.65,
               "PAH_Benzo[a]pyrene": 0.9, "PAH_total": 0.85, "OCP_DDT": 0.9,
               "PCB_total": 0.9, "PFAS_total": 0.85}

# 特征名映射(中文场地数据 → x_measured_ 特征名)
# 这是从用户检测数据到模型特征的桥梁
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


def _compute_per_point_breakdown_with_thr(factor: str, per_point_data: dict | None,
                                           thr_scalar: float | None) -> list:
    """v1.0.2(GPT P0-2): 单因子逐点 B/R 分解(标量阈值版)。

    直接接受已解析的标量阈值, 绕过 thresholds dict 格式问题。
    """
    if not per_point_data or thr_scalar is None:
        return []

    # canonical code → 中文元素名(As_mgkg→砷)
    _CANON_TO_CN = {"As": "砷", "Pb": "铅", "Cu": "铜", "Zn": "锌", "Cd": "镉",
                    "Cr": "铬", "Hg": "汞", "Ni": "镍"}
    cn_name = None
    for code_prefix, cn in _CANON_TO_CN.items():
        if factor.startswith(code_prefix):
            cn_name = cn
            break

    breakdown = []
    for point_id, point_vals in per_point_data.items():
        val = None
        for fk, fv in point_vals.items():
            if fk == factor or (cn_name and cn_name in fk):
                val = fv
                break
        if val is None:
            continue
        b = 1 if (thr_scalar and val > thr_scalar) else 0
        ratio = round(val / thr_scalar, 3) if (thr_scalar and thr_scalar > 0) else None
        breakdown.append({
            "point_id": point_id,
            "value": round(float(val), 4),
            "threshold": thr_scalar,
            "B": b,
            "severity_ratio": ratio,
        })
    breakdown.sort(key=lambda x: x["severity_ratio"] or 0, reverse=True)
    return breakdown


def _compute_per_point_breakdown(factor: str, per_point_data: dict | None,
                                   thresholds: dict, threshold_meta: dict) -> list:
    """v1.0.2(GPT P0-2): 单因子的逐点 B/R 分解。

    对每个采样点, 用该点数据计算:
    - value: 实测值
    - B: 超标标志(0/1)
    - severity_ratio: 超标倍数(value/threshold)
    - threshold: 该因子阈值

    返回 [{point_id, value, threshold, B, severity_ratio}, ...]。
    KOS 排名仍用最不利点, 此分解仅供透明展示。
    """
    if not per_point_data:
        return []

    # 因子归一化(中文符号匹配)
    from app.services.factor_normalizer import normalize_factors_v2
    normed_factor = normalize_factors_v2({factor: None})
    fac_key = list(normed_factor.keys())[0] if normed_factor else factor

    # v1.0.2(GPT P0-2): canonical code → 中文元素名映射(As_mgkg→砷)
    # per_point_data 的 key 是中文因子名, key_obstacle.factor 是 canonical code
    _CANON_TO_CN = {"As": "砷", "Pb": "铅", "Cu": "铜", "Zn": "锌", "Cd": "镉",
                    "Cr": "铬", "Hg": "汞", "Ni": "镍", "Cr_VI": "六价铬"}
    cn_name = None
    for code_prefix, cn in _CANON_TO_CN.items():
        if factor.startswith(code_prefix):
            cn_name = cn
            break

    # thr: kos_service 的 thresholds key 与 key_obstacle.factor 一致(canonical code)
    thr = thresholds.get(factor)
    # 兜底: 尝试归一化 key
    if thr is None:
        thr = thresholds.get(fac_key)
    # 安全: thr 可能是 dict(未解析)或 None, 只取标量
    if isinstance(thr, dict):
        thr = thr.get("limit") or thr.get("threshold")
    breakdown = []
    for point_id, point_vals in per_point_data.items():
        # 匹配该因子的值(支持 canonical code / 归一化 / 中文元素名)
        val = None
        for fk, fv in point_vals.items():
            if fk == factor or fk == fac_key or (cn_name and cn_name in fk):
                val = fv
                break
        if val is None:
            continue
        b = 1 if (thr and val > thr) else 0
        ratio = round(val / thr, 3) if (thr and thr > 0) else None
        breakdown.append({
            "point_id": point_id,
            "value": round(float(val), 4),
            "threshold": thr,
            "B": b,
            "severity_ratio": ratio,
        })
    # 按 severity_ratio 降序(最超标点在前)
    breakdown.sort(key=lambda x: x["severity_ratio"] or 0, reverse=True)
    return breakdown


def _compute_per_point_stats(per_point_data: dict | None, thresholds: dict,
                              threshold_meta: dict) -> dict:
    """v1.0.2(GPT 4.7): 按采样点计算超标统计。

    返回 {factor: {n_exceed_points, n_total_points, exceed_rate, max_ratio, p95, median}}
    """
    if not per_point_data:
        return {}

    # 收集每个 canonical 因子在所有点位的值
    from app.services.factor_normalizer import normalize_factors_v2
    factor_point_values = {}  # {canonical: [values across points]}

    for point_id, point_vals in per_point_data.items():
        normed = normalize_factors_v2(point_vals).get("factors", {})
        for fac, val in normed.items():
            factor_point_values.setdefault(fac, []).append(val)

    stats = {}
    for fac, vals in factor_point_values.items():
        if fac == "pH" or not vals:
            continue
        thr = thresholds.get(fac)
        if not thr or thr.get("type") != "upper" or thr.get("limit") is None:
            continue
        limit = float(thr["limit"])
        exceed_vals = [v for v in vals if v > limit]
        ratios = [v / limit for v in vals if v > limit] if limit > 0 else []
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        # P95
        p95_idx = int(n * 0.95)
        p95 = vals_sorted[min(p95_idx, n - 1)] if n > 0 else None
        # 中位数
        median = vals_sorted[n // 2] if n > 0 else None

        stats[fac] = {
            "n_total_points": n,
            "n_exceed_points": len(exceed_vals),
            "exceed_rate": round(len(exceed_vals) / n, 4) if n > 0 else 0,
            "max_value": max(vals) if vals else None,
            "max_exceedance_ratio": round(max(ratios), 2) if ratios else 0,
            "p95": round(p95, 4) if p95 else None,
            "median": round(median, 4) if median else None,
            "threshold_value": limit,
            "threshold_resolution_status": threshold_meta.get(fac, {}).get(
                "threshold_resolution_status", "resolved"),
        }
    return stats


def _compute_per_point_stats_dynamic(normalized_points: dict,
                                     per_point_thresholds: dict,
                                     per_point_meta: dict) -> dict:
    """按每个点位自己的 pH/用地阈值汇总法规超标统计。"""
    factor_rows: dict[str, list[dict]] = {}
    for point_id, point_values in normalized_points.items():
        thresholds = per_point_thresholds.get(point_id, {})
        metadata = per_point_meta.get(point_id, {})
        for factor, value in point_values.items():
            threshold = thresholds.get(factor)
            if threshold is None:
                continue
            detail = compute_severity_detail(value, threshold)
            factor_rows.setdefault(factor, []).append({
                "point_id": point_id,
                "value": float(value),
                "B": int(detail.get("B") or 0),
                "ratio": float(detail.get("exceedance_ratio") or 0.0),
                "threshold": metadata.get(factor, {}).get("threshold_value"),
                "threshold_resolution_status": metadata.get(factor, {}).get(
                    "threshold_resolution_status", "resolved"
                ),
            })

    output = {}
    for factor, rows in factor_rows.items():
        values = sorted(row["value"] for row in rows)
        exceed = [row for row in rows if row["B"] == 1]
        count = len(values)
        output[factor] = {
            "n_total_points": count,
            "n_exceed_points": len(exceed),
            "exceed_rate": round(len(exceed) / count, 4) if count else 0.0,
            "max_value": max(values) if values else None,
            "max_exceedance_ratio": round(
                max((row["ratio"] for row in exceed), default=0.0), 4
            ),
            "p95": round(values[min(int(count * 0.95), count - 1)], 4) if count else None,
            "median": round(values[count // 2], 4) if count else None,
            "point_details": rows,
        }
    return output


def _normalize_per_point_data(per_point_data: dict | None) -> dict:
    if not per_point_data:
        return {}
    from app.services.factor_normalizer import normalize_factors_v2
    return {
        point_id: normalize_factors_v2(values).get("factors", {})
        for point_id, values in per_point_data.items()
    }


def _select_decision_point(per_point_data: dict | None, thresholds: dict,
                           per_point_thresholds: dict | None = None) -> dict | None:
    """选择一个真实采样点用于局部模型解释。

    选择顺序为最大法规超标倍数、超标因子数、超标倍数总和、有效因子数。
    这里不拼接不同点位的最大值，返回的 ``factor_values`` 始终来自同一采样点。
    """
    if not per_point_data:
        return None

    candidates = []
    normalized_points = _normalize_per_point_data(per_point_data)
    for point_id, normalized in normalized_points.items():
        if not normalized:
            continue
        exceedances = []
        factor_evidence = []
        for factor, value in normalized.items():
            point_threshold_map = (per_point_thresholds or {}).get(point_id, thresholds)
            threshold = point_threshold_map.get(factor)
            if threshold is None:
                continue
            detail = compute_severity_detail(value, threshold)
            if detail.get("B") == 1:
                ratio = float(detail.get("exceedance_ratio") or 0.0)
                exceedances.append(ratio)
                factor_evidence.append({
                    "factor": factor,
                    "value": float(value),
                    "exceedance_ratio": round(ratio, 6),
                })
        score = (
            max(exceedances, default=0.0),
            len(exceedances),
            sum(exceedances),
            len(normalized),
        )
        candidates.append({
            "point_id": point_id,
            "factor_values": normalized,
            "selection_score": score,
            "exceedance_evidence": sorted(
                factor_evidence,
                key=lambda item: item["exceedance_ratio"],
                reverse=True,
            ),
        })

    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (item["selection_score"], str(item["point_id"])),
        reverse=True,
    )
    return candidates[0]


def run_kos_diagnosis(site_values: dict, track: str = "prod", subset: str = "all",
                      top_n: int = 10, site_pH: float | None = None,
                      land_use_type: str | None = None, db_session=None,
                      per_point_data: dict | None = None) -> dict:
    """运行完整 KOS 诊断。
    site_values: {因子名(各种格式): 浓度值} — 全场地每因子最大值(兼容)
    track: prod / eco
    subset: all / hm / op / hm_op (决定用哪个模型)
    site_pH: 场地 pH 值(用于动态阈值选择, M0-2)
    land_use_type: 土地用途(用于动态阈值选择)
    db_session: 数据库 session(用于查询 StandardThreshold, M0-2)
    per_point_data: v1.0.2(GPT 4.7) {point_id: {factor_name: value}} 按采样点分组
                    用于计算超标点数/超标率/P95/最大超标倍数
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
        from app.services.threshold_resolver import resolve_threshold_from_db
        for fac in list(factors.keys()):
            if fac == "pH":
                thresholds["pH"] = PH_THRESHOLD[track]
                continue
            thr_result = resolve_threshold_from_db(
                db_session, fac, track=track, site_pH=site_pH, land_use_type=land_use_type)
            status = thr_result["threshold_resolution_status"]
            if status in ("resolved", "heuristic", "fallback"):
                # resolved=国标, heuristic=文献兜底(GB15618扩展), fallback=最严档兜底
                thresholds[fac] = thr_result["threshold"]
                threshold_meta[fac] = thr_result
                if status in ("heuristic", "fallback"):
                    # 文献兜底阈值仍可参与KOS，但标记为待核实（证据等级自动降为C）
                    data_quality_flags.append(
                        f"threshold_{status}: {fac} 使用{thr_result.get('standard','文献')}兜底值, "
                        f"限值={thr_result.get('threshold_value','?')} {thr_result.get('threshold_unit','')}, 待核实"
                    )
            elif status == "advisory":
                # v1.0.2: 描述性指标（Sand/Silt/Clay/Elevation/MAP/Slope）不报错，静默跳过
                threshold_meta[fac] = thr_result
            else:
                # ambiguous / not_found 不得进入正式法规 Top-N。
                ambiguous_factors.append(fac)
                data_quality_flags.append(
                    f"threshold_{status}: "
                    f"{fac} 无法唯一解析权威阈值, 已退出正式KOS并要求复核"
                )

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

    # v1.0.2(): S 用模型层 Top-5 稳定性(从 metrics_file 读)
    factor_stability = {}
    try:
        registry = load_registry()
        model_info_s = registry["models"].get(model_id, {})
        # top5_stability 在 metrics_file 里(非注册表顶层)
        metrics_file = model_info_s.get("metrics_file")
        if metrics_file:
            metrics_path = os.path.join(ROOT, metrics_file) if not os.path.isabs(metrics_file) else metrics_file
            if os.path.exists(metrics_path):
                with open(metrics_path, encoding="utf-8") as mf:
                    metrics = json.load(mf)
                top5 = metrics.get("top5_stability")
                if top5 is not None:
                    # 所有因子用同一个模型层稳定性值(模型级,非因子级)
                    factor_stability = {f: float(top5) for f in factors}
    except Exception:
        pass

    # 每个采样点按该点 pH 独立解析阈值。只有 resolved 权威阈值进入正式 KOS；
    # ambiguous/heuristic/fallback 仅进入复核层，不能冒充法规超标结论。
    normalized_points = _normalize_per_point_data(per_point_data)
    per_point_thresholds: dict = {}
    per_point_meta: dict = {}
    point_unresolved = []
    if db_session is not None and normalized_points:
        from app.services.threshold_resolver import resolve_threshold_from_db
        for point_id, point_values in normalized_points.items():
            point_pH = point_values.get("pH")
            point_threshold_map = {}
            point_meta_map = {}
            for factor in point_values:
                if factor == "pH":
                    point_threshold_map[factor] = PH_THRESHOLD[track]
                    point_meta_map[factor] = {
                        "threshold": PH_THRESHOLD[track],
                        "threshold_value": None,
                        "threshold_unit": "无量纲",
                        "threshold_standard": "土壤用途适宜区间",
                        "threshold_version": "v1",
                        "pH_condition": "",
                        "land_use_type": land_use_type or "",
                        "threshold_resolution_status": "resolved",
                    }
                    continue
                resolved = resolve_threshold_from_db(
                    db_session,
                    factor,
                    track=track,
                    site_pH=point_pH,
                    land_use_type=land_use_type,
                )
                status = resolved.get("threshold_resolution_status")
                if status in ("resolved", "heuristic", "fallback"):
                    point_threshold_map[factor] = resolved["threshold"]
                    point_meta_map[factor] = resolved
                else:
                    # v1.0.3: advisory 因子（描述性指标）不参与告警，静默跳过
                    if status != "advisory":
                        point_unresolved.append({
                            "point_id": point_id,
                            "factor": factor,
                            "status": status,
                            "reason": resolved.get("note") or resolved.get("fallback_note") or "无权威阈值",
                        })
            per_point_thresholds[point_id] = point_threshold_map
            per_point_meta[point_id] = point_meta_map

    # KOS 计算。场地汇总仍保留模型关注/补测层；正式 Top-N 在有逐点数据时
    # 改为“逐点计算后按因子取最不利真实点”，不再用跨点位虚拟向量判 B/R。
    kos_result = compute_kos(
        shap_measured, factors, thresholds, weights, evidence,
        top_n=top_n, op_model=is_op, factor_stability=factor_stability
    )
    if normalized_points and per_point_thresholds:
        best_by_factor = {}
        for point_id, point_values in normalized_points.items():
            point_threshold_map = per_point_thresholds.get(point_id, {})
            point_result = compute_kos(
                shap_measured,
                point_values,
                point_threshold_map,
                weights,
                {factor: "A" for factor in point_values},
                top_n=max(top_n, len(point_values)),
                op_model=is_op,
                factor_stability=factor_stability,
            )
            for item in point_result.get("key_obstacles", []):
                factor = item["factor"]
                candidate = dict(item)
                candidate["decision_point_id"] = point_id
                metadata = per_point_meta.get(point_id, {}).get(factor, {})
                candidate.update({
                    "threshold_value": metadata.get("threshold_value"),
                    "threshold_unit": metadata.get("threshold_unit", "mg/kg"),
                    "threshold_standard": metadata.get("threshold_standard", ""),
                    "threshold_version": metadata.get("threshold_version", ""),
                    "pH_condition": metadata.get("pH_condition", ""),
                    "land_use_type": metadata.get("land_use_type", ""),
                    "threshold_source_id": metadata.get("threshold_source_id"),
                    "threshold_resolution_status": metadata.get("threshold_resolution_status", "resolved"),
                })
                previous = best_by_factor.get(factor)
                if previous is None or candidate["KOS"] > previous["KOS"]:
                    best_by_factor[factor] = candidate

        point_formal = sorted(
            best_by_factor.values(), key=lambda item: item["KOS"], reverse=True
        )
        point_formal = point_formal[:top_n]
        for rank, item in enumerate(point_formal, 1):
            item["rank"] = rank
            item["ranking_difference_small"] = (
                rank > 1 and point_formal[rank - 2]["KOS"] - item["KOS"] < 0.01
            )
        kos_result["key_obstacles"] = point_formal
        kos_result["explicit_obstacles"] = [
            {
                "factor": item["factor"],
                "value": item["value"],
                "threshold": item["threshold"],
                "severity_R": item["R"],
                "point_id": item["decision_point_id"],
                "source": "逐点规则判障碍",
            }
            for item in point_formal
        ]
        kos_result["n_formal"] = len(best_by_factor)
        kos_result["review_required"] = (
            kos_result.get("review_required", False) or bool(point_unresolved)
        )
        if point_unresolved:
            kos_result.setdefault("data_quality_flags", []).append(
                f"{len(point_unresolved)} 个点位-因子组合因阈值未解析而退出正式KOS"
            )

    # M0-2: 给 key_obstacles 附加阈值元数据
    for k in kos_result.get("key_obstacles", []):
        fac = k.get("factor")
        point_id = k.get("decision_point_id")
        tm = ((per_point_meta.get(point_id, {}) if point_id is not None else {}).get(fac)
              or threshold_meta.get(fac))
        if tm:
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

    # v1.0.2(GPT P0-2): 逐点 B/R 分解 — 哪些采样点超标、超标多少倍
    # KOS 排名仍用最不利点(保守决策), 但附逐点透明分解
    # 独立循环(不依赖 threshold_meta), 用 thresholds dict 的标量提取
    for k in kos_result.get("key_obstacles", []):
        fac = k.get("factor")
        if normalized_points and per_point_thresholds:
            breakdown = []
            for point_id, point_values in normalized_points.items():
                if fac not in point_values:
                    continue
                point_threshold = per_point_thresholds.get(point_id, {}).get(fac)
                if point_threshold is None:
                    continue
                detail = compute_severity_detail(point_values[fac], point_threshold)
                metadata = per_point_meta.get(point_id, {}).get(fac, {})
                breakdown.append({
                    "point_id": point_id,
                    "value": round(float(point_values[fac]), 4),
                    "threshold": metadata.get("threshold_value"),
                    "threshold_standard": metadata.get("threshold_standard", ""),
                    "pH_condition": metadata.get("pH_condition", ""),
                    "B": int(detail.get("B") or 0),
                    "severity_ratio": round(float(detail.get("exceedance_ratio") or 0.0), 4),
                })
            breakdown.sort(key=lambda item: item["severity_ratio"], reverse=True)
            k["per_point_breakdown"] = breakdown
            continue
        # 用 key_obstacle 已解析的 threshold_value(标量), 避免 thresholds dict 格式问题
        _thr_scalar = k.get("threshold_value")
        if _thr_scalar is None:
            _thr_raw = thresholds.get(fac)
            _thr_scalar = _thr_raw.get("limit") if isinstance(_thr_raw, dict) else _thr_raw
        k["per_point_breakdown"] = _compute_per_point_breakdown_with_thr(
            fac, per_point_data, _thr_scalar)

    # 未知有机物三道防线
    # v1.0.3: 已知因子包含所有系统认识的因子
    from app.models import FactorDictionary
    known_factors = (set(factors.keys()) | set(thresholds.keys())
                     | {fd.factor_code for fd in db_session.query(FactorDictionary.factor_code).all() if fd.factor_code}
                     | {fd.factor_name for fd in db_session.query(FactorDictionary.factor_name).all() if fd.factor_name})
    organic_result = guardrail_check(factors, known_factors)

    # 模型贡献度: 优先解释一个真实的最不利采样点; 不得把不同点位最大值
    # 拼成虚拟场地向量。局部解释不可用时才显式降级为全局模型背景贡献。
    model_contribution = []
    local_shap_for_site = None
    local_shap_status = "not_attempted"
    decision_point = _select_decision_point(
        per_point_data, thresholds, per_point_thresholds
    )
    if len(shap_measured) > 0:
        if decision_point:
            try:
                from ml.explain.shap_service import compute_local_shap_for_point
                bundle = _kos_engine.load_model_and_shap(subset, track)
                local_shap_for_site = compute_local_shap_for_point(
                    bundle.get("model"),
                    bundle.get("feature_cols") or [],
                    decision_point["factor_values"],
                )
                local_shap_status = "available" if local_shap_for_site else "unavailable"
            except Exception as exc:
                local_shap_status = (
                    f"unavailable:{type(exc).__name__}:{str(exc)[:160]}"
                )
                data_quality_flags.append(local_shap_status)

        if local_shap_for_site:
            measured_at_point = set(decision_point["factor_values"])
            local_rows = [
                (factor, float(value))
                for factor, value in local_shap_for_site.items()
                if factor in measured_at_point
            ]
            local_rows.sort(key=lambda item: abs(item[1]), reverse=True)
            total_abs_local = sum(abs(value) for _, value in local_rows)
            for factor, value in local_rows[:10]:
                model_contribution.append({
                    "factor": factor,
                    "contribution": round(abs(value) / total_abs_local, 6)
                    if total_abs_local > 0 else 0.0,
                    "direction": "positive" if value >= 0 else "negative",
                    "contribution_scope": "local_point",
                    "local_shap_value": round(value, 6),
                    "decision_point_id": decision_point["point_id"],
                    "local_shap_note": "基于同一真实最不利采样点的局部SHAP",
                })
        else:
            total_shap = (float(shap_measured["mean_abs_shap"].sum())
                          if "mean_abs_shap" in shap_measured.columns else 0.0)
            for _, row in shap_measured.head(10).iterrows():
                raw = float(row.get("mean_abs_shap", 0))
                model_contribution.append({
                    "factor": row["group"],
                    "contribution": round(raw / total_shap, 6) if total_shap > 0 else 0.0,
                    "direction": row.get("direction", "positive"),
                    "contribution_scope": "global_model",
                    "local_shap_value": None,
                    "decision_point_id": decision_point["point_id"] if decision_point else None,
                    "local_shap_note": "局部解释不可用，仅展示训练集全局背景贡献",
                })

    # v1.0.2(GPT 4.7): 按采样点计算超标统计(超标点数/超标率/P95/最大超标倍数)
    per_point_stats = (
        _compute_per_point_stats_dynamic(
            normalized_points, per_point_thresholds, per_point_meta
        )
        if normalized_points and per_point_thresholds else
        _compute_per_point_stats(per_point_data, thresholds, threshold_meta)
    )

    # 四层输出( P0 规则)
    # Round9 P0-3.2: 真实 coverage + subset + model_version(供审计 payload 完整)
    measured_factors_set = {
        md.get("canonical") for md in mapping_details if md.get("canonical")
    }
    # 从 model_info.feature_list 或 key_obstacles/w_expected 推断模型期望因子集
    _expected = set()
    if isinstance(model_info.get("feature_list"), list):
        _expected = {str(f) for f in model_info["feature_list"]}
    if not _expected and "group" in shap_measured.columns:
        _expected = {
            str(group) for group in shap_measured["group"].dropna().tolist()
            if not str(group).startswith("缺失指示_")
        }
    if not _expected:
        # 兜底: 用 kos_engine 的全部 canonical 因子
        try:
            _expected = set(getattr(_kos_engine, "CANONICAL_FACTORS", set())) or set()
        except Exception:
            _expected = set()
    coverage_value = (round(len(measured_factors_set & _expected)
                             / max(len(_expected), 1), 4)
                       if _expected else 0.0)
    # model_version: 优先从 registry 读真实版本, 否则 fallback
    model_version_out = model_info.get("version") or "p3_alpha_v0.8"
    output = {
        "track": track,
        "subset": subset,  # Round9 P0-3.2: 显式加入(原 kos_service 不返回, 由 API 注入)
        "model_id": model_id,
        "model_version": model_version_out,  # Round9 P0-3.2: 真实模型版本
        "data_version": "Gold Dataset v0.8",
        "threshold_version": ("数据库动态阈值(StandardThreshold)" if db_session and thresholds
                              else "静态硬编码(需传入db_session启用动态阈值)"),
        "model_status": model_info["status"],
        "model_algorithm": model_info.get("algorithm"),
        "model_metrics": model_info.get("metrics") or {},
        "model_n_features": model_info.get("n_features"),
        "model_artifact_path": model_info.get("model_file"),
        "model_validation_strategy": "group_split",
        "model_group_key": "id_DOI/source",
        "coverage": coverage_value,  # Round9 P0-3.2: 真实覆盖率(实测因子/模型期望因子)
        # M0-1: 因子映射详情
        "mapping_details": mapping_details,
        "mapping_conflicts": mapping_conflicts,
        "unmapped": unmapped,
        "unit_conversion_details": unit_conversion_details,
        # M0-2: 阈值解析详情
        "ambiguous_threshold_factors": ambiguous_factors,
        "point_threshold_unresolved": point_unresolved,
        "rule_aggregation_method": (
            "per_point_dynamic_threshold_then_site_factor_worst_case"
            if normalized_points and per_point_thresholds else
            "site_factor_worst_case"
        ),
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
             "stability_is_constant": k.get("stability_is_constant", False),
             "stability_note": k.get("stability_note",
                                     "v1.0.2: S=模型层Top-5稳定性(跨bootstrap子样),非因子层重复样稳定性"),
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
             "fallback_note": k.get("fallback_note", ""),
             # v1.0.2(GPT P0-2): 逐点 B/R 分解(每个超标因子的采样点级别明细)
             "per_point_breakdown": k.get("per_point_breakdown", [])}
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
        "model_feature_names": sorted({
            str(group) for group in shap_measured.get("group", pd.Series(dtype=str)).dropna().tolist()
        }),
        "model_contribution_scope": (
            "local_point" if local_shap_for_site else "global_model"
        ),
        "local_shap_status": local_shap_status,
        "decision_point_id": decision_point["point_id"] if decision_point else None,
        "decision_point_selection": (
            {
                "method": "max_rule_exceedance_then_count",
                "selection_score": list(decision_point["selection_score"]),
                "exceedance_evidence": decision_point["exceedance_evidence"],
            }
            if decision_point else None
        ),
        "data_quality_flags": list(dict.fromkeys(data_quality_flags + kos_result["data_quality_flags"] + (
            ["OP 模型为探索性,建议结合规则筛查和人工复核"] if is_exploratory else []
        ) + (
            [f"检测到 {organic_result['summary']['n_family_warning']} 个族群未收录物质,"
             f"{organic_result['summary']['n_unknown']} 个完全未知物质"] if organic_result["summary"]["has_unknown_risk"] else []
        ))),
        "review_required": kos_result["review_required"] or is_exploratory or organic_result["summary"]["has_unknown_risk"],
        "limitations": model_info["limitations"],
        "organic_guardrails": organic_result["summary"],
        "kos_weights": KOS_W,
        # v1.0.2(GPT 4.7): 按采样点的超标统计
        "per_point_stats": per_point_stats,
        "n_sampling_points": len(per_point_data) if per_point_data else 0,
        "interpretation_note": (
            "模型贡献度为同一真实最不利采样点的局部SHAP，非因果、非法规判定依据"
            if local_shap_for_site else
            "局部SHAP不可用，当前仅展示训练集全局mean|SHAP|背景贡献；非因果、非法规判定依据"
        ),
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
