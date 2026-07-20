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


def _normalize_economic(indicator_code: str, raw_value: float, params: dict) -> float | None:
    """经济指标参照区间归一化(R3 审计第五类)。

    使用 official reference ranges 的 min/max 作为锚点(非场内 Min-Max):
      normalized = (raw - min) / (max - min)
    负向指标(cost 类)取反: normalized = 1 - normalized
    超出范围的值用 clip 截断到 [0, 1], 但保留原始值供审计追溯。
    """
    ref = params.get("economic_reference_ranges", {}).get("ranges", {}).get(indicator_code)
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


def _aggregate_pollutant_risk(factor_list: list, series: dict,
                               safety_thresholds: dict, d_code: str,
                               threshold_resolution_status: dict | None = None) -> tuple:
    """Round8 审计三类: 综合全部污染物因子的风险归一化。

    返回 (score_or_None, status) 二元组:
      - status="measured": 有实测+有阈值, score 是数值
      - status="unresolved_threshold": 有实测但全部因子阈值未解析 → 禁止回退 Min-Max
        (审计 3.5: 不得用场内 Min-Max 伪装正式评价, 进入 review_required/blocked)
      - status="missing": 无实测数据
      - status="partial_resolved": 部分因子有阈值, 部分无阈值
        (审计 3.10: 正常砷+严重镉必须由镉决定 D16 风险 — 用最严重超标因子决定)

    策略(满足单调性 + 不丢绝对污染程度):
      1. 对每个污染物因子, 计算 max(浓度)/阈值 = 超标比例 r
      2. 取所有有阈值因子的最大超标比例 r_max(最严重因子决定风险)
      3. 用超标比例归一化: r_max=0→1.0(安全), r_max=1→0.5(刚好达标边界),
         r_max=2→0.0(超标2倍, 极高风险)
      公式: score = max(0, 1 - max(0, r_max - 1)) → r≤1时score=1, r=2时score=0

    Round8 审计 3.5: 有实测值但没有阈值时, 不得回退场内 Min-Max 生成正式评价。
    """
    threshold_resolution_status = threshold_resolution_status or {}
    ratios = []
    has_any_data = False
    has_threshold = False
    has_unresolved_threshold = False
    for fc in factor_list:
        if fc in series and any(x is not None for x in series[fc]):
            vals = [v for v in series[fc] if v is not None]
            if not vals:
                continue
            max_val = max(vals)
            has_any_data = True
            # Round8 审计 3.2-3.3: 阈值解析状态以 threshold_resolution_status 为准
            fc_status = threshold_resolution_status.get(fc, "unknown")
            thr = safety_thresholds.get(fc)
            if thr and thr.get("limit") and thr["limit"] > 0:
                ratio = max_val / thr["limit"]
                ratios.append((fc, ratio))
                has_threshold = True
            else:
                # 有实测值但无阈值 → 标记 unresolved
                has_unresolved_threshold = True

    if not has_any_data:
        return (None, "missing")

    if ratios:
        # Round8 审计 3.10: 用最严重超标因子决定风险(正常砷+严重镉→镉决定)
        r_max = max(r[1] for r in ratios)
        worst_factor = max(ratios, key=lambda x: x[1])[0]
        # 单调性: 超标比例越高, 得分越低
        # r_max ≤ 1 (未超标) → score = 1.0
        # r_max = 1 → score = 1.0 (阈值边界)
        # r_max = 2 → score = 0.0 (超标一倍)
        # r_max > 2 → score = 0.0 (clip)
        if r_max <= 1.0:
            score = 1.0
        else:
            score = max(0.0, 1.0 - (r_max - 1.0))
        status = "partial_resolved" if has_unresolved_threshold else "measured"
        return (score, status)
    elif has_unresolved_threshold:
        # Round8 审计 3.5: 有实测值但全部因子阈值未解析 → 禁止回退 Min-Max
        return (None, "unresolved_threshold")
    return (None, "missing")


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
    "D3_土壤机械组成": ["机械组成", "质地", "土壤质地"],
    "D4_土壤含水率": ["含水率", "水分"],
    "D5_阳离子交换量": ["阳离子交换量", "CEC"],
    "D6_盐基饱和度": ["盐基饱和度"],
    "D7_pH": ["pH"],
    "D8_土壤有机质": ["有机质", "SOC"],
    "D9_水稳性团聚体": ["水稳性团聚体"],
    "D10_有效态锌铁锰硼钙": ["有效锌", "有效铁", "有效锰", "有效硼", "有效钙"],
    "D11_氮磷钾": ["全氮", "总氮", "全磷", "速效钾"],
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


