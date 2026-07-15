"""Prepare batch3 OP-only paper_ids — exclude ALL existing CSVs (op_only + hm_op + _duplicates + _violations).

batch2 失败的 151 篇(429无CSV)不在排除集, 会被自动重新选中重试。
"""
import csv
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCREEN = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/screen_op_china_v2.csv"
ME = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
OUT = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/batch3_paper_ids.json"
BATCH_SIZE = 200

existing = set()
for pool in ["op_only", "hm_op"]:
    for f in glob.glob(f"{ME}/{pool}/*.csv"):
        existing.add(os.path.basename(f)[:-4])
for sub in ["_duplicates", "_violations"]:
    d = f"{ME}/{sub}"
    if os.path.exists(d):
        for f in glob.glob(f"{d}/*.csv"):
            existing.add(os.path.basename(f)[:-4])

op_only = []
with open(SCREEN, encoding="utf-8-sig") as fh:
    for row in csv.DictReader(fh):
        if row.get("has_hm", "").strip().lower() != "true":
            op_only.append(row.get("序号", "").strip())
op_only = [p for p in op_only if p]

available = [p for p in op_only if p not in existing]
batch3 = available[:BATCH_SIZE]
json.dump(batch3, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

print(f"OP-only候选池: {len(op_only)}")
print(f"已处理(排除): {len(existing)} (op_only+hm_op+duplicates+violations)")
print(f"OP-only已处理交集: {len(set(op_only) & existing)}")
print(f"可用未处理: {len(available)}")
print(f"batch3分配: {len(batch3)}, 剩余后续批次: {len(available) - BATCH_SIZE}")
print(f"前5: {batch3[:5]}")
print(f"后5: {batch3[-5:]}")
