"""宽松扫描: 找所有"含 HM + OP + 浓度单位 + 多行"表格的 HM+OP 论文

裴总判断: 几百篇一定有。之前 scan 太严(行采样点≥5),漏了小样本/中文点位/特殊编号。
本扫描放宽: 任何表格含 HM元素 + OP + 浓度单位 + 行≥4 → 候选(Agent精读判断)
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
OP_RE = re.compile(r"PAH|PCB|DDT|HCH|PBDE|BaP|Bap|petroleum|TPH|石油烃|多环|naphthalene|phenanthrene|pyrene|benzo|fluoranthene|chrysene|∑16|Σ16|有机氯|有机磷", re.I)
UNIT_RE = re.compile(r"mg\s*/?\s*kg|mg\s*kg|mg·kg|μg\s*/?\s*kg|ug\s*/?\s*kg|ng\s*/?\s*g|ng\s*kg|ppm|ppb", re.I)

def strip_tags(s): return re.sub(r"<[^>]+>", " ", s)

def main():
    v2 = pd.read_csv(OUT / "screen_hm_op_china_v2.csv", dtype=str, keep_default_na=False)
    done = set()
    for sub in ["hm_op", "op_only"]:
        d = OUT / "manual_extract" / sub
        if d.exists():
            for f in d.glob("*.csv"): done.add(f.stem)
    print(f"已读 {len(done)} 篇, 宽松扫描 HM+OP {len(v2)} 篇...")
    candidates = []
    for i, r in v2.iterrows():
        pid, stem = r["序号"], r["stem"]
        if pid in done: continue
        md = ROOT / stem / "parsed" / "paper.md"
        if not md.exists(): continue
        txt = md.read_text(encoding="utf-8", errors="replace")
        tables = TABLE_RE.findall(txt)
        best_hm_op_rows = 0
        best_has_both = False
        for tbl in tables:
            rows = TR_RE.findall(tbl)
            if len(rows) < 4: continue
            text = strip_tags(tbl)
            has_unit = bool(UNIT_RE.search(text))
            if not has_unit: continue
            has_hm = bool(HM_RE.search(text))
            has_op = bool(OP_RE.search(text))
            if has_hm and has_op:
                best_has_both = True
                best_hm_op_rows = max(best_hm_op_rows, len(rows))
        if best_has_both:
            candidates.append({"paper_id": pid, "stem": stem, "title": r["英文标题"],
                               "op_groups": r["op_groups"], "max_rows": best_hm_op_rows})
        if (i + 1) % 100 == 0:
            print(f"  进度 {i+1}/{len(v2)}, 已找 {len(candidates)} 候选")
    df = pd.DataFrame(candidates)
    df.to_csv(OUT / "scan_hmop_loose.csv", index=False, encoding="utf-8-sig")
    print(f"\n=== 宽松扫描结果 ===")
    print(f"未读 HM+OP 含 HM+OP+浓度表格的论文: {len(df)} 篇")
    print(f"按表格行数分布: {df['max_rows'].value_counts(bins=[0,10,20,50,100,1000]).sort_index().to_dict()}")
    print(f"\n候选样例(行数降序):")
    for _, r in df.sort_values("max_rows", ascending=False).head(20).iterrows():
        print(f"  {r['paper_id']} | {int(r['max_rows'])}行 | {r['op_groups'][:18]:18s} | {r['title'][:42]}")

if __name__ == "__main__":
    main()
