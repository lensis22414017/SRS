"""课题二 功能重构可行性评价 — 冻结方法基线 M-REC-2025 (SRS v1.2 年度验收版)。

唯一方法来源(逐表核对, 不使用推断出的替代规则):
  《(2025年)污染场地土壤生态-生产功能障碍识别与重构利用的评价方法+年度报告》
    表2.18 生产功能指标权重(26 项, Σ=0.9643)      → 全指标路径权重
    表2.19 生产功能指标权重(指标数据缺失, 10 项, Σ=1.0001) → 缺失数据路径(准则层)权重
    表2.20 生态功能指标权重(110 项, Σ=1.0058)     → 全指标路径权重
    表2.21 生态功能指标权重(指标数据缺失, 9 项, Σ=1.0063)  → 缺失数据路径权重
    表2.22 指标分等赋值表(F)                       → 每项指标的分等与赋分
    表2.23 评分对应等级(>50 可行, ≤50 不可行)
    §2.3.3 综合评价: 综合得分 = Σ(F_i × T_i); 测定指标缺失时, 土壤质量类和修复潜力类
           "参考综合指数法和内梅罗指数法 P = [(P平均² + P权重²)/2]^(1/2) 计算分值"。

与 v1.1 实现相比的更正(见 docs/annual/method_baseline_M-REC-2025.md):
  * 不再在"已测指标"内把全部权重重标化到 1; 全指标路径按表2.18/2.20 原值 Σ(F×T)。
  * 内梅罗公式只用于缺失数据路径中两个类别(土壤质量类/修复潜力类)的类别分值, 不再套在总分上。
  * 补齐表2.22 中 v1.1 缺失的分等赋值: 有效土层厚度、土壤容重(类别)、生物多样性、盐渍化程度、
    灌排能力、地下水埋深、表层土壤质地、光温生产潜力、C库变化因子、剖面构型、地形坡度(6 档)。
  * 删除 v1.1 中无方法依据的默认分: "剖面构型无实测默认70分""地形坡度默认60分",
    六六六/滴滴涕/苯并[a]芘"超限=10分"(GB 15618 无管制值, 方法规定此时仅按 50/100 赋分)。
  * 污染物按方法 3 档赋分(超管制值 10 / 超筛选值 50 / 未超筛选值 100), 生产轨道用 GB 15618-2018,
    生态轨道用 GB 36600-2018 第一类用地; 均取 data/standards 中经官方 PDF 核对的阈值。
  * 不做未登记的换算: 有机质≠有机碳、全氮≠水解性氮、总铬≠六价铬; 缺对应指标即"缺测"。

方法文件内的明显笔误按"同表规律"更正并显式登记(待陈亮/宋伟杰确认, 见 DEFERRED):
  * C库变化因子(耕地) ④温带/北温带潮湿 0.69 赋分 "690" → 69 (同表其余档 F = 因子 × 100)。
  * 生态 有效土层 ④100-150 cm 赋分 "00" → 90 (与生产轨道同档一致)。
"""
from __future__ import annotations

import math
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

METHOD_VERSION = "M-REC-2025 (frozen for SRS v1.2.0)"
METHOD_SOURCE = "（2025年）污染场地土壤生态-生产功能障碍识别与重构利用的评价方法+年度报告.docx 表2.18–2.23, §2.3.3"
FEASIBLE_THRESHOLD = 50.0

# ───────────────────────── 方法笔误更正登记(可追溯) ─────────────────────────
DEFERRED = [
    {"id": "M-01", "item": "C库变化因子(耕地) ④档赋分", "source_value": "690", "applied": "69",
     "basis": "表2.22 同行其余档 F = 因子×100 (48/58/64/—/80)", "status": "待确认"},
    {"id": "M-02", "item": "生态 有效土层 ④100-150 cm 赋分", "source_value": "00", "applied": "90",
     "basis": "生产轨道同档为 90; 生态行其余档与生产一致", "status": "待确认"},
    {"id": "M-03", "item": "表2.18 未给 土壤有机碳含量、剖面构型 的指标层权重", "source_value": "—",
     "applied": "全指标路径中两项只赋分展示、不计权; 缺失数据路径按表2.19 准则层权重计入",
     "basis": "表2.18 共 26 项, 表2.19 两项为单列准则", "status": "待确认"},
    {"id": "M-04", "item": "缺失数据路径中类别内 P权重 的权重口径", "source_value": "未规定",
     "applied": "取表2.18/2.20 指标层权重, 在该类已测指标内归一后加权", "basis": "§2.3.3 未给出类内权重",
     "status": "待确认"},
    {"id": "M-05", "item": "分级区间端点归属", "source_value": "表2.22 仅写 a-b",
     "applied": "下限含、上限不含([a,b)); 方法明确写'含'的(如 pH 6.5-7.5)按原文", "basis": "工程约定",
     "status": "待确认"},
    {"id": "M-06", "item": "旱地/水田 未注明时的肥力分档", "source_value": "表2.22 分旱地/水田",
     "applied": "两套分档都算, 取较低 F (保守), 并在结果中标注", "basis": "与 GB 15618 农用地类型未知时取严档的原则一致",
     "status": "待确认"},
    {"id": "M-07", "item": "表2.18 指标'六价铬' vs 子课题数据'Cr'(未注明形态)", "source_value": "六价铬",
     "applied": "生产轨道按 GB 15618 总铬阈值评分并标注; 生态轨道 GB 36600 仅有六价铬, 总铬不换算 → 无规则",
     "basis": "GB 15618 规定的是总铬", "status": "待确认"},
    {"id": "M-08", "item": "生态 剖面构型 无 '粘/砂/粘、通体粘、粘/砂/砂' 档; ④档文本 '壤/粘/' 不完整",
     "source_value": "表2.22", "applied": "该类构型生态轨道记为'无赋分规则'; '壤/粘/' 按 '壤/粘/粘' 读取",
     "basis": "原文缺档/截断", "status": "待确认"},
]

