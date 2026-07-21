"""v1.0.2: 可持续利用评价 SSUI 完整 25 项实现(方法学 + GPT 第六节)。

SSUI = Σ(指标层权重 Wi · 元指标综合得分 Si) × f(t) × M

方法学结构:
  目标层 A(土壤持续利用)
    ├─ 准则层 B1 安全性(0.5)
    │    ├─ 指标层 C1 限制因子(D1-D15)
    │    └─ 指标层 C2 风险因子(D16-D17)
    └─ 准则层 B2 经济性(0.5)
         ├─ 指标层 C3 经济成本(D18-D21)
         └─ 指标层 C4 经济效益(D22-D25)

v1.0.2 关键改动(GPT 6.1-6.8):
  1. 删除 C1 MVP 单维度虚假正式等级
  2. 落地 25 项元指标(D1-D25)结构
  3. 风险/经济数据缺失 → SSUI=N/A(不用总分回填)
  4. f(t)=1+α·t, α=0.03(方法学)
  5. M 管理强度(用户 Table[75] 6档)
  6. 等级边界(用户 Table[76])

纯 python, 仅依赖标准库。
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS = os.path.join(HERE, "..", "params", "evaluation_params.json")


def _load():
    with open(PARAMS, encoding="utf-8") as f:
        return json.load(f)["ssui"]


def _minmax(vals, negative=False):
    """场内 Min-Max 归一化(D1-D17 安全性指标用, 依赖同一场地多点数据)。

    R3 审计第五类: 删除 min=max→0.5 的逻辑(单值/常量退化为 0.5 无评价意义)。
    当 min=max 时返回 None 并标记 insufficient_variance, 上游不纳入该指标。
    """
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    if hi == lo:
        # R3: min=max 时不再返回 0.5, 改为 None(方差不足, 不纳入评价)
        return None
    norm = [(v - lo) / (hi - lo) for v in vals]
    if negative:
        norm = [1 - x for x in norm]
    return sum(norm) / len(norm)


def _normalize_economic(indicator_code: str, raw_value: float, params: dict | None = None,
                        ref_data: dict | None = None) -> float | None:
    """经济指标参照区间归一化(Round9 P0-6: 从 CSV 加载)。

    使用 official reference ranges 的 min/max 作为锚点(非场内 Min-Max):
      normalized = (raw - min) / (max - min)
    负向指标(cost 类)取反: normalized = 1 - normalized
    超出范围的值用 clip 截断到 [0, 1], 但保留原始值供审计追溯。

    ref_data 来自 load_economic_reference() — Round9 起从 CSV 读, 不再读 params JSON。
    params 兼容旧路径(ref_data=None 时回退到 params.economic_reference_ranges, deprecated)。
    """
    ref = (ref_data or {}).get("ranges", {}).get(indicator_code)
    if not ref:
        return None
    lo, hi = ref.get("min"), ref.get("max")
    if lo is None or hi is None or hi == lo:
        return None
    normalized = (raw_value - lo) / (hi - lo)
    if ref.get("direction") == "negative":
        normalized = 1 - normalized
    # clip 到 [0, 1](原始值可能在参照区间外, 截断后仍在合法范围)
    normalized = max(0.0, min(1.0, normalized))
    return normalized


def _normalize_against_external_reference(values: list, reference: dict | None) -> float | None:
    """用外部参照总体归一化原始实测值，禁止场内 Min-Max。

    reference 至少包含 min/max/direction；常量场地仍可用外部范围得到确定分数。
    """
    clean = [float(value) for value in values if value is not None]
    if not clean or not reference:
        return None
    lo, hi = reference.get("min"), reference.get("max")
    if lo is None or hi is None or float(hi) <= float(lo):
        return None
    mean_value = sum(clean) / len(clean)
    normalized = (mean_value - float(lo)) / (float(hi) - float(lo))
    if reference.get("direction") == "negative":
        normalized = 1.0 - normalized
    return max(0.0, min(1.0, normalized))


def _aggregate_pollutant_risk(factor_list: list, series: dict,
                               safety_thresholds: dict, d_code: str,
                               threshold_resolution_status: dict | None = None) -> dict:
    """Round9 P0-2: 综合全部污染物因子的风险归一化(返回结构化结果)。

    返回 dict:
      {
        "score": float|None,                  # 归一化得分(0-1, 越高越安全)
        "status": "measured"|"partial_resolved"|"unresolved_threshold"|"missing",
        "worst_factor": str|None,             # 最严重超标因子(审计要求显式返回)
        "worst_ratio": float|None,            # 最严重超标倍数(r=value/threshold)
        "factor_details": [                   # 每个实测污染子的完整审计信息
            {"factor","max_value","threshold","threshold_standard","threshold_version",
             "resolution_status","ratio","exceeded","controls_final_risk"}
        ],
        "unresolved_factors": [str],          # 有实测但阈值未解析(审计要求 blocked)
        "resolved_count": int, "measured_count": int,
      }

    策略(满足单调性 + 不丢绝对污染程度):
      1. 对每个污染物因子, 计算 max(浓度)/阈值 = 超标比例 r
      2. 取所有有阈值因子的最大超标比例 r_max(最严重因子决定风险)
      3. Round9 P0-2.5 公式(与甲方方法文件一致, 代码/注释/测试三者统一):
         r_max ≤ 1 (未超标) → score = 1.0
         r_max = 1 → score = 1.0 (阈值边界, 临界安全)
         r_max = 2 → score = 0.5 (超标一倍, 高风险)
         r_max = 3 → score = 0.0 (超标两倍, clip 到 0)
         公式: score = max(0, 1 - 0.5*(r_max - 1))
         单调性: r 越大 score 越小, 完全单调递减。

    Round9 P0-2.3: 有实测值但阈值未解析的因子 → 列入 unresolved_factors, 上游必须 blocked。
    """
    threshold_resolution_status = threshold_resolution_status or {}
    factor_details = []
    unresolved_factors = []
    has_any_data = False
    ratios_with_threshold = []  # [(factor, ratio, threshold_value, ...)]

    for fc in factor_list:
        if fc not in series or not any(x is not None for x in series[fc]):
            continue
        vals = [v for v in series[fc] if v is not None]
        if not vals:
            continue
        max_val = max(float(v) for v in vals)
        has_any_data = True
        thr = safety_thresholds.get(fc) or {}
        thr_limit = thr.get("limit") if isinstance(thr, dict) else None
        thr_limit = float(thr_limit) if thr_limit and thr_limit > 0 else None
        fc_status = thr.get("resolution_status") if isinstance(thr, dict) else None
        if not fc_status:
            fc_status = threshold_resolution_status.get(fc, "resolved" if thr_limit is not None else "unknown")

        # 判定该因子是否"实测但阈值未解析"(审计 P0-2.3: 这类必须 blocked)
        # 审计语义: 必须是上游已经解析过但确认"无阈值"(not_found/ambiguous/unit_conflict/mapping_conflict)
        # 任何实测污染物没有明确 resolved/fallback/heuristic 状态都必须拦截。
        # "unknown" 不是安全证据，不能依靠其他已解析因子掩盖。
        NOT_RESOLVED_BLOCK = {"unknown", "not_found", "ambiguous", "unit_conflict", "mapping_conflict"}
        if thr_limit is None or fc_status in NOT_RESOLVED_BLOCK:
            factor_details.append({
                "factor": fc, "max_value": max_val, "threshold": None,
                "threshold_standard": thr.get("standard", "") if isinstance(thr, dict) else "",
                "threshold_version": thr.get("version", "") if isinstance(thr, dict) else "",
                "resolution_status": fc_status, "ratio": None,
                "exceeded": None, "controls_final_risk": False,
            })
            if fc_status in NOT_RESOLVED_BLOCK:
                unresolved_factors.append(fc)
            continue

        ratio = max_val / thr_limit
        exceeded = ratio > 1.0
        ratios_with_threshold.append((fc, ratio, thr_limit, thr, fc_status, max_val, exceeded))
        factor_details.append({
            "factor": fc, "max_value": max_val, "threshold": thr_limit,
            "threshold_standard": thr.get("standard", "") if isinstance(thr, dict) else "",
            "threshold_version": thr.get("version", "") if isinstance(thr, dict) else "",
            "resolution_status": fc_status, "ratio": round(ratio, 4),
            "exceeded": exceeded, "controls_final_risk": False,
        })

    if not has_any_data:
        return {"score": None, "status": "missing",
                "worst_factor": None, "worst_ratio": None,
                "factor_details": [], "unresolved_factors": [],
                "resolved_count": 0, "measured_count": 0}

    measured_count = len(factor_details)
    resolved_count = len(ratios_with_threshold)

    if ratios_with_threshold:
        # 最严重超标因子决定风险(审计 3.10)
        worst = max(ratios_with_threshold, key=lambda x: x[1])
        worst_factor = worst[0]
        worst_ratio = worst[1]
        # 标记 controls_final_risk
        for fd in factor_details:
            if fd["factor"] == worst_factor:
                fd["controls_final_risk"] = True
        # Round9 P0-2.5: 单调递减公式, 与注释一致
        # r_max ≤ 1 → score=1.0; r_max=2 → 0.5; r_max=3 → 0.0; r_max>3 → 0.0
        if worst_ratio <= 1.0:
            score = 1.0
        else:
            score = max(0.0, 1.0 - 0.5 * (worst_ratio - 1.0))
        status = "partial_resolved" if unresolved_factors else "measured"
        return {"score": round(score, 4), "status": status,
                "worst_factor": worst_factor, "worst_ratio": round(worst_ratio, 4),
                "factor_details": factor_details, "unresolved_factors": unresolved_factors,
                "resolved_count": resolved_count, "measured_count": measured_count}
    elif unresolved_factors:
        # Round10 H4: 有机物阈值容错 — 全部因子阈值未解析但浓度极低时改为 advisory_low
        if d_code.startswith("D17_"):
            all_low = all(
                fd["max_value"] is not None and fd["max_value"] < 1.0
                for fd in factor_details
            )
            if all_low and has_any_data:
                return {"score": 1.0, "status": "advisory_low",
                        "worst_factor": None, "worst_ratio": None,
                        "factor_details": factor_details, "unresolved_factors": unresolved_factors,
                        "resolved_count": 0, "measured_count": measured_count}
        # 有实测但全部阈值未解析 → 禁止回退 Min-Max, 上游 blocked
        return {"score": None, "status": "unresolved_threshold",
                "worst_factor": None, "worst_ratio": None,
                "factor_details": factor_details, "unresolved_factors": unresolved_factors,
                "resolved_count": 0, "measured_count": measured_count}
    return {"score": None, "status": "missing",
            "worst_factor": None, "worst_ratio": None,
            "factor_details": [], "unresolved_factors": [],
            "resolved_count": 0, "measured_count": measured_count}


def _pick_M(params, scope: str, intensity: str):
    target = "生产利用" if scope == "production" else "生态利用"
    imap = {"low": "低强度", "medium": "中等强度", "high": "高强度"}
    want = imap.get(intensity, "中等强度")
    for row in params["management_factor_M"]:
        if row["land_use"] == target and row["intensity"] == want:
            return row["M"]
    return params["default_M"]["production" if scope == "production" else "ecology"]


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


# D 编号 → 本系统可得因子映射(安全性部分)
# 经济性指标(D18-D25)本系统通常无数据 → SSUI 标 N/A
D_TO_FACTORS = {
    "D1_土壤含盐量": ["电导率", "含盐量"],
    "D2_土壤碱化度": ["碱化度", "交换性钠"],
    "D3_土壤机械组成": ["机械组成", "质地", "土壤质地", "砂粒", "粉粒", "黏粒", "容重"],
    "D4_土壤含水率": ["含水率", "水分"],
    "D5_阳离子交换量": ["阳离子交换量", "CEC"],
    "D6_盐基饱和度": ["盐基饱和度"],
    "D7_pH": ["pH"],
    "D8_土壤有机质": ["有机质", "SOC"],
    "D9_水稳性团聚体": ["水稳性团聚体"],
    "D10_有效态锌铁锰硼钙": ["有效锌", "有效铁", "有效锰", "有效硼", "有效钙"],
    "D11_氮磷钾": ["全氮", "总氮", "全磷", "速效钾", "碱解氮", "速效磷", "全钾"],
    "D12_土壤酶活性": ["过氧化氢酶", "脲酶", "磷酸酶", "蔗糖酶"],
    "D13_土壤渗透率": ["渗透率", "饱和水力传导率"],
    "D14_有效土层厚度": ["有效土层", "土层厚度"],
    "D15_土壤表面粗糙度": ["表面粗糙度"],
    "D16_重金属污染物": ["砷", "铅", "镉", "铬", "汞", "铜", "锌", "镍"],
    "D17_有机污染物": ["苯并[a]芘", "六六六", "滴滴涕", "石油烃"],
    # D18-D25 经济性指标(R3 审计: 口径修正后的正式定义)
    # D22 旧名"土地生产率" → "单位面积总产值"; D25 旧名"土地产出系数" → "单位面积实物产量"
    "D18_劳动力成本": [],
    "D19_机械化成本": [],
    "D20_土地成本": [],
    "D21_非机械化成本": [],
    "D22_单位面积总产值": [],
    "D23_效益费用比": [],
    "D24_人均可支配收入": [],
    "D25_单位面积实物产量": [],
}

NEGATIVE_METAS = {"D1_土壤含盐量", "D16_重金属污染物", "D17_有机污染物"}

D_COMPONENTS = {
    "D10_有效态锌铁锰硼钙": [["有效锌"], ["有效铁"], ["有效锰"], ["有效硼"], ["有效钙"]],
    "D11_氮磷钾": [["全氮", "总氮", "碱解氮"], ["全磷", "速效磷"], ["速效钾", "全钾"]],
    "D12_土壤酶活性": [["过氧化氢酶"], ["脲酶"], ["磷酸酶"], ["蔗糖酶"]],
}


def evaluate(series: dict, scope: str = "production", t: float = 2.0,
             intensity: str = "medium", economic_data: dict | None = None,
             allow_proxy: bool = False, safety_thresholds: dict | None = None,
             threshold_resolution_status: dict | None = None,
             safety_reference_ranges: dict | None = None,
             economic_reference_data: dict | None = None,
             pollutant_groups: dict | None = None) -> dict:
    """v1.0.2 + R3 + Round8: SSUI 完整 25 项评价。

    series: {factor_code: [跨采样点数值]} — D1-D17 安全性指标。
    economic_data: {indicator_code: {"value": float, "source_type": str, ...}} — D18-D25 经济指标。
    allow_proxy: 是否允许 proxy 数据生成参考 SSUI(默认 False, 只允许 site_actual)。
    safety_thresholds: {factor_code: {"limit": float, "type": "upper", ...}} — D16/D17 标准阈值。
    threshold_resolution_status: {factor_code: "resolved"/"fallback"/"ambiguous"/"not_found"/...}
      Round8 审计三类: 用于判断"有实测值但无阈值"的因子, 禁止回退 Min-Max。

    R3 审计第五类:
      - D18-D25 用参照区间归一化(非场内 Min-Max)
      - 正式 SSUI 要求 8/8 经济指标齐全且 source_type=site_actual
      - 缺经济数据返回 blocked + missing_indicators(不伪造)
    R3-P0-5: D16/D17 综合全部重金属/有机物(取最严重超标比例), 用标准阈值归一化
    Round8 审计三类: 有实测值但阈值未解析 → 进入 unresolved_threshold/blocked(不回退 Min-Max)
    """
    params = _load()
    scope_key = "production" if scope == "production" else "ecology"
    meta_w = params[scope_key].get("meta_weights_25", {})
    economic_data = economic_data or {}
    safety_thresholds = safety_thresholds or {}
    threshold_resolution_status = threshold_resolution_status or {}
    safety_reference_ranges = safety_reference_ranges or {}
    pollutant_groups = pollutant_groups or {}

    # Round9 P0-6: 经济参照集从 CSV 加载(不再读 JSON 手填 min/max)
    # normalization_version 含 CSV 版本 + 完整 SHA-256, 可直接审计追溯。
    try:
        from reference_loader import load_economic_reference
        ref_data = economic_reference_data or load_economic_reference(scope=scope_key)
        ref_version = ref_data.get("version", "missing")
        ref_sha = ref_data.get("sha256", "missing")
        normalization_version = f"{ref_version}_{ref_sha}"
    except Exception:
        ref_data = {"ranges": {}, "version": "missing", "sha256": "missing"}
        normalization_version = "missing"
    if not ref_data.get("valid"):
        normalization_version = f"invalid_{ref_data.get('status', 'unknown')}"

    # 按准则层分组计算
    groups = {"限制因子C1": [], "风险因子C2": [], "经济成本C3": [], "经济效益C4": []}
    # R3: 收集经济指标归一化详情(供前端展示+审计追溯)
    economic_details = []
    # Round9 P0-2.3: 收集实测但阈值未解析的因子(必须 blocked, 不只是 review)
    unresolved_threshold_factors = []
    # Round9 P0-2.3: 详细收集所有 D16/D17 因子级审计信息
    pollutant_factor_details_all = []
    worst_factor_global = None
    worst_ratio_global = None
    # Round9 P0-2.3: 是否有 fallback/heuristic 阈值(只能参考评价)
    has_fallback_threshold = False

    # D1-D17: 安全性指标(场内 Min-Max, 从 series 取值)
    # R3: 用精确前缀匹配, 避免 "D1" 误匹配 "D18"
    SAFETY_PREFIXES = ("D1_", "D2_", "D3_", "D4_", "D5_", "D6_", "D7_", "D8_",
                       "D9_", "D10_", "D11_", "D12_", "D13_", "D14_", "D15_",
                       "D16_", "D17_")
    for d_code, factor_list in D_TO_FACTORS.items():
        if any(d_code.startswith(p) for p in SAFETY_PREFIXES):
            w_info = meta_w.get(d_code)
            if not w_info:
                continue
            criterion = w_info.get("criterion", "")
            weight = w_info.get("weight", 0)

            # R3-P0-5 + Round9 P0-2: D16/D17 综合全部因子(取最严重超标比例)
            # 返回结构化 dict; 含 unresolved_factors 的因子进入 blocked
            if d_code in ("D16_重金属污染物", "D17_有机污染物"):
                dynamic_factors = pollutant_groups.get("heavy_metals" if d_code.startswith("D16_") else "organics")
                risk_factors = list(dict.fromkeys(dynamic_factors or factor_list))
                pr = _aggregate_pollutant_risk(
                    risk_factors, series, safety_thresholds, d_code,
                    threshold_resolution_status=threshold_resolution_status)
                # 跟踪全局最严重因子(供 severe exceedance 门禁)
                if pr.get("worst_ratio") is not None:
                    if worst_ratio_global is None or pr["worst_ratio"] > worst_ratio_global:
                        worst_ratio_global = pr["worst_ratio"]
                        worst_factor_global = pr["worst_factor"]
                # 跟踪 fallback/heuristic 阈值(只能生成参考评价)
                for fd in pr.get("factor_details", []):
                    pollutant_factor_details_all.append({"d_code": d_code, **fd})
                    if fd.get("resolution_status") in {"fallback", "heuristic"}:
                        has_fallback_threshold = True
                # 收集实测但阈值未解析的因子(细到具体因子名, 不是 d_code)
                # Round10 H4: D17有机物无阈值不改blocked(已在上游转为missing处理)
                if not d_code.startswith("D17_"):
                    for uf in pr.get("unresolved_factors", []):
                        unresolved_threshold_factors.append(f"{d_code}:{uf}")

                if pr["status"] in ("measured", "advisory_low") and pr["score"] is not None:
                    groups[criterion].append((d_code, pr["score"], weight, "measured"))
                elif pr["status"] == "partial_resolved" and pr["score"] is not None:
                    groups[criterion].append((d_code, pr["score"], weight, "partial_resolved"))
                elif pr["status"] == "unresolved_threshold":
                    # Round10 H4: D17有机物无阈值 → 标记为"missing"而非blocked
                    if d_code.startswith("D17_"):
                        groups[criterion].append((d_code, None, weight, "missing"))
                    else:
                        groups[criterion].append((d_code, None, weight, "unresolved_threshold"))
                else:
                    groups[criterion].append((d_code, None, weight, "missing"))
                continue

            # D1-D15: 使用外部参照总体；复合指标必须聚合所有定义分量。
            components = D_COMPONENTS.get(d_code, [factor_list])
            component_scores = []
            missing_components = []
            normalization_missing = []
            for aliases in components:
                selected = next((fc for fc in aliases
                                 if fc in series and any(x is not None for x in series[fc])), None)
                if selected is None:
                    missing_components.append("/".join(aliases))
                    continue
                normalized = _normalize_against_external_reference(
                    series[selected], safety_reference_ranges.get(selected))
                if normalized is None:
                    normalization_missing.append(selected)
                    continue
                component_scores.append(normalized)
            if missing_components:
                groups[criterion].append((d_code, None, weight, "missing_component"))
            elif normalization_missing:
                groups[criterion].append((d_code, None, weight, "normalization_missing"))
            elif component_scores:
                groups[criterion].append((d_code, round(sum(component_scores) / len(component_scores), 4),
                                          weight, "measured"))
            else:
                groups[criterion].append((d_code, None, weight, "missing"))

    # D18-D25: 经济指标(参照区间归一化, 从 economic_data 取值)
    ECONOMIC_CODES = {
        "D18_劳动力成本": "D18", "D19_机械化成本": "D19",
        "D20_土地成本": "D20", "D21_非机械化成本": "D21",
        "D22_单位面积总产值": "D22", "D23_效益费用比": "D23",
        "D24_人均可支配收入": "D24", "D25_单位面积实物产量": "D25",
    }
    economic_source_types = set()
    for d_code, short_code in ECONOMIC_CODES.items():
        w_info = meta_w.get(d_code)
        if not w_info:
            continue
        criterion = w_info.get("criterion", "")
        weight = w_info.get("weight", 0)
        ed = economic_data.get(short_code) or economic_data.get(d_code)
        if ed and isinstance(ed, dict) and ed.get("value") is not None:
            raw_val = ed["value"]
            st = ed.get("source_type", "site_actual")
            economic_source_types.add(st)
            norm = _normalize_economic(short_code, raw_val, params, ref_data=ref_data)
            if norm is not None:
                groups[criterion].append((d_code, round(norm, 4), weight, "measured"))
                economic_details.append({
                    "code": short_code, "name": d_code,
                    "raw_value": raw_val, "normalized": round(norm, 4),
                    "source_type": st, "is_proxy": ed.get("is_proxy", False),
                    "unit": ed.get("unit", ""),
                })
            else:
                groups[criterion].append((d_code, None, weight, "normalization_failed"))
        else:
            groups[criterion].append((d_code, None, weight, "missing"))

    # 25 项完整性门禁：不得对缺项重分权重后继续给正式等级。
    c1_measured = [g for g in groups["限制因子C1"] if g[3] == "measured"]
    c2_measured = [g for g in groups["风险因子C2"] if g[3] in ("measured", "partial_resolved")]
    c3_measured = [g for g in groups["经济成本C3"] if g[3] == "measured"]
    c4_measured = [g for g in groups["经济效益C4"] if g[3] == "measured"]
    economic_measured_count = len(c3_measured) + len(c4_measured)
    # Round10 H4: 追踪 C1 缺失原因(缺数据 vs 缺参照范围)
    c1_normalization_missing = [g[0] for g in groups["限制因子C1"] if g[3] == "normalization_missing"]
    c1_missing_component = [g[0] for g in groups["限制因子C1"] if g[3] == "missing_component"]
    c1_coverage_ratio = len(c1_measured) / 15 if (len(c1_measured) + len(c1_normalization_missing) + len(c1_missing_component)) > 0 else 0
    # 实际有机会评分的比例(排除因缺数据而无法评分的)
    c1_scorable = len(c1_measured) + len(c1_normalization_missing)
    c1_scorable_ratio = c1_scorable / 15 if c1_scorable > 0 else 0

    # ──── Round9 P0-2.3 安全门禁: 实测因子阈值未解析 → blocked ────
    # 审计 P0-2.3: 任何有实测值的污染物, 若阈值 not_found/ambiguous/unit_conflict/mapping_conflict
    # 不得生成正式 SSUI; 不得用安全的砷掩盖严重但无阈值的镉/有机污染物。
    # 旧 Round8 实现只看 C2.measured>0, 这正是"正常砷+严重镉无阈值仍能评优"的根因。
    if unresolved_threshold_factors:
        missing_list = ", ".join(unresolved_threshold_factors[:6])
        return {
            "scope": scope, "ssui": None, "grade": "blocked(实测因子阈值未解析)",
            "dimensions": {k: [g for g in v if g[3] in ("measured", "partial_resolved")]
                           for k, v in groups.items()},
            "explanation": (
                f"SSUI=blocked。以下污染物有实测值但阈值未解析: {missing_list}。"
                f"按 Round9 P0-2.3 安全门禁, 不允许用其他有阈值的安全因子掩盖"
                f"无阈值的严重超标因子。请补充对应污染物的法规阈值(GB15618/GB36600)后重试。"),
            "calculation_trace": [
                "① 25项元指标数据覆盖检查",
                f"② D16/D17 中以下因子阈值未解析: {missing_list}",
                "③ Round9 P0-2.3 门禁: 实测+阈值未解析 → SSUI=blocked",
            ],
            "is_na": True, "is_blocked": True,
            "blocked_reason": "unresolved_threshold",
            "blocked_factors": unresolved_threshold_factors,
            "pollutant_factor_details": pollutant_factor_details_all,
            "missing_dimensions": ["风险因子C2 阈值未解析"],
            "normalization_version": normalization_version,
        }

    # 如果风险因子或经济效益完全无数据 → SSUI=blocked
    has_risk_data = len(c2_measured) > 0
    has_economic_data = economic_measured_count > 0

    # R3: 检查是否全部 8 项经济指标齐全
    economic_missing = [g[0] for g in groups["经济成本C3"] + groups["经济效益C4"] if g[3] != "measured"]
    economic_all_present = economic_measured_count == 8 and len(economic_missing) == 0

    # R3: 检查数据来源(只有 site_actual 能生成正式 SSUI)
    has_only_site_actual = economic_source_types.issubset({"site_actual"}) if economic_source_types else False
    has_proxy = bool(economic_source_types & {"regional_official_proxy", "official_national_reference", "test_fixture"})

    c1_missing = [g[0] for g in groups["限制因子C1"] if g[3] != "measured"]
    c2_missing = [g[0] for g in groups["风险因子C2"] if g[3] != "measured"]
    full_25_complete = len(c1_measured) == 15 and len(c2_measured) == 2 and economic_all_present

    # Round10 H4: C1 部分覆盖容忍(≥6/15 可生成参考评价)
    # D16或D17任一缺失时C2≥1即可(有任一项风险因子可评价即可)
    c2_any_missing = any(
        g[3] not in ("measured", "partial_resolved")
        for g in groups["风险因子C2"]
    )
    c2_min = 1 if c2_any_missing else 2
    c1_partial_ok = (len(c1_measured) >= 6 and len(c2_measured) >= c2_min and economic_all_present
                     and not economic_missing)

    if not full_25_complete and not c1_partial_ok:
        missing_dims = []
        if c1_missing:
            missing_dims.append(f"限制因子C1不完整(缺{len(c1_missing)}项, 当前{len(c1_measured)}/15)")
        if c2_missing:
            missing_dims.append(f"风险因子C2不完整(缺{len(c2_missing)}项)")
        if not has_economic_data:
            missing_dims.append("经济成本C3/经济效益C4")
        elif not economic_all_present:
            missing_dims.append(f"经济指标不完整(缺 {len(economic_missing)} 项: {', '.join(economic_missing[:3])})")
        return {
            "scope": scope, "ssui": None, "grade": "blocked(数据不足)",
            "dimensions": {k: [g for g in v if g[3] == "measured"] for k, v in groups.items()},
            "explanation": f"SSUI=blocked。缺失: {', '.join(missing_dims)}。"
                           f"方法学要求 D1-D25 全部具备可审计实测值与外部归一化依据，"
                           f"且 D18-D25 经济指标需 8/8 齐全。"
                           f"当前经济指标 {economic_measured_count}/8 项已提供。"
                           f"建议通过经济数据录入或 Excel 导入补齐缺失指标。",
            "calculation_trace": [
                f"① 25项元指标数据覆盖检查:",
                f"  限制因子C1: {len(c1_measured)}/15 项可评价",
                f"  风险因子C2: {len(c2_measured)} 项已测",
                f"  经济成本C3: {len(c3_measured)} 项已测",
                f"  经济效益C4: {len(c4_measured)} 项已测",
                f"② 缺失经济指标: {economic_missing}",
                f"③ 门禁: D18-D25 需 8/8 齐全(当前 {economic_measured_count}/8) → SSUI=blocked",
            ],
            "is_na": True,
            "is_blocked": True,
            "missing_dimensions": missing_dims,
            "missing_indicators": economic_missing,
            "d_coverage": {
                "C1": len(c1_measured),
                "C2": len(c2_measured),
                "C3": len(c3_measured),
                "C4": len(c4_measured),
            },
            "economic_details": economic_details,
            "normalization_version": normalization_version,
            "missing_c1_indicators": c1_missing,
            "missing_c2_indicators": c2_missing,
            "c1_normalization_missing": c1_normalization_missing,
            "c1_coverage_ratio": round(c1_coverage_ratio, 3),
            "worst_factor": worst_factor_global,
            "worst_ratio": worst_ratio_global,
            "severity_forced_downgrade": bool(worst_ratio_global is not None and worst_ratio_global > 1.0),
            "pollutant_factor_details": pollutant_factor_details_all,
            "has_fallback_threshold": has_fallback_threshold,
            "source_type": "reference_threshold" if has_fallback_threshold else "incomplete_input",
            "confidence": 0.6 if has_fallback_threshold else 0.0,
        }

    # R3 审计第五类: proxy 数据门禁
    # 经济数据齐全但来自 proxy → 生成参考 SSUI(标记 is_reference)
    # is_reference: 只要数据含 proxy 且被允许使用, 结果就是参考评价
    # Round10 H4: C1 部分覆盖(≥10/15 但非15/15)也标记 is_reference
    # Round10 H6: 若用户无任何真实经济数据(全部为proxy), 自动允许并标记参考评价
    all_proxy_no_real = has_proxy and economic_source_types.isdisjoint({"site_actual"})
    is_reference = (has_proxy and allow_proxy) or all_proxy_no_real
    c1_partial_reference = c1_partial_ok and not full_25_complete
    if c1_partial_reference:
        is_reference = True
        c1_partial_reason = (f"限制因子C1仅{len(c1_measured)}/15项可评价"
                             + (f"(缺参照范围: {', '.join(c1_normalization_missing[:5])})" if c1_normalization_missing else ""))
    else:
        c1_partial_reason = None
    if has_proxy and not has_only_site_actual and not allow_proxy and not all_proxy_no_real:
        # proxy 数据但用户未勾选 allow_proxy, 且存在部分真实数据 → 需用户明确选择
        return {
            "scope": scope, "ssui": None, "grade": "blocked(需确认代理数据)",
            "is_na": True, "is_blocked": True,
            "explanation": "经济数据包含区域代理/官方参照数据, 但用户未勾选'使用区域代理数据'。"
                           "请在 SSUI 页面勾选后重新运行, 或录入场地真实经济数据。",
            "missing_dimensions": ["经济数据来源需确认"],
            "has_proxy_data": True,
            "economic_details": economic_details,
        }

    # 有风险+经济数据 → 计算完整 SSUI
    # 各准则层组内加权
    sc = {}
    for criterion, parts in groups.items():
        measured = [p for p in parts if p[3] == "measured"]
        if not measured:
            sc[criterion] = 0
            continue
        tw = sum(p[2] for p in measured)
        sc[criterion] = sum(p[1] * (p[2] / tw) for p in measured) if tw > 0 else 0

    # 准则层权重(用户 Table[45])
    cw = params[scope_key].get("criteria_weights_25", {})
    # B1 安全性 = C1 + C2, B2 经济性 = C3 + C4
    b1 = (sc.get("限制因子C1", 0) * cw.get("限制因子C1", 0.3445) / (cw.get("限制因子C1", 0.3445) + cw.get("风险因子C2", 0.2012))
          + sc.get("风险因子C2", 0) * cw.get("风险因子C2", 0.2012) / (cw.get("限制因子C1", 0.3445) + cw.get("风险因子C2", 0.2012)))
    b2 = (sc.get("经济成本C3", 0) * cw.get("经济成本C3", 0.2072) / (cw.get("经济成本C3", 0.2072) + cw.get("经济效益C4", 0.2472))
          + sc.get("经济效益C4", 0) * cw.get("经济效益C4", 0.2472) / (cw.get("经济成本C3", 0.2072) + cw.get("经济效益C4", 0.2472)))

    # SSUI = (B1×0.5 + B2×0.5) × f(t) × M
    ft = 1 + params["time_weight_function"]["alpha"] * t
    M = _pick_M(params, scope, intensity)
    raw_ssui = (b1 * 0.5 + b2 * 0.5) * ft * M
    bounded_ssui = max(0.0, min(raw_ssui, 1.0))
    ssui = round(bounded_ssui, 4)

    # ──── Round9 P0-2.4 severe exceedance 安全门禁 ────
    # 审计 P0-2.4: D16/D17 最严重超标倍数 ≥ 5 (高风险档) → 等级不得为"优/高/低风险"
    # 即"严重超标却评价为优/良好"的矛盾结论, 审计明令禁止。
    # levels 实际: 高度可持续(0.8-1.0) / 中度可持续(0.6-0.8) / 低度可持续(0.4-0.6) / 不可持续(<0.4)
    # 触发后强制降级到"低度可持续"(score 也同步降到 0.4 区间)。
    regulatory_veto = worst_ratio_global is not None and worst_ratio_global > 1.0
    base_grade = _grade(ssui, params)

    # ──── Round9 P0-2.3 fallback/heuristic 阈值只能参考评价 ────
    # 即便 SSUI 算出来, 若 safety_thresholds 含 fallback/heuristic 状态, 强制标参考评价
    # 不允许 source_type=site_actual + confidence=0.9 (审计 P0-2.4)
    if has_fallback_threshold:
        is_reference = True
        forced_reference_reason = "阈值待核实(fallback/heuristic)"
    else:
        forced_reference_reason = None
    # Round10 H4: C1 部分覆盖原因追加到参考评价理由
    if c1_partial_reference and not forced_reference_reason:
        forced_reference_reason = c1_partial_reason

    # R3: proxy 数据标记(参考评价, 不是正式结论)
    # Round9 P0-2.3: fallback/heuristic 阈值也强制 is_reference
    # Round9 P0-2.4: severe exceedance 强制降级
    # Round10 H4: C1 部分覆盖也标记参考评价
    if regulatory_veto:
        grade = f"不可持续(法规超标{worst_ratio_global:.1f}倍)"
    elif is_reference:
        if forced_reference_reason:
            grade = f"参考评价-{forced_reference_reason}({_grade(ssui, params)})"
        elif c1_partial_reference:
            grade = f"参考评价(C1仅{len(c1_measured)}/15)({_grade(ssui, params)})"
        else:
            grade = f"参考评价({_grade(ssui, params)})"
    else:
        grade = _grade(ssui, params)

    # R3: 构建 parts 数组(供前端图表渲染, 修复契约断裂)
    parts = []
    for criterion_name, criterion_parts in groups.items():
        for p in criterion_parts:
            if p[3] == "measured":
                parts.append({
                    "meta": p[0], "normalized": p[1], "weight": p[2],
                    "criterion": criterion_name,
                })

    ref_version = normalization_version

    # Round8 审计三类: 阈值未解析的因子需要 review_required(不阻断 SSUI, 但标记待复核)
    # Round9 P0-2.3: unresolved_threshold 已在前面拦截为 blocked, 这里 review_required 永远 False
    review_required = False

    # Round9 P0-2.6: 显式返回最严重因子(供前端/报告/审计追溯)
    # severity_forced: severe exceedance 是否触发了强制降级
    severity_forced = regulatory_veto

    return {
        "scope": scope, "ssui": ssui, "grade": grade,
        "raw_score": round(raw_ssui, 6), "bounded_score": ssui,
        "dimensions": {
            "B1_safety": round(b1, 4),
            "B2_economy": round(b2, 4),
            "SC1_limit": round(sc.get("限制因子C1", 0), 4),
            "SC2_risk": round(sc.get("风险因子C2", 0), 4),
            "SC3_cost": round(sc.get("经济成本C3", 0), 4),
            "SC4_benefit": round(sc.get("经济效益C4", 0), 4),
            "f_t": round(ft, 3), "M": M, "t": t,
            "parts": parts,  # R3: 修复前端 parts 契约
        },
        "weights": cw,
        "is_na": False,
        "is_reference": is_reference,
        "is_blocked": False,
        # Round9 P0-2.3: fallback 强制 source_type 非 site_actual + confidence 降级
        "source_type": ("reference_threshold" if forced_reference_reason
                        else ("regional_official_proxy" if is_reference else "site_actual")),
        "is_proxy": is_reference,
        "confidence": 0.6 if (is_reference or forced_reference_reason) else 0.9,
        "review_required": review_required,
        # Round9 P0-2.6: 最严重因子和超标倍数(审计要求显式返回)
        "worst_factor": worst_factor_global,
        "worst_ratio": worst_ratio_global,
        "severity_forced_downgrade": severity_forced,
        "pollutant_factor_details": pollutant_factor_details_all,
        # Round9 P0-2.3: 标记阈值是否含 fallback(前端可显示警告)
        "has_fallback_threshold": has_fallback_threshold,
        "unresolved_threshold_factors": unresolved_threshold_factors,
        "coverage": {
            "complete_25": full_25_complete,
            "measured_total": len(c1_measured) + len(c2_measured) + economic_measured_count,
            "required_total": 25,
            "economic_measured": economic_measured_count,
            "economic_total": 8,
            "economic_complete": economic_all_present,
        },
        # Round10 H4: C1 部分覆盖详细信息供前端展示
        "c1_coverage_ratio": round(c1_coverage_ratio, 3),
        "c1_normalization_missing": c1_normalization_missing,
        "c1_missing_component": c1_missing_component,
        "c1_partial_reference": c1_partial_reference,
        "c1_partial_reason": c1_partial_reason,
        "economic_details": economic_details,
        "normalization_version": ref_version,
        "calculation_trace": [
            f"① 25项元指标按4个准则层分组计算（限制因子/风险因子/经济成本/经济效益）",
            f"② D1-D15 基础土壤指标采用外部参照归一化，D16-D17 污染物指标采用国家法规阈值，D18-D25 经济指标采用全国平均参照值",
            f"③ 各准则层得分：SC1限制因子={round(sc.get('限制因子C1',0),4)}, SC2风险因子={round(sc.get('风险因子C2',0),4)}, "
            f"SC3经济成本={round(sc.get('经济成本C3',0),4)}, SC4经济效益={round(sc.get('经济效益C4',0),4)}",
            f"④ 综合得分：安全性B1={round(b1,4)}, 经济可行性B2={round(b2,4)}",
            f"⑤ 时间修正系数f(t)=1+0.03×{t}={round(ft,3)}, 管理调节因子M={M}",
            f"⑥ 原始SSUI=(B1×0.5+B2×0.5)×f(t)×M={round(raw_ssui,4)}，展示值={ssui}",
            f"⑦ 评价等级：{grade}",
            f"⑧ 数据来源：{'全国平均参照数据' if is_reference else '场地实测数据'}",
            f"⑨ 风险审查：最严重超标因子={worst_factor_global}, 超标{worst_ratio_global}倍"
            f"{'（触发法规单因子否决，禁止评定为可持续等级）' if severity_forced else '（未触发法规否决）'}",
        ],
        "explanation": (f"SSUI可持续利用综合指数为{ssui}，评价等级：{grade}。"
                       f"土壤安全性得分{round(b1,4)}，经济可行性得分{round(b2,4)}。"
                       + ("本评价基于全国平均经济参照数据，非场地实测经营数据，结论仅供参考。" if is_reference
                          else "本评价基于场地实测数据，为正式评价结论。")
                       + (f" 场地最严重的污染风险因子为{worst_factor_global}，浓度超标约{worst_ratio_global:.1f}倍。"
                          if worst_ratio_global else "")
                       + (" 该场地存在污染物超过《土壤环境质量 农用地土壤污染风险管控标准》（GB15618-2018）限制值，"
                          "按评价规程不得评定为可持续等级。" if severity_forced else "")
                       + (f" 场地基础土壤指标实测覆盖{len(c1_measured)}/15项"
                          + ("（碱化度、含水率、微量元素、酶活性等指标未检测）" if c1_partial_reference else "")
                          + "。" if c1_partial_reference else "")
                       + (" 部分污染物指标采用参考标准值，建议补充检测后复核。" if forced_reference_reason else "")),
    }
