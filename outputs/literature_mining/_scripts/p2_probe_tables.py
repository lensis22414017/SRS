"""P2 前置探测 v2: 修正 v1 的两个测量 bug

v1 bug:
  1. 只找 markdown `|` 表格 → 漏掉 MinerU 输出的 HTML <table> 标签
  2. images glob 只找 *.png → 实际全是 .jpg, 全报 0

v2 修正:
  - 统计 HTML <table> 出现数 + <tr> 行数 (表格规模)
  - 统计 images/ 所有图片格式 (jpg/jpeg/png/gif/bmp/webp)
  - 物理验证 si/*.pdf 存在性 (catalog SI 字段不可信)
  - 分级 extract_strategy:
      si_available   : 有 SI PDF → 优先精读 SI 找采样点表 (Tier 1)
      html_table     : 主文 HTML 表格 ≥5 行 → 解析统计汇总 (Tier 2)
      figure_only    : 仅图片 → needs_digitization (Tier 3)
      text_only      : 无表格无图 → 正文数值抽取 (Tier 4)
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
IMG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}


def count_images(img_dir: Path) -> int:
    if not img_dir.exists():
        return 0
    try:
        return sum(1 for f in img_dir.iterdir() if f.suffix.lower() in IMG_EXTS)
    except Exception:
        return 0


def main():
    cand = pd.read_csv(OUT_DIR / "candidate_literature_op_hmop.csv", dtype=str, keep_default_na=False)
    ab = cand[cand["candidate_level"].isin(["A", "B"])].copy()
    print(f"A+B 级候选总数: {len(ab)}")

    rows = []
    for _, r in ab.iterrows():
        stem = r["stem"]
        md = LIT_ROOT / stem / "parsed" / "paper.md"
        img_dir = LIT_ROOT / stem / "parsed" / "images"
        si_dir = LIT_ROOT / stem / "si"

        rec = {
            "paper_id": r["paper_id"], "level": r["candidate_level"], "stem": stem,
            "md_exists": md.exists(),
            "n_html_tables": 0, "n_tr_rows": 0, "has_html_table": False,
            "n_images": count_images(img_dir),
            "si_dir_exists": si_dir.exists(),
            "n_si_pdfs": 0,
            "total_md_lines": 0,
        }

        if si_dir.exists():
            try:
                rec["n_si_pdfs"] = sum(1 for f in si_dir.iterdir() if f.suffix.lower() == ".pdf")
            except Exception:
                rec["n_si_pdfs"] = 0

        if md.exists():
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            rec["total_md_lines"] = len(text.split("\n"))
            rec["n_html_tables"] = len(TABLE_OPEN_PAT.findall(text))
            rec["n_tr_rows"] = len(TR_PAT.findall(text))
            rec["has_html_table"] = rec["n_tr_rows"] >= 3  # 至少 3 行才算真表格

        # 分级 (优先级 si > html_table > figure > text)
        if rec["n_si_pdfs"] > 0:
            rec["extract_strategy"] = "si_available"
        elif rec["has_html_table"]:
            rec["extract_strategy"] = "html_table"
        elif rec["n_images"] > 0:
            rec["extract_strategy"] = "figure_only"
        else:
            rec["extract_strategy"] = "text_only"

        rows.append(rec)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "p2_probe_v2.csv", index=False, encoding="utf-8-sig")

    # ===== 统计 =====
    print(f"\n=== 真实可抽性分布 (修正 v1 bug 后) ===")
    print(f"paper.md 存在: {df['md_exists'].sum()}/{len(df)}")
    print(f"有 HTML 表格 (≥3 <tr>): {df['has_html_table'].sum()}")
    print(f"  其中 A 级: {((df['level']=='A') & df['has_html_table']).sum()}")
    print(f"  其中 B 级: {((df['level']=='B') & df['has_html_table']).sum()}")
    print(f"SI 目录存在: {df['si_dir_exists'].sum()}")
    print(f"有 SI PDF: {(df['n_si_pdfs']>0).sum()}")
    print(f"  其中 A 级: {((df['level']=='A') & (df['n_si_pdfs']>0)).sum()}")
    print(f"  其中 B 级: {((df['level']=='B') & (df['n_si_pdfs']>0)).sum()}")
    print(f"images/ 有图: {(df['n_images']>0).sum()}, 平均图数: {df['n_images'].mean():.1f}")

    print(f"\n=== extract_strategy 分布 (P2 调度依据) ===")
    print(df["extract_strategy"].value_counts().to_string())

    print(f"\n=== A 级强候选 SI/表格盘点 (P2 首批) ===")
    a_df = df[df["level"] == "A"].sort_values("n_si_pdfs", ascending=False)
    print(f"A 级共 {len(a_df)} 篇:")
    for _, r in a_df.head(30).iterrows():
        print(f"  {r['paper_id']} si={r['n_si_pdfs']} tbl={r['n_html_tables']} tr={r['n_tr_rows']:>3} img={r['n_images']:>3} [{r['extract_strategy']}] | {r['stem'][:40]}")

    # 裴总 14 强候选命中情况
    print(f"\n=== 裴总 14 强候选 SI/表格命中 ===")
    strong_ids = ["P01646", "P00137", "P00245", "P00408", "P00694", "P11648"]
    for pid in strong_ids:
        hit = df[df["paper_id"] == pid]
        if len(hit):
            r = hit.iloc[0]
            print(f"  {pid} [{r['level']}] si={r['n_si_pdfs']} tbl={r['n_html_tables']} tr={r['n_tr_rows']} img={r['n_images']} [{r['extract_strategy']}]")

    print(f"\n输出: {OUT_DIR / 'p2_probe_v2.csv'}")


if __name__ == "__main__":
    main()
