"""Audit build_wide OP-only definition bug.

build_wide_manual.py:86 defines OP-only = ~is_hm_op, which INCLUDES HM-only
samples (n_op==0). This quantifies how many HM-only canonicals leaked into
the OP-only table, and recomputes the TRUE OP-only count with the correct
filter (n_op>0 & n_hm==0).
"""
import csv
import glob
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
HM = {"Cd_mgkg", "Pb_mgkg", "Cr_mgkg", "As_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg"}

# canonical -> (paper_id, set(pollutants))
canon = defaultdict(lambda: [None, set(), None])
for d in ["hm_op", "op_only"]:
    for f in glob.glob(f"{BASE}/{d}/*.csv"):
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
        except Exception:
            continue
        for r in rows:
            pid = r.get("paper_id", "")
            sid = str(r.get("sample_id", ""))
            poll = r.get("pollutant_std", "")
            val = r.get("value", "")
            if not pid or not sid or not poll:
                continue
            try:
                v = float(val)
            except (ValueError, TypeError):
                continue
            if v < 0:
                continue
            c = f"{pid}_{sid}"
            canon[c][0] = pid
            canon[c][1].add(poll)
            canon[c][2] = d

# Classify each canonical
buckets = {"op_only_true": [], "hm_only": [], "hm_op": []}
for c, (pid, polls, d) in canon.items():
    n_hm = len([p for p in polls if p in HM])
    n_op = len([p for p in polls if p not in HM])
    if n_hm > 0 and n_op > 0:
        buckets["hm_op"].append((c, pid, d))
    elif n_op > 0 and n_hm == 0:
        buckets["op_only_true"].append((c, pid, d))
    elif n_hm > 0 and n_op == 0:
        buckets["hm_only"].append((c, pid, d))

def src(xs):
    return len(set(x[1] for x in xs))

print("=== canonical 分类 (修正 build_wide bug) ===")
print(f"真 OP-only (n_op>0 & n_hm==0): {len(buckets['op_only_true'])} sample / {src(buckets['op_only_true'])} source")
print(f"HM-only 泄漏  (n_hm>0 & n_op==0): {len(buckets['hm_only'])} sample / {src(buckets['hm_only'])} source")
print(f"HM+OP 复合   (n_hm>0 & n_op>0): {len(buckets['hm_op'])} sample / {src(buckets['hm_op'])} source")
print()
print(f"build_wide 当前 OP-only(=264) = 真 OP-only + HM-only 泄漏 = {len(buckets['op_only_true'])} + {len(buckets['hm_only'])} = {len(buckets['op_only_true'])+len(buckets['hm_only'])}")
print()
print("--- HM-only 泄漏样本 (这些不该在 OP-only 表里) ---")
leak_src = defaultdict(int)
for c, pid, d in buckets["hm_only"]:
    leak_src[pid] += 1
for pid, n in sorted(leak_src.items(), key=lambda x: -x[1])[:15]:
    print(f"  {pid}: {n} 个纯 HM 采样点")
print()
print("--- 真 OP-only 来源分布 ---")
op_src = defaultdict(int)
for c, pid, d in buckets["op_only_true"]:
    op_src[pid] += 1
for pid, n in sorted(op_src.items(), key=lambda x: -x[1])[:15]:
    print(f"  {pid}: {n} 个 OP-only 采样点")
