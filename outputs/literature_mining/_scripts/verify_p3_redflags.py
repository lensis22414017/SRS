"""P3 红旗验证:
  1. P11676 是否排除植物 (Zea mays)? 为何还有 10 个 training_ready?
  2. P01524 的 7 个是否真跨表配对 (_s HM + _tr PCB)?
  3. P10991/P03303 土壤真实性抽查
"""
import sys
import re
from io import StringIO
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, LIT_ROOT
import pandas as pd

df = pd.read_csv(OUT_DIR / "extracted_observations_long_op_hmop.csv", dtype=str, keep_default_na=False)
site = pd.read_csv(OUT_DIR / "site_dataset_summary_op_hmop.csv", dtype=str, keep_default_na=False)

print("="*70)
print("红旗 1: P11676 (摘要记录为 Zea mays 玉米植物, 应排除)")
print("="*70)
p11676 = df[df["paper_id"] == "P11676"]
print(f"P11676 总观测: {len(p11676)}, readiness:")
print(p11676["readiness"].value_counts().to_string())
print(f"\n  site_name 样本 (前 5):")
print(p11676["site_name"].drop_duplicates().head(5).to_string())
print(f"\n  evidence_location 表号:")
tbls = p11676["evidence_location"].str.extract(r"tbl#(\d+)")[0].value_counts()
print(tbls.to_string())
# dump P11676 的 paper.md 表标题
md = LIT_ROOT / p11676["evidence_location"].iloc[0].split("/")[0] / "parsed" / "paper.md"
if md.exists():
    text = md.read_text(encoding="utf-8", errors="ignore")
    # 找所有 Table N 标题
    titles = re.findall(r"(Table\s*\d+[^\n]{0,100})", text)
    print(f"\n  P11676 paper.md 表标题:")
    for t in titles[:10]:
        print(f"    {t[:90]}")

print("\n"+"="*70)
print("红旗 2: P01524 跨表配对验证 (7 个 training_ready)")
print("="*70)
p01524_tr = df[(df["paper_id"] == "P01524") & (df["readiness"] == "training_ready_hm_op")]
print(f"P01524 training_ready 观测: {len(p01524_tr)}")
print(f"  canonical_sample_id:")
print(p01524_tr["canonical_sample_id"].drop_duplicates().to_string())
print(f"\n  每个 canonical 的 family + 来源表前缀 (_s/_tr):")
for csid in p01524_tr["canonical_sample_id"].unique():
    sub = p01524_tr[p01524_tr["canonical_sample_id"] == csid]
    fams = sorted(sub["pollutant_family"].unique())
    prefixes = sorted(sub["sample_id"].str.extract(r"_(s\d+|tr\d+)_")[0].unique())
    print(f"    {csid}: families={fams} prefixes={prefixes}")

print("\n"+"="*70)
print("红旗 3: P10991 / P03303 土壤真实性 (贡献 22+19 sample)")
print("="*70)
for pid in ["P10991", "P03303"]:
    pdf = df[df["paper_id"] == pid]
    print(f"\n{pid}: {len(pdf)} 观测, readiness={pdf['readiness'].value_counts().to_dict()}")
    # paper 标题
    cand = pd.read_csv(OUT_DIR / "candidate_literature_op_hmop.csv", dtype=str, keep_default_na=False)
    title = cand[cand["paper_id"] == pid]["title"].iloc[0] if pid in cand["paper_id"].values else "?"
    print(f"  论文标题: {title[:100]}")
    print(f"  site_name 样本: {pdf['site_name'].drop_duplicates().head(3).tolist()}")
    print(f"  pollutant_name_std: {sorted(pdf['pollutant_name_std'].unique())}")
    # 表标题
    stem = pdf["evidence_location"].iloc[0].split("/")[0]
    md = LIT_ROOT / stem / "parsed" / "paper.md"
    if md.exists():
        text = md.read_text(encoding="utf-8", errors="ignore")
        titles = re.findall(r"(Table\s*\d+[^\n]{0,100})", text)
        print(f"  表标题 (前 5):")
        for t in titles[:5]:
            print(f"    {t[:85]}")

print("\n"+"="*70)
print("红旗 4: OPFR 误入 (不在 v0.8 OP_RAW, 应标 qa_flag)")
print("="*70)
opfr = df[df["pollutant_name_std"] == "SumOPFR_ngg"]
print(f"SumOPFR_ngg 观测: {len(opfr)}")
if len(opfr):
    print(f"  已标 opfr_not_in_v0.8_op_raw: {opfr['qa_flag'].str.contains('opfr', na=False).sum()}")
