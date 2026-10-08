"""v1.1 课题三: 修复后 SSUI 计算(按方法 PPT 第 13–15 页原式, 不截断、不静默归一化)。

SSUI = f(t) × Σ_{j=1..4}(v_j × S_j) × M
  S_j = Σ_i w_ij × s_i       (s_i ∈ [0,1]: 指标分级得分, 由导入表提供)
  f(t) = 1 + 0.03 t          (t: 修复后年数)
  M ∈ [1.1, 1.2] 生产 / [1.05, 1.1] 生态

与旧 ssui.evaluate 的差异(缺陷 D-05/D-06/D-14):
  - 生产/生态权重分别取第 14/13 页(旧实现两轨互换);
  - 不把 SSUI 截断到 [0,1]: 输出原值, 超 1 时标 exceeds_unit_range;
  - 准则层直接按 Σ v_j S_j 聚合(旧实现在 B 层内重归一化 C 并乘 0.5);
  - C4 组内权重和 ≠ 1 原样使用, 并在 warnings 中列出, 不静默归一化。
"""
from __future__ import annotations

import json
import os

TEMPLATE_VERSION = "SSUI-POST-v1.1"
METHOD_VERSION = "ssui_pptx_v1"


def _weights_path(root: str | None = None) -> str:
    if root:
        return os.path.join(root, "data", "standards", "ssui_weights_pptx_v1.json")
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(os.path.dirname(here)), "data", "standards", "ssui_weights_pptx_v1.json")


def load_weights(root: str | None = None) -> dict:
    with open(_weights_path(root), encoding="utf-8") as fh:
        return json.load(fh)


def indicator_catalog(root: str | None = None) -> list[dict]:
    return load_weights(root)["indicators"]


def grade(value: float, W: dict) -> str:
    for lv in W["levels"]:
        lo, hi = lv["min"], lv["max"]
        if (lo is None or value >= lo) and value < (hi if hi is not None else float("inf")):
            return lv["label"]
    if value >= 1.0:
        return "高度可持续"
    return W["levels"][-1]["label"]


def compute(scores: dict, track: str, t: float, M: float, W: dict | None = None) -> dict:
    """scores: {"D1": 0.72, ...} 共 25 项 s_i ∈ [0,1]。缺任何一项 → status=insufficient。"""
    W = W or load_weights()
    if track not in ("production", "ecology"):
        raise ValueError("track 必须为 production/ecology")
    errors, warnings = [], []
    lo, hi = W["M_range"][track]
    if M is None or not (lo - 1e-9 <= float(M) <= hi + 1e-9):
        errors.append(f"M={M} 超出方法规定区间 [{lo}, {hi}]({track})")
    if t is None or float(t) < 0:
        errors.append(f"t={t} 无效(须 ≥ 0 年)")
    inds = W["indicators"]
    missing = [i["code"] for i in inds if scores.get(i["code"]) is None]
    for code, v in scores.items():
        if v is not None and not (0.0 <= float(v) <= 1.0):
            errors.append(f"{code} 得分 {v} 不在 [0,1]")
    group_sums = {}
    for c in ("C1", "C2", "C3", "C4"):
        s = sum(i["w_" + track] for i in inds if i["criterion"] == c)
        group_sums[c] = round(s, 4)
        if abs(s - 1.0) > 0.01:
            warnings.append(f"{c} 组内权重和 = {s:.3f} ≠ 1(方法文件原值, 未归一化, 待课题组确认)")
    conflicts = [i["code"] for i in inds if i["id_conflict"]]
    if conflicts:
        warnings.append(f"D 编号以第 13/14 页权重表为准; 第 6 页层次图有 {len(conflicts)} 处编号不一致")
    base = {"track": track, "t": t, "M": M, "group_sums": group_sums, "warnings": warnings,
            "method_version": METHOD_VERSION, "method_status": "provisional",
            "formula": W["formula"]}
    if errors or missing:
        return {**base, "status": "insufficient" if missing and not errors else "invalid",
                "ssui": None, "grade": None, "errors": errors, "missing_indicators": missing}
    S = {}
    contrib = []
    for c in ("C1", "C2", "C3", "C4"):
        S[c] = sum(i["w_" + track] * float(scores[i["code"]]) for i in inds if i["criterion"] == c)
    v = W["criterion_weights"][track]
    weighted = sum(v[c] * S[c] for c in S)
    ft = 1 + W["time_alpha"] * float(t)
    raw = ft * weighted * float(M)
    for i in inds:
        contrib.append({"code": i["code"], "name": i["name"], "criterion": i["criterion"],
                        "s": float(scores[i["code"]]), "w": i["w_" + track],
                        "contribution": round(v[i["criterion"]] * i["w_" + track] * float(scores[i["code"]]) * ft * float(M), 6)})
    exceeds = raw > 1.0
    if exceeds:
        warnings.append(f"SSUI 原值 {raw:.4f} > 1.0: 等级区间仅定义到 1.0, 按'高度可持续'显示并标记待确认(未截断)")
    thr = W["support_threshold"]["value"]
    return {**base, "status": "ok", "ssui": round(raw, 6), "grade": grade(raw, W),
            "exceeds_unit_range": exceeds, "f_t": round(ft, 6), "criterion_scores": {k: round(x, 6) for k, x in S.items()},
            "criterion_weights": v, "weighted_sum": round(weighted, 6), "contributions": contrib,
            "feasible": raw >= thr, "support_threshold": thr, "errors": [], "missing_indicators": []}
