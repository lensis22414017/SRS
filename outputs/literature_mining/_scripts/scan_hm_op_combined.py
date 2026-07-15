"""最终综合扫描: 找"采样点行 + HM + OP 同表"的遗漏 HM+OP 论文

之前 scan_sample_row 找采样点表, scan_hm_in_op 找 HM 表。
本扫描专门找 HM+OP 同表 (一行采样点, 列含 HM 元素 + OP 族), 这是 A 级 HM+OP 数据。
"""
from __future__ import annotations
import sys, re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd

ROOT = Path(r"G:\文献整理_最终")
OUT = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining")
TABLE_RE = re.compile(r"<table>(.*?)</table>", re.DOTALL | re.IGNORECASE)
TR_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
HM_RE = re.compile(r"\b(Cd|Pb|Cr|As|Hg|Cu|Zn|Ni)\b")
OP_RE = re.compile(r"PAH|PCB|DDT|HCH|PBDE|BaP|Bap|petroleum|TPH|石油烃|多环|Σ16|∑16|naphthalene|phenanthrene|pyrene|benzo", re.I)
STAT_RE = re.compile(r"^(mean|max|min|median|sd|std|sem|range|average|背景|阈值|grade)", re.I)


def strip(s):
    return re.sub(r"<[^>]+>", " ", s).strip()


def is_sample(s):
    s = strip(s)
    if not s or len(s) > 30 or STAT_RE.match(s):
        return False
    if re.match(r"^[\d.]+\.\d", s):
        return False
    if re.match(r"^\d{1,4}$", s):
        return True
    if re.match(r"^(s|site|station|sample|sp|st|bh|p)\s*[-_]?\d", s, re.I):
        return True
    if re.match(r"^[A-Za-z]\d{0,2}$", s) and len(s) <= 3:
        return True
    if re.search(r"[一-鿿]", s) and len(s) <= 12 and not any(w in s for w in ["均值", "平均", "最大", "最小", "标准", "背景", "阈", "含量", "浓度"]):
        return True
    return False


def scan_table_hmop(tbl):
    rows = TR_RE.findall(tbl)
    if len(rows) < 5:
        return None
    parsed = [[strip(c) for c in CELL_RE.findall(r)] for r in rows]
    text = " ".join(c for r in parsed for c in r)
    has_unit = bool(re.search(r"mg\s*/?\s*kg|mg\s*kg|μg|ng\s*/?\s*g|ppm|ppb", text, re.I))
    if not has_unit:
        return None
    # 行采样点
    row_samples = sum(1 for cells in parsed[1:] if cells and is_sample(cells[0]))
    # 列采样点 (转置)
    header = parsed[0] if parsed else []
    col_samples = sum(1 for c in header[1:] if is_sample(c)) if len(header) > 3 else 0
    # HM + OP 同表 (文本含 HM 元素≥3 + OP)
    hm_cnt = len(HM_RE.findall(text))
    has_op = bool(OP_RE.search(text))
    if hm_cnt < 3 or not has_op:
        return None
    # HM/OP 作列名或行名
    hm_cols = sum(1 for c in header if HM_RE.search(c))
    op_cols = sum(1 for c in header if OP_RE.search(c))
    hm_rows = sum(1 for cells in parsed[1:] if cells and HM_RE.search(cells[0]))
    op_rows = sum(1 for cells in parsed[1:] if cells and OP_RE.search(cells[0]))
    is_hmop_same = (hm_cols >= 3 and op_cols >= 1) or (hm_rows >= 3 and op_rows >= 1)
    if not is_hmop_same:
        return None
    return {"n_rows": len(rows), "row_samples": row_samples, "col_samples": col_samples,
            "hm_cols": hm_cols, "op_cols": op_cols, "hm_rows": hm_rows, "op_rows": op_rows}


def main():
    done = set()
    # 所有已读 paper_id (hm_op + op_only manual_extract 目录)
    for sub in ["hm_op", "op_only"]:
        d = OUT / "manual_extract" / sub
        if d.exists():
            for f in d.glob("*.csv"):
                done.add(f.stem)
    print(f"已读 {len(done)} 篇, 扫描未读的 HM+OP 同表...")

    results = []
    for pool, screen_file in [("hmop", "screen_hm_op_china_v2.csv"), ("op_only", "screen_op_china_v2.csv")]:
        v2 = pd.read_csv(OUT / screen_file, dtype=str, keep_default_na=False)
        for i, r in v2.iterrows():
            pid, stem = r["序号"], r["stem"]
            if pid in done:
                continue
            md = ROOT / stem / "parsed" / "paper.md"
            if not md.exists():
                continue
            txt = md.read_text(encoding="utf-8", errors="replace")
            for tbl in TABLE_RE.findall(txt):
                info = scan_table_hmop(tbl)
                if info and (info["row_samples"] >= 5 or info["col_samples"] >= 5):
                    results.append({"paper_id": pid, "stem": stem, "pool": pool,
                                    "title": r["英文标题"], "op_groups": r["op_groups"], **info})
                    break
            if (i + 1) % 400 == 0:
                print(f"  {pool} 进度 {i+1}/{len(v2)}")
    df = pd.DataFrame(results)
    if df.empty:
        print("\n未找到未读的 HM+OP 同表候选")
        return
    df.to_csv(OUT / "scan_hmop_sametable.csv", index=False, encoding="utf-8-sig")
    print(f"\n=== 未读 HM+OP 同表候选: {len(df)} 篇 ===")
    for _, r in df.sort_values(["row_samples", "col_samples"], ascending=False).head(25).iterrows():
        print(f"  {r['paper_id']} | 行{int(r['row_samples'])} 列{int(r['col_samples'])} HM列{int(r['hm_cols'])} OP列{int(r['op_cols'])} | {r['pool']} | {r['op_groups'][:18]:18s} | {r['title'][:40]}")


if __name__ == "__main__":
    main()
