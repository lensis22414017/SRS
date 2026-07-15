"""验证 P2 v3 抽取质量:
  1. P01524 跨表配对情况 (tbl#1 HM 正常表 + tbl#3 PCB 转置表, 采样点 A/B/C 是否都抽到)
  2. 157 个 HM_OP sample_id 来源论文分布
  3. 假阳性扫描 (_mean summary 混入 / value=1 伪值 / sample_id 碰撞)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR
import pandas as pd

df = pd.read_csv(OUT_DIR / "extracted_observations_long_op_hmop.csv", dtype=str, keep_default_na=False)
df["value_std"] = pd.to_numeric(df["value_std"], errors="coerce")

print("="*70)
print("验证 1: P01524 (温岭电子垃圾, HM tbl#1 + PCB tbl#3/4 跨表配对金矿)")
print("="*70)
p01524 = df[df["paper_id"] == "P01524"]
print(f"P01524 总观测: {len(p01524)}")
print(f"  evidence_location 表号分布:")
p01524_tbls = p01524["evidence_location"].str.extract(r"tbl#(\d+)")[0].value_counts()
print(p01524_tbls.to_string())
print(f"\n  sample_id 前缀分布 (_s=正常表 / _tr=转置表):")
p01524_pref = p01524["sample_id"].str.extract(r"_(s\d+|tr\d+|mean)_")[0].value_counts()
print(p01524_pref.to_string())
print(f"\n  采样点标签 (从 sample_id 提取尾部):")
p01524_sites = p01524["sample_id"].str.extract(r"_([A-Za-z]\d?|[A-Za-z]+)$")[0].value_counts()
print(p01524_sites.head(20).to_string())
print(f"\n  pollutant_name_std 分布:")
print(p01524["pollutant_name_std"].value_counts().to_string())
print(f"\n  按 sample_id 看配对 (HM 族 vs OP 族):")
p01524_fam = p01524.groupby("sample_id")["pollutant_family"].apply(lambda x: sorted(set(x)))
for sid, fams in p01524_fam.items():
    if "HM" in fams and len([f for f in fams if f != "HM"]) > 0:
        print(f"    {sid}: {fams}")

print("\n"+"="*70)
print("验证 2: 157 个 HM_OP sample_id 来源论文分布 (top 25)")
print("="*70)
sample_fam = df.groupby("sample_id")["pollutant_family"].apply(lambda x: set(x))
hm_op_samples = [sid for sid, f in sample_fam.items() if "HM" in f and len(f - {"HM"}) > 0]
hm_op_df = df[df["sample_id"].isin(hm_op_samples)]
src = hm_op_df.groupby("paper_id").agg(
    n_sample_id=("sample_id", "nunique"),
    n_obs=("sample_id", "size"),
    families=("pollutant_family", lambda x: ",".join(sorted(set(x)))),
).sort_values("n_sample_id", ascending=False)
print(src.head(25).to_string())

print("\n"+"="*70)
print("验证 3: 假阳性扫描")
print("="*70)
# (a) summary _mean 混入 HM_OP
mean_hmop = hm_op_df[hm_op_df["sample_id"].str.endswith("_mean")]
print(f"(a) sample_id 以 _mean 结尾 (B_site_summary 混入 HM_OP): {len(mean_hmop)} 条, {mean_hmop['sample_id'].nunique()} sample_id")
# (b) value=1 伪值
v1 = hm_op_df[(hm_op_df["value_std"] == 1.0)]
print(f"(b) value_std==1 (合并单元格伪值): {len(v1)} 条, {v1['sample_id'].nunique()} sample_id")
qa_v1 = hm_op_df[hm_op_df["qa_flag"].str.contains("value_is_1", na=False)]
print(f"    其中已标 qa_flag=value_is_1: {len(qa_v1)} 条")
# (c) evidence B_site_summary
b_sum = hm_op_df[hm_op_df["evidence_level"] == "B_site_summary"]
print(f"(c) evidence=B_site_summary: {len(b_sum)} 条")
# (d) sample_id 碰撞: 不同论文是否共用 sample_id
sid_papers = hm_op_df.groupby("sample_id")["paper_id"].nunique()
collisions = sid_papers[sid_papers > 1]
print(f"(d) sample_id 跨论文碰撞: {len(collisions)} 个 (应=0)")

print("\n"+"="*70)
print("验证 4: 纯净 HM_OP sample_id (排除上述假阳性后)")
print("="*70)
clean_hmop = hm_op_df[
    (~hm_op_df["sample_id"].str.endswith("_mean")) &
    (hm_op_df["value_std"] != 1.0) &
    (hm_op_df["evidence_level"] == "A_sample_table")
]
clean_samples = clean_hmop["sample_id"].unique()
print(f"纯净 A 级 HM_OP sample_id: {len(clean_samples)}")
print(f"  涉及论文: {clean_hmop['paper_id'].nunique()}")
print(f"  有效观测: {len(clean_hmop)}")
print(f"  论文分布:")
print(clean_hmop.groupby("paper_id")["sample_id"].nunique().sort_values(ascending=False).head(25).to_string())

print("\n"+"="*70)
print("验证 5: 跨表配对机会 (同论文 _s 表 + _tr 表)")
print("="*70)
# 找同论文既有 _s 又有 _tr 的论文 (潜在跨表配对)
for pid in hm_op_df["paper_id"].unique():
    pdf = hm_op_df[hm_op_df["paper_id"] == pid]
    has_s = pdf["sample_id"].str.contains(r"_s\d+_", regex=True).any()
    has_tr = pdf["sample_id"].str.contains(r"_tr\d+_", regex=True).any()
    if has_s and has_tr:
        n = pdf["sample_id"].nunique()
        print(f"  {pid}: 同时有正常表(_s)+转置表(_tr) 观测, sample_id={n} (P3 需归一化)")
