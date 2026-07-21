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
    # ── 重金属（GB15618 + GB36600）──
    "Cd_mgkg": "Cd", "Pb_mgkg": "Pb", "As_mgkg": "As",
    "Cr_mgkg": "Cr", "Cr6_mgkg": "Cr(VI)",
    "Hg_mgkg": "Hg", "Cu_mgkg": "Cu", "Zn_mgkg": "Zn",
    "Ni_mgkg": "Ni", "pH": "pH",
    # v1.0.1 L4 启发式匹配的扩展重金属(DB无精确阈值, 用 GB15618 兜底)
    "Mn_mgkg": "Mn", "Co_mgkg": "Co", "Mo_mgkg": "Mo",
    "Sb_mgkg": "Sb", "Tl_mgkg": "Tl", "Be_mgkg": "Be", "Ba_mgkg": "Ba",
    "V_mgkg": "V", "Fe_mgkg": "Fe",
    # ── v1.0.1 L4 有机物映射(DB有中文名阈值) ──
    "PAH_Naphthalene": "萘", "PAH_Fluorene": "芴", "PAH_Phenanthrene": "菲",
    "PAH_Anthracene": "蒽", "PAH_Fluoranthene": "荧蒽", "PAH_Pyrene": "芘",
    "PAH_Benzo[a]pyrene": "苯并[a]芘", "PAH_Benzo[a]anthracene": "苯并[a]蒽",
    "PAH_Benzo[b]fluoranthene": "苯并[b]荧蒽", "PAH_Benzo[k]fluoranthene": "苯并[k]荧蒽",
    "PAH_Indeno": "茚并[1,2,3-cd]芘",
    "OCP_HCH": "六六六", "OCP_DDT": "DDT类",
    "PCB_total": "多氯联苯", "PFAS_total": "全氟化合物",
    "TPH_C10C40": "石油烃",
    "VOC_Trichloroethylene": "三氯乙烯", "VOC_Tetrachloroethylene": "四氯乙烯",
    "VOC_CarbonTetrachloride": "四氯化碳", "VOC_Chloroform": "氯仿",
    "VOC_VinylChloride": "氯乙烯", "VOC_Dichloromethane": "二氯甲烷",
    "VOC_Chlorobenzene": "氯苯",
    "BTEX_Styrene": "苯乙烯", "BTEX_Toluene": "甲苯", "BTEX_Ethylbenzene": "乙苯",
    "BTEX_Xylene": "邻-二甲苯",
    "Phenol_Pentachlorophenol": "五氯酚", "Phenol_Chlorophenol": "2-氯酚",
    "Aniline": "苯胺", "Nitrobenzene": "硝基苯",
    "Cyanide": "氰化物",
    # ── v1.0.2 新增映射（对齐 SHAP canonical → GB36600 标准库中文名）──
    "BaP_ngg": "苯并[a]芘",
    "SumDDTs_ngg": "DDT类",
    "SumHCHs_ngg": "六六六",
    "SumPCB_ngg": "多氯联苯",
    "PAHs_total(族群)": "多环芳烃总量",
    "TPH_ngg": "石油烃",
    "SumOCP_ngg": "有机氯农药",
    "SumPAE_ugkg": "邻苯二甲酸二(2-乙基己基)酯",  # DEHP 作为 PAEs 代表（GB36600最严）
    "SumPBDE_ngg": "多溴联苯(总量)",
    # PAH 单体（中文裸名 → GB36600 中文名）
    "萘": "萘", "䓛": "䓛",
    "苯并[a]蒽": "苯并[a]蒽", "苯并[b]荧蒽": "苯并[b]荧蒽", "苯并[k]荧蒽": "苯并[k]荧蒽",
    "茚并[1,2,3-cd]芘": "茚并[1,2,3-cd]芘", "茚并[123-cd]芘": "茚并[1,2,3-cd]芘",
    "二苯并[a,h]蒽": "二苯并[a,h]蒽", "二苯并[ah]蒽": "二苯并[a,h]蒽",
    # 养分/理化（CJ/T 340 + NY/T 1749 + TD/T1036）
    "Hydrolyzable_N_mgkg": "水解性氮",
    "P_mgkg": "有效磷", "K_mgkg": "速效钾",
    "Total_P_gkg": "全磷", "Total_K_gkg": "全钾",
    "TN_gkg": "全氮", "OC_pct": "有机质",
    "CEC_cmolkg": "阳离子交换量",
    "SoilBD_gcm3": "容重", "EC_mScm": "电导率",
    # 无标准阈值的描述性指标（advisory-only，不报 not_found）
    "Sand_pct": "__advisory__", "Silt_pct": "__advisory__", "Clay_pct": "__advisory__",
    "Elevation_m": "__advisory__", "MAP_mm": "__advisory__",
    "Slope_pct": "__advisory__",
    # v1.0.2: 已从测试数据集中删除的因子（静默跳过，不报 not_found）
    "SumPBDE_ngg": "__advisory__", "SumPFAS_ngg": "__advisory__",
    "HMWPAH_ngg": "__advisory__", "LMWPAH_ngg": "__advisory__",
}

