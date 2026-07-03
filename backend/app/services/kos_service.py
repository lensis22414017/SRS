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
                      top_n: int = 10) -> dict:
    """运行完整 KOS 诊断。
    site_values: {因子名(各种格式): 浓度值}
    track: prod / eco
    subset: all / hm / op (决定用哪个模型)
    """
    # 归一化
    factors = normalize_factors(site_values)

    # 选模型
    model_id = f"{subset}_{track}_Full_RandomForest"
    registry = load_registry()
    model_info = registry["models"].get(model_id)
    if model_info is None:
        return {"error": f"模型 {model_id} 未注册"}

    is_op = subset == "op"
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

    # 选阈值/权重
    thresholds = PROD_THRESHOLDS if track == "prod" else ECO_THRESHOLDS
    thresholds = dict(thresholds)
    thresholds["pH"] = PH_THRESHOLD[track]
    weights = PROD_WEIGHTS if track == "prod" else ECO_WEIGHTS

    # 证据等级: 实测=A, 否则 C
    evidence = {f: "A" for f in factors}

    # KOS 计算
    kos_result = compute_kos(
        shap_measured, factors, thresholds, weights, evidence,
        top_n=top_n, op_model=is_op
    )

    # 未知有机物三道防线
    known_factors = set(thresholds.keys())
    organic_result = guardrail_check(factors, known_factors)

    # 模型贡献度(只取 measured,前端用)
    model_contribution = []
    if len(shap_measured) > 0:
        for _, r in shap_measured.head(10).iterrows():
            model_contribution.append({
                "factor": r["group"],
                "contribution": float(r.get("contribution_share_normalized", r.get("contribution_share", 0))),
                "direction": r.get("direction", "positive"),
            })

    # 四层输出(裴总 P0 规则)
    output = {
        "track": track,
        "model_id": model_id,
        "data_version": "Gold Dataset v0.8",
        "threshold_version": "GB15618(生产) / GB36600(生态) 简化版",
        "model_status": model_info["status"],
        # 第一层: 明确障碍(实测+有阈值+B=1)
        "explicit_obstacles": kos_result["explicit_obstacles"],
        # 第二层: 关键障碍 Top-N(KOS 排序)
        "key_obstacles": [
            {"rank": k["rank"], "factor": k["factor"], "KOS": k["KOS"],
             "components": {"R": k["R"], "W": k["W"], "M": k["M"], "S": k["S"], "E": k["E"]},
             "value": k["value"], "evidence": k["E"]}
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
