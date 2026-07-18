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
    _, factor_name = _extract_unit(raw_name)
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
    "全氮": "TN_gkg", "水解性氮": "TN_gkg", "碱解氮": "TN_gkg",
    "全磷": "P_mgkg", "有效磷": "P_mgkg", "速效磷": "P_mgkg",
    "全钾": "K_mgkg", "速效钾": "K_mgkg", "缓效钾": "K_mgkg",
    "容重": "SoilBD_gcm3", "土壤容重": "SoilBD_gcm3",
    "质地": "Clay_pct", "粘粒": "Clay_pct", "黏粒": "Clay_pct",
    "砂粒": "Sand_pct", "粉粒": "Silt_pct",
    "坡度": "Slope_pct", "海拔": "Elevation_m",
    "全铁": "Fe_mgkg", "铁": "Fe_mgkg",
    # ── PAH 多环芳烃(16种优先控制) ──
    "萘": "PAH_Naphthalene", "苊": "PAH_Acenaphthylene", "芴": "PAH_Fluorene",
    "菲": "PAH_Phenanthrene", "蒽": "PAH_Anthracene", "荧蒽": "PAH_Fluoranthene",
    "芘": "PAH_Pyrene", "苯并[a]蒽": "PAH_Benz[a]anthracene",
    "苯并芘": "PAH_Benzo[a]pyrene", "苯并[a]芘": "PAH_Benzo[a]pyrene",
    "苯并[b]荧蒽": "PAH_Benzo[b]fluoranthene", "苯并[k]荧蒽": "PAH_Benzo[k]fluoranthene",
    "茚并": "PAH_Indeno", "苝": "PAH_Perylene",
    # ── OCP 有机氯农药 ──
    "六六六": "OCP_HCH", "滴滴涕": "OCP_DDT", "氯丹": "OCP_Chlordane",
    "七氯": "OCP_Heptachlor", "毒杀芬": "OCP_Camphechlor", "灭蚁灵": "OCP_Mirex",
    "硫丹": "OCP_Endosulfan",
    # ── PCB 多氯联苯 ──
    "多氯联苯": "PCB_total", "联苯": "PCB_total",
    # ── PFAS 全氟化合物 ──
    "全氟": "PFAS_total", "全氟辛酸": "PFAS_PFOA", "全氟辛烷": "PFAS_PFOS",
    # ── PAE 邻苯二甲酸酯(塑化剂) ──
    "邻苯二甲酸": "PAE_total", "塑化剂": "PAE_total",
    # ── TPH 石油烃 ──
    "石油烃": "TPH_C10C40", "矿物油": "TPH_C10C40", "总石油": "TPH_C10C40",
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


def _extract_unit(col_name: str) -> tuple[str | None, str]:
    """从列名提取单位信息。返回 (单位, 去单位后的因子名)。

    如 "砷_As(μg/kg)" → ("μg/kg", "砷_As")
    """
    # 匹配括号内的单位
    m = re.search(r"[（(]\s*(μg/kg|ug/kg|ng/g|mg/kg|mg·kg|mg·kg⁻¹)\s*[)）]", col_name, re.IGNORECASE)
    if m:
        unit = m.group(1).lower().replace("·", "").replace("⁻¹", "")
        factor_name = re.sub(r"[（(]\s*[^)）]*[)）]", "", col_name).strip()
        return unit, factor_name
    return None, col_name


def normalize_factor_name(raw_name: str) -> tuple[str | None, dict]:
    """精确匹配单个因子名到 canonical。

    返回 (canonical or None, metadata)
    metadata 含: original_name, normalized_name, unit_raw, unit_converted, conversion_factor
    """
    meta: dict[str, Any] = {"original_name": raw_name}

    if raw_name is None or (isinstance(raw_name, float) and math.isnan(raw_name)):
        return None, meta

    unit_raw, factor_name = _extract_unit(str(raw_name))
    meta["unit_raw"] = unit_raw

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

    # 单位转换
    if unit_raw and unit_raw in _UNIT_CONVERSION:
        factor, target_unit = _UNIT_CONVERSION[unit_raw]
        meta["conversion_factor"] = factor
        meta["unit_converted"] = target_unit
    else:
        meta["conversion_factor"] = 1.0
        meta["unit_converted"] = unit_raw or "unknown"

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

    # 单位不明的因子标记
    for d in mapping_details:
        if d.get("unit_converted") == "unknown" and d["canonical"] not in ("pH",):
            data_quality_flags.append(
                f"因子 {d['original_name']}（→{d['canonical']}）单位不明，未做单位转换"
            )

    return {
        "factors": factors,
        "mapping_details": mapping_details,
        "mapping_conflicts": mapping_conflicts,
        "unmapped": unmapped,
        "data_quality_flags": data_quality_flags,
    }
