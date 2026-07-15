"""SRS 文献挖掘 - 共享工具模块 (P0)

职责:
1. catalog CSV 读取 (含 NULL 字节 \\0 清理, F10)
2. stem → 文件物理路径映射 (pathlib 原生 UTF-8, 不经 Git Bash 管道)
3. 单位换算 (HM→mg/kg, PAHs→ng/g, 族群按 build_gold_dataset.py op_raw 后缀)
4. OP/HM/理化 因子规范名清单 (对齐 build_gold_dataset.py:371-384)
5. land_use 细分类 (裴总枚举 12 类)
6. PowerShell 调用封装 (规避 Git Bash 大括号陷阱)
7. 可选复用 SRS standardize.py (province/landuse/unit 归一)

设计原则 (Karpathy):
- 不假设, 不臆造, 不确定保留原值 + qa_flag
- 纯 python, 可独立测试
- 所有路径用 pathlib.Path, 不经 Git Bash 管道 (规避中文乱码)
"""
from __future__ import annotations
import sys
import re
import subprocess
from pathlib import Path

# ===== 路径常量 =====
SRS_ROOT = Path(r"C:\Users\曾鸿\Desktop\SRS")
LIT_ROOT = Path(r"G:\文献整理_最终")
CATALOG_CSV = LIT_ROOT / "文献目录_literature_catalog.csv"
OUT_DIR = SRS_ROOT / "outputs" / "literature_mining"
SCRIPTS_DIR = OUT_DIR / "_scripts"

# ===== 可选复用 SRS standardize.py =====
_HAS_STD = False
_STD_ERR = ""
try:
    sys.path.insert(0, str(SRS_ROOT))
    from ml.cleaning.standardize import (  # type: ignore
        normalize_province as _std_prov,
        normalize_landuse as _std_landuse,
        normalize_unit as _std_unit,
        normalize_pollution_type as _std_ptype,
    )
    _HAS_STD = True
except Exception as e:  # noqa: BLE001
    _HAS_STD = False
    _STD_ERR = f"{type(e).__name__}: {e}"


# ===== 内置 fallback (standardize 不可用时) =====
_EN2CN_FALLBACK = {
    "guangdong": "广东", "zhejiang": "浙江", "jiangsu": "江苏", "beijing": "北京",
    "shandong": "山东", "liaoning": "辽宁", "hunan": "湖南", "hubei": "湖北",
    "henan": "河南", "sichuan": "四川", "jiangxi": "江西", "shaanxi": "陕西",
    "shanxi": "山西", "hebei": "河北", "tianjin": "天津", "shanghai": "上海",
    "chongqing": "重庆", "yunnan": "云南", "guizhou": "贵州", "fujian": "福建",
    "anhui": "安徽", "heilongjiang": "黑龙江", "jilin": "吉林", "liaoning": "辽宁",
}


def _normalize_unit_fallback(raw) -> str:
    """standardize 不可用时的简易单位归一。"""
    if raw is None:
        return "Unknown"
    s = str(raw).strip()
    if not s:
        return "Unknown"
    low = (s.lower().replace("μ", "u").replace("µ", "u")
           .replace(" ", "").replace("·", "").replace("_", ""))
    low = low.replace("kg-1", "/kg").replace("g-1", "/g")
    aliases = {
        "mg/kg": "mg/kg", "mgkg": "mg/kg", "mg/kgdw": "mg/kg",
        "ng/g": "ng/g", "ngg": "ng/g", "ng/gdw": "ng/g",
        "ug/kg": "ug/kg", "μg/kg": "ug/kg", "ugkg": "ug/kg",
        "g/kg": "g/kg", "gkg": "g/kg", "%": "%",
        "cmol/kg": "cmol/kg", "cmolkg": "cmol/kg",
    }
    return aliases.get(low, s)


def normalize_province(raw) -> str:
    if _HAS_STD:
        return _std_prov(raw)
    if raw is None:
        return "Unknown"
    s = str(raw).strip()
    if not s:
        return "Unknown"
    low = s.lower().replace(" province", "").strip()
    if low in _EN2CN_FALLBACK:
        return _EN2CN_FALLBACK[low]
    return s