def evaluate(series: dict, scope: str = "production", t: float = 2.0,
             intensity: str = "medium", economic_data: dict | None = None,
             allow_proxy: bool = False, safety_thresholds: dict | None = None,
             threshold_resolution_status: dict | None = None) -> dict:
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

    # 按准则层分组计算
    groups = {"限制因子C1": [], "风险因子C2": [], "经济成本C3": [], "经济效益C4": []}
    # R3: 收集经济指标归一化详情(供前端展示+审计追溯)
    economic_details = []
    # Round8: 收集阈值未解析因子(进入 review_required)
    unresolved_threshold_factors = []

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

            # R3-P0-5 + Round8 审计三类: D16/D17 综合全部因子(取最严重超标比例)
            # 返回 (score, status) 二元组; status="unresolved_threshold" 时禁止回退 Min-Max
            if d_code in ("D16_重金属污染物", "D17_有机污染物"):
                score_val, status_val = _aggregate_pollutant_risk(
                    factor_list, series, safety_thresholds, d_code,
                    threshold_resolution_status=threshold_resolution_status)
                if status_val == "measured" and score_val is not None:
                    groups[criterion].append((d_code, round(score_val, 4), weight, "measured"))
                elif status_val == "partial_resolved" and score_val is not None:
                    # 部分因子有阈值, 部分无 — 用最严重超标因子决定, 但标记 review_required
                    groups[criterion].append((d_code, round(score_val, 4), weight, "partial_resolved"))
                    unresolved_threshold_factors.append(d_code)
                elif status_val == "unresolved_threshold":
                    # Round8 审计 3.5: 有实测但阈值全部未解析 → 禁止 Min-Max 伪装正式结果
                    groups[criterion].append((d_code, None, weight, "unresolved_threshold"))
                    unresolved_threshold_factors.append(d_code)
                else:
                    groups[criterion].append((d_code, None, weight, "missing"))
                continue

            # D1-D15: 保持场内 Min-Max(非污染物, 场内归一化有意义)
            vals = None
            for fc in factor_list:
                if fc in series and any(x is not None for x in series[fc]):
                    vals = series[fc]
                    break
            if vals is not None:
                norm = _minmax(vals, negative=(d_code in NEGATIVE_METAS))
                if norm is not None:
                    groups[criterion].append((d_code, round(norm, 4), weight, "measured"))
                else:
                    # R3: min=max→None, 方差不足不纳入
                    groups[criterion].append((d_code, None, weight, "insufficient_variance"))
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
            norm = _normalize_economic(short_code, raw_val, params)
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

    # R3 审计第五类: 风险/经济数据缺失检查 + 8/8 经济齐全门禁
    c2_measured = [g for g in groups["风险因子C2"] if g[3] == "measured"]
    c3_measured = [g for g in groups["经济成本C3"] if g[3] == "measured"]
    c4_measured = [g for g in groups["经济效益C4"] if g[3] == "measured"]
    economic_measured_count = len(c3_measured) + len(c4_measured)

    # 如果风险因子或经济效益完全无数据 → SSUI=blocked
    has_risk_data = len(c2_measured) > 0
    has_economic_data = economic_measured_count > 0

    # R3: 检查是否全部 8 项经济指标齐全
    economic_missing = [g[0] for g in groups["经济成本C3"] + groups["经济效益C4"] if g[3] != "measured"]
    economic_all_present = economic_measured_count == 8 and len(economic_missing) == 0

    # R3: 检查数据来源(只有 site_actual 能生成正式 SSUI)
    has_only_site_actual = economic_source_types.issubset({"site_actual"}) if economic_source_types else False
    has_proxy = bool(economic_source_types & {"regional_official_proxy", "official_national_reference", "test_fixture"})

    if not has_risk_data or not has_economic_data or not economic_all_present:
        missing_dims = []
        if not has_risk_data:
            missing_dims.append("风险因子C2")
        if not has_economic_data:
            missing_dims.append("经济成本C3/经济效益C4")
        elif not economic_all_present:
            missing_dims.append(f"经济指标不完整(缺 {len(economic_missing)} 项: {', '.join(economic_missing[:3])})")
        return {
            "scope": scope, "ssui": None, "grade": "blocked(数据不足)",
            "dimensions": {k: [g for g in v if g[3] == "measured"] for k, v in groups.items()},
            "explanation": f"SSUI=blocked。缺失: {', '.join(missing_dims)}。"
                           f"方法学要求安全性(含风险因子)+经济性双重数据, "
                           f"且 D18-D25 经济指标需 8/8 齐全才能生成正式 SSUI。"
                           f"当前经济指标 {economic_measured_count}/8 项已提供。"
                           f"建议通过经济数据录入或 Excel 导入补齐缺失指标。",
            "calculation_trace": [
                f"① 25项元指标数据覆盖检查:",
                f"  限制因子C1: {len([g for g in groups['限制因子C1'] if g[3]=='measured'])} 项已测",
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
                "C1": len([g for g in groups["限制因子C1"] if g[3] == "measured"]),
                "C2": len(c2_measured),
                "C3": len(c3_measured),
                "C4": len(c4_measured),
            },
            "economic_details": economic_details,
            "normalization_version": params.get("economic_reference_ranges", {}).get("version", "unknown"),
        }

    # R3 审计第五类: proxy 数据门禁
    # 经济数据齐全但来自 proxy → 生成参考 SSUI(标记 is_reference)
    # is_reference: 只要数据含 proxy 且被允许使用, 结果就是参考评价
    is_reference = has_proxy and allow_proxy
    if has_proxy and not has_only_site_actual and not allow_proxy:
        # proxy 数据但用户未勾选 allow_proxy → 返回 blocked, 提示用户主动选择
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
    ssui = round(min(raw_ssui, 1.0), 4)

    # R3: proxy 数据标记(参考评价, 不是正式结论)
    if is_reference:
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

    ref_version = params.get("economic_reference_ranges", {}).get("version", "unknown")

    # Round8 审计三类: 阈值未解析的因子需要 review_required(不阻断 SSUI, 但标记待复核)
    review_required = bool(unresolved_threshold_factors)

    return {
        "scope": scope, "ssui": ssui, "grade": grade,
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
        "source_type": "regional_official_proxy" if is_reference else "site_actual",
        "is_proxy": is_reference,
        "confidence": 0.6 if is_reference else 0.9,
        "review_required": review_required,
        "unresolved_threshold_factors": unresolved_threshold_factors,
        "coverage": {
            "economic_measured": economic_measured_count,
            "economic_total": 8,
            "economic_complete": economic_all_present,
        },
        "economic_details": economic_details,
        "normalization_version": ref_version,
        "calculation_trace": [
            f"① 25项元指标按4个准则层分组计算(限制因子/风险因子/经济成本/经济效益)",
            f"② D1-D17 安全性: 场内Min-Max归一化; D18-D25 经济: 参照区间归一化({ref_version})",
            f"③ 各准则层组内加权: SC1={round(sc.get('限制因子C1',0),4)}, SC2={round(sc.get('风险因子C2',0),4)}, "
            f"SC3={round(sc.get('经济成本C3',0),4)}, SC4={round(sc.get('经济效益C4',0),4)}",
            f"④ B1安全性={round(b1,4)}, B2经济性={round(b2,4)}",
            f"⑤ f(t)=1+0.03×{t}={round(ft,3)}, M={M}",
            f"⑥ SSUI=(B1×0.5+B2×0.5)×f(t)×M={round(raw_ssui,4)}→min(,1.0)={ssui}",
            f"⑦ 等级: {grade}",
            f"⑧ 数据来源: {'区域代理数据(参考评价)' if is_reference else '场地实测数据(正式评价)'}",
        ],
        "explanation": f"SSUI(25项完整口径)={ssui}({grade})。"
                       f"B1安全性={round(b1,4)}, B2经济性={round(b2,4)}, f(t)={round(ft,3)}, M={M}。"
                       f"基于方法学25项元指标(D1-D25), 经济指标用{ref_version}参照区间归一化。"
                       + ("当前为参考评价(基于区域代理数据), 不作为场地正式结论。" if is_reference
                          else "当前为正式评价(基于场地实测经济数据)。"),
    }
