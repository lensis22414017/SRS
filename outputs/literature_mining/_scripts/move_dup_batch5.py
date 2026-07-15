"""Move batch5 confirmed duplicates (detect_duplicates铁证, 铁律#10保留最小)."""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
DUP = BASE + "/_duplicates"
os.makedirs(DUP, exist_ok=True)

# detect_duplicates 铁证(>=97%重叠): 保留最小 paper_id
TO_MOVE = ["P10653", "P06722", "P10778"]  # P06860<P10653(97%), P00680<P06722(100%), P02222<P10778(79%确认天津油田S1-S5数值+notes同源)
moved = []
for pid in TO_MOVE:
    for pool in ["op_only", "hm_op"]:
        src = f"{BASE}/{pool}/{pid}.csv"
        if os.path.exists(src) and not os.path.exists(f"{DUP}/{pid}.csv"):
            shutil.move(src, f"{DUP}/{pid}.csv")
            moved.append(f"{pool}/{pid}")
print(f"移除 {len(moved)} 篇铁证重复: {moved}")
print(f"_duplicates/ 累计: {sorted(os.listdir(DUP))}")