# ───────────────────────── 28 项重构指标 + 生态补充指标 ─────────────────────────
# kind: num / cat / pol(污染物, 由国标阈值赋分)
FEATURES: dict[str, dict] = {
    "cd": {"cn": "镉", "en": ["Cd", "cd_mgkg"], "unit": "mg/kg", "kind": "pol", "gb15618": "Cd", "gb36600": "Cd"},
    "hg": {"cn": "汞", "en": ["Hg", "hg_mgkg"], "unit": "mg/kg", "kind": "pol", "gb15618": "Hg", "gb36600": "Hg"},
    "as": {"cn": "砷", "en": ["As", "as_mgkg"], "unit": "mg/kg", "kind": "pol", "gb15618": "As", "gb36600": "As"},
    "pb": {"cn": "铅", "en": ["Pb", "pb_mgkg"], "unit": "mg/kg", "kind": "pol", "gb15618": "Pb", "gb36600": "Pb"},
    "cr": {"cn": "铬(总铬)", "en": ["Cr", "cr_mgkg", "总铬", "铬"], "unit": "mg/kg", "kind": "pol", "gb15618": "Cr",
           "gb36600": None, "eco_no_rule": "GB 36600 仅规定六价铬; 总铬不换算为六价铬"},
    "cr6": {"cn": "六价铬", "en": ["Cr(VI)", "铬(六价)", "铬（六价）", "cr6+", "铬 (VI)"], "unit": "mg/kg", "kind": "pol",
            "gb15618": None, "gb36600": "Cr(VI)", "prod_no_rule": "GB 15618 无六价铬项目; 生产轨道按总铬(Cr)评分"},
    "cu": {"cn": "铜", "en": ["Cu", "cu_mgkg"], "unit": "mg/kg", "kind": "pol", "gb15618": "Cu", "gb36600": "Cu"},
    "ni": {"cn": "镍", "en": ["Ni", "ni_mgkg"], "unit": "mg/kg", "kind": "pol", "gb15618": "Ni", "gb36600": "Ni"},
    "zn": {"cn": "锌", "en": ["Zn", "zn_mgkg"], "unit": "mg/kg", "kind": "pol", "gb15618": "Zn", "gb36600": None,
           "eco_no_rule": "GB 36600 表1/表2 无锌"},
    "bhc": {"cn": "六六六(总量)", "en": ["BHC", "HCH", "六六六", "六六六总量"], "unit": "mg/kg", "kind": "pol", "gb15618": "BHC",
            "gb36600": None, "eco_no_rule": "GB 36600 仅分别规定 α/β/γ-六六六, 无总量值"},
    "ddt": {"cn": "滴滴涕(总量)", "en": ["DDT", "滴滴涕", "滴滴涕总量"], "unit": "mg/kg", "kind": "pol", "gb15618": "DDT",
            "gb36600": None, "eco_no_rule": "GB 15618 '滴滴涕总量'(4 种衍生物)与 GB 36600 '滴滴涕'(2 种)定义不同, 不直接套用"},
    "bap": {"cn": "苯并[a]芘", "en": ["BAP", "BaP", "苯并[a]芘", "苯并 [a] 芘", "苯并芘"], "unit": "mg/kg", "kind": "pol",
            "gb15618": "BaP", "gb36600": "苯并[a]芘"},
    "soil_depth": {"cn": "有效土层厚度", "en": ["effective soil layer thickness", "有效土层", "有效土层厚度"], "unit": "cm", "kind": "num"},
    "ph": {"cn": "pH", "en": ["pH", "ph"], "unit": "无量纲", "kind": "num"},
    "bulk_density": {"cn": "土壤容重", "en": ["soil bulk density", "SoilBD_gcm3", "容重"], "unit": "类别(生产) / g/cm³(生态)", "kind": "cat_or_num"},
    "biodiversity": {"cn": "生物多样性", "en": ["biodiversity"], "unit": "类别", "kind": "cat"},
    "salinization": {"cn": "盐渍化程度", "en": ["salinization degree"], "unit": "类别", "kind": "cat"},
    "total_n": {"cn": "全氮", "en": ["total nitrogen", "TN_gkg", "TN"], "unit": "g/kg", "kind": "num"},
    "avail_p": {"cn": "有效磷", "en": ["available phosphorus", "AP"], "unit": "mg/kg", "kind": "num"},
    "avail_k": {"cn": "速效钾", "en": ["available potassium", "AK"], "unit": "mg/kg", "kind": "num"},
    "cec": {"cn": "阳离子交换量", "en": ["cation exchange capacity", "CEC_cmolkg", "CEC", "阳离子交换量（CEC）"], "unit": "cmol(+)/kg", "kind": "num"},
    "light_temp": {"cn": "光温生产潜力/气候生产潜力", "en": ["Light-temperature production potential", "光温/气候生产潜力指数", "光温生产潜力"], "unit": "指数", "kind": "num"},
    "slope": {"cn": "地形坡度", "en": ["terrain gradient", "坡度", "slope"], "unit": "°", "kind": "num"},
    "irrigation_drainage": {"cn": "灌排能力", "en": ["the capacity of irrigation and drainage", "灌排条件"], "unit": "类别", "kind": "cat"},
    "groundwater_depth": {"cn": "地下水埋深", "en": ["groundwater depth"], "unit": "m", "kind": "num"},
    "texture": {"cn": "耕地质地（表层土壤质地）", "en": ["surface soil texture", "表层土壤质地", "表土土壤质地", "土壤质地"], "unit": "类别", "kind": "cat"},
    "carbon_factor": {"cn": "C库变化因子（耕地）", "en": ["carbon pool variation factor(arable land)", "碳库变化因子（耕地）", "C库变化因子"], "unit": "类别/因子值", "kind": "cat"},
    "soc": {"cn": "土壤有机碳含量", "en": ["soil organic carbon content", "有机碳含量", "SOC"], "unit": "g/kg", "kind": "num"},
    "profile": {"cn": "剖面构型", "en": ["profile configuration"], "unit": "类别", "kind": "cat"},
    # —— 生态轨道表2.22 补充指标(子课题测试表未提供, 合成演示数据覆盖) ——
    "salt_content": {"cn": "含盐量", "en": ["salt content", "EC_mScm"], "unit": "g/kg", "kind": "num", "eco_only": True},
    "infiltration": {"cn": "土壤入渗率", "en": ["infiltration rate"], "unit": "mm/h", "kind": "num", "eco_only": True},
    "hydrolysable_n": {"cn": "水解性氮", "en": ["hydrolysable nitrogen"], "unit": "mg/kg", "kind": "num", "eco_only": True},
    "avail_s": {"cn": "有效硫", "en": ["available sulfur"], "unit": "mg/kg", "kind": "num", "eco_only": True},
    "avail_mg": {"cn": "有效镁", "en": ["available magnesium"], "unit": "mg/kg", "kind": "num", "eco_only": True},
    "avail_ca": {"cn": "有效钙", "en": ["available calcium"], "unit": "mg/kg", "kind": "num", "eco_only": True},
    "avail_fe": {"cn": "有效铁", "en": ["available iron"], "unit": "mg/kg", "kind": "num", "eco_only": True},
    "avail_mn": {"cn": "有效锰", "en": ["available manganese"], "unit": "mg/kg", "kind": "num", "eco_only": True},
    "avail_cu": {"cn": "有效铜", "en": ["available copper"], "unit": "mg/kg", "kind": "num", "eco_only": True},
    "avail_zn": {"cn": "有效锌", "en": ["available zinc"], "unit": "mg/kg", "kind": "num", "eco_only": True},
    "avail_mo": {"cn": "有效钼", "en": ["available molybdenum"], "unit": "mg/kg", "kind": "num", "eco_only": True},
    "soluble_cl": {"cn": "可溶性氯", "en": ["soluble chloride"], "unit": "mg/kg", "kind": "num", "eco_only": True},
}
RECON_28 = ["cd", "hg", "as", "pb", "cr", "cu", "ni", "zn", "bhc", "ddt", "bap", "soil_depth", "ph", "bulk_density",
            "biodiversity", "salinization", "total_n", "avail_p", "avail_k", "cec", "light_temp", "slope",
            "irrigation_drainage", "groundwater_depth", "texture", "carbon_factor", "soc", "profile"]

