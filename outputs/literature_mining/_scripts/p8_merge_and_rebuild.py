"""P8 Step 2 收尾: 合并 C 级观测到 extracted_long + 重跑 P3 readiness + P7 训练表

流程:
  1. 备份 A+B extracted_long (仅首次)
  2. 合并 A+B + C 级 → extracted_observations_long_op_hmop.csv (列对齐, C 缺列补空)
  3. 重跑 P3 (canonical 归一化 + readiness 判定 + 质量门控, 自动处理 A+B+C)
  4. 重跑 P7 (生成两张训练表, 含 C 级深挖增量)

输出:
  - extracted_observations_long_op_hmop.csv (合并后, P3 加 canonical/readiness)
  - site_dataset_summary_op_hmop.csv (P3 重新判定)
  - train_table_op_only.csv (P7, OP-only 训练表)
  - train_table_hm_op.csv (P7, HM+OP 训练表)
"""
from __future__ import annotations
import sys
import shutil
import subprocess
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR  # noqa: E402

import pandas as pd  # noqa: E402


def merge():
    ab_path = OUT_DIR / "extracted_observations_long_op_hmop.csv"
    c_path = OUT_DIR / "c_level_observations.csv"
    bak_path = OUT_DIR / "extracted_observations_long_ab_only.csv.bak"
    # 备份 A+B 基线 (仅首次, 用于可重复合并, 避免重跑时 C 已合入导致重复累加)
    if not bak_path.exists():
        shutil.copy2(ab_path, bak_path)
        print(f"[备份] A+B 基线 → {bak_path.name}")
    # 总是从备份读 A+B (避免重跑重复合并)
    ab = pd.read_csv(bak_path, dtype=str, keep_default_na=False)
    c = pd.read_csv(c_path, dtype=str, keep_default_na=False)
    # 列对齐: C 级可能缺 canonical_sample_id/readiness/matrix_flag/cross_table_pairable (P3 添加的列)
    for col in ab.columns:
        if col not in c.columns:
            c[col] = ""
    c = c[ab.columns]
    # 去重 (同 source+sample+pollutant, A+B 和 C 理论不重叠, 但防御性)
    merged = pd.concat([ab, c], ignore_index=True)
    merged.to_csv(ab_path, index=False, encoding="utf-8-sig")
    print(f"[P8 合并] A+B {len(ab)} + C {len(c)} = {len(merged)} 观测 / {merged['paper_id'].nunique()} 论文")


def rerun(script: str) -> int:
    r = subprocess.run([sys.executable, str(Path(__file__).parent / script)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"\n{'='*60}\n=== {script} ===\n{'='*60}")
    out = r.stdout or ""
    print(out[-2500:] if len(out) > 2500 else out)
    if r.returncode != 0:
        print(f"[ERROR {r.returncode}] {r.stderr[-1500:]}")
    return r.returncode


if __name__ == "__main__":
    merge()
    rc1 = rerun("p3_judge_readiness.py")
    rc2 = rerun("p7_build_train_tables.py") if rc1 == 0 else 1
    if rc1 == 0 and rc2 == 0:
        print("\n[P8] 完成. 两张训练表已更新 (含 C 级深挖 633 观测增量).")
    else:
        print(f"\n[P8] 异常: P3 rc={rc1}, P7 rc={rc2}. 请检查日志.")
