"""Move latest duplicate pairs (铁律#10 保留最小 paper_id)."""
import os, shutil, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
DUP = BASE + "/_duplicates"
os.makedirs(DUP, exist_ok=True)

# 铁证: 保留最小
TO_MOVE = {"P05447": "P04788", "P06574": "P05945"}  # larger:smaller
moved = []
for larger in TO_MOVE:
    for pool in ["op_only", "hm_op"]:
        src = f"{BASE}/{pool}/{larger}.csv"
        if os.path.exists(src) and not os.path.exists(f"{DUP}/{larger}.csv"):
            shutil.move(src, f"{DUP}/{larger}.csv")
            moved.append(f"{pool}/{larger}")
print(f"移除 {len(moved)} 篇: {moved}")
print(f"_duplicates/ 累计: {len(os.listdir(DUP))} 篇")
for larger, smaller in TO_MOVE.items():
    print(f"  {larger}→{smaller} (保留最小)")
