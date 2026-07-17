import sys
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
kos_engine_v0.8.py — 关键障碍综合得分 (KOS) 引擎
====================================================================
公式: KOS_i,t = B_i,t × (0.30×R + 0.25×W + 0.15×M + 0.20×S + 0.10×E)

强制规则(裴总放行口径 + 第一份附件):
1. 只有 B=1 (规则判障碍) 的因子进入正式关键障碍 Top-N
2. 只有实测因子 (x_measured_*) 可以进入正式排名
3. GEE/proxy 只能作背景协变量,不得作为正式障碍
4. x_missing_* 不得进入关键障碍 Top-N
5. family aggregate 可进入 extended KOS,标注 supplementary_screening
6. 未检测但重要的因子进入 recommended_tests
7. OP 模型结果必须带 exploratory / review_required 标记
8. SHAP 统一前端名为"模型贡献度",禁止写"障碍高度"或"因果"

输入:
  - shap_global (DataFrame): 来自 shap_contribution_filter 清洗后的 measured 贡献
  - factor_thresholds (dict): 因子→{upper/lower/interval} 阈值(来自规则引擎)
  - factor_values (dict): 该场地的因子实测值
  - factor_weights (dict): 因子→用途权重 W
  - factor_evidence (dict): 因子→证据等级 A/B/C/D

输出:
  - key_obstacles: 正式 Top-N (B=1 + measured + E in A/B)
  - supplementary_obstacles: 族群级 (family)
  - recommended_tests: 未实测重要因子
  - data_quality_flags: 缺失/proxy/OP 探索性等风险
====================================================================
"""
from __future__ import annotations
import os
import math
import joblib
import pandas as pd
import numpy as np
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# PyInstaller 打包后数据在 _MEIPASS 或其 _internal 子目录
if getattr(sys, "frozen", False):
    _mep = sys._MEIPASS
    if os.path.isdir(os.path.join(_mep, "ml")) or os.path.isdir(os.path.join(_mep, "data")):
        ROOT = _mep
    elif os.path.isdir(os.path.join(_mep, "_internal", "ml")):
        ROOT = os.path.join(_mep, "_internal")
ART = "ml/artifacts/p3_alpha"

# KOS 权重 (方法学规定,裴总确认)
KOS_W = {"R": 0.30, "W": 0.25, "M": 0.15, "S": 0.20, "E": 0.10}

# 证据等级分值
EVIDENCE_SCORE = {"A": 1.0, "B": 0.8, "C": 0.5, "D": 0.3}

# P0-4: KOS 严重度饱和上限 (超标 10 倍即视为严重度饱和, 不再线性增长)
KOS_SEVERITY_CAP_RATIO = 10


def compute_severity(value: float, threshold: dict) -> tuple[float, bool]:
    """计算规则严重度 R (4型) + 是否构成障碍 B。
    threshold 形如 {"type":"upper","limit":0.6} 或 {"type":"interval","min":5.5,"max":8.5}
    返回 (R in [0,1], B in {0,1})

    注: 此函数保留向后兼容 (tuple 返回). 透明化扩展见 compute_severity_detail.
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0, 0
    ttype = threshold.get("type", "upper")
    if ttype == "upper":
        limit = threshold.get("limit", 0)
        if value <= limit:
            return 0.0, 0
        # R = min(1, log(1 + value/limit) / log(1 + 10))  超标倍数对数化, cap=10倍
        ratio = value / limit if limit > 0 else 1.0
        r = min(1.0, math.log(1 + ratio) / math.log(11))
        return r, 1
    elif ttype == "lower":
        limit = threshold.get("limit", 0)
        if value >= limit:
            return 0.0, 0
        ratio = limit / value if value > 0 else 99
        r = min(1.0, math.log(1 + ratio) / math.log(11))
        return r, 1
    elif ttype == "interval":
        lo, hi = threshold.get("min", -np.inf), threshold.get("max", np.inf)
        if lo <= value <= hi:
            return 0.0, 0
        # 偏离最近边界
        dist = min(abs(value - lo), abs(value - hi))
        span = max(hi - lo, 0.1)
        r = min(1.0, dist / span)
        return r, 1
    return 0.0, 0