# ───────────────────────── 表2.22 类别 → 分级 ─────────────────────────
def _nc(s) -> str:
    s = str(s or "").strip().lower().replace("（", "(").replace("）", ")").replace("，", ",")
    s = re.sub(r"[\s\u00a0\t]+", " ", s)
    return s.replace(" ,", ",").replace("、 ", "、").strip()


CATEGORY_MAP: dict[str, dict[str, list[str]]] = {
    "bulk_density": {"适中": ["适中", "moderate", "适宜"], "偏轻": ["偏轻", "slightly light", "light", "偏松"],
                     "偏重": ["偏重", "heavy", "slightly heavy", "偏紧"]},
    "biodiversity": {"不丰富": ["不丰富", "not rich", "poor"], "一般": ["一般", "moderate", "medium"],
                     "丰富": ["丰富", "rich"]},
    "salinization": {"中度、重度": ["中度、重度", "moderate to severe", "中度-重度"],
                     "轻度、中度": ["轻度、中度", "mild to moderate", "轻度-中度"],
                     "无、轻度": ["无、轻度", "none to mild", "无-轻度"]},
    "irrigation_drainage": {"基本满足、不满足": ["基本满足、不满足", "basic satisfaction or dissatisfaction"],
                            "满足、基本满足": ["满足、基本满足", "satisfaction or basic satisfaction"],
                            "充分满足、满足": ["充分满足、满足", "fully satisfaction or satisfaction", "full satisfaction or satisfaction"]},
    "texture": {"砾质土": ["砾质土", "gravely soil", "gravelly soil", "砾质"], "砂土": ["砂土", "sandy soil", "sand", "沙土"],
                "粘土": ["粘土", "clay", "黏土"], "壤土": ["壤土", "loam"]},
    "carbon_factor": {"热带潮湿/湿": ["热带潮湿/湿", "tropical moist/wet", "tropical humid"],
                      "热带干燥": ["热带干燥", "tropical dry"], "热带山区": ["热带山区", "tropical montane"],
                      "温带/北温带潮湿": ["温带/北温带潮湿", "temperate/northern temperate humid areas", "temperate humid"],
                      "温带/北温带干燥": ["温带/北温带干燥", "temperate/northern temperate dry areas", "temperate dry"]},
}
CARBON_FACTOR_VALUE = {"热带潮湿/湿": 0.48, "热带干燥": 0.58, "热带山区": 0.64, "温带/北温带潮湿": 0.69, "温带/北温带干燥": 0.80}

