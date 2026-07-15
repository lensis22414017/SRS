"""Count CSV files and data rows in manual_extract/{hm_op,op_only}.

Reusable progress-check helper (called every 30 min by cron loop).
Counts only on-disk CSVs — the ground truth, not workflow-internal counters.
"""
import csv
import glob
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"

for d in ["hm_op", "op_only"]:
    files = sorted(glob.glob(f"{BASE}/{d}/*.csv"))
    rows = 0
    empty = 0
    for f in files:
        try:
            with open(f, encoding="utf-8-sig") as fh:
                r = list(csv.reader(fh))
                n = max(0, len(r) - 1)  # minus header
                rows += n
                if n == 0:
                    empty += 1
        except Exception as e:
            print(f"  ERR {f}: {e}")
    print(f"{d}: {len(files)} CSV ({empty} empty) / {rows} data rows")
