"""factor_normalizer.py — 因子名称规范化、单位转换、冲突检测（P0-1 修复）

替代 kos_service.py 中的子串匹配 normalize_factors，改为：
1. Unicode NFKC + strip + 大小写归一 + 全半角括号统一
2. 从 factor_aliases_v0.8.yaml 加载别名表，精确匹配（非子串）
3. 区分总铬 Cr_mgkg 与六价铬 Cr6_mgkg
4. 单位转换 μg/kg/ng/g → mg/kg
5. 同一 canonical 因子多来源列冲突 → mapping_conflicts（不静默覆盖）
"""
from __future__ import annotations
import sys

import os
import re
import unicodedata
import math
from typing import Any

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# PyInstaller 打包后数据在 _MEIPASS 或其 _internal 子目录
if getattr(sys, "frozen", False):
    _mep = sys._MEIPASS
    if os.path.isdir(os.path.join(_mep, "ml")) or os.path.isdir(os.path.join(_mep, "data")):
        _ROOT = _mep
    elif os.path.isdir(os.path.join(_mep, "_internal", "ml")):
        _ROOT = os.path.join(_mep, "_internal")
_ALIASES_PATH = os.path.join(_ROOT, "data", "knowledge", "factor_aliases_v0.8.yaml")
_UNIT_RULES_PATH = os.path.join(_ROOT, "data", "knowledge", "unit_conversion_rules_v0.8.yaml")

# 单位转换因子 → 目标统一为 mg/kg（重金属）或原单位（pH/养分）
_UNIT_CONVERSION = {
    # 从 → (转换系数, 目标单位)
    "μg/kg": (0.001, "mg/kg"),
    "ug/kg": (0.001, "mg/kg"),
    "ng/g": (0.001, "mg/kg"),
    "mg/kg": (1.0, "mg/kg"),
    "mg·kg": (1.0, "mg/kg"),
}


def _norm_key(s: str) -> str:
    """名称归一化: NFKC + strip + 小写 + 全角→半角括号 + 去空格 + 去单位后缀。"""
    if s is None:
        return ""
    # Unicode NFKC: 全角→半角, 兼容性分解
    s = unicodedata.normalize("NFKC", str(s))
    s = s.strip()
    # 小写（英文字母）
    s = s.lower()
    # 去除所有空格（"Cd (mg/kg)" → "cd(mg/kg)"）
    s = re.sub(r"\s+", "", s)
    return s


def _norm_key_aggressive(s: str) -> str:
    """更激进归一化: 去除 _-/(等分隔符, 用于组合名 fallback。

    "镉_cd" → "镉cd" → 匹配时拆成 "镉" 和 "cd" 分别查
    """
    s = _norm_key(s)
    # 去除分隔符: _ - / （）
    s = re.sub(r"[_\-/（）()]", "", s)
    return s


def _lookup_canonical(raw_name: str) -> str | None:
    """四级查找: 精确 → 去单位精确 → 组合名拆分 → 关键词模糊匹配。

    精确匹配优先（禁止子串匹配），组合名如"镉_Cd"按分隔符拆分后逐段查。
    v1.0.1: L1/L2/L3 失败后加 L4 关键词模糊匹配(含"镉/Cd"→Cd_mgkg)。
    """
    if not raw_name:
        return None

    # 第1级: 去单位后的精确匹配
    _, factor_name, _ = _extract_unit(raw_name)
    k = _norm_key(factor_name)
    if k in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[k]

    # 第2级: 原名(含单位)NFKC 精确匹配
    k2 = _norm_key(raw_name)
    if k2 in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[k2]

    # 第3级: 组合名拆分（"镉_Cd" → ["镉", "Cd"] 逐段查）
    # 只在分隔符拆分后,每段都做精确匹配(不做子串)
    parts = re.split(r"[_\-/（）()]", factor_name)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) > 1:
        for p in parts:
            pk = _norm_key(p)
            if pk in _ALIAS_TO_CANONICAL:
                return _ALIAS_TO_CANONICAL[pk]

    # 第4级: 关键词模糊匹配(含"镉/Cd"→Cd_mgkg, 启发式兜底)
    # 覆盖训练数据未见过但命名含标准关键词的因子(如"镉含量"/"Cd浓度")
    fuzzy = _fuzzy_keyword_match(factor_name)
    if fuzzy:
        return fuzzy

    return None