# 剖面构型: 单个构型 → 标准写法
PROFILE_TYPES = {
    "通体砾": ["通体砾", "whole body gravel", "whole body gravelly"],
    "通体沙": ["通体沙", "通体砂", "whole body sandy", "whole body sand"],
    "粘/砂/粘": ["粘/砂/粘", "clay/sand/clay"], "通体粘": ["通体粘", "whole body clay"],
    "粘/砂/砂": ["粘/砂/砂", "clay/sand/sand"], "砂/粘/粘": ["砂/粘/粘", "sand/clay/clay"],
    "砂/粘/砂": ["砂/粘/砂", "sand/clay/sand"], "壤/粘/粘": ["壤/粘/粘", "loam/clay/clay", "壤/粘/"],
    "壤/砂/砂": ["壤/砂/砂", "loam/sand/sand"], "壤/粘/壤": ["壤/粘/壤", "loam/clay/loam"],
    "通体壤": ["通体壤", "whole body loam"], "壤/砂/壤": ["壤/砂/壤", "loam/sand/loam"],
}
PROFILE_SCORE = {
    "production": {"通体砾": 30, "通体沙": 40, "粘/砂/粘": 50, "通体粘": 50, "粘/砂/砂": 50, "砂/粘/粘": 60,
                   "砂/粘/砂": 70, "壤/粘/粘": 70, "壤/砂/砂": 70, "壤/粘/壤": 90, "通体壤": 100, "壤/砂/壤": 100},
    "ecology": {"通体砾": 30, "通体沙": 40, "砂/粘/粘": 50, "砂/粘/砂": 70, "壤/粘/粘": 70, "壤/砂/砂": 70,
                "壤/粘/壤": 90, "通体壤": 100, "壤/砂/壤": 100},
}

CAT_SCORE = {
    "production": {
        "bulk_density": {"适中": 100, "偏轻": 50, "偏重": 50},
        "biodiversity": {"不丰富": 50, "一般": 80, "丰富": 100},
        "salinization": {"中度、重度": 30, "轻度、中度": 60, "无、轻度": 100},
        "irrigation_drainage": {"基本满足、不满足": 20, "满足、基本满足": 50, "充分满足、满足": 100},
        "texture": {"砾质土": 40, "砂土": 70, "粘土": 90, "壤土": 100},
        "carbon_factor": {"热带潮湿/湿": 48, "热带干燥": 58, "热带山区": 64, "温带/北温带潮湿": 69, "温带/北温带干燥": 80},
    },
    "ecology": {
        "irrigation_drainage": {"基本满足、不满足": 20, "满足、基本满足": 50, "充分满足、满足": 100},
        "texture": {"砾质土": 40, "砂土": 70, "粘土": 90, "壤土": 100},
    },
}


def normalize_category(fid: str, raw):
    """类别原文 → (标准类别, 说明)。无法识别 → (None, 原因)。"""
    if raw is None:
        return None, "缺测"
    if fid == "profile":
        parts = [p for p in re.split(r"[、;；,，]+", _nc(raw)) if p]
        std = []
        for p in parts:
            hit = next((k for k, al in PROFILE_TYPES.items() if p in [_nc(a) for a in al]), None)
            if hit is None:
                return None, f"无法识别的剖面构型: {p}"
            std.append(hit)
        return ("、".join(std), None) if std else (None, "缺测")
    if fid == "carbon_factor" and isinstance(raw, (int, float)):
        for k, v in CARBON_FACTOR_VALUE.items():
            if abs(float(raw) - v) < 1e-9:
                return k, None
        return None, f"C库变化因子数值 {raw} 不在表2.22 档位中"
    t = _nc(raw)
    for k, al in CATEGORY_MAP.get(fid, {}).items():
        if t in [_nc(a) for a in al]:
            return k, None
    return None, f"无法识别的类别: {raw}"


# ───────────────────────── 表2.22 数值分档 ─────────────────────────
def _bins_lo_inclusive(v, edges, scores):
    """edges 升序 [e1..en], scores 长度 n+1: v<e1→s0, e1≤v<e2→s1, …, v≥en→sn。"""
    for e, s in zip(edges, scores):
        if v < e:
            return s
    return scores[-1]


def _ph_prod(v):
    """表2.22 生产 pH: ①≤5.0 或 ≥9.0:20 ②5.0–5.5 或 8.5–9.0:40 ③5.5–6.0 或 8.0–8.5:60
    ④6.0–6.5 或 7.5–8.0:80 ⑤6.5–7.5(含端点):100。酸侧下限含, 碱侧上限含(M-05)。"""
    if v <= 5.0 or v >= 9.0:
        return 20
    if 6.5 <= v <= 7.5:
        return 100
    if v < 6.5:
        return 40 if v < 5.5 else (60 if v < 6.0 else 80)
    return 80 if v <= 8.0 else (60 if v <= 8.5 else 40)


FERTILITY = {  # (dryland edges, paddy edges); 赋分 10/50/100; 端点: ≤a→10, (a,b]→50, >b→100 (原文"0-a""a-b"">b")
    "total_n": ((0.5, 1.0), (0.6, 1.2)),
    "avail_p": ((3.75, 7.5), (6.25, 12.5)),
    "avail_k": ((40, 80), (50, 100)),
    "cec": ((6, 12), (7.5, 15)),
}


def _fert(v, edges):
    a, b = edges
    return 10 if v <= a else (50 if v <= b else 100)


