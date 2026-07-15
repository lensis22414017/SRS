"""Dump2: dirty pollutant_std rows + P01626/P09065 full CSV + P00395 makeup."""
import csv
import glob
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
DIRTY = {"NA", "N/A", "NOT_AVAILABLE", "SUMMARY_ONLY", "skip", "", "nan", "None"}

# ---- 1. 脏值 pollutant_std 行 ----
print("=" * 70)
print("1. pollutant_std 脏值行 (Agent 占位符, 非真实污染物)")
print("=" * 70)
dirty_rows = []
for d in ["hm_op", "op_only"]:
    for f in glob.glob(f"{BASE}/{d}/*.csv"):
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
        except Exception:
            continue
        for r in rows:
            poll = (r.get("pollutant_std") or "").strip()
            if poll in DIRTY:
                dirty_rows.append((d, f.split("/")[-1][:-4], r))
print(f"共 {len(dirty_rows)} 条脏值行:")
for d, pid, r in dirty_rows[:25]:
    val = r.get("value", "")
    sid = r.get("sample_id", "")
    loc = r.get("evidence_location", "")
    notes = (r.get("extract_notes") or "")[:60]
    print(f"  {d}/{pid} sid={sid!r} val={val!r} loc={loc!r}")
    if notes:
        print(f"      notes: {notes}")

# ---- 2. P01626 vs P09065 完整 CSV 逐行比对 ----
print("\n" + "=" * 70)
print("2. P01626 vs P09065 完整逐行比对")
print("=" * 70)
for pid in ["P01626", "P09065"]:
    print(f"\n--- [{pid}] ---")
    for d in ["hm_op", "op_only"]:
        f = f"{BASE}/{d}/{pid}.csv"
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
        except FileNotFoundError:
            continue
        for r in rows:
            print(f"  sid={r.get('sample_id')!r} poll={r.get('pollutant_std')!r} "
                  f"val={r.get('value')!r} unit={r.get('unit')!r} "
                  f"loc={r.get('evidence_location')!r}")
            notes = (r.get("extract_notes") or "")
            if notes:
                print(f"        notes: {notes[:100]}")

# ---- 3. P00395 污染物构成 (抗生素论文?) ----
print("\n" + "=" * 70)
print("3. P00395 污染物构成 (OP-only 表主力, 看是否纯抗生素)")
print("=" * 70)
poll_cnt = defaultdict(int)
for d in ["hm_op", "op_only"]:
    f = f"{BASE}/{d}/P00395.csv"
    try:
        rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
    except FileNotFoundError:
        continue
    for r in rows:
        poll_cnt[r.get("pollutant_std", "")] += 1
for poll, cnt in sorted(poll_cnt.items(), key=lambda x: -x[1]):
    print(f"  {poll}: {cnt}")
