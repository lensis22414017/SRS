"""Move extract-batch duplicates (detect_duplicates铁证, 铁律#10保留最小)."""
import os, shutil, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
DUP = BASE + "/_duplicates"
os.makedirs(DUP, exist_ok=True)

# 铁证(100%重叠): 保留最小 paper_id
TO_MOVE = {"P08569": "P01783", "P06587": "P00865", "P07943": "P07012"}
moved = []
for larger, smaller in TO_MOVE.items():
    for pool in ["op_only", "hm_op"]:
        src = f"{BASE}/{pool}/{larger}.csv"
        if os.path.exists(src) and not os.path.exists(f"{DUP}/{larger}.csv"):
            shutil.move(src, f"{DUP}/{larger}.csv")
            moved.append(f"{pool}/{larger}")
print(f"移除 {len(moved)} 篇铁证重复(100%重叠): {moved}")
print(f"_duplicates/ 累计: {sorted(os.listdir(DUP))}")
# Verify smaller papers exist
for larger, smaller in TO_MOVE.items():
    found = False
    for pool in ["op_only", "hm_op"]:
        if os.path.exists(f"{BASE}/{pool}/{smaller}.csv"):
            print(f"  保留 {smaller} in {pool}/")
            found = True
    if not found:
        print(f"  ⚠️ {smaller} NOT FOUND!")