def score_numeric(fid: str, v: float, scope: str, land_subtype: str | None):
    """返回 (F, 分档说明, 假设列表)。F=None 表示该轨道无赋分规则。"""
    notes: list[str] = []
    if scope == "production":
        if fid == "ph":
            return _ph_prod(v), "表2.22 生产 pH 5 档", notes
        if fid in FERTILITY:
            dry, pad = FERTILITY[fid]
            if land_subtype == "旱地":
                return _fert(v, dry), "表2.22 旱地分档", notes
            if land_subtype == "水田":
                return _fert(v, pad), "表2.22 水田分档", notes
            f = min(_fert(v, dry), _fert(v, pad))
            notes.append("旱地/水田未注明: 取两套分档中较低 F (M-06)")
            return f, "表2.22 旱地/水田取低", notes
        if fid == "soil_depth":
            return _bins_lo_inclusive(v, [30, 60, 100, 150], [10, 50, 70, 90, 100]), "表2.22 有效土层厚度", notes
        if fid == "slope":
            # ≥25:10; 15-25:30; 8-15:60; 5-8:80; 2-5:90; <2:100
            return _bins_lo_inclusive(v, [2, 5, 8, 15, 25], [100, 90, 80, 60, 30, 10]), "表2.22 地形坡度", notes
        if fid == "groundwater_depth":
            return (30 if v < 2 else (70 if v <= 3 else 100)), "表2.22 地下水埋深", notes
        if fid == "light_temp":
            return _bins_lo_inclusive(v, [1000, 2000, 3000, 4000], [20, 40, 60, 80, 100]), "表2.22 光温/气候生产潜力", notes
        if fid == "soc":
            return _bins_lo_inclusive(v, [3.5, 5.8, 11.6, 17.4, 23.2], [20, 40, 60, 80, 90, 100]), "表2.22 土壤有机碳(g/kg)", notes
        if fid == "carbon_factor":
            cat, why = normalize_category("carbon_factor", v)
            return (CAT_SCORE["production"]["carbon_factor"].get(cat) if cat else None), (why or "表2.22 C库变化因子"), notes
        return None, "生产轨道表2.22 无该指标数值分档", notes
    # ecology
    band = {"hydrolysable_n": (40, 200), "avail_p": (5, 60), "avail_k": (60, 300), "avail_s": (20, 500),
            "avail_mg": (50, 280), "avail_ca": (200, 5000), "avail_fe": (4, 350), "avail_mn": (0.6, 25),
            "avail_cu": (0.3, 8), "avail_zn": (1, 10), "avail_mo": (0.04, 2), "soc": (11.6, 46.4)}
    if fid == "ph":
        notes.append("pH 测定方法未注明: 按 2.5:1 水土比法档(5.0–8.5)")
        return (100 if 5.0 <= v <= 8.5 else 50), "表2.22 生态 pH", notes
    if fid == "salt_content":
        notes.append("含盐量测定方法未注明: 按 5:1 水土比法档(0.15–0.9)")
        return (100 if 0.15 <= v <= 0.9 else 50), "表2.22 生态 含盐量", notes
    if fid in band:
        lo, hi = band[fid]
        if fid == "soc":
            notes.append("表2.22 生态有机碳单位写作 mg/kg, 按 g/kg 理解(与生产轨道一致, 待确认)")
        return (100 if lo <= v <= hi else 50), f"表2.22 生态 {lo}–{hi}", notes
    if fid == "cec":
        return (100 if v >= 10 else 50), "表2.22 生态 CEC≥10", notes
    if fid == "bulk_density":
        return (100 if v < 1.35 else 50), "表2.22 生态 容重<1.35 Mg/m³", notes
    if fid == "infiltration":
        return (100 if v >= 6 else 50), "表2.22 生态 入渗率≥6 mm/h", notes
    if fid == "soluble_cl":
        return (100 if v > 10 else 50), "表2.22 生态 可溶性氯(原文 ≤10→50, >10→100)", notes
    if fid == "soil_depth":
        notes.append("生态有效土层 ④档原文 '00', 按 90 计 (M-02)")
        return _bins_lo_inclusive(v, [30, 60, 100, 150], [10, 50, 70, 90, 100]), "表2.22 生态 有效土层", notes
    if fid == "slope":
        return _bins_lo_inclusive(v, [2, 5, 8, 15, 25], [100, 90, 80, 60, 40, 10]), "表2.22 生态 地形坡度", notes
    if fid == "groundwater_depth":
        return (30 if v < 2 else (70 if v <= 3 else 100)), "表2.22 生态 地下水埋深", notes
    return None, "生态轨道表2.22 无该指标", notes


def score_category(fid: str, raw, scope: str):
    cat, why = normalize_category(fid, raw)
    if cat is None:
        return None, None, why
    if fid == "profile":
        table = PROFILE_SCORE[scope]
        scores = [table.get(p) for p in cat.split("、")]
        if any(s is None for s in scores):
            return None, cat, f"{'生态' if scope == 'ecology' else '生产'}轨道表2.22 无该剖面构型档 (M-08)"
        if len(set(scores)) > 1:
            return None, cat, "类别组跨越多个分档, 无法唯一赋分"
        return scores[0], cat, None
    table = CAT_SCORE[scope].get(fid)
    if table is None:
        return None, cat, f"{'生态' if scope == 'ecology' else '生产'}轨道表2.22 无该类别指标的赋分规则"
    return table.get(cat), cat, None


# ───────────────────────── 污染物 3 档赋分 ─────────────────────────
def _standards():
    import utilization as U  # 同目录
    return U, U.load_standards()


def score_pollutant(fid: str, v: float, scope: str, ph: float | None, farmland: str | None,
                    eco_land_class: str = "第一类用地"):
    """方法: ①超管制值 10 ②超筛选值未超管制值 50 ③未超筛选值 100; 无管制值时仅按 50/100。"""
    U, std = _standards()
    spec = FEATURES[fid]
    notes: list[str] = []
    if scope == "production":
        f = spec["gb15618"]
        if not f:
            return None, spec.get("prod_no_rule", "无 GB 15618 阈值"), notes
        if f in ("BHC", "DDT", "BaP"):
            scr = std["gb15618"].get((f, "screening", "其他"), {})
            vals = [x["value"] for x in scr.values()]
            if not vals:
                return None, "无 GB 15618 阈值", notes
            s = min(vals)
            return (50 if v > s else 100), f"GB 15618 表2 筛选值 {s} (无管制值)", notes
        scr_pass, ctrl_fail, scr_max, ctrl_min, n2 = U._gb15618_limits(std, f, ph, farmland)
        notes += n2
        if scr_pass is None:
            return None, "无 GB 15618 阈值", notes
        if ctrl_min is not None and v > ctrl_min:
            if ctrl_fail is not None and v <= ctrl_fail:
                notes.append(f"pH 未知: {v} 介于管制值区间 ({ctrl_min}, {ctrl_fail}], 保守按超管制值计")
            return 10, f"超 GB 15618 管制值 {ctrl_min}", notes
        if v > scr_pass:
            return 50, f"超 GB 15618 筛选值 {scr_pass}" + (f" (未超管制值 {ctrl_min})" if ctrl_min else " (无管制值)"), notes
        return 100, f"未超 GB 15618 筛选值 {scr_pass}", notes
    f = spec.get("gb36600")
    if not f:
        return None, spec.get("eco_no_rule", "无 GB 36600 阈值"), notes
    rec = std["gb36600"].get((U._key(f), eco_land_class))
    if not rec or rec.get("screening") is None:
        return None, "无 GB 36600 阈值", notes
    s, c = rec["screening"], rec.get("control")
    if c is not None and v > c:
        return 10, f"超 GB 36600 {eco_land_class}管制值 {c}", notes
    if v > s:
        return 50, f"超 GB 36600 {eco_land_class}筛选值 {s}", notes
    return 100, f"未超 GB 36600 {eco_land_class}筛选值 {s}", notes


