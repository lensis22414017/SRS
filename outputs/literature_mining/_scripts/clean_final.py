"""Final clean — 干净土壤训练集 (裴总: 自行决断, 目标干净可训练).

剔除类(不干净):
- P09845: 盆栽老化实验 → _violations/ (铁律A3, CG1老化后值非场地原始本底)
- P00258: 删Sum_PAH行 (6种PAH子集非16EPA标准; 保留HM-only, 退出HM+OP表)
- P00242: 删EW(DW)行 (3 workshops跨点多点合并=区域均值嫌疑 + Cr/Zn同为1717排版错误)

保留降级(site-Mean, 裴总P07067方向, 真实场地测定):
- P02317(n=10 UMT矿区梯度) / P07067(n=5 贵屿) / P00242 A/EW(S)/EW(OBS)(composite)
"""
import csv
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
VIOL = BASE + "/_violations"
os.makedirs(VIOL, exist_ok=True)
log = []


def rewrite(f, rows, keep):
    if len(keep) < len(rows):
        with open(f, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(keep)
    return len(rows), len(keep)


# 1. P09845 盆栽老化 → _violations/
src = f"{BASE}/hm_op/P09845.csv"
if os.path.exists(src) and not os.path.exists(f"{VIOL}/P09845.csv"):
    shutil.move(src, f"{VIOL}/P09845.csv")
    log.append("P09845 盆栽老化实验 → _violations/ (铁律A3, CG1老化后非场地原始本底)")

# 2. P00258 删 Sum_PAH 行 (6种PAH子集, 非标准16EPA)
f = f"{BASE}/hm_op/P00258.csv"
if os.path.exists(f):
    rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
    keep = [r for r in rows if r.get("pollutant_std") != "Sum_PAH_ngg"]
    n0, n1 = rewrite(f, rows, keep)
    if n1 < n0:
        log.append(f"P00258 删Sum_PAH {n0}→{n1} (6种非16EPA子集; 保留HM-only退出HM+OP表)")

# 3. P00242 删 EW(DW) (3 workshops跨点多点合并 + Cr/Zn排版错误)
f = f"{BASE}/hm_op/P00242.csv"
if os.path.exists(f):
    rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
    keep = [r for r in rows if r.get("sample_id") != "EW(DW)"]
    n0, n1 = rewrite(f, rows, keep)
    if n1 < n0:
        log.append(f"P00242 删EW(DW) {n0}→{n1} (3 workshops跨点合并+排版错误; 保留A/EW(S)/EW(OBS) composite)")

print("=== 最终清理 (干净训练集) ===")
for l in log:
    print("  ✅ " + l)
if not log:
    print("  (本次无需清理, 可能已执行过)")

print("\n保留降级(site-Mean, 裴总方向): P02317(n=10)/P07067(n=5)/P00242 A·EW(S)·EW(OBS)(composite)")
print("_violations/ 现有:", sorted(os.listdir(VIOL)) if os.path.exists(VIOL) else [])
