"""Prepare batch2 OP-only paper_ids (200 unprocessed) from screen_op_china_v2.csv.

Logic:
1. Filter has_hm=True → HM+OP candidate (exclude from OP-only batch)
2. Exclude ALL paper_ids already in manual_extract/{op_only,hm_op}/*.csv
3. Exclude _duplicates/ (already identified as duplicate)
4. Take first 200 from remaining → batch2
Output: JSON array to stdout + save to batch2_paper_ids.json
"""
import csv
import glob
import json
import sys
import os

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCREEN = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/screen_op_china_v2.csv"
ME = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
OUT = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/batch2_paper_ids.json"
BATCH_SIZE = 200

# 1. Load screen_op_china_v2.csv
all_papers = []
with open(SCREEN, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        all_papers.append(row)
print(f"screen_op_china_v2.csv: {len(all_papers)} 篇")

# 2. Collect existing paper_ids in manual_extract (exclude _duplicates/)
existing = set()
for pool in ["op_only", "hm_op"]:
    for f in glob.glob(f"{ME}/{pool}/*.csv"):
        pid = os.path.basename(f)[:-4]
        existing.add(pid)
print(f"manual_extract 已有 CSV: {len(existing)} 篇")

# Also add _duplicates/ (already known duplicates)
dup_dir = f"{ME}/_duplicates"
if os.path.exists(dup_dir):
    for f in glob.glob(f"{dup_dir}/*.csv"):
        pid = os.path.basename(f)[:-4]
        existing.add(pid)
        print(f"  _duplicates: {pid}")

# 3. Classify
op_only = []      # has_hm=False or empty
hm_op = []        # has_hm=True
for p in all_papers:
    pid = p.get("序号", "").strip()
    if not pid:
        continue
    has_hm = p.get("has_hm", "").strip().lower()
    if has_hm == "true":
        hm_op.append(pid)
    else:
        op_only.append(pid)

print(f"OP-only 候选: {len(op_only)} 篇")
print(f"HM+OP 候选:  {len(hm_op)} 篇")

# 4. Find unprocessed OP-only
available = [pid for pid in op_only if pid not in existing]
print(f"OP-only 未处理: {len(available)} 篇")

# 5. Take first 200
batch2 = available[:BATCH_SIZE]
print(f"\nbatch2 前 {len(batch2)} 篇 paper_ids:")

# Save
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(batch2, f, ensure_ascii=False, indent=2)
print(f"\n已保存到 {OUT}")

# Print summary
print("\n--- 本批次统计 ---")
print(f"OP-only 候选池大小: {len(op_only)}")
print(f"已处理(从manual_extract去重): {len(existing)}")
print(f"其中OP-only已处理(交集): {len(set(op_only) & existing)}")
print(f"可用未处理: {len(available)}")
print(f"batch2分配: {len(batch2)}")
print(f"剩余(后续批次): {len(available) - BATCH_SIZE}")

# Preview first/last few
print(f"\nbatch2 前5: {batch2[:5]}")
print(f"batch2 后5: {batch2[-5:]}")
