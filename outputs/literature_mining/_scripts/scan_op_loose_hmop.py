"""宽松扫描 OP-only 1328 篇, 找含 HM+OP+浓度表格的隐藏 HM+OP 论文

之前 scan_hm_in_op 只找 HM 表,漏了 HM+OP 同表。
本扫描: OP-only 论文里找含 HM元素+OP+浓度单位+多行的表格(可转HM+OP)
"""
import sys, re
from pathlib import Path
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except: pass
import pandas as pd

ROOT = Path(r"G:\文献整理_最终")
OUT = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining")
TABLE_RE = re.compile(r"<table>(.*?)</table>", re.DOTALL | re.IGNORECASE)
TR_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
HM_RE = re.compile(r"\b(Cd|Pb|Cr|As|Hg|Cu|Zn|Ni|Cadmium|Lead|Chromium|Arsenic|Mercury|Copper|Zinc|Nickel|镉|铅|铬|砷|汞|铜|锌|镍)\b")
OP_RE = re.compile(r"PAH|PCB|DDT|HCH|PBDE|BaP|Bap|petroleum|TPH|石油烃|多环|naphthalene|phenanthrene|pyrene|benzo|fluoranthene|chrysene|∑16|Σ16", re.I)
UNIT_RE = re.compile(r"mg\s*/?\s*kg|mg\s*kg|mg·kg|μg\s*/?\s*kg|ug\s*/?\s*kg|ng\s*/?\s*g|ng\s*kg|ppm|ppb", re.I)

def strip_tags(s): return re.sub(r"<[^>]+>", " ", s)

def main():
    v2 = pd.read_csv(OUT / "screen_op_china_v2.csv", dtype=str, keep_default_na=False)
    done = set()
    for sub in ["hm_op", "op_only"]:
        d = OUT / "manual_extract" / sub
        if d.exists():
            for f in d.glob("*.csv"): done.add(f.stem)
    candidates = []
    for i, r in v2.iterrows():
        pid, stem = r["序号"], r["stem"]
        if pid in done: continue
        md = ROOT / stem / "parsed" / "paper.md"
        if not md.exists(): continue
        txt = md.read_text(encoding="utf-8", errors="replace")
        best_rows = 0
        found = False
        for tbl in TABLE_RE.findall(txt):
            rows = TR_RE.findall(tbl)
            if len(rows) < 4: continue
            text = strip_tags(tbl)
            if not UNIT_RE.search(text): continue
            if HM_RE.search(text) and OP_RE.search(text):
                found = True
                best_rows = max(best_rows, len(rows))
        if found:
            candidates.append({"paper_id": pid, "stem": stem, "title": r["英文标题"], "op_groups": r["op_groups"], "max_rows": best_rows})
        if (i + 1) % 300 == 0:
            print(f"  进度 {i+1}/{len(v2)}, 候选 {len(candidates)}")
    df = pd.DataFrame(candidates)
    df.to_csv(OUT / "scan_op_hmop_hidden.csv", index=False, encoding="utf-8-sig")
    print(f"\nOP-only 含 HM+OP+浓度表格(未读): {len(df)} 篇")
    for _, r in df.sort_values("max_rows", ascending=False).head(25).iterrows():
        print(f"  {r['paper_id']} | {int(r['max_rows'])}行 | {r['op_groups'][:18]:18s} | {r['title'][:42]}")

if __name__ == "__main__":
    main()