def compute_severity_detail(value: float, threshold: dict) -> dict:
    """P0-4 透明化扩展: 在 compute_severity 基础上返回完整诊断元数据。

    返回字段:
      - R: 严重度 [0,1] (与 compute_severity 一致)
      - B: 是否构成障碍 {0,1}
      - exceedance_ratio: 超标倍数 value/limit (upper 类型); 其他类型视阈值形态给默认
      - severity_cap_ratio: 饱和上限常数 (默认 KOS_SEVERITY_CAP_RATIO=10)
      - severity_saturated: exceedance_ratio >= severity_cap_ratio 时为 True
      - threshold_type: upper/lower/interval
    """
    detail = {
        "R": 0.0, "B": 0,
        "exceedance_ratio": 0.0,
        "severity_cap_ratio": KOS_SEVERITY_CAP_RATIO,
        "severity_saturated": False,
        "threshold_type": threshold.get("type", "upper") if threshold else "upper",
    }
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return detail
    ttype = threshold.get("type", "upper")
    if ttype == "upper":
        limit = threshold.get("limit", 0)
        ratio = (value / limit) if limit > 0 else 0.0
        detail["exceedance_ratio"] = ratio
        detail["severity_saturated"] = ratio >= KOS_SEVERITY_CAP_RATIO
        if value <= limit:
            return detail
        r = min(1.0, math.log(1 + ratio) / math.log(11))
        detail["R"] = r
        detail["B"] = 1
        return detail
    elif ttype == "lower":
        limit = threshold.get("limit", 0)
        ratio = (limit / value) if value > 0 else 99.0
        detail["exceedance_ratio"] = ratio
        detail["severity_saturated"] = ratio >= KOS_SEVERITY_CAP_RATIO
        if value >= limit:
            return detail
        r = min(1.0, math.log(1 + ratio) / math.log(11))
        detail["R"] = r
        detail["B"] = 1
        return detail
    elif ttype == "interval":
        lo, hi = threshold.get("min", -np.inf), threshold.get("max", np.inf)
        if lo <= value <= hi:
            return detail
        dist = min(abs(value - lo), abs(value - hi))
        span = max(hi - lo, 0.1)
        ratio = dist / span
        detail["exceedance_ratio"] = ratio
        detail["severity_saturated"] = ratio >= KOS_SEVERITY_CAP_RATIO
        r = min(1.0, ratio)
        detail["R"] = r
        detail["B"] = 1
        return detail
    return detail


def load_model_and_shap(subset: str, track: str) -> dict:
    """加载 P3-Alpha 模型 + SHAP global (已清洗的 measured 贡献)"""
    model_id = f"{subset}_{track}_Full_RandomForest"
    bundle = joblib.load(f"{ART}/{model_id}.joblib")
    sg_path = f"{ART}/{model_id}_shap_global.parquet"
    sg = pd.read_parquet(sg_path) if os.path.exists(sg_path) else pd.DataFrame()
    metrics_path = f"{ART}/{model_id}_metrics.json"
    import json
    with open(metrics_path, encoding="utf-8") as f:
        metrics = json.load(f)
    return {
        "model_id": model_id,
        "model": bundle["model"],
        "feature_cols": bundle["feature_cols"],
        "shap_global": sg,
        "metrics": metrics,
        "subset": subset,
        "track": track,
    }


