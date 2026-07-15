"""Deep quality audit (verify-skill automated layer).

Checks 3 high-risk violation classes that scan_stat_rows cannot catch:
1. Unit mismatch: HM must be mg/kg, OP must be ng/g (mismatch = wrong magnitude)
2. Outliers: HM >5000 mg/kg or OP >100000 ng/g flagged (may be threshold/summary)
3. Big-N papers: >30 sampling points per paper = provincial survey site-Mean suspect
"""
import csv
import glob
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
HM = {"Cd_mgkg", "Pb_mgkg", "Cr_mgkg", "As_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg"}

unit_issues = []      # (dir, pid, sid, poll, val, unit)
outliers = []         # (dir, pid, sid, poll, val, unit, reason)
per_paper_pts = defaultdict(set)   # pid -> set of sample_id
per_paper_rows = defaultdict(int)

for d in ["hm_op", "op_only"]:
    for f in glob.glob(f"{BASE}/{d}/*.csv"):
        fname = f.replace("\\", "/").split("/")[-1]
        pid = fname[:-4]
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
        except Exception:
            continue
        for r in rows:
            sid = r.get("sample_id", "")
            poll = r.get("pollutant_std", "")
            val = r.get("value", "")
            unit = (r.get("unit", "") or "").strip()
            if not sid or not poll:
                continue
            per_paper_pts[pid].add(sid)
            per_paper_rows[pid] += 1
            try:
                v = float(val)
            except (ValueError, TypeError):
                continue
            is_hm = poll in HM
            # 1. 单位检查
            ul = unit.lower().replace(" ", "")
            if is_hm and ul and ul not in ("mg/kg", "mg·kg", "mgkg-1", "mg/kg-1"):
                unit_issues.append((d, pid, sid, poll, v, unit))
            if not is_hm and ul and "ng" not in ul and "mg" not in ul:
                unit_issues.append((d, pid, sid, poll, v, unit))
            # 2. 异常值
            if is_hm and v > 5000:
                outliers.append((d, pid, sid, poll, v, unit, "HM>5000"))
            if not is_hm and v > 100000:
                outliers.append((d, pid, sid, poll, v, unit, "OP>100000"))

print("=== 1. 单位错位嫌疑 (HM应mg/kg, OP应ng/g) ===")
print(f"共 {len(unit_issues)} 条")
for u in unit_issues[:25]:
    print(f"  {u[0]}/{u[1]} sid={u[2]!r} {u[3]}={u[4]} unit={u[5]!r}")

print(f"\n=== 2. 异常值嫌疑 (HM>5000 或 OP>100000) ===")
print(f"共 {len(outliers)} 条")
# 按 pid 聚合, 避免刷屏
by_pid = defaultdict(list)
for o in outliers:
    by_pid[o[1]].append(o)
for pid, os_ in sorted(by_pid.items(), key=lambda x: -len(x[1]))[:15]:
    vals = [o[4] for o in os_]
    print(f"  {pid}: {len(os_)}条  poll={os_[0][3]}  val范围[{min(vals)},{max(vals)}]  例sid={os_[0][2]!r}")

print(f"\n=== 3. 大N论文 (>30采样点 = 省级调研site-Mean嫌疑) ===")
big = sorted(per_paper_pts.items(), key=lambda x: -len(x[1]))
for pid, sids in big:
    n = len(sids)
    if n > 30:
        print(f"  {pid}: {n} 采样点 / {per_paper_rows[pid]} 行")