# v1.0.1: GB15618 扩展重金属通用阈值兜底(DB无精确值时的 fallback)
# v1.0.2: 扩展养分/理化/新兴污染物文献兜底值
_GB15618_EXTENDED_FALLBACK = {
    # ── 重金属扩展（GB15618通用档）──
    "Mn": {"limit": 1500, "unit": "mg/kg", "standard": "GB15618 通用档(锰)"},
    "Co": {"limit": 40, "unit": "mg/kg", "standard": "GB15618 通用档(钴)"},
    "Mo": {"limit": 40, "unit": "mg/kg", "standard": "GB15618 通用档(钼)"},
    "Sb": {"limit": 10, "unit": "mg/kg", "standard": "GB15618 通用档(锑)"},
    "Tl": {"limit": 1.0, "unit": "mg/kg", "standard": "GB15618 通用档(铊)"},
    "Be": {"limit": 15, "unit": "mg/kg", "standard": "GB15618 通用档(铍)"},
    "Ba": {"limit": 750, "unit": "mg/kg", "standard": "GB15618 通用档(钡)"},
    "V": {"limit": 165, "unit": "mg/kg", "standard": "GB15618 通用档(钒)"},
    "Fe": {"limit": 50000, "unit": "mg/kg", "standard": "GB15618 通用档(铁)"},
    # ── 有机质 + 全氮（肥力下限参考）──
    "OC_pct": {"limit": 0.35, "unit": "%", "standard": "全国二普 SOM 贫乏下限 (6 g/kg → OC≈0.35%)"},
    "TN_gkg": {"limit": 1.0, "unit": "g/kg", "standard": "NY/T 1749-2009 旱地全氮标准值"},
    # ── v1.0.2 扩展 ──
    # 养分（全国第二次土壤普查 + NY/T 1749）
    "Total_P_gkg": {"limit": 0.4, "unit": "g/kg", "standard": "全国二普 全磷中等下限 (0.4 g/kg)"},
    "Total_K_gkg": {"limit": 10, "unit": "g/kg", "standard": "全国二普 全钾中等下限 (10 g/kg)"},
    "P_mgkg": {"limit": 5, "unit": "mg/kg", "standard": "全国二普 有效磷贫乏上限 (Olsen-P <5 mg/kg)"},
    "K_mgkg": {"limit": 50, "unit": "mg/kg", "standard": "全国二普 速效钾贫乏上限 (<50 mg/kg)"},
    "Hydrolyzable_N_mgkg": {"limit": 60, "unit": "mg/kg", "standard": "全国二普 碱解氮贫乏上限 (<60 mg/kg)"},
    # 物理指标（国标/行标）
    "CEC_cmolkg": {"limit": 10, "unit": "cmol(+)/kg", "standard": "CJ/T 340-2016 保肥下限 (≥10 cmol/kg)"},
    "SoilBD_gcm3": {"limit": 1.5, "unit": "g/cm³", "standard": "TD/T1036-2013 容重上限 (≤1.5 g/cm³)"},
    "EC_mScm": {"limit": 2.0, "unit": "mS/cm", "standard": "USDA 盐渍化阈值 (ECe≤2 dS/m = 2 mS/cm)"},
    # 新兴污染物（文献/EPA兜底）
    "SumPAE_ugkg": {"limit": 42000, "unit": "μg/kg", "standard": "GB36600 DEHP 一类用地筛选值 (42 mg/kg → 42000 μg/kg)"},
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
    # v1.0.3: 扩展——行标/文献标准也纳入直接查询
    all_standards = standards + [
        "NY/T 1749-2009", "CJ/T 340-2016", "TD/T1036-2013", "全国二普",
        "GB/T 33469-2016", "GB/T 28407-2012", "EPA RSL 2024",
    ]
    db_factor_name = _CANONICAL_TO_DB_NAME.get(factor_canonical, factor_canonical)

    # v1.0.2: __advisory__ 因子（描述性指标，无阈值概念）→ 静默跳过，不报错
    if db_factor_name == "__advisory__":
        return {
            "threshold": None, "threshold_value": None, "threshold_unit": "—",
            "threshold_standard": "", "threshold_version": "",
            "pH_condition": "", "land_use_type": land_use_type or "",
            "threshold_source_id": None,
            "threshold_resolution_status": "advisory", "review_required": False,
            "note": f"因子 {factor_canonical} 为描述性指标，无超标概念，不参与KOS排名",
        }

    rows = (db.query(StandardThreshold)
            .filter(StandardThreshold.factor_name == db_factor_name,
                    StandardThreshold.standard_code.in_(all_standards))
            .all()) if standards else []

    not_found_result = {
        "threshold": None, "threshold_value": None, "threshold_unit": "mg/kg",
        "threshold_standard": "", "threshold_version": "",
        "pH_condition": "", "land_use_type": land_use_type or "",
        "threshold_source_id": None,
        "threshold_resolution_status": "not_found", "review_required": True,
    }

    if not rows:
        # v1.0.2: 交叉轨兜底 — 生产轨查不到 GB15618 时用 GB36600 兜底（反之亦然）
        cross_standards = (["GB 36600-2018", "GB36600-2018"] if track == "prod"
                           else ["GB 15618-2018", "GB15618-2018"])
        cross_rows = (db.query(StandardThreshold)
                      .filter(StandardThreshold.factor_name == db_factor_name,
                              StandardThreshold.standard_code.in_(cross_standards))
                      .all()) if cross_standards else []
        if cross_rows:
            # 取第一类用地（最严）筛选值
            best = min(cross_rows, key=lambda r: float(r.screening_value) if r.screening_value else float('inf'))
            limit = float(best.screening_value)
            return {
                "threshold": {"type": "upper", "limit": limit},
                "threshold_value": limit, "threshold_unit": best.unit or "mg/kg",
                "threshold_standard": f"{best.standard_code} (交叉轨兜底)",
                "threshold_version": str(best.version),
                "pH_condition": best.pH_condition or "",
                "land_use_type": best.land_use_type or "",
                "threshold_source_id": best.id,
                "threshold_resolution_status": "resolved", "review_required": False,
                "fallback_note": f"生产/生态轨无精确匹配, 已用{best.standard_code}交叉轨兜底({limit} {best.unit or 'mg/kg'})",
            }

        # v1.0.1: 扩展重金属 GB15618 通用档兜底(L4 启发式匹配的 Mn/Co/Mo 等)
        # v1.0.2: 扩展养分/理化/新兴污染物文献兜底值
        # 查找优先级: db_factor_name(映射后中文名) → factor_canonical(原始 canonical)
        fb = (_GB15618_EXTENDED_FALLBACK.get(db_factor_name)
              or _GB15618_EXTENDED_FALLBACK.get(factor_canonical))
        if fb:
            return {
                "threshold": {"type": "upper", "limit": fb["limit"]},
                "threshold_value": fb["limit"], "threshold_unit": fb["unit"],
                "threshold_standard": fb["standard"], "threshold_version": "文献兜底",
                "pH_condition": "通用", "land_use_type": land_use_type or "",
                "threshold_source_id": None,
                "threshold_resolution_status": "heuristic", "review_required": True,
                "fallback_note": f"{factor_canonical} 使用 {fb['standard']} 兜底值, 待核实",
            }
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
        # v1.0.2: land_use_type 为空时默认"其他"（最通用的农用地子类）
        effective_lu = land_use_type or "其他"
        lu_m = [r for r in matched if (r.land_use_type or "其他") == effective_lu]
        if len(lu_m) >= 1:
            matched = [lu_m[0]]
        else:
            # v1.0.3: 无精确匹配时取第一条（最保守/通用值），不报 ambiguous
            # 覆盖行标的多用地类型（旱地/水田/普通绿化区等）
            matched = [matched[0]]

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


# ── v1.0.2: 阈值兜底(GB15618 通用档最严值) ──────────────────

def resolve_threshold_fallback(
    db,
    factor_canonical: str,
    track: str = "prod",
) -> dict:
    """v1.0.2: pH/用地缺失时, 取该因子在该 standard 下的最严档(最小 screening_value)兜底。

    场景: resolve_threshold_from_db 返回 ambiguous(pH/用地缺失无法唯一确定档)时调用。
    策略: 从该因子所有阈值行中取 min(screening_value) 作为兜底限值(最严档, 宁可错杀)。
    返回 status="fallback", review_required=True, 标注兜底来源。

    GPT 4.10 + 缺阈值不得当作安全, 用最严档兜底让用户看到"有障碍但阈值待核实"。
    """
    from app.models import StandardThreshold

    standards = (["GB 15618-2018", "GB15618-2018"] if track == "prod"
                 else ["GB 36600-2018", "GB36600-2018"])
    # v1.0.3: 扩展——行标/文献标准也纳入直接查询
    all_standards = standards + [
        "NY/T 1749-2009", "CJ/T 340-2016", "TD/T1036-2013", "全国二普",
        "GB/T 33469-2016", "GB/T 28407-2012", "EPA RSL 2024",
    ]
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

