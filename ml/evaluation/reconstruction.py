"""功能重构可行性评价 (改进模糊综合评价法 + v1.0.2 GPT 审计修复)。

T_total = Σ(F_i × W_i);  W_i 取自方法文件指标层权重(在"已测指标"内重标化);
等级: T>50 可行, ≤50 不可行 (表2.23)。
区分生产/生态两套指标体系与权重。

v1.0.2 改动(GPT 第五节 + 甲方方法文件):
  1. score_pollutant 缺阈值不再给100分(阻断"超标却评价为优")
     → 调 resolve_threshold_fallback 取GB15618最严档兜底; 仍无→退出打分
  2. 覆盖率门禁: 已测指标/总指标 < 30% → "证据不足/无法评价"
  3. 改进模糊综合评价: 内梅罗指数 P总分=[(P平均²+P权重²)/2]^(1/2)
  4. 缺指标用 MICE 插补(可选, 外部传入); 不简单删除重分权重

纯 python, 仅依赖标准库 + (可选)外部传入的污染物筛选值。可独立测试。
"""
from __future__ import annotations

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_DIR = os.path.join(HERE, "..", "params")
PARAMS = os.path.join(PARAMS_DIR, "evaluation_params.json")
RULES = os.path.join(PARAMS_DIR, "reconstruction_scoring_rules.json")

POLLUTANT_FACTORS = {"砷", "铅", "铜", "锌", "镉", "铬", "汞", "镍", "铬(六价)", "六价铬"}

# v1.0.2(GPT 5.5): 覆盖率门禁 — 已测指标占比低于此值 → 证据不足
COVERAGE_GATE = 0.30


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _find_weight(iw: dict, name: str):
    """权重键匹配: 精确 -> 前缀(处理 '砷 (As)'、'铬 (VI)' 等带后缀键)。"""
    if name in iw:
        return iw[name]
    for k, v in iw.items():
        if k == name or k.startswith(name + " ") or k.startswith(name + "(") \
                or k.startswith(name + " ("):
            return v
    return None


def score_ph(value, scope, rules) -> int | None:
    if value is None:
        return None
    spec = rules[scope].get("pH")
    if not spec:
        return None
    for seg in spec["segments"]:
        if "range" in seg:
            lo, hi = seg["range"]
            if lo <= value <= hi:
                return seg["score"]
            alt = seg.get("alt_range")
            if alt and alt[0] <= value <= alt[1]:
                return seg["score"]
        else:  # 端点段
            mx = seg.get("max")
            omn = seg.get("or_min")
            if (mx is not None and value <= mx) or (omn is not None and value >= omn):
                return seg["score"]
    return None


def score_thresholds_asc(value, segs) -> int | None:
    """segs: [[upper, score], ..., [null, score]] 升序。"""
    if value is None:
        return None
    for upper, score in segs:
        if upper is None or value <= upper:
            return score
    return segs[-1][1]


def score_band(value, ok_range, in_score, out_score) -> int | None:
    if value is None:
        return None
    lo, hi = ok_range
    return in_score if lo <= value <= hi else out_score


def score_pollutant(value, screen_limit) -> int | None:
    """v1.0.2(GPT 5.4): 无管制值时不再给100分(阻断"超标却评价为优")。

    - value is None → 退出打分(返回 None)
    - screen_limit is None → 退出打分(该因子不参与评价, 不奖励也不惩罚)
    - 未超筛选值 → 100
    - 超筛选值 → 50
    调用方应在 screen_limit 为 None 时先调 resolve_threshold_fallback 兜底。
    """
    if value is None:
        return None
    if screen_limit is None:
        # v1.0.2: 无标准 → 该因子退出打分(GPT 5.4 不得当作安全)
        return None
    return 100 if value <= screen_limit else 50


