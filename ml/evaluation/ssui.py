"""可持续利用评价 SSUI (分维度多指标分块赋权)。

SSUI = (Σ vCi·SCi) · f(t) · M
  - SCi: 各维度组内元指标 Min-Max 归一化后线性加权;
  - f(t)=1+α·t, α=0.03 (来源方法文件正文);
  - M: 管理调节因子(表3.49)。
等级见表3.50。

MVP 口径(裴总确认): 个旧无经济性/风险因子实测数据, 先计算"安全性-限制因子 C1"
单维度 SSUI, 顶层权重置 1, 并在解释中明确标注"未纳入风险/经济维度"。

纯 python, 仅依赖标准库。输入为各因子跨采样点的数值序列。
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS = os.path.join(HERE, "..", "params", "evaluation_params.json")

# C1 限制因子元指标 -> 本系统 factor_code 映射 (个旧可得部分)
# 元指标含盐量(电导率)/CEC/pH/有机质/氮磷钾(总氮总磷速效钾)
C1_META_TO_FACTORS = {
    "土壤含盐量": ["电导率", "含盐量"],
    "阳离子交换量": ["阳离子交换量"],
    "pH": ["pH"],
    "土壤有机质": ["有机质"],
    "氮磷钾": ["全氮", "全磷", "速效钾"],
}
# 正向指标(越高越优); 含盐量为负向
NEGATIVE_METAS = {"土壤含盐量"}


def _load():
    with open(PARAMS, encoding="utf-8") as f:
        return json.load(f)["ssui"]


def _minmax(vals, negative=False):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    if hi == lo:
        norm = [0.5] * len(vals)            # 无差异取中性
    else:
        norm = [(v - lo) / (hi - lo) for v in vals]
        if negative:
            norm = [1 - x for x in norm]
    return sum(norm) / len(norm)


def _pick_M(params, land_use: str, intensity: str):
    target = "生产利用" if land_use == "production" else "生态利用"
    imap = {"low": "低强度", "medium": "中等强度", "high": "高强度"}
    want = imap.get(intensity, "中等强度")
    for row in params["management_factor_M"]:
        if row["land_use"] == target and row["intensity"] == want:
            return row["M"]
    return params["default_M"]["production" if land_use == "production" else "ecology"]


def _grade(ssui, params):
    for lv in params["levels"]:
        rng = lv["range"].replace("＜", "<")
        if rng.startswith("<"):
            if ssui < float(rng[1:]):
                return lv["label"]
        elif "-" in rng:
            lo, hi = [float(x) for x in rng.split("-")]
            if lo <= ssui <= hi:
                return lv["label"]
    return params["levels"][-1]["label"]


def evaluate(series: dict, scope: str = "production", t: float = 2.0,
             intensity: str = "medium") -> dict:
    """series: {factor_code: [跨采样点数值]}。scope: production/ecology。"""
    params = _load()
    scope_key = "production" if scope == "production" else "ecology"
    meta_w = params[scope_key]["meta_weights"]  # 元指标->{criterion, weight}

    # C1 限制因子: 元指标聚合
    sc1_parts = []   # (meta_name, normalized, weight)
    for meta_name, factor_codes in C1_META_TO_FACTORS.items():
        # 找该元指标的权重(键含 D 编号, 用前缀/包含匹配)
        w = None
        for k, v in meta_w.items():
            if k.startswith(meta_name) and v.get("criterion", "").startswith("限制因子"):
                w = v["weight"]; break
        if w is None:
            continue
        # 取本系统可得的第一个有数据因子
        vals = None
        for fc in factor_codes:
            if fc in series and any(x is not None for x in series[fc]):
                vals = series[fc]; break
        if vals is None:
            continue
        norm = _minmax(vals, negative=(meta_name in NEGATIVE_METAS))
        if norm is not None:
            sc1_parts.append((meta_name, round(norm, 4), w))

    if not sc1_parts:
        return {"scope": scope, "ssui": None, "grade": "无足够指标",
                "dimensions": {}, "explanation": "C1 限制因子无可用元指标"}

    tw = sum(w for _, _, w in sc1_parts)
    sc1 = sum(n * (w / tw) for _, n, w in sc1_parts)

    ft = 1 + params["time_weight_function"]["alpha"] * t
    M = _pick_M(params, scope, intensity)
    raw = sc1 * ft * M
    ssui = round(min(raw, 1.0), 4)        # 等级表上限 1.0
    grade = _grade(ssui, params)

    covered = {p[0] for p in sc1_parts}
    all_c1 = {k for k in C1_META_TO_FACTORS}
    missing_c1 = sorted(all_c1 - covered)
    explanation = (
        f"SSUI(安全性-限制因子口径)={ssui} ({grade})。"
        f"SC1={round(sc1,4)} 基于 {len(sc1_parts)} 项已测元指标(Min-Max 归一+组内重标化), "
        f"f(t)={round(ft,3)}(t={t}), M={M}({'生产' if scope=='production' else '生态'})。"
        f"⚠️ MVP 口径: 未纳入风险因子(C2)与经济性(C3/C4)维度(本场地缺经济/酶活/风险数据), "
        f"C1 内缺测元指标: {', '.join(missing_c1) or '无'}。"
        f"结论仅反映安全性-限制因子层面, 完整 SSUI 需补充经济性与风险数据。")
    trace = [
        f"① 选择安全性-限制因子 C1 作为 MVP 评价口径, 纳入 {len(sc1_parts)} 项已测元指标。",
        "② 对各元指标做 Min-Max 归一化(含盐量为负向指标): "
        + "; ".join(f"{n}={v}" for n, v, _ in sc1_parts),
        f"③ C1 组内权重重标化(原始权重和 {round(tw, 4)} → 1): "
        + "; ".join(f"{n}={round(w / tw * 100, 2)}%" for n, _, w in sc1_parts),
        "④ SC1 = Σ(归一化得分 × 重标化权重) = "
        + " + ".join(f"{v}×{round(w / tw, 4)}" for _, v, w in sc1_parts)
        + f" = {round(sc1, 4)}。",
        f"⑤ 时间权重 f(t)=1+0.03×{t}={round(ft, 3)}, 管理调节因子 M={M}, 原始 SSUI={round(raw, 4)}。",
        f"⑥ SSUI = min(SC1×f(t)×M, 1.0) = {ssui}, 等级判定为 {grade}。",
    ]
    return {
        "scope": scope, "ssui": ssui, "grade": grade,
        "dimensions": {
            "SC1_limit_factor": round(sc1, 4),
            "parts": [{"meta": n, "normalized": v, "weight": round(w, 6)}
                      for n, v, w in sc1_parts],
            "f_t": round(ft, 3), "M": M, "t": t,
        },
        "weights": {n: round(w / tw, 4) for n, _, w in sc1_parts},
        "limiting_factors": [n for n, v, _ in sc1_parts if v < 0.4],
        "risk_factors": [],
        "missing_dimensions": ["风险因子C2", "经济成本C3", "经济效益C4"],
        "calculation_trace": trace,
        "explanation": explanation,
    }
