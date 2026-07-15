"""Move confirmed duplicate papers to _duplicates/ (retain paper_id min).

铁律#10: 重复论文保留 paper_id 最小。
- P01626 < P09065: 移除 P09065 (台州电子废物, 8值逐点相同)
- P07067 < P07068: 移除 P07068 (贵屿焚烧点, 21值逐点相同)
用 shutil.move (非 shell mv) 避免中文用户名 MSYS 编码坑。
"""
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
DUP = BASE + "/_duplicates"
os.makedirs(DUP, exist_ok=True)

TO_MOVE = ["P09065", "P07068"]  # 保留 P01626, P07067
moved = []
for pid in TO_MOVE:
    for pool in ["hm_op", "op_only"]:
        src = f"{BASE}/{pool}/{pid}.csv"
        if os.path.exists(src):
            dst = f"{DUP}/{pid}.csv"
            if os.path.exists(dst):
                print(f"  [跳过] {dst} 已存在")
                continue
            shutil.move(src, dst)
            moved.append(f"{pool}/{pid}.csv → _duplicates/{pid}.csv")

print(f"移动 {len(moved)} 个重复论文到 _duplicates/:")
for m in moved:
    print(f"  {m}")