# ───────────────────────── 权重表(原值, 不归一) ─────────────────────────
T218 = {  # 表2.18 生产 指标层(26 项)
    "soil_depth": 0.0980, "ph": 0.0352, "bulk_density": 0.0725, "biodiversity": 0.0588, "salinization": 0.0644,
    "total_n": 0.0479, "avail_p": 0.0260, "avail_k": 0.0421, "cec": 0.0195, "hg": 0.1046, "as": 0.0751,
    "cd": 0.0361, "pb": 0.0223, "cr": 0.0284, "bap": 0.0304, "ddt": 0.0231, "bhc": 0.0454, "ni": 0.0219,
    "cu": 0.0112, "zn": 0.0065, "light_temp": 0.0305, "slope": 0.0134, "irrigation_drainage": 0.0102,
    "groundwater_depth": 0.0074, "texture": 0.0256, "carbon_factor": 0.0078,
}
T219 = {  # 表2.19 生产 指标数据缺失(准则层)
    "土壤质量类": 0.1526, "修复潜力类": 0.2894, "light_temp": 0.0842, "slope": 0.0757, "irrigation_drainage": 0.1119,
    "groundwater_depth": 0.0988, "texture": 0.0481, "carbon_factor": 0.0081, "soc": 0.0835, "profile": 0.0478,
}
T221 = {  # 表2.21 生态 指标数据缺失(准则层)
    "土壤质量类": 0.2497, "修复潜力类": 0.1939, "texture": 0.0567, "carbon_factor_grass": 0.0097,
    "irrigation_drainage": 0.1448, "soc": 0.0868, "slope": 0.0922, "profile": 0.0557, "groundwater_depth": 0.1168,
}
CLASS_MEMBERS = {
    "production": {
        "土壤质量类": ["soil_depth", "ph", "bulk_density", "biodiversity", "salinization", "total_n", "avail_p", "avail_k", "cec"],
        "修复潜力类": ["hg", "as", "cd", "pb", "cr", "bap", "ddt", "bhc", "ni", "cu", "zn"],
    },
    "ecology": {
        "土壤质量类": ["ph", "salt_content", "infiltration", "cec", "hydrolysable_n", "avail_p", "avail_k", "avail_s",
                     "avail_mg", "avail_ca", "avail_fe", "avail_mn", "avail_cu", "avail_zn", "avail_mo", "soluble_cl",
                     "bulk_density", "soil_depth"],
        "修复潜力类": ["as", "cd", "cr6", "cu", "pb", "hg", "ni", "bap"],  # 本数据结构内可映射到 GB 36600 的污染物
    },
}
# 表2.20 中与上述特征对应的指标层权重(用于缺失数据路径类内 P权重)
T220_FEATURE = {  # 表2.20 原值(由 docx 表格解析, 见 D09 weights_reconciliation)
    "ph": 0.0262, "salt_content": 0.0334, "infiltration": 0.037, "cec": 0.0257, "hydrolysable_n": 0.0289, "avail_p": 0.0433, "avail_k": 0.0236, "avail_s": 0.0275, "avail_mg": 0.0233, "avail_ca": 0.0237, "avail_fe": 0.0206, "avail_mn": 0.0215, "avail_cu": 0.018, "avail_zn": 0.0324, "avail_mo": 0.0283, "soluble_cl": 0.0344, "bulk_density": 0.0512, "soil_depth": 0.047, "as": 0.0053, "cd": 0.0082, "cr6": 0.0135, "cu": 0.0032, "pb": 0.0042, "hg": 0.0222, "ni": 0.0025, "bap": 0.0043,
}


def _nemerow(scored: list[tuple[str, float, float]]):
    """scored: [(fid, F, w)] → (P, P平均, P权重)。P权重 = ΣF·w/Σw (M-04)。"""
    p_avg = sum(f for _, f, _ in scored) / len(scored)
    tw = sum(w for _, _, w in scored)
    p_w = sum(f * w for _, f, w in scored) / tw if tw > 0 else p_avg
    return math.sqrt((p_avg ** 2 + p_w ** 2) / 2), p_avg, p_w