def normalize_unit(raw) -> str:
    return _std_unit(raw) if _HAS_STD else _normalize_unit_fallback(raw)


# ===== catalog 读取 =====
def load_catalog():
    """读 catalog CSV, 清理 NULL 字节 \\0 (F10)。返回 DataFrame (全 str)。"""
    import pandas as pd
    from io import BytesIO
    raw = CATALOG_CSV.read_bytes()
    cleaned = raw.replace(b"\x00", b"")  # 清理 NULL 字节
    df = pd.read_csv(BytesIO(cleaned), encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return df


def stem_to_paths(stem: str) -> dict:
    """stem → 文献物理路径字典。不检查存在性。"""
    root = LIT_ROOT / stem
    return {
        "root": root,
        "paper_pdf": root / "paper.pdf",
        "metadata_json": root / "metadata.json",
        "paper_md": root / "parsed" / "paper.md",
        "images_dir": root / "parsed" / "images",
    }


def resolve_stem_path(stem: str) -> Path:
    """resolve stem 到真实目录 Path, 校验存在。不存在抛 FileNotFoundError。"""
    p = LIT_ROOT / stem
    if not p.exists():
        # 尝试大小写/首字母变体
        candidates = list(LIT_ROOT.glob(f"*{stem[:20]}*"))
        if candidates:
            return candidates[0]
        raise FileNotFoundError(f"stem 目录不存在: {p}")
    return p


# ===== 因子规范名清单 (对齐 build_gold_dataset.py:371-384) =====
# HM_OP 判定: 同一 sample_id 的 wide format 列名必须命中以下清单
HM_RAW = ["Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cr_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg"]
OP_RAW = ["Sum_PAH_ngg", "BaP_ngg", "SumDDTs_ngg", "SumHCHs_ngg", "SumOCP_ngg",
          "SumPCB_ngg", "SumPBDE_ngg", "SumPFAS_ngg", "SumPAE_ugkg", "TotalPHC_mgkg"]

# US EPA 16 PAH 单体 (规范名 _ngg) - 抽取单体后可聚合为 Sum_PAH_ngg
PAH_MONOMERS_NGG = ["Nap_ngg", "Acy_ngg", "Ace_ngg", "Flu_ngg", "Phe_ngg", "Ant_ngg",
                    "Flt_ngg", "Pyr_ngg", "BaA_ngg", "Chr_ngg", "BbF_ngg", "BkF_ngg",
                    "BaP_ngg", "Ind_ngg", "DahA_ngg", "BghiP_ngg"]

# HM 扩展 (model_feature_dictionary 有, 但 hm_raw 不含; 可抽但不直接触发 hm_signal)
HM_EXTENDED = ["Co_mgkg", "V_mgkg", "Sb_mgkg", "Be_mgkg", "Mn_mgkg", "Al_mgkg", "Fe_mgkg"]

# 理化特征
SOIL_PHYS_CHEM = ["pH", "SoilBD_gcm3", "OC_pct", "OM_pct", "TN_gkg", "TP_gkg", "TK_gkg",
                  "AN_mgkg", "AP_mgkg", "AK_mgkg", "EC_mScm", "CEC_cmolkg",
                  "Clay_pct", "Sand_pct", "Silt_pct"]

# TPH 别名 (SRS 体系命名分裂, common.py 两个都认)
TPH_ALIASES = ["TotalPHC_mgkg", "TPH_ngg", "TPH_mgkg", "PetroleumHC_mgkg"]


# ===== 单位换算 =====
TARGET_UNIT = {}
for h in HM_RAW + HM_EXTENDED:
    TARGET_UNIT[h] = "mg/kg"
for p in PAH_MONOMERS_NGG:
    TARGET_UNIT[p] = "ng/g"
for o in OP_RAW:
    if o.endswith("_mgkg"):
        TARGET_UNIT[o] = "mg/kg"
    elif o.endswith("_ugkg"):
        TARGET_UNIT[o] = "ug/kg"
    else:
        TARGET_UNIT[o] = "ng/g"
TARGET_UNIT["TPH_ngg"] = "ng/g"
TARGET_UNIT.update({
    "pH": "-", "SoilBD_gcm3": "g/cm3", "OC_pct": "%", "OM_pct": "%",
    "TN_gkg": "g/kg", "TP_gkg": "g/kg", "TK_gkg": "g/kg",
    "AN_mgkg": "mg/kg", "AP_mgkg": "mg/kg", "AK_mgkg": "mg/kg",
    "EC_mScm": "mS/cm", "CEC_cmolkg": "cmol/kg",
})

# (from_unit, to_unit) → multiplier ; value_std = value_original × multiplier
UNIT_MULTIPLIER = {
    # → mg/kg
    ("mg/kg", "mg/kg"): 1.0, ("ug/kg", "mg/kg"): 0.001, ("ng/g", "mg/kg"): 0.001,
    ("ug/g", "mg/kg"): 1.0, ("ppm", "mg/kg"): 1.0,
    # → ng/g
    ("ng/g", "ng/g"): 1.0, ("ug/kg", "ng/g"): 1.0, ("mg/kg", "ng/g"): 1000.0,
    ("pg/g", "ng/g"): 0.001, ("ppt", "ng/g"): 0.001, ("ppb", "ng/g"): 1.0,
    # → ug/kg
    ("ug/kg", "ug/kg"): 1.0, ("ng/g", "ug/kg"): 1.0, ("mg/kg", "ug/kg"): 1000.0,
    # → g/kg
    ("g/kg", "g/kg"): 1.0, ("mg/kg", "g/kg"): 0.001, ("%", "g/kg"): 10.0,
    # → %
    ("%", "%"): 1.0, ("g/kg", "%"): 0.1, ("mg/kg", "%"): 0.0001,
    # → cmol/kg
    ("cmol/kg", "cmol/kg"): 1.0,
    # → g/cm3
    ("g/cm3", "g/cm3"): 1.0, ("mg/cm3", "g/cm3"): 0.001,
    # → mS/cm
    ("mS/cm", "mS/cm"): 1.0, ("us/cm", "mS/cm"): 0.001,
    # → -
    ("-", "-"): 1.0,
}


def convert_value(value_original, unit_original, target_unit):
    """单位换算。返回 (value_std, conversion_note, qa_flag)。

    不确定保留原值, qa_flag=unit_uncertain (绝不猜)。
    """
    if value_original is None or unit_original is None or target_unit is None:
        return None, "", "missing_input"
    if target_unit == "-":
        # 无量纲 (如 pH)
        try:
            return float(value_original), f"无量纲: {value_original} {unit_original}", ""
        except (ValueError, TypeError):
            return None, "", "value_not_numeric"
    try:
        v = float(value_original)
    except (ValueError, TypeError):
        return None, "", "value_not_numeric"

    uo = normalize_unit(unit_original)
    key = (uo, target_unit)
    if key in UNIT_MULTIPLIER:
        m = UNIT_MULTIPLIER[key]
        if m == 1.0 and uo == target_unit:
            note = f"{value_original} {unit_original} (已是 {target_unit})"
        elif m == 1.0:
            note = f"{value_original} {unit_original} → {target_unit} (同量级, 写法归一)"
        else:
            note = f"{value_original} {unit_original} × {m} = {round(v*m,6)} {target_unit}"
        return round(v * m, 6), note, ""
    if uo == target_unit:
        return v, f"{value_original} {unit_original} (写法已归一)", ""
    return v, f"未换算: {unit_original}→{target_unit} 无规则, 保留原值", "unit_uncertain"


# ===== land_use 细分类 (裴总枚举 12 类) =====
LANDUSE_RULES = [
    ("water_level_fluctuation_zone", ["water level fluctuation", "water-level fluctuation",
                                       "WLF", "riparian reservoir", "消落带", "水位波动",
                                       "三峡", "库区", "hydro-fluctuation"]),
    ("riparian", ["riparian", "河岸", "滨河", "floodplain"]),
    ("agricultural", ["agricultur", "farmland", "paddy", "cropland", "农田", "耕地",
                      "农用地", "水稻土", "园地", "蔬菜"]),
    ("urban_green", ["green space", "greenland", "绿地", "urban soil", "城市土壤"]),
    ("roadside", ["roadside", "street soil", "道路", "公路", "traffic"]),
    ("park", ["park soil", "园林"]),
    ("industrial", ["industr", "工厂", "工业", "abandoned", "遗留地", "brownfield",
                    "棕地", "redevelop"]),
    ("mining", ["mining", "mine", "矿", "tailings", "尾矿", "slag"]),
    ("e_waste", ["e-waste", "electronic waste", "电子垃圾", "电子废弃物", "Taizhou", "贵屿"]),
    ("oilfield", ["oilfield", "oil field", "petroleum contam", "油田", "石化", "石油污染", "Shengli"]),
    ("coking", ["coking", "coke", "焦化", "焦化厂", "coal tar"]),
    ("other", []),
]


def classify_landuse(text: str) -> str:
    """文本 → land_use 枚举。命中第一个规则返回。"""
    if not text:
        return "other"
    s = str(text).lower()
    for label, kws in LANDUSE_RULES:
        if any(kw.lower() in s for kw in kws):
            return label
    return "other"


# ===== PowerShell 调用封装 (规避 Git Bash 大括号陷阱) =====
def powershell(command: str, timeout: int = 60) -> str:
    """调用 PowerShell。command 不应含 {} (会被 Git Bash 误解析)。

    用 -LiteralPath 处理中文/特殊字符路径。返回 stdout (utf-8)。
    """
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True, text=True, timeout=timeout, encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return f"[ERROR {result.returncode}] {result.stderr.strip()}"
    return result.stdout


# ===== 裴总 14 强候选 (题名片段 + DOI) =====
STRONG_CANDIDATE_TITLES = [
    "Heavy metals and PAHs drive ecological and health risks in Chinese water level fluctuation zones",
    "Pollution Characteristics and Evaluation of Heavy Metals and Polycyclic Aromatic Hydrocarbons in Agricultural Land of Qinhuangdao",
    "Polycyclic aromatic hydrocarbons and heavy metals in urban environments",
    "Distribution characteristics and health risk assessment of heavy metals and PAHs in the soils of green spaces in Shanghai",
    "Organophosphate Flame Retardants in Soils of Zhejiang Province",
    "Phthalates in residential and agricultural soils from an electronic waste-polluted region in South China",
    "PBDEs in soil and dust from plastic production and surrounding areas in eastern China",
    "PAHs in urban soils from Shenyang",
    "PAHs in abandoned industrial",
]
STRONG_CANDIDATE_DOIS = [
    "10.1016/j.jhazmat.2025.140728",
    "10.1002/ldr.3456",
    "10.1007/s10661-019-7476-2",
    "10.1007/s00244-019-00675-0",
    "10.1007/s11356-019-04669-2",
]


def is_strong_candidate(title: str, doi: str) -> bool:
    """裴总 14 强候选匹配 (题名子串 + DOI)。"""
    t = (title or "").lower()
    d = (doi or "").lower().strip()
    for tt in STRONG_CANDIDATE_TITLES:
        if tt.lower() in t:
            return True
    for dd in STRONG_CANDIDATE_DOIS:
        if dd.lower() in d:
            return True
    return False


# ===== 关键词正则 (P1 筛选) =====
OP_KEYWORDS = re.compile(
    r"PAH|多环芳烃|PCB|多氯联苯|PBDE|多溴|PFAS|全氟|PAE|phthalate|邻苯二甲酸|"
    r"OCP|DDT|HCH|六六六|TPH|petroleum hydrocarbon|石油烃|OPFR|有机磷阻燃|"
    r"emerging organic|chlorinated pesticide|有机氯|"
    r"organic pollut|organic contamin|有机污染物|有机污染",
    re.IGNORECASE,
)
HM_KEYWORDS = re.compile(
    r"(?:^|\W)(Cd|Pb|As|Hg|Cr|Cu|Zn|Ni|Co|Sb|Mn)(?:\W|$)|重金属|heavy metal",
    re.IGNORECASE,
)
COMPOUND_KEYWORDS = re.compile(
    r"heavy metal.{0,40}(?:PAH|多环芳烃|PCB|PBDE|PFAS|PAE|TPH|petroleum)|"
    r"(?:PAH|多环芳烃|PCB|PBDE|PFAS|PAE|TPH|petroleum).{0,40}heavy metal|"
    r"co-contaminat|combined risk|joint risk|复合污染|联合风险|协同风险|"
    r"重金属.{0,20}(?:PAH|多环芳烃)|(?:PAH|多环芳烃).{0,20}重金属",
    re.IGNORECASE,
)


# ===== 长格式 schema (对齐 clean_observations_long_v0.8.csv 28 列) =====
LONG_FORMAT_COLUMNS = [
    "sample_id", "site_id", "source_id", "province", "region", "pollution_type",
    "sampling_time", "factor_id", "factor_name_cn", "track", "data_role",
    "value_original", "value_std", "unit_original", "unit_std", "raw_value_text",
    "censoring_flag", "detection_limit", "selected_column", "source_columns",
    "is_measured", "is_family_aggregate", "is_proxy", "is_missing", "coverage_pct",
    "evidence_level", "reliability_weight",
    # 裴总任务额外字段 (并入训练前可剥离)
    "paper_id", "doi", "title", "year", "city_or_region", "site_name",
    "land_use", "sample_label", "sampling_depth_cm", "latitude", "longitude",
    "pollutant_family", "pollutant_name_original", "conversion_note",
    "evidence_location", "extraction_note", "qa_flag",
]


if __name__ == "__main__":
    print("=" * 60)
    print("common.py 自检")
    print("=" * 60)
    print(f"SRS_ROOT exists: {SRS_ROOT.exists()}")
    print(f"LIT_ROOT exists: {LIT_ROOT.exists()}")
    print(f"CATALOG_CSV exists: {CATALOG_CSV.exists()}")
    print(f"HAS_STANDARDIZE: {_HAS_STD}" + (f" (err: {_STD_ERR})" if not _HAS_STD else ""))

    cat = load_catalog()
    print(f"\ncatalog shape: {cat.shape}")
    print(f"columns: {list(cat.columns)}")
    print(f"region==China: {(cat['region'] == 'China').sum()}")
    print(f"SI==present: {(cat['SI'] == 'present').sum()}")

    # stem 路径解析测试 (前 3 行非空 stem)
    if "stem" in cat.columns:
        tested = 0
        for s in cat["stem"]:
            if s and tested < 3:
                try:
                    paths = stem_to_paths(s)
                    exists = paths["paper_md"].exists()
                    print(f"  stem[{tested}] paper_md exists={exists}: {s[:60]}")
                    tested += 1
                except Exception as e:
                    print(f"  stem 解析失败 {s[:40]}: {e}")
                    tested += 1

    # 单位换算测试
    print("\n单位换算测试:")
    for vo, uo, tu in [(0.5, "mg/kg", "mg/kg"), (500, "ug/kg", "ng/g"),
                       (0.3, "mg/kg", "ng/g"), (12, "ug/kg", "mg/kg")]:
        v, note, qa = convert_value(vo, uo, tu)
        print(f"  {vo} {uo} → {tu}: value={v} qa={qa} | {note}")

    # land_use 测试
    print("\nland_use 分类测试:")
    for t in ["Three Gorges Reservoir riparian", "Taizhou e-waste site",
              "Shenyang urban soil", "Qinhuangdao agricultural land"]:
        print(f"  '{t}' → {classify_landuse(t)}")

    print("\n强候选匹配测试:")
    print(f"  秦皇岛题名: {is_strong_candidate('Pollution Characteristics and Evaluation of Heavy Metals and Polycyclic Aromatic Hydrocarbons in Agricultural Land of Qinhuangdao', '')}")
    print(f"  DOI 140728: {is_strong_candidate('', '10.1016/j.jhazmat.2025.140728')}")