def _load_aliases() -> dict[str, dict]:
    """加载 factor_aliases_v0.8.yaml，返回 {canonical: {aliases: [...], ...}}。"""
    if not os.path.isfile(_ALIASES_PATH):
        return {}
    with open(_ALIASES_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


_ALIASES = _load_aliases()

# 构建 反向查找表: {规范化别名 → canonical}
# 精确匹配，不做子串
_ALIAS_TO_CANONICAL: dict[str, str] = {}
if _ALIASES:
    for canonical, info in _ALIASES.items():
        _ALIAS_TO_CANONICAL[_norm_key(canonical)] = canonical
        for alias in (info.get("aliases") or []):
            _ALIAS_TO_CANONICAL[_norm_key(alias)] = canonical
        for co in (info.get("coalesce") or []):
            _ALIAS_TO_CANONICAL[_norm_key(co)] = canonical

# 补充 Cr6 的精确匹配（确保 Cr 不误配 Cr(VI)）
# factor_aliases 已有 Cr6_mgkg → 六价铬/Cr(VI)/Cr6+，这里只是确保优先级

# ── v1.0.1 L4 关键词模糊匹配兜底 ─────────────────────────────
# 当 L1/L2/L3 精确匹配都失败时, 用关键词扫描匹配 canonical code
# 覆盖训练数据未见过但命名含标准关键词的因子(如"镉含量"/"Cd浓度"/"铜指标")
# 参考: C:\Users\曾鸿\Desktop\000\0_背景资料\整合报告.txt (122 种障碍因子清单)
# 设计原则: 中文字符关键词直接匹配; 英文单字母/双字母需带边界(括号/下划线/中文后缀)
_KEYWORD_TO_CANONICAL: dict[str, str] = {
    # ── 重金属中文关键词(直接匹配, 无歧义) ──
    "镉": "Cd_mgkg", "铅": "Pb_mgkg", "砷": "As_mgkg", "铜": "Cu_mgkg",
    "锌": "Zn_mgkg", "汞": "Hg_mgkg", "镍": "Ni_mgkg", "锰": "Mn_mgkg",
    "钴": "Co_mgkg", "钼": "Mo_mgkg", "锑": "Sb_mgkg", "铊": "Tl_mgkg",
    "铍": "Be_mgkg", "钡": "Ba_mgkg", "钒": "V_mgkg",
    # ── 理化性质 ──
    "阳离子交换": "CEC_cmolkg", "阳离子交换量": "CEC_cmolkg",
    "电导率": "EC_mScm",
    "有机碳": "OC_pct", "有机质": "OC_pct",
    # v0.8.1 拆分化学形态: 全氮=总量 TN_gkg; 水解性氮/碱解氮=速效 Hydrolyzable_N_mgkg
    "全氮": "TN_gkg", "总氮": "TN_gkg",
    "水解性氮": "Hydrolyzable_N_mgkg", "碱解氮": "Hydrolyzable_N_mgkg", "速效氮": "Hydrolyzable_N_mgkg",
    # v0.8.1 拆分: 全磷=总量 Total_P_gkg; 有效磷/速效磷=速效 P_mgkg
    "全磷": "Total_P_gkg", "总磷": "Total_P_gkg",
    "有效磷": "P_mgkg", "速效磷": "P_mgkg",
    # v0.8.1 拆分: 全钾=总量 Total_K_gkg; 速效钾/有效钾=速效 K_mgkg
    "全钾": "Total_K_gkg", "总钾": "Total_K_gkg",
    "速效钾": "K_mgkg", "有效钾": "K_mgkg", "缓效钾": "K_mgkg",
    "容重": "SoilBD_gcm3", "土壤容重": "SoilBD_gcm3",
    "质地": "Clay_pct", "粘粒": "Clay_pct", "黏粒": "Clay_pct",
    "砂粒": "Sand_pct", "粉粒": "Silt_pct",
    "坡度": "Slope_pct", "海拔": "Elevation_m",
    "全铁": "Fe_mgkg", "铁": "Fe_mgkg",
    # ── v0.8.1 PAH 单体（对齐 SHAP group 名：中文裸名）──
    "萘": "萘", "䓛": "䓛", "菲": "菲", "芴": "芴", "蒽": "蒽", "芘": "芘",
    "苯并[a]蒽": "苯并[a]蒽", "苯并(a)蒽": "苯并[a]蒽",
    "苯并芘": "BaP_ngg", "苯并[a]芘": "BaP_ngg", "苯并(a)芘": "BaP_ngg",
    "苯并[b]荧蒽": "苯并[b]荧蒽", "苯并[k]荧蒽": "苯并[k]荧蒽",
    "茚并": "茚并[1,2,3-cd]芘",
    "二苯并": "二苯并[a,h]蒽",
    "二苯并[a,h]蒽": "二苯并[a,h]蒽", "二苯并[ah]蒽": "二苯并[ah]蒽",
    # ── v0.8.1 有机汇总（对齐 SHAP group 名）──
    "多环芳烃": "PAHs_total(族群)", "PAHs": "PAHs_total(族群)",
    "高分子量PAH": "HMWPAH_ngg", "高分子量多环芳烃": "HMWPAH_ngg",
    "低分子量PAH": "LMWPAH_ngg", "低分子量多环芳烃": "LMWPAH_ngg",
    # ── OCP 有机氯农药（v0.8.1 统一到 SHAP group）──
    "六六六": "SumHCHs_ngg", "滴滴涕": "SumDDTs_ngg",
    "有机氯": "SumOCP_ngg", "有机氯农药": "SumOCP_ngg",
    "氯丹": "SumOCP_ngg", "七氯": "SumOCP_ngg",
    "毒杀芬": "SumOCP_ngg", "灭蚁灵": "SumOCP_ngg", "硫丹": "SumOCP_ngg",
    # ── v0.8.1 PCB（注意: 删"联苯"关键词避免 PBDE 误配）──
    "多氯联苯": "SumPCB_ngg",
    # ── PFAS ──
    "全氟": "SumPFAS_ngg", "全氟辛酸": "SumPFAS_ngg", "全氟辛烷": "SumPFAS_ngg",
    # ── PAE ──
    "邻苯二甲酸": "SumPAE_ugkg", "塑化剂": "SumPAE_ugkg",
    # ── TPH ──
    "石油烃": "TPH_ngg", "矿物油": "TPH_ngg", "总石油": "TPH_ngg",
    # ── PBDE ──
    "多溴联苯醚": "SumPBDE_ngg",
    # ── BTEX 苯系物 ──
    "苯乙烯": "BTEX_Styrene", "甲苯": "BTEX_Toluene",
    "乙苯": "BTEX_Ethylbenzene", "二甲苯": "BTEX_Xylene",
    # ── 酚类 ──
    "五氯酚": "Phenol_Pentachlorophenol", "硝基酚": "Phenol_Nitrophenol",
    "氯酚": "Phenol_Chlorophenol", "二氯酚": "Phenol_Dichlorophenol",
    # ── 氯代烃 ──
    "三氯乙烯": "VOC_Trichloroethylene", "四氯乙烯": "VOC_Tetrachloroethylene",
    "四氯化碳": "VOC_CarbonTetrachloride", "氯仿": "VOC_Chloroform",
    "氯甲烷": "VOC_Chloromethane", "氯乙烯": "VOC_VinylChloride",
    "二氯甲烷": "VOC_Dichloromethane", "二氯乙烷": "VOC_Dichloroethane",
    "二氯苯": "VOC_Dichlorobenzene", "氯苯": "VOC_Chlorobenzene",
    # ── 其他有机物 ──
    "苯胺": "Aniline", "硝基苯": "Nitrobenzene",
    "阿特拉津": "Atrazine", "莠去津": "Atrazine",
    "二噁英": "Dioxin", "氰化物": "Cyanide",
    # 英文全名(无歧义, 直接匹配)
    "cadmium": "Cd_mgkg", "lead": "Pb_mgkg", "arsenic": "As_mgkg", "copper": "Cu_mgkg",
    "zinc": "Zn_mgkg", "mercury": "Hg_mgkg", "nickel": "Ni_mgkg", "manganese": "Mn_mgkg",
    "cobalt": "Co_mgkg", "molybdenum": "Mo_mgkg", "antimony": "Sb_mgkg", "thallium": "Tl_mgkg",
    "beryllium": "Be_mgkg", "barium": "Ba_mgkg", "vanadium": "V_mgkg",
}

# 英文符号 → canonical 的映射(需用正则边界匹配, 避免子串误配)
# 如 "Cd浓度" 命中 cd, 但 "record" 中的 cd 不命中(因后跟 e 非中文/数字/边界符)
_SYMBOL_PATTERNS: list[tuple[str, str]] = [
    (r"cd(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Cd_mgkg"),
    (r"pb(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Pb_mgkg"),
    (r"as(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "As_mgkg"),
    (r"cu(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Cu_mgkg"),
    (r"zn(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Zn_mgkg"),
    (r"hg(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Hg_mgkg"),
    (r"ni(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Ni_mgkg"),
    (r"mn(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Mn_mgkg"),
    (r"\bco(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Co_mgkg"),
    (r"\bmo(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Mo_mgkg"),
    (r"\bsb(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Sb_mgkg"),
    (r"\btl(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Tl_mgkg"),
    (r"\bbe(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Be_mgkg"),
    (r"\bba(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "Ba_mgkg"),
    (r"\bv(?=[\s（(＿_含量浓度指标值检测水平测定分析总量\d]|$)", "V_mgkg"),
    # 有机物英文缩写
    (r"\bpah\b", "PAH_total"), (r"\bpfos\b", "PFAS_PFOS"), (r"\bpfoa\b", "PFAS_PFOA"),
    (r"\bpfas\b", "PFAS_total"), (r"\btph\b", "TPH_C10C40"),
    (r"\bpcb\b", "PCB_total"), (r"\bddt\b", "OCP_DDT"), (r"\bhch\b", "OCP_HCH"),
    # 注意: "铬"/"Cr"/"cr" 不在表内(需区分总铬vs六价铬), 依赖 L1/L2/L3 精确匹配
]

# 形态冲突检查(总铬vs六价铬等) — 匹配时排除冲突关键词
_FORM_CONFLICT_KEYWORDS = ["六价", "cr6", "cr(vi)", "crvi", "有效态", "水溶态", "交换态"]


def _fuzzy_keyword_match(factor_name: str) -> str | None:
    """L4 关键词模糊匹配: 对 factor_name 做关键词扫描, 命中→返回 canonical code。

    规则:
    1. 先做形态冲突检查(含"六价"/"cr6"/"有效态"等→不匹配, 避免误配)
    2. 中文关键词直接匹配(无歧义)
    3. 英文符号用正则前瞻边界匹配(后跟中文后缀/数字/括号/下划线/行尾)
       避免把"cd"误匹配到"record"等无关词
    """
    if not factor_name:
        return None
    s = factor_name.lower().strip()

    # 形态冲突检查
    for ck in _FORM_CONFLICT_KEYWORDS:
        if ck in s:
            return None

    # 中文关键词扫描(直接包含匹配, 按关键词长度降序优先匹配长词避免短词误配)
    for keyword in sorted(_KEYWORD_TO_CANONICAL.keys(), key=len, reverse=True):
        if keyword in s:
            return _KEYWORD_TO_CANONICAL[keyword]

    # 英文符号正则边界匹配
    for pattern, canonical in _SYMBOL_PATTERNS:
        if re.search(pattern, s):
            return canonical

    return None


# ── v0.8.1 单位分类 ─────────────────────────────
# unit_category 用于区分"原单位使用"（不报单位不明）与"需要转换"（mg/kg ↔ ng/g ↔ μg/kg）
_UNIT_CATEGORY_MAP: dict[str, str] = {
    # 质量浓度（需要互相转换）
    "mg/kg": "concentration_mgkg", "mgkg": "concentration_mgkg",
    "mg·kg": "concentration_mgkg", "mg·kg⁻¹": "concentration_mgkg",
    "μg/kg": "concentration_ugkg", "ug/kg": "concentration_ugkg",
    "ng/g": "concentration_ngg", "ngg": "concentration_ngg",
    # 养分（原单位使用）
    "g/kg": "native_g_kg", "g·kg⁻¹": "native_g_kg",
    # 容重/密度（原单位使用）
    "g/cm³": "native_density", "g·cm⁻³": "native_density", "g/cm3": "native_density",
    # CEC（原单位使用）
    "cmol/kg": "native_cmol", "cmol·kg⁻¹": "native_cmol",
    "cmol(+)/kg": "native_cmol", "cmolkg": "native_cmol",
    # 电导率（原单位使用）
    "ms/cm": "native_ec", "mscm": "native_ec",
    "ds/m": "native_ec", "μs/cm": "native_ec",
    # 百分比（原单位使用）
    "%": "native_percent", "％": "native_percent",
    # 长度/角度（原单位使用）
    "m": "native_length", "mm": "native_length", "度": "native_slope",
}

# 单位标准规范名
_UNIT_NORMALIZE: dict[str, str] = {
    "mgkg": "mg/kg", "mg·kg": "mg/kg", "mg·kg⁻¹": "mg/kg",
    "μg/kg": "μg/kg", "ug/kg": "μg/kg",
    "ng/g": "ng/g", "ngg": "ng/g",
    "g/kg": "g/kg", "g·kg⁻¹": "g/kg",
    "g/cm³": "g/cm³", "g·cm⁻³": "g/cm³", "g/cm3": "g/cm³",
    "cmol/kg": "cmol(+)/kg", "cmol·kg⁻¹": "cmol(+)/kg",
    "cmol(+)/kg": "cmol(+)/kg", "cmolkg": "cmol(+)/kg",
    "ms/cm": "mS/cm", "mscm": "mS/cm",
    "ds/m": "dS/m", "μs/cm": "μS/cm",
    "%": "%", "％": "%",
    "m": "m", "mm": "mm", "度": "度",
}

# preferred_unit 到 unit_category 的映射
_PREFERRED_UNIT_TO_CATEGORY: dict[str, str] = {
    "mg/kg": "concentration_mgkg",
    "μg/kg": "concentration_ugkg",
    "ng/g": "concentration_ngg",
    "g/kg": "native_g_kg",
    "g/cm³": "native_density",
    "cmol(+)/kg": "native_cmol",
    "mS/cm": "native_ec", "dS/m": "native_ec", "μS/cm": "native_ec",
    "%": "native_percent",
    "m": "native_length", "mm": "native_length", "度": "native_slope",
    "1": "dimensionless",
}

# unit_category 间的转换因子（μg/kg 等价于 0.001 mg/kg, 即与 ng/g 同数量级）
_CONVERSION_MATRIX: dict[tuple[str, str], float] = {
    ("concentration_mgkg", "concentration_ngg"): 1000.0,
    ("concentration_mgkg", "concentration_ugkg"): 1000.0,
    ("concentration_ngg", "concentration_mgkg"): 0.001,
    ("concentration_ugkg", "concentration_mgkg"): 0.001,
    ("concentration_ngg", "concentration_ugkg"): 1.0,
    ("concentration_ugkg", "concentration_ngg"): 1.0,
}


def _extract_unit(col_name: str) -> tuple[str | None, str, str]:
    """从列名提取单位信息。返回 (unit_raw, factor_name, unit_category)。

    unit_raw: 识别到的原始单位文本（如"mg/kg"）
    factor_name: 去单位括号后的因子名
    unit_category: 单位分类标签（concentration_mgkg/native_percent/.../unknown）

    如 "砷_As（μg/kg）" → ("μg/kg", "砷_As", "concentration_ugkg")
    如 "有机质（%）" → ("%", "有机质", "native_percent")
    如 "海拔（m）" → ("m", "海拔", "native_length")
    """
    if not col_name:
        return None, str(col_name), "unknown"

    # 匹配括号内的单位（中文括号 / 英文括号）
    s = str(col_name)
    m = re.search(r"[（(]\s*([^)）\s]*)\s*[)）]", s)
    if m:
        raw_unit = m.group(1).strip()
        # 移除括号及其内容
        factor_name = re.sub(r"[（(]\s*[^)）]*[)）]", "", s).strip()
        # 归一化单位文本
        unit_lower = raw_unit.lower().replace("·", "").replace("⁻¹", "")
        category = _UNIT_CATEGORY_MAP.get(unit_lower, "unknown")
        # 规范化单位名（用于展示）
        normalized_unit = _UNIT_NORMALIZE.get(unit_lower, raw_unit)
        return normalized_unit, factor_name, category

    # 无括号单位：尝试从列名后缀推断（如 "pH"、"萘"）
    return None, s, "unknown"


def _resolve_conversion(input_category: str, canonical: str | None) -> tuple[float, str]:
    """计算输入值需要乘的转换因子，以对齐 canonical 的 preferred_unit。

    返回 (factor, target_unit_display)
    - factor: 输入值需要乘的系数
    - target_unit_display: canonical 的目标单位（如"ng/g"）

    如 输入 category=concentration_mgkg, canonical=BaP_ngg(preferred_unit=ng/g)
       → factor=1000.0, target="ng/g"
    """
    if canonical is None:
        return 1.0, "unknown"
    info = _ALIASES.get(canonical, {})
    preferred = info.get("preferred_unit")
    if not preferred:
        # 无 preferred_unit 声明: 重金属默认 mg/kg
        if canonical.endswith("_mgkg"):
            preferred = "mg/kg"
        elif canonical.endswith("_ngg"):
            preferred = "ng/g"
        elif canonical.endswith("_ugkg"):
            preferred = "μg/kg"
        else:
            return 1.0, "native"
    target_cat = _PREFERRED_UNIT_TO_CATEGORY.get(preferred, "unknown")
    if input_category == target_cat or target_cat == "unknown":
        return 1.0, preferred
    factor = _CONVERSION_MATRIX.get((input_category, target_cat))
    if factor is not None:
        return factor, preferred
    return 1.0, preferred


def normalize_factor_name(raw_name: str) -> tuple[str | None, dict]:
    """精确匹配单个因子名到 canonical。

    返回 (canonical or None, metadata)
    metadata 含: original_name, normalized_name, unit_raw, unit_converted,
               conversion_factor, unit_category, match_method, target_unit
    """
    meta: dict[str, Any] = {"original_name": raw_name}

    if raw_name is None or (isinstance(raw_name, float) and math.isnan(raw_name)):
        return None, meta

    unit_raw, factor_name, unit_category = _extract_unit(str(raw_name))
    meta["unit_raw"] = unit_raw
    meta["unit_category"] = unit_category

    normed = _norm_key(factor_name)
    meta["normalized_name"] = normed

    canonical = _lookup_canonical(str(raw_name))

    # v1.0.1: 标注匹配方式(精确/L4启发式模糊)
    if canonical:
        # 检查是否走 L4 关键词模糊匹配(L1/L2/L3 精确匹配表里查不到的)
        k_precise = _norm_key(factor_name)
        k2_precise = _norm_key(str(raw_name))
        if k_precise in _ALIAS_TO_CANONICAL or k2_precise in _ALIAS_TO_CANONICAL:
            meta["match_method"] = "exact"
        else:
            meta["match_method"] = "fuzzy_keyword"
    else:
        meta["match_method"] = "unmapped"

    # ── v0.8.1 单位智能转换 ──
    conversion_factor, target_unit = _resolve_conversion(unit_category, canonical)
    meta["conversion_factor"] = conversion_factor
    meta["target_unit"] = target_unit
    meta["unit_converted"] = target_unit  # canonical 的目标单位

    # 旧兼容: 保留原有 _UNIT_CONVERSION 逻辑（对没有 preferred_unit 的老因子仍生效）
    if conversion_factor == 1.0 and unit_raw and unit_raw in _UNIT_CONVERSION:
        factor, tgt = _UNIT_CONVERSION[unit_raw]
        meta["conversion_factor"] = factor
        meta["unit_converted"] = tgt

    return canonical, meta


def normalize_factors_v2(raw_values: dict) -> dict:
    """因子名规范化 + 单位转换 + 冲突检测（P0-1 核心函数）。

    返回:
        {
            "factors": {canonical: converted_value},
            "mapping_details": [{original_name, canonical, unit_raw, unit_converted, conversion_factor}],
            "mapping_conflicts": [{canonical, sources: [original_names]}],
            "unmapped": [original_names],
            "data_quality_flags": [str],
        }
    """
    factors: dict[str, float] = {}
    mapping_details: list[dict] = []
    mapping_conflicts: list[dict] = []
    unmapped: list[str] = []
    data_quality_flags: list[str] = []

    # 记录 canonical → 来源列（用于冲突检测）
    canonical_sources: dict[str, list[str]] = {}

    for raw_name, raw_value in raw_values.items():
        if raw_value is None or (isinstance(raw_value, float) and math.isnan(raw_value)):
            continue

        canonical, meta = normalize_factor_name(raw_name)

        if canonical is None:
            unmapped.append(str(raw_name))
            # 未匹配的保留原名（可能是未知有机物，交由 guardrails 处理）
            try:
                factors[str(raw_name)] = float(raw_value)
            except (TypeError, ValueError):
                pass
            continue

        # 单位转换
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            data_quality_flags.append(f"因子 {raw_name} 值无法转为数值: {raw_value}")
            continue

        converted_value = value * meta.get("conversion_factor", 1.0)

        meta["canonical"] = canonical
        meta["original_value"] = value
        meta["converted_value"] = converted_value
        mapping_details.append(meta)

        # 冲突检测：同一 canonical 已有不同来源
        if canonical in factors and canonical_sources.get(canonical, [None])[-1] != str(raw_name):
            conflict_entry = next(
                (c for c in mapping_conflicts if c["canonical"] == canonical), None
            )
            if conflict_entry:
                if str(raw_name) not in conflict_entry["sources"]:
                    conflict_entry["sources"].append(str(raw_name))
            else:
                mapping_conflicts.append({
                    "canonical": canonical,
                    "sources": canonical_sources.get(canonical, []) + [str(raw_name)],
                })
            data_quality_flags.append(
                f"因子 {canonical} 有多个来源列({', '.join(canonical_sources.get(canonical, []) + [str(raw_name)])})，存在冲突"
            )
            # 不静默覆盖，保留第一个值，标记 review_required

        elif canonical not in factors:
            factors[canonical] = converted_value
            canonical_sources[canonical] = [str(raw_name)]
        else:
            # 同一来源列重复（key 相同），更新值
            factors[canonical] = converted_value

    # v0.8.1: 只对真正"单位不明"的因子打标记（排除原生单位和 dimensionless）
    # 如果 unit_category 是 unknown 但 canonical 有 preferred_unit，从 preferred_unit 推断类别
    NATIVE_CATEGORIES = {"native_g_kg", "native_density", "native_cmol", "native_ec",
                         "native_percent", "native_length", "native_slope", "dimensionless"}
    for d in mapping_details:
        cat = d.get("unit_category", "unknown")
        cano = d.get("canonical", "")
        # 尝试从 canonical 的 preferred_unit 推断
        if cat == "unknown" and cano:
            info = _ALIASES.get(cano, {})
            pref = info.get("preferred_unit", "")
            inferred_cat = _PREFERRED_UNIT_TO_CATEGORY.get(pref, "unknown")
            if inferred_cat != "unknown":
                d["unit_category"] = inferred_cat
                d["unit_converted"] = pref
                cat = inferred_cat
        if cat == "unknown" and cano not in ("pH",):
            data_quality_flags.append(
                f"因子 {d['original_name']}（→{cano}）单位不明，未做单位转换"
            )

    return {
        "factors": factors,
        "mapping_details": mapping_details,
        "mapping_conflicts": mapping_conflicts,
        "unmapped": unmapped,
        "data_quality_flags": data_quality_flags,
    }
