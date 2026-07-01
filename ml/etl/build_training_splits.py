"""三块训练数据派生 + group-split(HM/OP/复合) + 双标签(生产/生态)。

复用 ml/models/dataset_splits.build_real_splits(连通分量 DOI/Source 零泄漏)。

双阈值库架构(2026-06-24 Wave D, 方案A — 项目组已批):
  - 标签_生产: HM按GB15618 pH四段路由(场地SoilpH动态选段, 方案A核心) + OP按GB36600一类阈值
  - 标签_生态: HM按生态库'二类用地'值(GB36600二类, 项目组定义生态=宽) + OP暂用一类值(生态二类对齐待Wave B)
  - group-split 用 标签_生产 做主分层; 标签_生产/标签_生态 两列供双模型分别训练
标签派生: 任一因子超对应轨阈值→1(木桶效应, GB15618§6.2), 否则0。
数据局限(实事求是标注):
  - HM_CSV(29993行)无SoilpH列 → HM块按默认正常段6.5<pH≤7.5+'其他'旱地派生(无pH无法路由)
  - merged OP/复合块有SoilpH → 按实测pH路由GB15618四段
  - 训练数据无水田/其他/绿地细分列 → 生产默认'其他'旱地(数据代表性)/生态默认'二类用地'(项目组定义)
  - 用途是人为决策(项目组): 不按Pollution_Type推断用途, 双标签都派生, 训练两套模型, 测试双用途都试
运行: cd backend && .venv/bin/python ../ml/etl/build_training_splits.py [hm|op|composite|all]
"""
import os, sys, csv, json, re
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))
from dataset_splits import build_real_splits  # noqa: E402

MERGED = os.path.join(ROOT, "data", "raw", "merged_std33,zh .xlsx")
HM_CSV = os.path.join(ROOT, "data", "raw", "真实训练集_GB15618.csv")
GB36600_CSV = os.path.join(ROOT, "data", "standards", "GB36600_有机阈值_权威.csv")
GB36600_FALLBACK = os.path.join(ROOT, "data", "knowledge_base", "有机物阈值补充_GB36600.csv")
THRESH_PROD = os.path.join(ROOT, "data", "knowledge_base", "阈值库", "生产", "thresholds.csv")
THRESH_ECO = os.path.join(ROOT, "data", "knowledge_base", "阈值库", "生态", "thresholds.csv")
OUT_BASE = os.path.join(ROOT, "data", "training")

HM_COLS = {"Cd_mgkg": "镉", "Pb_mgkg": "铅", "As_mgkg": "砷", "Cr_mgkg": "铬",
           "Hg_mgkg": "汞", "Cu_mgkg": "铜", "Zn_mgkg": "锌", "Ni_mgkg": "镍"}
# HM_CSV 重金属列即中文名(无_mgkg后缀), 单列映射供 _label_dual 识别HM分支
HM_COLS_ZH = {c: c for c in ["镉", "铅", "砷", "铬", "汞", "铜", "锌", "镍"]}
# 有机列(merged → 中文) — 用于 OP/复合派生
ORG_COLS_MAP = {
    "Sum_PAH_ngg": "多环芳烃总量", "BaP_ngg": "苯并芘", "SumOCP_ngg": "有机氯农药",
    "SumDDTs_ngg": "DDT类", "SumPCB_ngg": "多氯联苯", "SumHCHs_ngg": "六六六总量",
    "SumPAE_ugkg": "邻苯二甲酸酯", "SumPBDE_ngg": "多溴二苯醚", "SumPFAS_ngg": "全氟化合物",
    "TPH_ngg": "石油烃", "HMWPAH_ngg": "高分子量PAH", "LMWPAH_ngg": "低分子量PAH",
}

# === GB15618 pH四段(生产轨重金属路由, 方案A) ===
PH_SEGMENTS = [("pH≤5.5", lambda p: p <= 5.5),
               ("5.5<pH≤6.5", lambda p: 5.5 < p <= 6.5),
               ("6.5<pH≤7.5", lambda p: 6.5 < p <= 7.5),
               ("pH>7.5", lambda p: p > 7.5)]
DEFAULT_PH_SEG = "6.5<pH≤7.5"   # 无SoilpH默认正常段(项目组"正常pH≤7.5")
DEFAULT_PROD_LAND = "其他"      # 生产轨无用地细分默认旱地(GB15618默认类, 数据代表性)
DEFAULT_ECO_LAND = "二类用地"   # 生态轨默认宽值场景(项目组定义生态=GB36600二类)


