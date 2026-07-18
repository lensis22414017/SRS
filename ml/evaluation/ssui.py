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
    """场内 Min-Max 归一化(注: 方法学要求跨场地锚点, MVP 用场内)。"""
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    if hi == lo:
        norm = [0.5] * len(vals)
    else:
        norm = [(v - lo) / (hi - lo) for v in vals]
        if negative:
            norm = [1 - x for x in norm]
    return sum(norm) / len(norm)


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
    # D18-D25 经济性指标(本系统通常无数据)
    "D18_劳动力成本": [],
    "D19_机械化成本": [],
    "D20_土地成本": [],
    "D21_非机械化成本": [],
    "D22_土地生产率": [],
    "D23_效益费用比": [],
    "D24_人均可支配收入": [],
    "D25_土地产出系数": [],
}

NEGATIVE_METAS = {"D1_土壤含盐量", "D16_重金属污染物", "D17_有机污染物"}


def evaluate(series: dict, scope: str = "production", t: float = 2.0,
             intensity: str = "medium") -> dict:
    """v1.0.2: SSUI 完整 25 项评价。

    series: {factor_code: [跨采样点数值]}。
    scope: production/ecology。
    t: 评价期跨度(年), 前端让用户选择(GPT 6.5)。
    intensity: 管理强度 low/medium/high。

    GPT 6.4: 风险/经济数据缺失 → SSUI=N/A, 不用总分回填。
    """
    params = _load()
    scope_key = "production" if scope == "production" else "ecology"
    meta_w = params[scope_key].get("meta_weights_25", {})

    # 按准则层分组计算
    groups = {"限制因子C1": [], "风险因子C2": [], "经济成本C3": [], "经济效益C4": []}

    for d_code, factor_list in D_TO_FACTORS.items():
        w_info = meta_w.get(d_code)
        if not w_info:
            continue
        criterion = w_info.get("criterion", "")
        weight = w_info.get("weight", 0)

        # 找可得因子数据
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
            # 未测
            groups[criterion].append((d_code, None, weight, "missing"))

    # v1.0.2(GPT 6.4): 风险/经济数据缺失检查
    c2_measured = [g for g in groups["风险因子C2"] if g[3] == "measured"]
    c3_measured = [g for g in groups["经济成本C3"] if g[3] == "measured"]
    c4_measured = [g for g in groups["经济效益C4"] if g[3] == "measured"]

    # 如果风险因子或经济效益完全无数据 → SSUI=N/A(GPT 6.4)
    has_risk_data = len(c2_measured) > 0
    has_economic_data = len(c3_measured) > 0 or len(c4_measured) > 0

    if not has_risk_data or not has_economic_data:
        missing_dims = []
        if not has_risk_data:
            missing_dims.append("风险因子C2")
        if not has_economic_data:
            missing_dims.append("经济成本C3/经济效益C4")
        return {
            "scope": scope, "ssui": None, "grade": "N/A(数据不足)",
            "dimensions": {k: [g for g in v if g[3] == "measured"] for k, v in groups.items()},
            "explanation": f"SSUI=N/A。缺失维度: {', '.join(missing_dims)}。"
                           f"方法学要求安全性(含风险因子)+经济性双重数据, "
                           f"当前场地缺{'风险' if not has_risk_data else ''}"
                           f"{'+' if not has_risk_data and not has_economic_data else ''}"
                           f"{'经济' if not has_economic_data else ''}数据, "
                           f"无法计算完整 SSUI(25项指标)。建议补充缺失维度数据。",
            "calculation_trace": [
                f"① 25项元指标数据覆盖检查:",
                f"  限制因子C1: {len([g for g in groups['限制因子C1'] if g[3]=='measured'])} 项已测",
                f"  风险因子C2: {len(c2_measured)} 项已测",
                f"  经济成本C3: {len(c3_measured)} 项已测",
                f"  经济效益C4: {len(c4_measured)} 项已测",
                f"② 缺失维度: {', '.join(missing_dims)} → SSUI=N/A(GPT 6.4)",
            ],
            "is_na": True,
            "missing_dimensions": missing_dims,
            "d_coverage": {
                "C1": len([g for g in groups["限制因子C1"] if g[3] == "measured"]),
                "C2": len(c2_measured),
                "C3": len(c3_measured),
                "C4": len(c4_measured),
            },
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
    grade = _grade(ssui, params)

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
        },
        "weights": cw,
        "is_na": False,
        "calculation_trace": [
            f"① 25项元指标按4个准则层分组计算(限制因子/风险因子/经济成本/经济效益)",
            f"② 各准则层组内加权(MVP场内Min-Max归一化): SC1={round(sc.get('限制因子C1',0),4)}, SC2={round(sc.get('风险因子C2',0),4)}, "
            f"SC3={round(sc.get('经济成本C3',0),4)}, SC4={round(sc.get('经济效益C4',0),4)}",
            f"③ B1安全性={round(b1,4)}, B2经济性={round(b2,4)}",
            f"④ f(t)=1+0.03×{t}={round(ft,3)}, M={M}",
            f"⑤ SSUI=(B1×0.5+B2×0.5)×f(t)×M={round(raw_ssui,4)}→min(,1.0)={ssui}",
            f"⑥ 等级: {grade}",
            f"⑦ 口径说明: MVP用场内Min-Max归一化, 准则层权重来自方法学; "
            f"跨场地锚点/PCA降维/博弈论赋权需多场地数据(后续版本)",
        ],
        "explanation": f"SSUI(25项完整口径,MVP场内归一化)={ssui}({grade})。"
                       f"B1安全性={round(b1,4)}, B2经济性={round(b2,4)}, f(t)={round(ft,3)}, M={M}。"
                       f"基于方法学25项元指标(D1-D25)。"
                       f"当前为MVP口径(场内Min-Max), 跨场地可比性待后续版本。",
    }