def compute_kos(
    shap_global_measured: pd.DataFrame,
    factor_values: dict,
    factor_thresholds: dict,
    factor_weights: dict,
    factor_evidence: dict,
    top_n: int = 10,
    op_model: bool = False,
) -> dict:
    """核心 KOS 计算。

    shap_global_measured: 清洗后的实测贡献 DataFrame,需有 group/mean_abs_shap/contribution_share/direction
    factor_values: {factor_name: value}  该场地实测值
    factor_thresholds: {factor_name: threshold_dict}
    factor_weights: {factor_name: W in [0,1]}
    factor_evidence: {factor_name: 'A'/'B'/'C'/'D'}
    """
    # 构造 M 映射 (模型贡献度, 来自 SHAP measured, 归一化)
    if len(shap_global_measured) > 0:
        total = shap_global_measured["mean_abs_shap"].sum()
        m_map = dict(zip(shap_global_measured["group"], shap_global_measured["mean_abs_shap"] / total if total > 0 else 0))
    else:
        m_map = {}

    results = []              # formal: 实测+有阈值+B=1+E(A/B)
    model_attention = []      # candidate: 实测+模型见过+无阈值或B不可判 → 需专家复核
    recommended = []          # 未实测的重要因子 → 补测建议
    all_factors = set(factor_thresholds.keys()) | set(factor_values.keys())

    # 模型见过的特征集合(来自 SHAP measured 的 group)
    model_known_factors = set(m_map.keys()) if m_map else set()

    for fac in all_factors:
        val = factor_values.get(fac)
        thr = factor_thresholds.get(fac)
        is_measured = val is not None and not (isinstance(val, float) and math.isnan(val))
        in_model = fac in model_known_factors
        m = float(m_map.get(fac, 0.0))
        w = factor_weights.get(fac, 0.5)
        e_str = factor_evidence.get(fac, "C")
        e = EVIDENCE_SCORE.get(e_str, 0.5)
        s = 0.8

        # 无阈值但实测+模型见过 → model_attention(裴总 P0 四层规则)
        if thr is None:
            if is_measured and in_model and m > 0.01:
                model_attention.append({
                    "factor": fac, "value": val, "threshold": None,
                    "M": round(m, 4), "W": round(w, 4),
                    "E": e_str, "is_measured": True, "in_model": True,
                    "layer": "model_attention",
                    "review_required": True,
                    "reason": "实测且模型见过但无阈值,无法判B,进模型关注因子(需专家复核)",
                })
            elif is_measured and not in_model:
                # 实测但模型没见过 → unknown_alert(交由调用方做族群归类)
                model_attention.append({
                    "factor": fac, "value": val, "threshold": None,
                    "M": 0.0, "E": e_str, "is_measured": True, "in_model": False,
                    "layer": "unknown_alert",
                    "review_required": True,
                    "reason": "实测但模型未见过且无阈值,无法标准化障碍判定,建议送检/专家复核",
                })
            elif not is_measured:
                recommended.append({
                    "factor": fac, "value": None, "threshold": None,
                    "E": e_str, "is_measured": False,
                    "layer": "recommended_test",
                    "reason": f"未实测,证据等级{e_str}",
                })
            continue

        # 有阈值: 计算 B, R (compute_severity 保留向后兼容)
        # P0-4: 同时调用 compute_severity_detail 拿透明化元数据
        r, b = compute_severity(val, thr)
        sev_detail = compute_severity_detail(val, thr)
        entry = {
            "factor": fac, "value": val, "threshold": thr,
            "B": b, "R": round(r, 4), "W": round(w, 4),
            "M": round(m, 4), "S": round(s, 4), "E": e_str,
            "E_score": e, "is_measured": is_measured,
            # P0-4 透明化字段 (新增, 不改 R/B 主逻辑)
            "exceedance_ratio": round(float(sev_detail["exceedance_ratio"]), 4),
            "severity_cap_ratio": sev_detail["severity_cap_ratio"],
            "severity_saturated": bool(sev_detail["severity_saturated"]),
            # S=0.8 占位参数透明化
            "stability_is_constant": True,
            "stability_note": "当前无重复样稳定性数据,S为固定占位参数",
        }

        if b == 1 and is_measured and e_str in ("A", "B"):
            # 第一层+第二层: 明确障碍 + 正式 KOS Top-N
            kos = 1.0 * (KOS_W["R"] * r + KOS_W["W"] * w + KOS_W["M"] * m + KOS_W["S"] * s + KOS_W["E"] * e)
            entry["KOS"] = round(kos, 4)
            entry["layer"] = "formal"
            results.append(entry)
        elif is_measured and b == 0 and in_model and m > 0.01:
            # 有阈值但未超标 + 模型关注 → model_attention
            entry["KOS"] = 0.0
            entry["layer"] = "model_attention"
            entry["review_required"] = True
            entry["reason"] = "实测未超标但模型贡献度高,关注潜在风险"
            model_attention.append(entry)
        elif not is_measured:
            entry["KOS"] = 0.0
            entry["layer"] = "recommended_test"
            recommended.append(entry)

    # 排序
    results.sort(key=lambda x: x["KOS"], reverse=True)
    model_attention.sort(key=lambda x: x.get("M", 0), reverse=True)
    key_obstacles = results[:top_n]

    # P0-4: 相邻 KOS 差 < 0.01 → 标记 ranking_difference_small
    for i, k in enumerate(key_obstacles):
        if i == 0:
            k["ranking_difference_small"] = False
            continue
        prev_kos = key_obstacles[i - 1]["KOS"]
        diff = prev_kos - k["KOS"]
        k["ranking_difference_small"] = bool(diff < 0.01)

    data_quality_flags = []
    if op_model:
        data_quality_flags.append("OP 模型为探索性,建议结合规则筛查和人工复核")

    return {
        "explicit_obstacles": [{"factor": k["factor"], "value": k["value"],
                                "threshold": k["threshold"], "severity_R": k["R"],
                                "source": "规则判障碍"} for k in key_obstacles],
        "key_obstacles": [{"rank": i + 1, **k} for i, k in enumerate(key_obstacles)],
        "model_attention_factors": model_attention[:15],
        "recommended_tests": recommended[:10],
        "data_quality_flags": data_quality_flags,
        "n_formal": len(results),
        "n_model_attention": len(model_attention),
        "n_recommended": len(recommended),
        "review_required": len(model_attention) > 0 or op_model,
        "kos_weights": KOS_W,
    }