def _write_splits(splits, checks, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rename = {"train_real": "train", "valid_real_group_split": "valid",
              "test_real_group_split": "test", "external_literature_holdout": "external"}
    summary = {}
    for k, df in splits.items():
        fn = rename.get(k, k)
        df.to_csv(os.path.join(out_dir, f"{fn}.csv"), index=False, encoding="utf-8-sig")
        summary[fn] = len(df)
    with open(os.path.join(out_dir, "splits_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"sizes": summary, "leakage_all_passed": checks["all_passed"],
                   "label_dist": {k: {"生产": int((df.get("标签_生产") == 1).sum()) if "标签_生产" in df.columns else None,
                                      "生态": int((df.get("标签_生态") == 1).sum()) if "标签_生态" in df.columns else None}
                                  for k, df in splits.items()}}, f, ensure_ascii=False, indent=2)
    print(f"  → {out_dir}: {summary} 零泄漏={checks['all_passed']}")


def _load_org_thresholds():
    """加载 GB36600 有机阈值(ng/g 原始单位)。优先 OCR 精确版, 回退保守补充版。

    从 threshold_original 文本(如'≤550ng/g')解析数值, 保持 ng/g(与 merged 有机列同单位)。
    OP双轨暂同用此一类阈值(生态二类命名对齐待Wave B)。
    """
    thr = {}
    for path in (GB36600_CSV, GB36600_FALLBACK):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                f_name = (r.get("factor_name") or r.get("factor") or "").strip()
                if not f_name:
                    continue
                v = r.get("cat1") or r.get("threshold_max") or ""
                try:
                    val = float(v)
                except (ValueError, TypeError):
                    m = re.search(r"≤\s*([\d.]+)", r.get("threshold_original") or "")
                    val = float(m.group(1)) if m else None
                if val is None:
                    continue
                thr[f_name] = val  # 保持原单位(ng/g), 与 merged 有机列直接比
        if thr:
            break
    return thr


def _parse_thr_val(s):
    """阈值文本→float。'30'→30; '≤60mg/kg'→60; '35-45mg/kg'→45(区间取上界,判超标偏保守)。None=无法解析。"""
    s = str(s).strip()
    m = re.search(r"([\d.]+)\s*-\s*([\d.]+)", s)
    if m:
        return float(m.group(2))  # 区间取上界
    m = re.search(r"≤?\s*([\d.]+)", s)
    return float(m.group(1)) if m else None


def _load_thresh_csv(path):
    """读阈值库CSV→行list(每行dict, _val=解析后float,无法解析的跳过)。"""
    rows = []
    if not os.path.exists(path):
        print(f"  ⚠️ 阈值库不存在: {path}")
        return rows
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            v = _parse_thr_val(r.get("threshold_value", ""))
            if v is None:
                continue
            r["_val"] = v
            rows.append(r)
    return rows


def _route_ph_seg(soilph):
    """SoilpH→GB15618段字符串。NaN/缺失→默认正常段6.5<pH≤7.5。"""
    if pd.isna(soilph):
        return DEFAULT_PH_SEG
    try:
        p = float(soilph)
    except (ValueError, TypeError):
        return DEFAULT_PH_SEG
    for seg, fn in PH_SEGMENTS:
        if fn(p):
            return seg
    return DEFAULT_PH_SEG


def _prod_hm_thresh(factor, soilph, prod_rows):
    """生产轨重金属按SoilpH路由GB15618四段(方案A)。land默认'其他',退化匹配该段任意land(锌/镍通用)。"""
    seg = _route_ph_seg(soilph)
    for r in prod_rows:
        if r.get("category") != "HM":
            continue
        if r["factor"] == factor and r.get("ph_segment") == seg and r.get("land_class") == DEFAULT_PROD_LAND:
            return r["_val"]
    for r in prod_rows:  # 退化: 该段任意land(通用因子)
        if r.get("category") != "HM":
            continue
        if r["factor"] == factor and r.get("ph_segment") == seg:
            return r["_val"]
    return None


def _eco_hm_thresh(factor, eco_rows):
    """生态轨重金属默认'二类用地'(宽值, 项目组定义生态=GB36600二类)。退化取该因子任意land。"""
    for r in eco_rows:
        if r.get("category") != "HM":
            continue
        if r["factor"] == factor and r.get("land_class") == DEFAULT_ECO_LAND:
            return r["_val"]
    for r in eco_rows:  # 退化: 任意land(自然保育区等单land因子)
        if r.get("category") != "HM":
            continue
        if r["factor"] == factor:
            return r["_val"]
    return None


def _is_hm_col(col):
    return col in HM_COLS or col in HM_COLS_ZH


def _label_dual(row, factor_cols, prod_rows, eco_rows, org_thresh):
    """派生双标签(标签_生产, 标签_生态)。任一因子超对应轨阈值→1(木桶效应)。
    HM: 库mg/kg vs 数据mg/kg直接比; 生产按SoilpH路由(无pH默认正常段), 生态按二类用地。
    OP: ng/g数据 vs ng/g一类阈值(权威CSV), 双轨暂同值(生态二类对齐待Wave B)。"""
    soilph = row.get("SoilpH", row.get("pH"))
    lab_prod = 0
    lab_eco = 0
    for col, cn in factor_cols.items():
        if col not in row:
            continue
        v = row[col]
        if pd.isna(v):
            continue
        try:
            val = float(v)
        except (ValueError, TypeError):
            continue
        if _is_hm_col(col):
            tp = _prod_hm_thresh(cn, soilph, prod_rows)
            te = _eco_hm_thresh(cn, eco_rows)
            if tp is not None and val > tp:
                lab_prod = 1
            if te is not None and val > te:
                lab_eco = 1
        else:
            t = org_thresh.get(cn)
            if t and val > t:  # OP ng/g vs ng/g 一类阈值
                lab_prod = 1
                lab_eco = 1  # OP双轨暂同(一类保守); 生态二类命名对齐待Wave B
    return lab_prod, lab_eco


def _attach_dual_labels(df, factor_cols, prod_rows, eco_rows, org_thresh):
    """给df附加 标签_生产/标签_生态/标签(=生产, group-split主分层用) 三列。"""
    dual = df.apply(lambda r: _label_dual(r, factor_cols, prod_rows, eco_rows, org_thresh), axis=1)
    df["标签_生产"] = [x[0] for x in dual]
    df["标签_生态"] = [x[1] for x in dual]
    df["标签"] = df["标签_生产"]
    return df


def build_hm():
    print("[HM] 真实训练集_GB15618 group-split + 双标签(无SoilpH→默认正常段)...")
    df = pd.read_csv(HM_CSV)
    prod_rows = _load_thresh_csv(THRESH_PROD)
    eco_rows = _load_thresh_csv(THRESH_ECO)
    _attach_dual_labels(df, HM_COLS_ZH, prod_rows, eco_rows, {})  # HM块无OP
    df["id_DOI"] = df.get("DOI", "")
    df["id_Source"] = df.get("Source", "")
    print(f"  HM 行数={len(df)}, 生产标签1={df['标签_生产'].mean():.2%}, 生态标签1={df['标签_生态'].mean():.2%}")
    splits, checks = build_real_splits(df, seed=42)
    _write_splits(splits, checks, os.path.join(OUT_BASE, "hm"))


def _build_merged_block(ptype_filter, out_name, include_hm=True, include_org=True):
    """从 merged 派生 OP/复合 block + 双标签 + group-split。"""
    print(f"[{out_name}] merged {ptype_filter} 派生...")
    df = pd.read_excel(MERGED)
    sub = df[df["Pollution_Type"].isin(ptype_filter)].copy()
    factor_cols = {}
    if include_hm:
        factor_cols.update(HM_COLS)
    if include_org:
        factor_cols.update(ORG_COLS_MAP)
    keep = ["DOI", "Source", "Latitude", "Longitude", "Province", "Pollution_Type",
            "SoilpH", "pH", "OC_pct"] + list(factor_cols.keys())
    keep = [c for c in keep if c in sub.columns]
    sub = sub[keep].copy()
    prod_rows = _load_thresh_csv(THRESH_PROD)
    eco_rows = _load_thresh_csv(THRESH_ECO)
    org_thresh = _load_org_thresholds()
    _attach_dual_labels(sub, factor_cols, prod_rows, eco_rows, org_thresh)
    sub["id_DOI"] = sub.get("DOI", "")
    sub["id_Source"] = sub.get("Source", "")
    print(f"  {out_name} 行数={len(sub)}, 生产标签1={sub['标签_生产'].mean():.2%}, 生态标签1={sub['标签_生态'].mean():.2%}, 因子列={len(factor_cols)}")
    splits, checks = build_real_splits(sub, seed=42)
    _write_splits(splits, checks, os.path.join(OUT_BASE, out_name))


def build_op():
    _build_merged_block(["OP", "PAH", "OCP", "PAH+OCP"], "op", include_hm=False, include_org=True)


def build_composite():
    _build_merged_block(["HM+OP"], "composite", include_hm=True, include_org=True)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("hm", "all"):
        build_hm()
    if which in ("op", "all"):
        build_op()
    if which in ("composite", "all"):
        build_composite()
    print("\n完成。三块 train/valid/test → data/training/{hm,op,composite}/ (双标签: 标签_生产/标签_生态)")
