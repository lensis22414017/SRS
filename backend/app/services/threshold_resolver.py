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

P0-2 新增: resolve_threshold_from_db — 从 StandardThreshold 数据库表按 pH/land_use 动态查询。
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


# ── P0-2: 从 StandardThreshold 数据库表动态查询 ──────────────────────────

def _match_pH_condition_db(pH_condition: str, site_pH: float | None) -> bool:
    """检查场地 pH 是否匹配数据库阈值记录的 pH_condition。

    GB15618 的 pH 分档格式(数据库 pH_condition 列):
      pH<=5.5 / 5.5<pH<=6.5 / 6.5<pH<=7.5 / pH>7.5
    GB36600: not_applicable (建设用地不分 pH)
    """
    if not pH_condition or pH_condition == "not_applicable":
        return True
    if site_pH is None:
        return False  # 阈值有 pH 条件但场地无 pH → 不匹配

    cond = pH_condition.strip().replace(" ", "")

    if cond.startswith("pH<="):
        return site_pH <= float(cond.replace("pH<=", ""))
    elif cond.startswith("pH>"):
        return site_pH > float(cond.replace("pH>", "").replace("=", ""))
    elif "<pH<=" in cond:
        parts = cond.split("<pH<=")
        return float(parts[0]) < site_pH <= float(parts[1])
    elif "<pH<" in cond:
        parts = cond.split("<pH<")
        return float(parts[0]) < site_pH < float(parts[1])
    return False


_CANONICAL_TO_DB_NAME = {
    "Cd_mgkg": "Cd", "Pb_mgkg": "Pb", "As_mgkg": "As",
    "Cr_mgkg": "Cr", "Cr6_mgkg": "Cr(VI)",
    "Hg_mgkg": "Hg", "Cu_mgkg": "Cu", "Zn_mgkg": "Zn",
    "Ni_mgkg": "Ni", "pH": "pH",
}


def resolve_threshold_from_db(
    db,
    factor_canonical: str,
    track: str = "prod",
    site_pH: float | None = None,
    land_use_type: str | None = None,
) -> dict:
    """从 StandardThreshold 表按 pH/land_use 动态查询阈值（P0-2）。

    track: "prod"(GB15618农用地) / "eco"(GB36600建设用地)
    返回 status: resolved / ambiguous / not_found
    """
    from app.models import StandardThreshold

    standards = (["GB 15618-2018", "GB15618-2018"] if track == "prod"
                 else ["GB 36600-2018", "GB36600-2018"])
    db_factor_name = _CANONICAL_TO_DB_NAME.get(factor_canonical, factor_canonical)

    rows = (db.query(StandardThreshold)
            .filter(StandardThreshold.factor_name == db_factor_name,
                    StandardThreshold.standard_code.in_(standards))
            .all()) if standards else []

    not_found_result = {
        "threshold": None, "threshold_value": None, "threshold_unit": "mg/kg",
        "threshold_standard": "", "threshold_version": "",
        "pH_condition": "", "land_use_type": land_use_type or "",
        "threshold_source_id": None,
        "threshold_resolution_status": "not_found", "review_required": True,
    }

    if not rows:
        return not_found_result

    # pH 特殊处理（固定区间）
    if factor_canonical == "pH":
        return {
            "threshold": {"type": "interval",
                          "min": 5.5 if track == "prod" else 5.0,
                          "max": 8.5 if track == "prod" else 8.3},
            "threshold_value": None, "threshold_unit": "无量纲",
            "threshold_standard": standards[0], "threshold_version": "2018",
            "pH_condition": "", "land_use_type": land_use_type or "",
            "threshold_source_id": rows[0].id if rows else None,
            "threshold_resolution_status": "resolved", "review_required": False,
        }

    # 按 pH 条件筛选
    matched = [r for r in rows if _match_pH_condition_db(r.pH_condition, site_pH)]

    if len(matched) == 0:
        return {**not_found_result,
                "threshold_resolution_status": "ambiguous",
                "note": f"因子 {factor_canonical} 需要 pH 确定阈值档，场地缺 pH"}

    if len(matched) > 1:
        # M0-2: 删除生态轨"默认第二类用地"的隐式默认;
        # 土地用途不明确时必须 ambiguous, 不得猜测
        if land_use_type:
            lu_m = [r for r in matched if land_use_type in (r.land_use_type or "")]
            if len(lu_m) == 1:
                matched = lu_m
        if len(matched) > 1:
            return {**not_found_result,
                    "threshold_resolution_status": "ambiguous",
                    "threshold_standard": matched[0].standard_code,
                    "note": f"因子 {factor_canonical} 匹配 {len(matched)} 条阈值，土地用途不明确，无法唯一确定"}

    r = matched[0]
    limit = float(r.screening_value) if r.screening_value is not None else None
    return {
        "threshold": {"type": "upper", "limit": limit},
        "threshold_value": limit,
        "threshold_unit": r.unit or "mg/kg",
        "threshold_standard": r.standard_code,
        "threshold_version": str(r.version),
        "pH_condition": r.pH_condition or "",
        "land_use_type": r.land_use_type or "",
        "threshold_source_id": r.id,
        "threshold_resolution_status": "resolved",
        "review_required": False,
    }


# ── v1.0.2: 阈值兜底(裴总决策: GB15618 通用档最严值) ──────────────────

def resolve_threshold_fallback(
    db,
    factor_canonical: str,
    track: str = "prod",
) -> dict:
    """v1.0.2: pH/用地缺失时, 取该因子在该 standard 下的最严档(最小 screening_value)兜底。

    场景: resolve_threshold_from_db 返回 ambiguous(pH/用地缺失无法唯一确定档)时调用。
    策略: 从该因子所有阈值行中取 min(screening_value) 作为兜底限值(最严档, 宁可错杀)。
    返回 status="fallback", review_required=True, 标注兜底来源。

    GPT 4.10 + 裴总决策: 缺阈值不得当作安全, 用最严档兜底让甲方看到"有障碍但阈值待核实"。
    """
    from app.models import StandardThreshold

    standards = (["GB 15618-2018", "GB15618-2018"] if track == "prod"
                 else ["GB 36600-2018", "GB36600-2018"])
    db_factor_name = _CANONICAL_TO_DB_NAME.get(factor_canonical, factor_canonical)

    rows = (db.query(StandardThreshold)
            .filter(StandardThreshold.factor_name == db_factor_name,
                    StandardThreshold.standard_code.in_(standards),
                    StandardThreshold.screening_value.isnot(None))
            .all()) if standards else []

    not_found_result = {
        "threshold": None, "threshold_value": None, "threshold_unit": "mg/kg",
        "threshold_standard": "", "threshold_version": "",
        "pH_condition": "", "land_use_type": "",
        "threshold_source_id": None,
        "threshold_resolution_status": "not_found", "review_required": True,
    }

    if not rows:
        return not_found_result

    # 取最严档(最小 screening_value)
    strictest = min(rows, key=lambda r: float(r.screening_value) if r.screening_value is not None else float('inf'))
    limit = float(strictest.screening_value)
    return {
        "threshold": {"type": "upper", "limit": limit},
        "threshold_value": limit,
        "threshold_unit": strictest.unit or "mg/kg",
        "threshold_standard": strictest.standard_code,
        "threshold_version": str(strictest.version),
        "pH_condition": "",
        "land_use_type": "",
        "threshold_source_id": strictest.id,
        "threshold_resolution_status": "fallback",
        "review_required": True,
        "fallback_note": f"pH/用地缺失, 已用{factor_canonical}最严档({limit})兜底, 请核实场地pH/用地类型",
    }

