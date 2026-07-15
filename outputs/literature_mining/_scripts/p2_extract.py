"""P2 结构化抽取 v3 (转置表支持 + 标签唯一性)

v3 新增 (相对 v2.1):
  1. 转置表检测 (is_transposed_table): PCB/PAH/PBDE 单体表常"污染物作行, 采样点作列"
     → extract_transposed: 抽 Total/Sum 行作族群汇总, 每列一个采样点
     → 救回 P01524 tbl#3/4 等 PCB 单体表 (HM_OP 配对金矿)
  2. find_label_column 用唯一性: 合并单元格的大类列唯一值低, 采样点编号列唯一值高
     → P01524 tbl#1 选 col1 (A/B/C) 而非 col0 (e-waste 大类)

继承 v2.1 规则:
  - 文献对比表 (References 列) → 拒绝
  - 植物/生物/飞灰浓度 → 拒绝 (扩充: ryegrass/sorghum/牧草)
  - summary 表 (Mean/Median) → B_site_summary, 只抽 Mean
  - sample 表 → A_sample_table
  - non_numeric/missing → 不记录
"""
from __future__ import annotations
import sys
import re
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (  # noqa: E402
    OUT_DIR, LIT_ROOT, convert_value, classify_landuse,
)

import pandas as pd  # noqa: E402