# ───────────────────────── 单指标评分(统一入口) ─────────────────────────
def score_indicator(fid: str, value, scope: str, ph=None, farmland=None, land_subtype=None,
                    eco_land_class="第一类用地"):
    """返回 dict(fid, F, status, rule, category, notes)。status: scored / missing / no_rule / invalid。"""
    spec = FEATURES[fid]
    base = {"fid": fid, "indicator": spec["cn"], "raw_value": value, "F": None, "category": None, "notes": []}
    if value is None or (isinstance(value, float) and math.isnan(value)) or (isinstance(value, str) and not value.strip()):
        return {**base, "status": "missing", "rule": "缺测"}
    if scope == "production" and spec.get("eco_only"):
        return {**base, "status": "no_rule", "rule": "仅生态轨道指标"}
    if spec["kind"] == "pol":
        try:
            v = float(value)
        except (TypeError, ValueError):
            return {**base, "status": "invalid", "rule": f"非数值: {value!r}"}
        f, rule, notes = score_pollutant(fid, v, scope, ph, farmland, eco_land_class)
        return {**base, "F": f, "status": "scored" if f is not None else "no_rule", "rule": rule, "notes": notes}
    is_num = isinstance(value, (int, float)) and not isinstance(value, bool)
    if spec["kind"] in ("cat",) or (spec["kind"] == "cat_or_num" and not is_num):
        if fid == "carbon_factor" and is_num:
            f, rule, notes = score_numeric(fid, float(value), scope, land_subtype)
            if scope == "ecology":
                return {**base, "status": "no_rule", "rule": "生态轨道使用 C库变化因子（草地）, 不使用耕地因子"}
            return {**base, "F": f, "status": "scored" if f is not None else "invalid", "rule": rule}
        if scope == "ecology" and fid in ("biodiversity", "salinization", "carbon_factor"):
            return {**base, "status": "no_rule", "rule": "生态轨道表2.22 无该指标"}
        if scope == "ecology" and fid == "bulk_density":
            return {**base, "status": "no_rule", "rule": "生态轨道容重按数值(≥1.35 Mg/m³)赋分, 类别值无规则"}
        f, cat, why = score_category(fid, value, scope)
        if f is None:
            st = "invalid" if (why or "").startswith("无法识别") else "no_rule"
            return {**base, "category": cat, "status": st, "rule": why}
        return {**base, "F": f, "category": cat, "status": "scored", "rule": f"表2.22 {cat}"}
    try:
        v = float(value)
    except (TypeError, ValueError):
        return {**base, "status": "invalid", "rule": f"非数值: {value!r}"}
    if not math.isfinite(v):
        return {**base, "status": "invalid", "rule": "非有限数值"}
    if scope == "production" and fid == "bulk_density":
        return {**base, "status": "no_rule", "rule": "生产轨道容重按类别(适中/偏轻/偏重)赋分, 数值无规则"}
    f, rule, notes = score_numeric(fid, v, scope, land_subtype)
    return {**base, "F": f, "status": "scored" if f is not None else "no_rule", "rule": rule, "notes": notes}


# ───────────────────────── 综合评价 ─────────────────────────
def evaluate(values: dict, scope: str, ph: float | None = None, farmland: str | None = None,
             land_subtype: str | None = None, eco_land_class: str = "第一类用地") -> dict:
    """values: {feature_id: 数值或类别文本}(场地代表值)。返回结构与 v1.1 reconstruction.evaluate 兼容。"""
    if scope not in ("production", "ecology"):
        raise ValueError(f"非法 scope: {scope}")
    if ph is None and isinstance(values.get("ph"), (int, float)):
        ph = float(values["ph"])
    fids = [f for f in FEATURES if not (scope == "production" and FEATURES[f].get("eco_only"))]
    items = {f: score_indicator(f, values.get(f), scope, ph, farmland, land_subtype, eco_land_class) for f in fids}
    if scope == "ecology":
        items["carbon_factor_grass"] = {"fid": "carbon_factor_grass", "indicator": "C库变化因子（草地）", "raw_value": None,
                                        "F": 100, "category": None, "status": "scored", "notes": [],
                                        "rule": "表2.22 生态 C库变化因子（草地）分等 '/' 赋分 100 (方法规定常数)"}
    scored = {f: it for f, it in items.items() if it["status"] == "scored"}
    trace: list[str] = [f"方法基线 {METHOD_VERSION}; 来源 {METHOD_SOURCE}"]
    dims, total, path, insufficient, missing_criteria = [], 0.0, None, False, []

    if scope == "production" and all(f in scored for f in T218):
        path = "full"
        wsum = sum(T218.values())
        for f, w in T218.items():
            c = scored[f]["F"] * w
            total += c
            dims.append({**_dim(scored[f]), "weight": w, "contribution": round(c, 4), "criterion": _crit(f, scope)})
        for f in ("soc", "profile"):
            if f in scored:
                dims.append({**_dim(scored[f]), "weight": 0.0, "contribution": 0.0, "criterion": "未计权(M-03)"})
        trace.append(f"全指标路径: 表2.18 的 26 项均已赋分; 综合得分 = Σ(F×T) (权重原值, Σ={wsum:.4f}, 不归一; 理论最高分 {wsum*100:.2f})")
    else:
        path = "missing_data"
        table = T219 if scope == "production" else T221
        trace.append(f"缺失数据路径: 按 {'表2.19' if scope == 'production' else '表2.21'} 准则层权重; 土壤质量类/修复潜力类用内梅罗指数计类别分")
        for crit, w in table.items():
            if crit in ("土壤质量类", "修复潜力类"):
                mem = CLASS_MEMBERS[scope][crit]
                ws = T218 if scope == "production" else T220_FEATURE
                sc = [(f, scored[f]["F"], ws.get(f, 0.0)) for f in mem if f in scored]
                if not sc:
                    insufficient = True
                    missing_criteria.append(crit)
                    trace.append(f"  {crit}: 无已赋分指标 → 证据不足")
                    continue
                p, p_avg, p_w = _nemerow(sc)
                total += p * w
                dims.append({"indicator": crit, "fid": crit, "F": round(p, 2), "raw_value": None, "category": None,
                             "rule": f"内梅罗 P=[(P平均²+P权重²)/2]^½, P平均={p_avg:.2f}, P权重={p_w:.2f}, n={len(sc)}",
                             "weight": w, "contribution": round(p * w, 4), "criterion": crit,
                             "members": [{**_dim(scored[f]), "weight_in_class": ws.get(f, 0.0)} for f, _, _ in sc]})
                trace.append(f"  {crit}: n={len(sc)}/{len(mem)}, P平均={p_avg:.2f}, P权重={p_w:.2f}, P={p:.2f}, ×{w}")
            else:
                if crit not in scored:
                    insufficient = True
                    missing_criteria.append(FEATURES.get(crit, {}).get("cn", crit) if crit in FEATURES else items.get(crit, {}).get("indicator", crit))
                    st = items.get(crit, {})
                    trace.append(f"  {st.get('indicator', crit)}: {st.get('status', 'missing')} ({st.get('rule', '')}) → 证据不足")
                    continue
                c = scored[crit]["F"] * w
                total += c
                dims.append({**_dim(scored[crit]), "weight": w, "contribution": round(c, 4), "criterion": "单项准则"})
                trace.append(f"  {scored[crit]['indicator']}: F={scored[crit]['F']} ×{w}")

    covered = [f for f in RECON_28 if f in scored]
    not_scored = {f: {"indicator": it["indicator"], "status": it["status"], "rule": it["rule"]}
                  for f, it in items.items() if it["status"] != "scored" and f in RECON_28}
    assumptions = sorted({n for it in items.values() for n in it.get("notes", [])})
    coverage = len(covered) / len(RECON_28)
    track = "生产" if scope == "production" else "生态"
    if insufficient:
        return {"scope": scope, "score": None, "grade": "证据不足/无法评价", "path": path,
                "method_version": METHOD_VERSION, "dimensions": dims, "weights": {},
                "limiting_factors": [], "missing_indicators": missing_criteria, "not_scored": not_scored,
                "calculation_trace": trace, "assumptions": assumptions, "coverage_rate": coverage,
                "coverage_gate": None, "is_insufficient": True, "items": items,
                "explanation": (f"{track}功能重构可行性: 方法要求的准则 {', '.join(missing_criteria)} 无可赋分数据, "
                                f"按冻结方法无法计算综合得分(不以默认值补齐)。已赋分 28 项指标中的 {len(covered)} 项。")}
    score = round(total, 2)
    grade = "可行" if score > FEASIBLE_THRESHOLD else "不可行"
    limiting = sorted([d for d in dims if d.get("F") is not None and d["F"] <= 60], key=lambda d: d["F"])
    trace.append(f"综合得分 {score} {'>' if score > 50 else '≤'} 50 → {grade} (表2.23)")
    return {"scope": scope, "score": score, "grade": grade, "path": path, "method_version": METHOD_VERSION,
            "dimensions": dims, "weights": {d["indicator"]: d["weight"] for d in dims},
            "limiting_factors": [d["indicator"] for d in limiting], "missing_indicators": [],
            "not_scored": not_scored, "calculation_trace": trace, "assumptions": assumptions,
            "coverage_rate": coverage, "coverage_gate": None, "is_insufficient": False, "items": items,
            "explanation": (f"{track}功能重构可行性(方法 {METHOD_VERSION}, {'全指标' if path == 'full' else '缺失数据'}路径): "
                            f"综合得分 {score} → {grade}。F≤60 的限制性指标: "
                            f"{', '.join(d['indicator'] for d in limiting) or '无'}。"
                            "评分不能替代法规安全门禁; 利用方向结论见利用决策。")}


