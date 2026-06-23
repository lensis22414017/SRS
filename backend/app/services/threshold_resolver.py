"""阈值解析器: 正确处理知识库中"按 pH 分段"的污染物限值。

关键事实(经核查 统一障碍因子知识库_V1.0):
  - 生产用地污染物行的 threshold_min/threshold_max 列存的是 **pH 分段断点**,
    真正的浓度限值写在 threshold_original 文本里, 形如:
      "全国通用，pH≤5.5时，≤30mg/kg"
      "全国通用，5.5<pH≤6.5时，≤40mg/kg"
      "全国通用，6.5<pH≤7.5时，≤25mg/kg"
      "全国通用，pH>7.5时，≤20mg/kg"
    且同一因子有"水田/果园用地"与"其他用地"两套(限值不同)。
  - 生态用地行的 threshold_original 多为直接浓度("二类用地区≤60mg/kg"、"其他绿地35-45mg/kg")。

因此不能直接用 threshold_min/max 比较浓度, 必须解析文本 + 结合样点 pH。
本模块从 threshold_original 解析出 (pH 区间, 浓度限值, 用地子类), 供校验/分等使用。
"""
from __future__ import annotations

import csv
import re

_LIMIT_RE = re.compile(r"≤\s*([\d.]+)\s*(?:mg/kg|ng/g|ng/kg|μg/kg|ug/kg)")
_RANGE_RE = re.compile(r"([\d.]+)\s*[-~]\s*([\d.]+)\s*mg/kg")
_PH_LE = re.compile(r"pH\s*≤\s*([\d.]+)")
_PH_GT = re.compile(r"pH\s*>\s*([\d.]+)")
_PH_BETWEEN = re.compile(r"([\d.]+)\s*<\s*pH\s*≤\s*([\d.]+)")


def parse_threshold_original(text: str) -> dict | None:
    """解析单条 threshold_original 文本 -> {ph_min, ph_max, limit, limit_max, raw}。"""
    if not text:
        return None
    t = text.strip()
    ph_min = ph_max = None
    mb = _PH_BETWEEN.search(t)
    if mb:
        ph_min, ph_max = float(mb.group(1)), float(mb.group(2))
    else:
        mle = _PH_LE.search(t)
        mgt = _PH_GT.search(t)
        if mle:
            ph_max = float(mle.group(1))
        if mgt:
            ph_min = float(mgt.group(1))
    limit = limit_max = None
    mr = _RANGE_RE.search(t)
    ml = _LIMIT_RE.search(t)
    if ml:
        limit = float(ml.group(1))
    elif mr:
        limit = float(mr.group(1))
        limit_max = float(mr.group(2))
    if limit is None and limit_max is None:
        return None
    return {"ph_min": ph_min, "ph_max": ph_max, "limit": limit,
            "limit_max": limit_max, "raw": t}


def _land_subtype(application_scenario: str | None) -> str:
    s = (application_scenario or "").strip()
    if s in ("水田用地", "果园用地", "旱地用地", "园地用地"):
        return s
    if s == "其他用地" or not s:
        return "其他用地"
    return s or "其他用地"


def build_pollutant_limits(kb_csv: str) -> dict:
    """factor_name -> {scope: {land_subtype: [seg,...]}}。seg 含 pH 区间与浓度限值。"""
    out: dict[str, dict] = {}
    with open(kb_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # threshold_original 中"用地"声明只出现在每组首行, 后续行 application_scenario 为空, 需向下填充
    last_scenario_by_key: dict[tuple, str] = {}
    for r in rows:
        name = (r.get("factor_name") or "").strip()
        if not name:
            continue
        scope_raw = (r.get("applicable_scope") or "").strip()
        scope = {"生产用地": "production", "生态用地": "ecology"}.get(scope_raw, scope_raw)
        key = (name, scope)
        scen = (r.get("application_scenario") or "").strip()
        if scen:
            last_scenario_by_key[key] = scen
        scen_eff = last_scenario_by_key.get(key, "其他用地")
        sub = _land_subtype(scen_eff)
        parsed = parse_threshold_original(r.get("threshold_original"))
        if not parsed:
            continue
        out.setdefault(name, {}).setdefault(scope, {}).setdefault(sub, []).append({
            "ph_min": parsed["ph_min"], "ph_max": parsed["ph_max"],
            "limit": parsed["limit"], "limit_max": parsed["limit_max"],
            "source": (r.get("standard_source") or "").strip(),
            "raw": parsed["raw"],
        })
    return out


def resolve_limit(limits: dict, factor: str, ph: float | None,
                  scope: str = "production", land_subtype: str = "其他用地") -> dict | None:
    """给定因子/pH/用地, 取浓度上限段。pH 缺失时取该用地子类首个有限值段。"""
    by_scope = limits.get(factor, {}).get(scope, {})
    segs = by_scope.get(land_subtype) or next(iter(by_scope.values()), [])
    if not segs:
        return None
    if ph is not None:
        for s in segs:
            lo = s["ph_min"] if s["ph_min"] is not None else float("-inf")
            hi = s["ph_max"] if s["ph_max"] is not None else float("inf")
            if lo < ph <= hi or (s["ph_min"] is None and s["ph_max"] is None):
                return s
    # 回退: 第一段
    return segs[0]