# ===== LaTeX 清洗 =====
def clean_latex(text: str) -> str:
    if not text:
        return ""
    t = str(text)
    t = re.sub(r"\\mathbf\{([^}]*)\}", r"\1", t)
    t = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", t)
    t = re.sub(r"\\(left|right)[(|\])]", "", t)
    t = re.sub(r"\\cdot", "·", t)
    t = re.sub(r"\\times", "×", t)
    t = re.sub(r"\^\{[^}]*\}", "", t)
    t = re.sub(r"\^\S", "", t)
    t = re.sub(r"\\(sum|Sigma)", "∑", t)
    t = t.replace("$", "").replace("\\", "").replace("{", "").replace("}", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ===== 污染物识别 =====
HM_MAP = {
    "Cd": "Cd_mgkg", "Pb": "Pb_mgkg", "As": "As_mgkg", "Hg": "Hg_mgkg",
    "Cr": "Cr_mgkg", "Cu": "Cu_mgkg", "Zn": "Zn_mgkg", "Ni": "Ni_mgkg",
    "Co": "Co_mgkg", "Mn": "Mn_mgkg",
}
HM_ELEMENT_PAT = re.compile(r"\b(Cd|Pb|As|Hg|Cr|Cu|Zn|Ni|Co|Mn|Sb|V|Al|Fe)\b")

OP_FAMILY_MAP = [
    (re.compile(r"∑\s*PAH|ΣPAH|total\s*PAH|TPAH|Σ\s*PAH|sum\s*PAH", re.I), "Sum_PAH_ngg", "PAHs"),
    (re.compile(r"\bPAH", re.I), "Sum_PAH_ngg", "PAHs"),
    (re.compile(r"∑\s*PCB|total\s*PCB|sum\s*PCB|ΣPCB|total\s*\d+\s*PCB|total\s*indicator", re.I), "SumPCB_ngg", "PCBs"),
    (re.compile(r"\bPCB", re.I), "SumPCB_ngg", "PCBs"),
    (re.compile(r"∑\s*PBDE|total\s*PBDE|ΣPBDE", re.I), "SumPBDE_ngg", "PBDEs"),
    (re.compile(r"\bPBDE|\bBDE", re.I), "SumPBDE_ngg", "PBDEs"),
    (re.compile(r"∑\s*PFAS|total\s*PFAS|ΣPFAS", re.I), "SumPFAS_ngg", "PFAS"),
    (re.compile(r"\bPFAS", re.I), "SumPFAS_ngg", "PFAS"),
    (re.compile(r"∑\s*OCP|total\s*OCP|ΣOCP", re.I), "SumOCP_ngg", "OCPs"),
    (re.compile(r"DDT|∑DDT", re.I), "SumDDTs_ngg", "OCPs"),
    (re.compile(r"HCH|∑HCH", re.I), "SumHCHs_ngg", "OCPs"),
    (re.compile(r"∑\s*PAE|total\s*PAE|phthalate", re.I), "SumPAE_ugkg", "PAEs"),
    (re.compile(r"\bTPH\b|petroleum\s*hydrocarbon|TotalPHC|石油烃", re.I), "TotalPHC_mgkg", "TPH"),
    (re.compile(r"OPFR|organophosphate\s*flame|∑OPFR", re.I), "SumOPFR_ngg", "OPFRs"),
]

UNIT_PAT = re.compile(
    r"(mg\s*[·/.\-]?\s*kg|ng\s*[·/.\-]?\s*g|μg\s*[·/.\-]?\s*kg|ug\s*[·/.\-]?\s*kg|"
    r"mg\s*kg|ng\s*g|ppb|ppm)",
    re.I,
)

# PAH 单体缩写 (EPA 16)
PAH_MONOMER_ABBR = ["nap", "acy", "ace", "fl ", "flu", "phe", "ant", "flt", "pyr",
                    "baa", "chr", "bbf", "bkf", "bap", "ind", "dah", "bghip", "bgp"]

# ===== PAH 16 单体完整识别 (C 级 OP-only 论文核心: PAH 单体转置表) =====
# BaP 特殊: SRS OP_RAW 单独含 BaP_ngg (族群级, 非聚合)
# 其他 15 单体 → Sum_PAH_ngg + is_monomer=True (sample 级聚合为 Sum_PAH)
# 顺序: 长词/特殊优先 (苯并芘先于芘, 苯并荧蒽先于荧蒽), 避免短词误匹配
PAH_MONOMER_PATTERNS = [
    # BaP (族群级)
    (re.compile(r"benzo\s*[\[(]\s*a\s*[\])]\s*pyrene|苯并\s*[\[(]\s*a\s*[\])]\s*芘|苯并芘|\bBaP\b", re.I),
     "BaP", True),
    # 苯并环 (长词先)
    (re.compile(r"benzo\s*[\[(]\s*a\s*[\])]\s*anthracene|苯并\s*[\[(]\s*a\s*[\])]\s*蒽|\bBaA\b|\bBaa\b", re.I), "BaA", False),
    (re.compile(r"benzo\s*[\[(]\s*b\s*[\])]\s*fluoranthene|苯并\s*[\[(]\s*b\s*[\])]\s*荧蒽|\bBbF\b|\bBbf\b", re.I), "BbF", False),
    (re.compile(r"benzo\s*[\[(]\s*k\s*[\])]\s*fluoranthene|苯并\s*[\[(]\s*k\s*[\])]\s*荧蒽|\bBkF\b|\bBkf\b", re.I), "BkF", False),
    (re.compile(r"benzo\s*[\[(]\s*ghi\s*[\])]\s*perylene|苯并\s*[\[(]?\s*ghi\s*[\])]\s*苝|\bBghiP\b|\bBgP\b", re.I), "BghiP", False),
    (re.compile(r"indeno\s*[\[(]\s*1,2,3.?cd\s*[\])]\s*pyrene|茚并\s*[\[(]?\s*1,2,3.?cd\s*[\])]\s*芘|\bIcdP\b|\bInP\b", re.I), "IcdP", False),
    (re.compile(r"dibenzo\s*[\[(]\s*ah\s*[\])]\s*anthracene|二苯并\s*[\[(]?\s*ah\s*[\])]\s*蒽|\bDahA\b|\bDBahA\b", re.I), "DahA", False),
    # 英文全名
    (re.compile(r"\bnaphthalene\b", re.I), "Nap", False),
    (re.compile(r"\bacenaphthylene\b", re.I), "Acy", False),
    (re.compile(r"\bacenaphthene\b", re.I), "Ace", False),
    (re.compile(r"\bfluorene\b", re.I), "Flu", False),
    (re.compile(r"\bphenanthrene\b", re.I), "Phe", False),
    (re.compile(r"\banthracene\b", re.I), "Ant", False),
    (re.compile(r"\bfluoranthene\b", re.I), "Flt", False),
    (re.compile(r"\bpyrene\b", re.I), "Pyr", False),
    (re.compile(r"\bchrysene\b", re.I), "Chr", False),
    # 中文短词 (最后, 避免误伤)
    (re.compile(r"荧蒽"), "Flt", False),
    (re.compile(r"芘"), "Pyr", False),
    (re.compile(r"菲"), "Phe", False),
    (re.compile(r"蒽"), "Ant", False),
    (re.compile(r"屈|䓛"), "Chr", False),
    (re.compile(r"萘"), "Nap", False),
    (re.compile(r"芴"), "Flu", False),
]


def _try_pah_monomer(cleaned: str) -> dict | None:
    """识别 PAH 单体. BaP → BaP_ngg (族群级); 其他 → Sum_PAH_ngg + is_monomer (需聚合)."""
    for pat, abbr, is_bap in PAH_MONOMER_PATTERNS:
        if pat.search(cleaned):
            if is_bap:
                return {"pollutant_std": "BaP_ngg", "family": "PAHs",
                        "is_monomer": False, "monomer_abbr": abbr}
            return {"pollutant_std": "Sum_PAH_ngg", "family": "PAHs",
                    "is_monomer": True, "monomer_abbr": abbr}
    return None


def _aggregate_monomers(records: list) -> list:
    """聚合同 sample_id + 同 pollutant_std 的单体记录为族群.
    若该 sample_id 已有非 monomer 同族群记录 (论文报告 Sum), 优先用非 monomer, 丢弃单体.
    若只有单体, 求和聚合为一条族群记录."""
    if not records:
        return records
    from collections import defaultdict
    by_key = defaultdict(lambda: {"mono": [], "non_mono": []})
    for r in records:
        is_mono = "monomer_needs_aggregation" in (r.get("qa_flag") or "")
        key = (r["sample_id"], r["pollutant_name_std"])
        if is_mono:
            by_key[key]["mono"].append(r)
        else:
            by_key[key]["non_mono"].append(r)
    out = []
    for key, recs in by_key.items():
        if recs["non_mono"]:
            out.extend(recs["non_mono"])
        elif recs["mono"]:
            vals = [r for r in recs["mono"] if r.get("value_std") is not None]
            if not vals:
                out.extend(recs["mono"])
                continue
            summed = sum(r["value_std"] for r in vals)
            base = vals[0].copy()
            base["value_std"] = summed
            base["value_original"] = f"Σ{len(vals)}monomers={summed:.4g}"
            base["qa_flag"] = (base.get("qa_flag") or "").replace(
                "monomer_needs_aggregation", "monomer_aggregated")
            base["extraction_note"] = f"聚合 {len(vals)} 单体求和→{summed:.4g} {base.get('extraction_note','')[:40]}"
            out.append(base)
    return out


def parse_header(col_text_combined: str) -> dict:
    cleaned = clean_latex(col_text_combined)
    low = cleaned.lower()
    is_agg = bool(re.search(r"∑|Σ|total|sum", cleaned, re.I))
    for pat, std, fam in OP_FAMILY_MAP:
        if pat.search(cleaned):
            unit_m = UNIT_PAT.search(low)
            return {"pollutant_std": std, "family": fam,
                    "unit": unit_m.group(1).lower() if unit_m else "",
                    "is_aggregate": is_agg, "confidence": "high" if unit_m else "mid"}
    # PAH 单体 fallback (族群词未匹配, 尝试 16 单体识别 - C 级 PAH 调查核心)
    pah = _try_pah_monomer(cleaned)
    if pah:
        unit_m = UNIT_PAT.search(low)
        return {"pollutant_std": pah["pollutant_std"], "family": "PAHs",
                "unit": unit_m.group(1).lower() if unit_m else "",
                "is_aggregate": not pah["is_monomer"],
                "is_monomer": pah["is_monomer"],
                "monomer_abbr": pah["monomer_abbr"],
                "confidence": "high" if unit_m else "mid"}
    hm_m = HM_ELEMENT_PAT.search(cleaned)
    if hm_m and hm_m.group(1) in HM_MAP:
        unit_m = UNIT_PAT.search(low)
        return {"pollutant_std": HM_MAP[hm_m.group(1)], "family": "HM",
                "unit": unit_m.group(1).lower() if unit_m else "",
                "is_aggregate": False, "confidence": "high" if unit_m else "mid"}
    return {"pollutant_std": None, "family": None, "unit": "", "is_aggregate": False, "confidence": "none"}


# ===== 拒绝规则 =====
# 注意: "plant" 单独用会误伤 "recycling plants" (回收厂), 改用组合词
NON_SOIL_KEYWORDS = [
    "plant tissue", "plant sample", "plant root", "plant shoot", "plant leaf",
    "plant body", "in plant", "of plant", "plants were", "plant species",
    "leaf", "leaves", "root", "stem", "shoot", "maize", "zea mays",
    "wheat", "rice plant", "straw", "grain", "tissue", "crab", "biota", "fish",
    "vegetable", "earthworm", "fly ash", "seed", "kernel",
    "种子", "根", "茎", "叶", "玉米", "小麦", "水稻植株", "蟹", "生物体",
    "飞灰", "籽粒", "草木", "植株", "油菜籽", "籽仁", "皮仁", "谷粒",
    "作物体内", "植物体", "茎叶", "地上部", "地下部", "籽实",
    "ryegrass", "黑麦草", "sorghum", "sudan", "高粱", "苏丹草",
    "苜蓿", "alfalfa", "牧草", "饲料", "地上部分",
]
REFERENCE_COL_KEYWORDS = ["reference", "参考文献", "出处", "来源文献", "data source", "cited", "ref."]
CONTINUOUS_FEATURE_COLS = ["distance", "depth", "age", "year", "elevation", "slope",
                           "ph", "soc", "cec", "longitude", "latitude", "altitude",
                           "precipitation", "temperature", "population", "density"]


def is_reference_table(tbl: pd.DataFrame) -> bool:
    for ci in range(min(tbl.shape[1], 12)):
        for ri in range(min(tbl.shape[0], 3)):
            if any(kw in str(tbl.iloc[ri, ci]).lower() for kw in REFERENCE_COL_KEYWORDS):
                return True
    return False


EXP_KEYWORDS = ["ck ", "ck)", "(ck", "ck\t", "treatment", "处理组", "处理 ",
                "dry weight", "干重", "germination", "发芽率", "biomass",
                "root length", "株高", "shoot biomass", "root biomass",
                "adding amount", "添加量", "spike", "接种",
                # 修复实验信号 (P09208: microbial-plant bioremediation, 土壤调理剂处理组)
                "bioremediation", "bioaugmentation", "biostimulation", "remediation experiment",
                "soil conditioner", "conditioner", "no soil", "urea", "fertilizer",
                "fertilisation", "amendment", "biochar", "compost", "manure",
                "inoculat", "steriliz", "microbial community structure",
                "修复实验", "土壤调理", "改良剂", "尿素", "肥料", "堆肥", "接种",
                # 降解/去除实验 (P11188: BaP degradation rate in pH test group)
                "degradation rate", "降解率", "removal efficiency", "去除率",
                "test group", "试验组", "试验编号",
                # 方法验证: 加标回收率 (P11363: 16种PAHs平均加标回收率)
                "加标回收", "回收率", "recovery", "spike recovery", "standard addition",
                # 毒性当量 (P00355 Table 4 TEQ - 非浓度, 是 BaP 等效毒性加权值, 违反"风险指数≠浓度")
                # 注意: is_non_soil_matrix 用 text.lower(), 关键词必须小写
                "teq", "toxic equivalent", "毒性当量", "bap equivalent", "benzo(a)pyrene equivalent"]
LANDUSE_AGG_WORDS = ["arable", "agricultural", "garden", "forest", "paddy",
                     "upland", "farmland", "woodland", "grassland",
                     "耕地", "园地", "林地", "草地", "稻田", "旱地"]


def is_non_soil_matrix(title: str, tbl_sample: str = "") -> bool:
    text = (title + " " + tbl_sample).lower()
    if any(kw in text for kw in NON_SOIL_KEYWORDS):
        return True
    if any(kw in text for kw in EXP_KEYWORDS):
        return True
    if re.search(r"\bck\b", text):  # CK 对照组 (植物培养实验)
        return True
    return False


def is_landuse_aggregate(tbl: pd.DataFrame, label_col: int, header_row: int) -> bool:
    """检测土地利用汇总表 (P03303: 'Arable land (n=159)' 全国均值, 非场地).
    信号: label 列值是土地利用类型词, 或含 (n=大数字 ≥20)."""
    if label_col < 0 or header_row < 0:
        return False
    vals = [str(tbl.iloc[ri, label_col]).lower()
            for ri in range(header_row + 1, min(header_row + 8, tbl.shape[0]))]
    hits = 0
    for v in vals:
        if any(k in v for k in LANDUSE_AGG_WORDS):
            hits += 1
        m = re.search(r"\bn\s*=\s*(\d+)", v)
        if m and int(m.group(1)) >= 20:
            hits += 1
    return hits >= 2


# ===== 表格类型检测 =====
SUMMARY_KEYWORDS = ["mean", "median", "minimum", "maximum", "average",
                    "标准差", "平均值", "中位", "最小", "最大", "geomean"]
SAMPLE_LABEL_KEYWORDS = ["sample", "site", "地点", "采样点", "样点", "站位",
                         "station", "site type", "land use", "site name",
                         "sample no", "sample type", "plot"]


def is_transposed_table(tbl: pd.DataFrame) -> bool:
    """转置表: 首列含多个污染物单体 (PCB-28/PAH 缩写/BDE-xx)。"""
    if tbl.shape[0] < 4 or tbl.shape[1] < 3:
        return False
    monomer_hits = 0
    for ri in range(min(tbl.shape[0], 20)):
        v = str(tbl.iloc[ri, 0]).lower().strip()
        if re.match(r"^pcb-?\d", v) or re.match(r"^bde-?\d", v):
            monomer_hits += 1
        elif any(v.startswith(a) for a in PAH_MONOMER_ABBR):
            monomer_hits += 1
        elif re.match(r"^(tri|tetra|penta|hexa|hepta|octa)-", v):
            monomer_hits += 1
    return monomer_hits >= 3


def detect_table_type(tbl: pd.DataFrame, data_start: int) -> str:
    if data_start >= tbl.shape[0]:
        return "unknown"
    first_col_vals = [str(tbl.iloc[ri, 0]).lower().strip()
                      for ri in range(data_start, min(data_start + 8, tbl.shape[0]))
                      if str(tbl.iloc[ri, 0]).strip() and str(tbl.iloc[ri, 0]).lower() != "nan"]
    if sum(1 for v in first_col_vals if any(kw in v for kw in SUMMARY_KEYWORDS)) >= 2:
        return "summary"
    return "sample"


def find_header_row(tbl: pd.DataFrame) -> int:
    best_ri, best_score = -1, 0
    for ri in range(min(4, tbl.shape[0])):
        score = 0
        for ci in range(tbl.shape[1]):
            cleaned = clean_latex(str(tbl.iloc[ri, ci]))
            if HM_ELEMENT_PAT.search(cleaned) or any(p.search(cleaned) for p, _, _ in OP_FAMILY_MAP):
                score += 1
            if UNIT_PAT.search(cleaned.lower()):
                score += 1
        if score > best_score:
            best_score, best_ri = score, ri
    return best_ri if best_score >= 2 else -1


def find_label_column(tbl: pd.DataFrame, header_row: int, exclude_cols: set = None) -> int:
    """选 sample/site 标签列, 优先唯一性高 (非合并单元格)。"""
    exclude_cols = exclude_cols or set()
    candidates = []
    for ci in range(min(tbl.shape[1], 12)):
        if ci in exclude_cols:
            continue
        cells = [str(tbl.iloc[ri, ci]).lower() for ri in range(header_row, min(header_row + 2, tbl.shape[0]))]
        joined = " ".join(cells)
        if any(kw in joined for kw in SAMPLE_LABEL_KEYWORDS) and not any(c in joined for c in CONTINUOUS_FEATURE_COLS):
            data_vals = [str(tbl.iloc[ri, ci]) for ri in range(header_row + 1, tbl.shape[0])]
            unique = len(set(v for v in data_vals if v and v.lower() != "nan"))
            candidates.append((ci, unique))
    if candidates:
        candidates.sort(key=lambda x: -x[1])
        return candidates[0][0]
    return 0


# ===== 数值解析 =====
def _join_digits(s: str) -> str:
    return re.sub(r"(?<=\d)\s+(?=\d)", "", s)


def parse_value(raw) -> tuple:
    if raw is None:
        return None, "missing", "None"
    s = str(raw).strip()
    if s.lower() in ("nan", "none", "", "/", "-", "—", "--"):
        return None, "missing", f"空值/{s}"
    if re.match(r"^(nd|n\.d\.?|not detected|<dl|bdl|nr)$", s, re.I):
        return None, "below_detection", f"未检出 {s}"
    pm = re.search(r"([\d][\d.\s ]*?)\s*\\?pm\s*([\d][\d.\s ]*)", s)
    if pm:
        try:
            return float(_join_digits(pm.group(1).strip())), "mean_with_sd", \
                   f"均值±SD: {_join_digits(pm.group(1))}±{_join_digits(pm.group(2))}"
        except ValueError:
            pass
    m = re.match(r"^[<≤]\s*([\d.]+)$", s)
    if m:
        try:
            return float(m.group(1)), "below_detection", f"<检出限 {s}"
        except ValueError:
            pass
    m = re.match(r"^([\d.]+)\s*[~\-–]\s*([\d.]+)$", s)
    if m:
        try:
            lo, hi = float(m.group(1)), float(m.group(2))
            return (lo + hi) / 2, "range_avg", f"范围 {s} 取均值"
        except ValueError:
            pass
    cleaned = _join_digits(s).replace(" ", "")
    try:
        v = float(cleaned)
        flag, note = "", ""
        if v == 1 and re.match(r"^1$", cleaned):
            flag, note = "value_is_1_suspicious", "MinerU 合并单元格可能误读为 1"
        return v, flag, note
    except ValueError:
        return None, "non_numeric", f"非数值 {s[:25]}"


def _unit_from_title(title: str, pollutant_std: str) -> str:
    """从表标题提取单位。MinerU 常丢 μ 头, -g/kg → μg/kg。"""
    low = (title or "").lower()
    if "μg/kg" in low or "ug/kg" in low or "µg/kg" in low or "μg kg" in low or "(μg" in low or "-g/kg" in low or "μgkg" in low:
        return "ug/kg"
    if "ng/g" in low or "ng g" in low or "ngg" in low or "(ng" in low:
        return "ng/g"
    if "mg/kg" in low or "mg kg" in low or "mgkg" in low or "(mg" in low or "mg·kg" in low:
        return "mg/kg"
    if pollutant_std.endswith("_mgkg"):
        return "mg/kg"
    if pollutant_std.endswith("_ngg"):
        return "ng/g"
    if pollutant_std.endswith("_ugkg"):
        return "ug/kg"
    return ""


def _build_record(paper_info, stem, tbl_idx, ri, ci, spec, raw_val,
                  value, censoring, parse_note, tbl, header_row,
                  sample_id, site_label, evidence, pollution_type_table):
    target_unit = ("mg/kg" if spec["pollutant_std"].endswith("_mgkg")
                   else "ng/g" if spec["pollutant_std"].endswith("_ngg")
                   else "ug/kg" if spec["pollutant_std"].endswith("_ugkg")
                   else spec["unit"])
    value_std, conv_note, qa = (convert_value(value, spec["unit"] or "unknown", target_unit)
                                if value is not None else (None, "", "missing"))
    qa_flags = []
    if qa:
        qa_flags.append(qa)
    if spec["pollutant_std"] == "SumOPFR_ngg":
        qa_flags.append("opfr_not_in_v0.8_op_raw")
    if censoring == "value_is_1_suspicious":
        qa_flags.append("value_is_1_suspicious")
    if spec.get("is_monomer"):
        qa_flags.append("monomer_needs_aggregation")
    return {
        "source_id": paper_info.get("doi") or paper_info["paper_id"],
        "paper_id": paper_info["paper_id"], "doi": paper_info.get("doi", ""),
        "title": paper_info.get("title", "")[:120], "year": paper_info.get("year", ""),
        "province": paper_info.get("province", ""), "city_or_region": paper_info.get("city_or_region", ""),
        "site_name": site_label, "land_use": paper_info.get("land_use", "other"),
        "sample_id": sample_id, "sampling_depth_cm": "", "latitude": "", "longitude": "",
        "pollution_type": pollution_type_table, "pollutant_family": spec["family"],
        "pollutant_name_original": str(spec.get("raw_name", ""))[:50],
        "pollutant_name_std": spec["pollutant_std"],
        "value_original": str(raw_val)[:30], "unit_original": spec["unit"],
        "value_std": value_std, "unit_std": target_unit, "conversion_note": conv_note,
        "censoring_flag": censoring if censoring else "measured", "detection_limit": "",
        "evidence_level": evidence,
        "evidence_location": f"{stem}/parsed/paper.md tbl#{tbl_idx} row{ri} col{ci}",
        "extraction_note": f"hdr='{clean_latex(str(spec.get('raw_name','')))[:30]}' {parse_note} {spec['confidence']}",
        "qa_flag": ";".join(qa_flags),
    }


# ===== 转置表抽取 =====
def extract_transposed(tbl: pd.DataFrame, title: str, paper_info: dict, stem: str, tbl_idx: int) -> tuple:
    """转置表: 行=污染物单体, 列=采样点。优先抽 Total/Sum 行作族群汇总。"""
    n_rows, n_cols = tbl.shape
    # 找表头 (含 Compound/congener 的行)
    header_row = 0
    for ri in range(min(4, n_rows)):
        v = str(tbl.iloc[ri, 0]).lower()
        if any(k in v for k in ["compound", "congener", "pollutant", "污染物", "种类"]):
            header_row = ri
            break
    # 采样点编号行 = header_row + 1
    sample_row = header_row + 1
    if sample_row >= n_rows:
        return [], "transposed_no_sample_row", "无采样点编号行"

    # 检测转置表类型:
    # 类型 A (P01524): sample_row 是采样点编号行 (col0=编号/S1), 数据从 sample_row+1
    # 类型 B (P00355): sample_row 实际是首个单体数据行 (col0=Naphthalene/PCB-28),
    #                 采样点列名在 header_row (表头行)
    src0_clean = clean_latex(str(tbl.iloc[sample_row, 0]))
    src0_low = src0_clean.lower().strip()
    is_type_b = bool(_try_pah_monomer(src0_clean)) or \
                bool(re.match(r"^pcb-?\d|^bde-?\d", src0_low))
    if is_type_b:
        sample_label_row = header_row
        data_start = sample_row
    else:
        sample_label_row = sample_row
        data_start = sample_row + 1

    unit = _unit_from_title(title, "SumPCB_ngg")
    # 找所有可识别的污染物行 (Total/Sum 优先, 单体次之)
    pollutant_rows = []  # [(ri, spec)]
    for ri in range(data_start, n_rows):
        raw_name = str(tbl.iloc[ri, 0])
        if not raw_name.strip() or raw_name.lower() == "nan":
            continue
        # 先用 parse_header (识别 Total PCBs/∑PAH 等)
        spec = parse_header(raw_name)
        is_total = bool(re.search(r"total|∑|sum|Σ", raw_name, re.I))
        if spec["pollutant_std"] and is_total:
            spec["raw_name"] = raw_name
            spec["unit"] = spec["unit"] or unit
            spec["is_monomer"] = False
            pollutant_rows.append((ri, spec, True))  # True=total行
        elif spec["pollutant_std"] and not is_total:
            # 单体行 (如 PCB-28, PCB-52) - 记录但标记需聚合
            spec["raw_name"] = raw_name
            spec["unit"] = spec["unit"] or unit
            spec["is_monomer"] = True
            pollutant_rows.append((ri, spec, False))

    if not pollutant_rows:
        return [], "transposed_no_pollutant", "转置表无可识别污染物行"

    # 若有 Total 行, 只用 Total (避免单体重复); 否则用全部单体
    total_rows = [r for r in pollutant_rows if r[2]]
    use_rows = total_rows if total_rows else pollutant_rows

    records = []
    pollution_type = "OP"  # 转置表默认 OP (PCB/PAH 单体)
    sample_cols_used = 0
    for ci in range(1, n_cols):
        sample_label = str(tbl.iloc[sample_label_row, ci]).strip()
        if not sample_label or sample_label.lower() == "nan":
            continue
        sample_cols_used += 1
        sample_id = f"{paper_info['paper_id']}_tr{ci}_{re.sub(r'[^A-Za-z0-9一-鿿]', '', sample_label)[:15]}"
        for ri, spec, is_total in use_rows:
            raw_val = tbl.iloc[ri, ci]
            value, censoring, parse_note = parse_value(raw_val)
            if value is None and censoring in ("missing", "non_numeric"):
                continue
            records.append(_build_record(
                paper_info, stem, tbl_idx, ri, ci, spec, raw_val,
                value, censoring, parse_note, tbl, header_row,
                sample_id, f"{sample_label} ({title[:30]})",
                "A_sample_table", pollution_type))

    if not records:
        return [], "transposed_no_data", f"无有效数值 (rows={len(use_rows)} cols={sample_cols_used})"
    fam_set = set(r[1]["family"] for r in use_rows)
    n_pre = len(records)
    records = _aggregate_monomers(records)
    return records, "ok_transposed", f"转置表 {len(use_rows)}污染物 × {sample_cols_used}采样点 = {n_pre}条→聚合{len(records)} family={fam_set}"


# ===== 正常表抽取 =====
def extract_table(tbl: pd.DataFrame, title: str, paper_info: dict, stem: str, tbl_idx: int) -> tuple:
    n_rows, n_cols = tbl.shape
    if n_rows < 3 or n_cols < 2:
        return [], "skip_too_small", f"{n_rows}x{n_cols}"
    if is_reference_table(tbl):
        return [], "reject_reference_compilation", "有 References 列, 二手文献对比表"
    # 非土壤: 检查 title + 表格内容 (治 P11676 植物实验 title 被截断的漏检)
    tbl_head_text = tbl.head(10).to_string(index=False, header=False).lower()[:700]
    if is_non_soil_matrix(title, tbl_head_text):
        return [], "reject_non_soil_matrix", "非土壤基质 (植物/实验/生物/飞灰)"

    # 转置表分流 (污染物作行)
    if is_transposed_table(tbl):
        return extract_transposed(tbl, title, paper_info, stem, tbl_idx)

    header_row = find_header_row(tbl)
    if header_row < 0:
        return [], "no_header", "未找到含污染物信号的表头行"

    col_specs = {}
    for ci in range(n_cols):
        header_text = f"{tbl.columns[ci]} {tbl.iloc[header_row, ci]}"
        if header_row + 1 < n_rows:
            header_text += f" {tbl.iloc[header_row + 1, ci]}"
        spec = parse_header(header_text)
        spec["raw_name"] = f"{tbl.columns[ci]} {tbl.iloc[header_row, ci]}"
        if spec["pollutant_std"] and spec["pollutant_std"] not in [s["pollutant_std"] for s in col_specs.values()]:
            col_specs[ci] = spec
    if not col_specs:
        return [], "no_pollutant_columns", "无列可解析为污染物"

    data_start = header_row + 1
    if header_row + 1 < n_rows:
        row_after = " ".join(str(tbl.iloc[header_row + 1, ci]).lower() for ci in range(n_cols))
        if any(u in row_after for u in ["mg/kg", "ng/g", "μg/kg", "mg·kg", "(mg", "(ng"]):
            data_start = header_row + 2

    table_type = detect_table_type(tbl, data_start)
    has_hm = any(s["family"] == "HM" for s in col_specs.values())
    has_op = any(s["family"] != "HM" for s in col_specs.values())
    pollution_type_table = "HM_OP" if (has_hm and has_op) else ("HM" if has_hm else "OP")
    records = []

    if table_type == "summary":
        mean_ri = -1
        for ri in range(data_start, n_rows):
            v = str(tbl.iloc[ri, 0]).lower()
            if "mean" in v or "average" in v or "平均值" in v:
                mean_ri = ri
                break
        if mean_ri < 0:
            return [], "no_mean_row", "summary 表无 Mean 行"
        sample_id = f"{paper_info['paper_id']}_mean"
        for ci, spec in col_specs.items():
            value, censoring, parse_note = parse_value(tbl.iloc[mean_ri, ci])
            if value is None and censoring in ("missing", "non_numeric"):
                continue
            records.append(_build_record(paper_info, stem, tbl_idx, mean_ri, ci, spec,
                                         tbl.iloc[mean_ri, ci], value, censoring, parse_note,
                                         tbl, header_row, sample_id, "site_mean_summary",
                                         "B_site_summary", pollution_type_table))
        records = _aggregate_monomers(records)
        return records, "ok_summary", f"summary Mean, {len(records)}条, type={pollution_type_table}"

    label_col = find_label_column(tbl, header_row, exclude_cols=set(col_specs.keys()))
    # 土地利用汇总检测 (P03303: Arable land (n=159) 全国均值, 违反"不把全省均值当场地")
    if is_landuse_aggregate(tbl, label_col, header_row):
        return [], "reject_landuse_aggregate", "土地利用类型汇总 (全国/全省均值, 非场地采样点)"
    sample_count = 0
    for ri in range(data_start, n_rows):
        first_val = str(tbl.iloc[ri, label_col]) if label_col >= 0 else ""
        low_fv = first_val.lower().strip()
        if not low_fv or low_fv == "nan":
            continue
        if any(kw in low_fv for kw in ["total", "sum", "∑", "合计", "平均值", "mean", "median"]):
            continue
        row_label = re.sub(r"[^\w一-鿿\-\.]", "_", first_val)[:25]
        sample_id = f"{paper_info['paper_id']}_s{ri}_{row_label}"
        sample_count += 1
        for ci, spec in col_specs.items():
            value, censoring, parse_note = parse_value(tbl.iloc[ri, ci])
            if value is None and censoring in ("missing", "non_numeric"):
                continue
            records.append(_build_record(paper_info, stem, tbl_idx, ri, ci, spec,
                                         tbl.iloc[ri, ci], value, censoring, parse_note,
                                         tbl, header_row, sample_id, first_val[:30],
                                         "A_sample_table", pollution_type_table))
    if not records:
        return [], "no_data_rows", f"type={table_type} samples=0"
    records = _aggregate_monomers(records)
    return records, "ok_samples", f"sample {sample_count}点, {len(records)}条, type={pollution_type_table}"


def main():
    cand = pd.read_csv(OUT_DIR / "candidate_literature_op_hmop.csv", dtype=str, keep_default_na=False)
    cand_idx = {r["paper_id"]: r for _, r in cand.iterrows()}
    clf = pd.read_csv(OUT_DIR / "p2_tables_classified.csv", dtype=str, keep_default_na=False)
    # v3: sample_conc + summary_conc + conc_like + other(有 has_hm/has_op 信号的转置候选)
    target = clf[clf["category"].isin(["sample_conc", "summary_conc", "conc_like"])].copy()
    # 补充 other 类但 has_hm+has_op 的表 (可能是转置表漏分类)
    other_compound = clf[(clf["category"] == "other") & (clf["has_hm"] == "True") & (clf["has_op"] == "True")]
    target = pd.concat([target, other_compound], ignore_index=True)
    print(f"待抽取表格: {len(target)} (含 {len(other_compound)} 个 other+HM+OP 转置候选)")

    all_records, log_rows = [], []
    for _, tr in target.iterrows():
        pid, stem, tbl_idx = tr["paper_id"], tr["stem"], int(tr["tbl_idx"])
        md = LIT_ROOT / stem / "parsed" / "paper.md"
        if not md.exists():
            log_rows.append({**tr.to_dict(), "extract_status": "md_missing", "extract_note": ""})
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
            tables = pd.read_html(StringIO(text))
        except Exception as e:
            log_rows.append({**tr.to_dict(), "extract_status": "parse_err", "extract_note": str(e)[:50]})
            continue
        if tbl_idx >= len(tables):
            log_rows.append({**tr.to_dict(), "extract_status": "tbl_idx_oor", "extract_note": ""})
            continue
        paper_row = cand_idx.get(pid, {})
        paper_info = {
            "paper_id": pid, "doi": paper_row.get("doi", ""),
            "title": paper_row.get("title", ""), "year": paper_row.get("year", ""),
            "province": "", "city_or_region": "", "site_name": paper_row.get("region", ""),
            "land_use": classify_landuse(stem + " " + paper_row.get("title", "")),
        }
        records, status, note = extract_table(tables[tbl_idx], tr["title"], paper_info, stem, tbl_idx)
        all_records.extend(records)
        log_rows.append({**tr.to_dict(), "extract_status": status, "extract_note": note[:110]})

    df_out = pd.DataFrame(all_records)
    out_path = OUT_DIR / "extracted_observations_long_op_hmop.csv"
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    df_log = pd.DataFrame(log_rows)
    df_log.to_csv(OUT_DIR / "p2_extraction_log.csv", index=False, encoding="utf-8-sig")

    print(f"\n=== P2 v3 抽取结果 ===")
    print(f"总观测: {len(df_out)}, 论文: {df_out['paper_id'].nunique() if len(df_out) else 0}")
    if len(df_out):
        valid = df_out[(df_out["value_std"].notna()) & (df_out["value_std"] != "") & (df_out["censoring_flag"] != "non_numeric")]
        print(f"有效数值观测: {len(valid)}")
        print(f"\nevidence_level:"); print(df_out["evidence_level"].value_counts().to_string())
        print(f"\npollution_type:"); print(df_out["pollution_type"].value_counts().to_string())
        print(f"\npollutant_name_std:"); print(df_out["pollutant_name_std"].value_counts().to_string())
        print(f"\n按 sample_id 配对的 HM_OP (P3 预演):")
        sample_fam = df_out.groupby("sample_id")["pollutant_family"].apply(lambda x: set(x))
        hm_op = [sid for sid, f in sample_fam.items() if "HM" in f and len(f - {"HM"}) > 0]
        print(f"  真 HM_OP sample_id: {len(hm_op)}")
        print(f"  涉及论文: {df_out[df_out['sample_id'].isin(hm_op)]['paper_id'].nunique()}")
        print(f"\n抽取日志:"); print(df_log["extract_status"].value_counts().to_string())
    print(f"\n输出: {out_path}")


if __name__ == "__main__":
    main()
