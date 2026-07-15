"""P2C 诊断: 扫描 C 级前 N 篇 conc 表的列标题/内容, 统计污染物词频

目的: 指导 parse_header 扩展方向. 避免盲目扩展 (Karpathy 4.1).
统计: Sum/Total 族群词 vs PAH 单体英文名 vs PAH 缩写 vs 中文 vs PFAS/PCB/BDE/DDT 单体.
输出: 各词类在 conc 表中的占比 + 前 20 个 conc 表的列标题样本 (人工核验).
"""
from __future__ import annotations
import sys
import os
import re
from io import StringIO
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, LIT_ROOT  # noqa: E402
from p2_classify_tables_v2 import classify_one, extract_title  # noqa: E402
from p2_extract import find_header_row, clean_latex  # noqa: E402

import pandas as pd  # noqa: E402

TABLE_OPEN_PAT = re.compile(r"<table[\s>]", re.I)

# 待统计的污染物词类 (用于判断 parse_header 需扩展哪些)
WORD_CLASSES = {
    "Sum_Total_PAH（现有识别）": [r"∑\s*PAH|ΣPAH|total\s*PAH|sum\s*PAH|TPAH|∑\s*\d+\s*PAH"],
    "PAH_单体_英文名": [r"\bnaphthalene\b|\bacenaphthyl|\bacenaphthene\b|\bfluorene\b|"
                       r"\bphenanthrene\b|\banthracene\b|\bfluoranthene\b|\bpyrene\b|"
                       r"\bchrysene\b|benzo\s*[\[(].*?[\])].*?(?:anthracene|pyrene|fluoranthene|perylene)|"
                       r"\bindeno\b|\bdibenzo\b|\bperylen"],
    "PAH_缩写": [r"\bBaP\b|\bBbF\b|\bBkF\b|\bBaA\b|\bBghiP\b|\bBgP\b|\bDahA\b|\bIcdP\b|\bDBahA\b"],
    "PAH_中文": [r"苯并\[?a\]?芘|苯并芘|萘|菲|芘|荧蒽|蒽|屈|䓛|苝|苯并蒽|苯并苝"],
    "Sum_PCB（现有）": [r"∑\s*PCB|total\s*PCB|ΣPCB|sum\s*PCB"],
    "PCB_同系物": [r"\bPCB-?\d+|\bCB-?\d+"],
    "BDE_同系物": [r"\bBDE-?\d+|\bPBDE-?\d+"],
    "PFAS_单体": [r"\bPFOS\b|\bPFOA\b|\bPFNA\b|\bPFHxS\b|\bPFBS\b|\bPFHpA\b|\bPFHxA\b|\bPFTA\b|\bPFUnA\b|\bPFDoA\b"],
    "DDT_单体": [r"p\s*,\s*p.?-?\s*DD[TDE]|o\s*,\s*p.?-?\s*DD[TDE]|\bpp.?-?DD[TDE]|"
                 r"\bp\s*,\s*p.?-?DDT|\bDDD\b|\bDDE\b"],
    "HCH_单体": [r"[αβγδ]\s*-?\s*HCH|alpha\s*-?\s*HCH|beta\s*-?\s*HCH|gamma\s*-?\s*HCH|delta\s*-?\s*HCH|"
                 r"α-HCH|β-HCH|γ-HCH|六六六"],
    "TPH_石油烃": [r"\bTPH\b|petroleum\s*hydrocarbon|TotalPHC|石油烃|总石油烃"],
    "中文_重金属": [r"镉|铅|汞|砷|铬|铜|锌|镍|类金属"],
}


def main():
    cand = pd.read_csv(OUT_DIR / "candidate_literature_op_hmop.csv", dtype=str, keep_default_na=False)
    c_level = cand[cand["candidate_level"] == "C"]
    limit = int(os.environ.get("P2C_DIAG_LIMIT", "100"))
    c_level = c_level.head(limit)
    print(f"诊断 C 级前 {len(c_level)} 篇\n")

    word_hits = {k: 0 for k in WORD_CLASSES}
    conc_table_count = 0
    header_samples = []
    paper_with_conc = set()

    for _, r in c_level.iterrows():
        md = LIT_ROOT / r["stem"] / "parsed" / "paper.md"
        if not md.exists():
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "<table" not in text.lower():
            continue
        positions = [m.start() for m in TABLE_OPEN_PAT.finditer(text)]
        try:
            tables = pd.read_html(StringIO(text))
        except Exception:
            continue
        for i, tbl in enumerate(tables):
            tbl_pos = positions[i] if i < len(positions) else 0
            title = extract_title(text[max(0, tbl_pos - 700):tbl_pos])
            try:
                tbl_text = tbl.to_string(index=False, header=False)
            except Exception:
                tbl_text = ""
            info = classify_one(tbl_text, title)
            if info["category"] in ("risk_or_source", "other"):
                continue
            conc_table_count += 1
            paper_with_conc.add(r["paper_id"])
            full_text = tbl_text + " " + title
            for k, pats in WORD_CLASSES.items():
                if any(re.search(p, full_text, re.I) for p in pats):
                    word_hits[k] += 1
            if len(header_samples) < 25:
                hr = find_header_row(tbl)
                if hr >= 0:
                    cols = []
                    for ci in range(min(tbl.shape[1], 12)):
                        h = clean_latex(f"{tbl.columns[ci]} {tbl.iloc[hr, ci]}")[:25]
                        cols.append(h)
                    header_samples.append((r["paper_id"], i, title[:55], cols, info["category"]))

    denom = conc_table_count or 1
    print(f"=== C 级前 {len(c_level)} 篇 conc 表统计 ===")
    print(f"conc 表总数: {conc_table_count} (涉及 {len(paper_with_conc)} 篇)")
    print(f"\n污染物词频 (占 conc 表 %):")
    for k, n in sorted(word_hits.items(), key=lambda x: -x[1]):
        bar = "#" * int(n / denom * 40)
        print(f"  {k:30s}: {n:4d} ({n/denom*100:4.0f}%) {bar}")

    print(f"\n=== 前 25 conc 表的列标题样本 (人工核验 parse_header 缺口) ===")
    for pid, ti, title, cols, cat in header_samples:
        print(f"\n[{pid} tbl#{ti} | {cat}] {title}")
        print(f"  cols: {cols}")

    print(f"\n=== 扩展建议 ===")
    if word_hits["PAH_单体_英文名"] / denom > 0.15 or word_hits["PAH_缩写"] / denom > 0.10:
        print("  [高优先] PAH 单体识别 (英文名+缩写 → Sum_PAH, BaP 单独)")
    if word_hits["PAH_中文"] / denom > 0.15:
        print("  [高优先] 中文 PAH 单体识别 (苯并芘/萘/菲...)")
    if word_hits["PCB_同系物"] / denom > 0.10:
        print("  [中优先] PCB 同系物识别 (PCB-28 等 → SumPCB)")
    if word_hits["PFAS_单体"] / denom > 0.10:
        print("  [中优先] PFAS 单体识别 (PFOS/PFOA → SumPFAS)")
    if word_hits["DDT_单体"] / denom > 0.10 or word_hits["HCH_单体"] / denom > 0.10:
        print("  [中优先] DDT/HCH 单体识别 (→ SumDDTs/SumHCHs)")
    if word_hits["Sum_Total_PAH（现有识别）"] / denom > 0.30:
        print("  [已覆盖] Sum/Total PAH 现有识别已够")


if __name__ == "__main__":
    main()