def evaluate(values: dict, scope: str, ph: float | None = None,
             screen_limits: dict | None = None,
             custom_weights: dict | None = None,
             imputed_values: dict | None = None) -> dict:
    """values: {factor_code: site_mean_value}; screen_limits: {factor: limit}。

    v1.0.2 改动:
      - 覆盖率门禁: 已测指标/总指标 < COVERAGE_GATE → "证据不足/无法评价"
      - 改进模糊综合评价: 内梅罗指数 P总分=[(P平均²+P权重²)/2]^(1/2)
      - 污染物无阈值时退出打分(不返100)
    v1.0.2(GPT P0-3): 新增 custom_weights/imputed_values 参数
      - custom_weights: 外部注入的AHP+客观组合权重, 替代静态 indicator_weights
      - imputed_values: MICE插补后的值, 合并到 values 再打分
    """
    params = _load(PARAMS)["reconstruction"][scope]
    rules = _load(RULES)
    iw = custom_weights if custom_weights else params["indicator_weights"]
    # v1.0.2(GPT P0-3): MICE 插补值合并
    if imputed_values:
        values = {**values, **imputed_values}
    land_subtype = _load(RULES).get("land_subtype_default", "dryland")

    scored = []  # (name, F, raw_weight)

    # pH
    if "pH" in values:
        f = score_ph(values["pH"], scope, rules)
        if f is not None and "pH" in iw:
            scored.append(("pH", f, iw["pH"]))

    # 农艺类(升序阈值)
    for name in ("全氮", "有效磷", "速效钾"):
        spec = rules[scope].get(name)
        if spec and spec.get("type") == "thresholds_asc" and name in values and name in iw:
            f = score_thresholds_asc(values[name], spec[land_subtype])
            if f is not None:
                scored.append((name, f, iw[name]))

    # 生态 band 类
    for name in ("水解性氮", "有效磷", "速效钾"):
        spec = rules[scope].get(name)
        if spec and spec.get("type") == "band" and name in values and name in iw \
                and not any(s[0] == name for s in scored):
            f = score_band(values[name], spec["ok_range"], spec["in_score"], spec["out_score"])
            if f is not None:
                scored.append((name, f, iw[name]))

    # 土壤有机碳含量(由有机质换算)
    soc_spec = rules[scope].get("土壤有机碳含量")
    if soc_spec and "有机质" in values and "土壤有机碳含量" in iw:
        soc = values["有机质"] * soc_spec.get("soc_multiply", 0.58)
        f = score_thresholds_asc(soc, soc_spec[land_subtype])
        if f is not None:
            scored.append(("土壤有机碳含量", f, iw["土壤有机碳含量"]))

    # 污染物(逐金属); 生态权重键可能形如 "砷 (As)"
    # v1.0.2: screen_limit 为 None 时 score_pollutant 返回 None(退出打分, 不给100)
    for factor in POLLUTANT_FACTORS:
        w = _find_weight(iw, factor)
        if factor in values and w is not None:
            lim = (screen_limits or {}).get(factor)
            f = score_pollutant(values[factor], lim)
            if f is not None:
                scored.append((factor, f, w))

    # v1.0.2(GPT 5.5): 覆盖率门禁
    all_indicators = set(iw.keys())
    coverage = len(scored) / len(all_indicators) if all_indicators else 0
    if coverage < COVERAGE_GATE:
        return {
            "scope": scope, "score": None, "grade": "证据不足/无法评价",
            "dimensions": [], "weights": {}, "limiting_factors": [],
            "missing_indicators": sorted(all_indicators - {s[0] for s in scored}),
            "calculation_trace": [
                f"① 已测指标 {len(scored)} 项 / 总指标 {len(all_indicators)} 项 = 覆盖率 {coverage:.1%}",
                f"② 覆盖率 < 门禁({COVERAGE_GATE:.0%}) → 证据不足, 不生成正式评价结论(GPT 5.5)",
            ],
            "explanation": f"{'生产' if scope=='production' else '生态'}功能重构: "
                           f"覆盖率 {coverage:.1%} 低于门禁 {COVERAGE_GATE:.0%}, 证据不足, "
                           f"不生成正式评价结论。已测 {len(scored)} 项, 缺测 {len(all_indicators) - len(scored)} 项。"
                           f"建议补充缺失指标后重新评价。",
            "coverage_rate": coverage,
            "coverage_gate": COVERAGE_GATE,
            "is_insufficient": True,
        }

    if not scored:
        return {"scope": scope, "score": None, "grade": "无足够指标",
                "dimensions": [], "weights": {}, "limiting_factors": [],
                "explanation": "无可评价指标"}

    total_w = sum(w for _, _, w in scored)
    dims = []
    score = 0.0
    for name, f, w in scored:
        nw = w / total_w
        contrib = f * nw
        score += contrib
        dims.append({"indicator": name, "F": f, "raw_weight": round(w, 6),
                     "norm_weight": round(nw, 6), "contribution": round(contrib, 4)})
    score = round(score, 2)

    # v1.0.2(GPT 5.1 + 甲方方法): 改进模糊综合评价 — 内梅罗指数
    # P总分 = [(P平均² + P权重²)/2]^(1/2)
    # P平均 = 简单算术平均, P权重 = 加权综合得分
    p_avg = sum(d["F"] for d in dims) / len(dims)
    p_weight = score
    nemerow_score = round(math.sqrt((p_avg ** 2 + p_weight ** 2) / 2), 2)

    grade = "可行" if nemerow_score > 50 else "不可行"
    limiting = sorted([d for d in dims if d["F"] <= 60], key=lambda d: d["F"])

    covered = {d["indicator"] for d in dims}
    all_w = set(iw.keys())
    missing = sorted(all_w - covered)

    # 计算过程轨迹(看得见摸得着)
    trace = [
        f"① 取场地各指标站点均值作为评价输入(共 {len(scored)} 项已测指标, 覆盖率 {coverage:.1%})。",
        f"② 按表2.22 分等赋值得分 F: " + "; ".join(f"{n}={f}分(原值{round(values.get(n, 0), 3) if n in values else '—'})" for n, f, _ in scored),
        f"③ 权重在已测指标内重标化(原始权重和 {round(total_w, 4)} → 1): " + "; ".join(f"{d['indicator']}={round(d['norm_weight'] * 100, 2)}%" for d in dims),
        f"④ 加权综合得分 P权重 = Σ(F × 重标化权重) = {p_weight}",
        f"⑤ 算术平均 P平均 = {p_avg}",
        f"⑥ 改进模糊综合评价(内梅罗指数): P总分 = [(P平均² + P权重²)/2]^(1/2) = [({p_avg}² + {p_weight}²)/2]^(1/2) = {nemerow_score}",
        f"⑦ 等级判定: P总分 {nemerow_score} {'>' if nemerow_score > 50 else '≤'} 50 → {grade}。",
    ]
    explanation = (
        f"{'生产' if scope=='production' else '生态'}功能重构可行性: 内梅罗综合得分 {nemerow_score} "
        f"({grade}, 阈值50)。基于 {len(dims)} 项已测指标(覆盖率 {coverage:.1%}, 权重已重标化)。"
        f"关键限制因子(F≤60): {', '.join(d['indicator'] for d in limiting) or '无'}。"
        f"未参与评价的指标 {len(missing)} 项(本场地缺测): {', '.join(missing[:8])}"
        f"{'…' if len(missing)>8 else ''}。")
    return {
        "scope": scope, "score": nemerow_score, "grade": grade,
        "dimensions": dims,
        "weights": {d["indicator"]: d["norm_weight"] for d in dims},
        "limiting_factors": [d["indicator"] for d in limiting],
        "missing_indicators": missing,
        "calculation_trace": trace,
        "explanation": explanation,
        "coverage_rate": coverage,
        "coverage_gate": COVERAGE_GATE,
        "is_insufficient": False,
        # v1.0.2: 保留原始加权得分供参考
        "raw_weighted_score": p_weight,
        "arithmetic_mean": p_avg,
        "nemerow_score": nemerow_score,
    }
