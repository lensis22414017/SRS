"""Step 2 前置: 快速 probe C 级 1055 篇 OP-only 的表格可抽性

复用 p2_probe_v2 逻辑, 目标改为 candidate_level=='C'.
评估 C 级有多少 HTML 表可抽取 (决定 extract 工作量).
"""
from __future__ import annotations
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, LIT_ROOT  # noqa: E402

import pandas as pd  # noqa: E402

TABLE_OPEN_PAT = re.compile(r"<table[\s>]", re.I)
TR_PAT = re.compile(r"<tr[\s>]", re.I)


def main():
    cand = pd.read_csv(OUT_DIR / "candidate_literature_op_hmop.csv", dtype=str, keep_default_na=False)
    c_level = cand[cand["candidate_level"] == "C"]
    print(f"C 级 (OP-only 中国土壤) 论文: {len(c_level)}")

    n_with_table = 0
    n_total_tables = 0
    n_with_many_tables = 0  # ≥5 表 (高可抽性)
    n_no_md = 0
    tr_distribution = []

    for _, r in c_level.iterrows():
        md = LIT_ROOT / r["stem"] / "parsed" / "paper.md"
        if not md.exists():
            n_no_md += 1
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            n_no_md += 1
            continue
        n_tables = len(TABLE_OPEN_PAT.findall(text))
        n_tr = len(TR_PAT.findall(text))
        if n_tr >= 3:
            n_with_table += 1
            n_total_tables += n_tables
            if n_tables >= 5:
                n_with_many_tables += 1
            tr_distribution.append(n_tr)

    print(f"\n=== C 级表格可抽性 ===")
    print(f"paper.md 缺失: {n_no_md}")
    print(f"有 HTML 表 (≥3 <tr>): {n_with_table} / {len(c_level)} ({n_with_table/len(c_level)*100:.0f}%)")
    print(f"表格总数: {n_total_tables}")
    print(f"高可抽性 (≥5 表): {n_with_many_tables} 篇")
    if tr_distribution:
        tr_series = pd.Series(tr_distribution)
        print(f"<tr> 行数分布: 中位={tr_series.median():.0f}, 均值={tr_series.mean():.0f}, "
              f"p90={tr_series.quantile(0.9):.0f}, max={tr_series.max()}")

    print(f"\n=== 增量预估 ===")
    # 假设有表论文平均贡献 5-10 个 OP 观测
    est_low = n_with_table * 3
    est_high = n_with_table * 10
    print(f"按每篇 3-10 观测估算, C 级可补 OP 观测: {est_low}-{est_high}")
    print(f"当前 OP-only sample: 212 → 深挖后预期 {212 + est_low//3}-{212 + est_high//3} sample (每 3 观测≈1 sample)")
    print(f"\n结论: {'✅ 值得全量 extract' if n_with_table > 100 else '⚠️ 表格少, 需图片数字化'}")


if __name__ == "__main__":
    main()
