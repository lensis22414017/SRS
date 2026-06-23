"""三块训练数据派生 + group-split(HM/OP/复合)。

复用 ml/models/dataset_splits.build_real_splits(连通分量 DOI/Source 零泄漏)。
- HM: 真实训练集_GB15618(8重金属, GB15618标签) → data/training/hm/
- OP: merged OP行 + 134有机列 + GB36600阈值标签 → data/training/op/
- 复合: merged HM+OP行 + 重金属+有机 + 标签 → data/training/composite/
标签派生: 任一因子超 GB15618(重金属)/GB36600(有机) 阈值 → 1(超标/障碍), 否则 0。
运行: cd backend && .venv/bin/python ../ml/etl/build_training_splits.py [hm|op|composite|all]
"""
import os, sys, csv, json
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))
from dataset_splits import build_real_splits  # noqa: E402

MERGED = os.path.join(ROOT, "data", "raw", "merged_std33,zh .xlsx")
HM_CSV = os.path.join(ROOT, "data", "raw", "真实训练集_GB15618.csv")
GB36600_CSV = os.path.join(ROOT, "data", "standards", "GB36600_有机阈值_权威.csv")
GB36600_FALLBACK = os.path.join(ROOT, "data", "knowledge_base", "有机物阈值补充_GB36600.csv")
OUT_BASE = os.path.join(ROOT, "data", "training")

HM_COLS = {"Cd_mgkg": "镉", "Pb_mgkg": "铅", "As_mgkg": "砷", "Cr_mgkg": "铬",
           "Hg_mgkg": "汞", "Cu_mgkg": "铜", "Zn_mgkg": "锌", "Ni_mgkg": "镍"}
# 有机列(merged → 中文) — 用于 OP/复合派生
ORG_COLS_MAP = {
    "Sum_PAH_ngg": "多环芳烃总量", "BaP_ngg": "苯并芘", "SumOCP_ngg": "有机氯农药",
    "SumDDTs_ngg": "DDT类", "SumPCB_ngg": "多氯联苯", "SumHCHs_ngg": "六六六总量",
    "SumPAE_ugkg": "邻苯二甲酸酯", "SumPBDE_ngg": "多溴二苯醚", "SumPFAS_ngg": "全氟化合物",
    "TPH_ngg": "石油烃", "HMWPAH_ngg": "高分子量PAH", "LMWPAH_ngg": "低分子量PAH",
}
# GB15618 重金属阈值(生产用地, 近似, 用于标签) — 与知识库一致
HM_THRESH = {"镉": 0.3, "铅": 70, "砷": 25, "铬": 150, "汞": 0.5, "铜": 50, "锌": 200, "镍": 60}


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
                   "label_dist": {k: int((df.get("标签") == 1).sum()) if "标签" in df.columns else None
                                  for k, df in splits.items()}}, f, ensure_ascii=False, indent=2)
    print(f"  → {out_dir}: {summary} 零泄漏={checks['all_passed']}")


def build_hm():
    print("[HM] 真实训练集_GB15618 group-split...")
    df = pd.read_csv(HM_CSV)
    df["id_DOI"] = df.get("DOI", "")
    df["id_Source"] = df.get("Source", "")
    splits, checks = build_real_splits(df, seed=42)
    _write_splits(splits, checks, os.path.join(OUT_BASE, "hm"))


def _load_org_thresholds():
    """加载 GB36600 有机阈值(ng/g 原始单位)。优先 OCR 精确版, 回退保守补充版。

    从 threshold_original 文本(如'≤550ng/g')解析数值, 保持 ng/g(与 merged 有机列同单位)。
    """
    import re
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


def _label_row(row, factor_cols, hm_thresh, org_thresh):
    """任一因子超阈值→1, 否则0。重金属 mg/kg 与 mg/kg 阈值比; 有机 ng/g 与 ng/g 阈值比(各自一致, 不转换)。"""
    for col, cn in factor_cols.items():
        if col not in row:
            continue
        v = row[col]
        if pd.isna(v):
            continue
        val = float(v)  # 原始单位(重金属 mg/kg / 有机 ng/g)
        t = hm_thresh.get(cn) if col in HM_COLS else org_thresh.get(cn)
        if t and val > t:
            return 1
    return 0


def _build_merged_block(ptype_filter, out_name, include_hm=True, include_org=True):
    """从 merged 派生 OP/复合 block + 标签 + group-split。"""
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
    org_thresh = _load_org_thresholds()
    sub["标签"] = sub.apply(lambda r: _label_row(r, factor_cols, HM_THRESH, org_thresh), axis=1)
    sub["id_DOI"] = sub.get("DOI", "")
    sub["id_Source"] = sub.get("Source", "")
    print(f"  {out_name} 行数={len(sub)}, 标签1占比={sub['标签'].mean():.2%}, 因子列={len(factor_cols)}")
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
    print("\n完成。三块 train/valid/test → data/training/{hm,op,composite}/")