def selftest():
    """KOS 引擎自测:用 all/prod 模型 SHAP + 模拟场地数据验证"""
    print("=" * 60)
    print("KOS 引擎自测 (kos_engine_selftest)")
    print("=" * 60)

    # 加载 all/prod SHAP (取 measured 部分)
    sg = pd.read_parquet(f"{ART}/all_prod_Full_RandomForest_shap_global.parquet")
    # 模拟清洗:只取非"缺失指示"的行
    measured = sg[~sg["group"].str.contains("缺失指示", na=False)].copy()

    # 模拟一个重金属超标场地
    factor_values = {"Cd_mgkg": 0.8, "As_mgkg": 30.0, "Pb_mgkg": 50.0, "Zn_mgkg": 200.0, "Cu_mgkg": 100.0}
    factor_thresholds = {
        "Cd_mgkg": {"type": "upper", "limit": 0.6},
        "As_mgkg": {"type": "upper", "limit": 40.0},
        "Pb_mgkg": {"type": "upper", "limit": 170.0},
        "Zn_mgkg": {"type": "upper", "limit": 300.0},
        "Cu_mgkg": {"type": "upper", "limit": 100.0},
        "Hg_mgkg": {"type": "upper", "limit": 1.3},  # 未测,应进补测
    }
    factor_weights = {"Cd_mgkg": 0.9, "As_mgkg": 0.85, "Pb_mgkg": 0.8, "Zn_mgkg": 0.7, "Cu_mgkg": 0.75, "Hg_mgkg": 0.6}
    factor_evidence = {"Cd_mgkg": "A", "As_mgkg": "A", "Pb_mgkg": "A", "Zn_mgkg": "A", "Cu_mgkg": "A", "Hg_mgkg": "C"}

    result = compute_kos(measured, factor_values, factor_thresholds, factor_weights, factor_evidence)

    print(f"\n正式关键障碍 (formal Top-N): {len(result['key_obstacles'])} 个")
    for k in result["key_obstacles"]:
        print(f"  {k['factor']:15s} KOS={k['KOS']:.4f} B={k['B']} R={k['R']:.3f} M={k['M']:.3f} val={k['value']}")
    print(f"\n建议补测: {len(result['recommended_tests'])} 个")
    for r in result["recommended_tests"]:
        print(f"  {r['factor']:15s} 未实测 E={r['E']}")

    # 断言
    assert len(result["key_obstacles"]) > 0, "正式 Top-N 不应为空"
    assert all(k["B"] == 1 for k in result["key_obstacles"]), "Top-N 必须全 B=1"
    assert all(k["is_measured"] for k in result["key_obstacles"]), "Top-N 必须全实测"
    assert any(r["factor"] == "Hg_mgkg" for r in result["recommended_tests"]), "未测 Hg 应进补测"
    assert result["key_obstacles"][0]["KOS"] > 0, "Top-1 KOS 应>0"

    out = "artifacts/overnight_20260703/kos_engine_selftest.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    import json
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ 自测通过,结果: {out}")
    return result


if __name__ == "__main__":
    selftest()
