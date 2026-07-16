"""factor_normalizer.py — 因子名称规范化、单位转换、冲突检测（P0-1 修复）

替代 kos_service.py 中的子串匹配 normalize_factors，改为：
1. Unicode NFKC + strip + 大小写归一 + 全半角括号统一
2. 从 factor_aliases_v0.8.yaml 加载别名表，精确匹配（非子串）
3. 区分总铬 Cr_mgkg 与六价铬 Cr6_mgkg
4. 单位转换 μg/kg/ng/g → mg/kg
5. 同一 canonical 因子多来源列冲突 → mapping_conflicts（不静默覆盖）
"""
from __future__ import annotations

import os
import re
import unicodedata
import math
from typing import Any

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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
    """三级查找: 精确 → 去单位精确 → 组合名拆分。

    精确匹配优先（禁止子串匹配），组合名如"镉_Cd"按分隔符拆分后逐段查。
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