def _dim(it):
    return {"indicator": it["indicator"], "fid": it["fid"], "F": it["F"], "raw_value": it.get("raw_value"),
            "category": it.get("category"), "rule": it.get("rule")}


def _crit(fid, scope):
    for c, mem in CLASS_MEMBERS[scope].items():
        if fid in mem:
            return c
    return "单项准则"


# ───────────────────────── 点位 → 场地代表值 (§2.3.2.1) ─────────────────────────
def site_representative(points: list[dict]) -> tuple[dict, dict]:
    """数值指标取中位数(§2.3.2.1: 分布未检验时用中位值), 类别指标取众数(并列取得分较低者由调用方审阅)。

    返回 (values, meta)。meta[fid] = {n, method, distinct}。
    """
    vals, meta = {}, {}
    for fid in FEATURES:
        xs = [p.get(fid) for p in points if p.get(fid) is not None and not (isinstance(p.get(fid), str) and not p.get(fid).strip())]
        if not xs:
            continue
        nums = [x for x in xs if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))]
        if len(nums) == len(xs):
            vals[fid] = float(statistics.median(nums))
            meta[fid] = {"n": len(nums), "method": "median", "min": min(nums), "max": max(nums)}
        else:
            cnt: dict = {}
            for x in xs:
                cnt[str(x)] = cnt.get(str(x), 0) + 1
            top = max(cnt.values())
            modes = sorted(k for k, c in cnt.items() if c == top)
            vals[fid] = modes[0]
            meta[fid] = {"n": len(xs), "method": "mode", "distinct": cnt, "tie": len(modes) > 1}
    return vals, meta


# ───────────────────────── 别名 → 特征 id ─────────────────────────
_ALIAS: dict[str, str] = {}
for _fid, _sp in FEATURES.items():
    for _a in [_sp["cn"], *_sp["en"]]:
        _ALIAS[_nc(_a)] = _fid
_ALIAS.update({_nc("有机质"): "__om__"})


def feature_id(header: str) -> str | None:
    """表头/因子名 → 特征 id。有机质返回特殊标记(不与有机碳等同, 不换算)。"""
    h = _nc(header)
    h = re.sub(r"\((mg/kg|g/kg|cm|m|°|cmol\(\+\)/kg|cmol/kg|mm/h|无量纲|类别|指数|类别/因子值|"
               r"类别\(生产\) / g/cm³\(生态\)|g/cm³|mg/l)\)$", "", h).strip()
    if h in _ALIAS:
        return _ALIAS[h]
    for part in re.split(r"[_]", h):  # 甲方表头 "镉_Cd"
        if part.strip() in _ALIAS:
            return _ALIAS[part.strip()]
    return None
