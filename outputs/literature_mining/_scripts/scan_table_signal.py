"""扫描 HM+OP 论文 paper.md，定位"主文含采样点级浓度表格"的候选论文

裴总铁律: 脚本只做定位(哪些论文可能有采样点级数据), 不做提取(提取靠Agent精读)
信号: 表格行数≥6 + 含浓度单位(mg/kg|μg/kg|ng/g) + 含采样点标识(S\d+|Sample|点位|单字母) + 含HM/OP污染物词
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

UNIT_PAT = re.compile(r"mg\s*/?\s*kg|μg\s*/?\s*kg|ug\s*/?\s*kg|ng\s*/?\s*g|mg\s*kg|μg\s*kg|ppm|ppb|mg·kg|μg·kg", re.I)
SAMPLE_LABEL_PAT = re.compile(r"\bS\d{1,3}\b|Sample\s*\d|sample\s*site|sampling\s*site|sampling\s*point|\b[A-G]\b\s|点位|采样点|site\s*\d|ST\d|BH\d|P\d{1,3}\b", re.I)
POLLUTANT_PAT = re.compile(r"Cd|Pb|Cr|As|Hg|Cu|Zn|Ni|PAH|PCB|DDT|HCH|PBDE|petroleum|石油烃|多环芳烃|重金属|cadmium|lead|arsenic|mercury|naphthalene|phenanthrene|pyrene|benzo", re.I)
TABLE_RE = re.compile(r"<table>(.*?)</table>", re.DOTALL | re.IGNORECASE)
TR_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s)


def scan_paper(md_path: Path) -> dict:
    try:
        txt = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"n_tables": 0, "max_rows": 0, "best_signal": 0, "candidate_tables": 0}
    tables = TABLE_RE.findall(txt)
    max_rows = 0
    candidate_tables = 0
    best_signal = 0  # 0-3 信号强度
    for tbl in tables:
        rows = TR_RE.findall(tbl)
        n_rows = len(rows)
        if n_rows > max_rows:
            max_rows = n_rows
        tbl_text = strip_tags(tbl)
        has_unit = bool(UNIT_PAT.search(tbl_text))
        has_label = bool(SAMPLE_LABEL_PAT.search(tbl_text))
        has_pollutant = bool(POLLUTANT_PAT.search(tbl_text))
        # 数值行数 (含小数/科学计数 的行)
        n_numeric = sum(1 for r in rows if re.search(r"\d+\.?\d*", strip_tags(r)) and re.search(r"\d", strip_tags(r)))
        signal = sum([has_unit, has_label, has_pollutant])
        # 候选: 行数≥6 + 至少2个信号 + 有数值行
        if n_rows >= 6 and signal >= 2 and n_numeric >= 4:
            candidate_tables += 1
            if signal > best_signal:
                best_signal = signal
    return {"n_tables": len(tables), "max_rows": max_rows, "best_signal": best_signal, "candidate_tables": candidate_tables}


def main():
    screen = pd.read_csv(OUT / "screen_hm_op_china_compound.csv", dtype=str, keep_default_na=False)
    print(f"扫描 HM+OP 论文: {len(screen)} 篇...")
    results = []
    for i, r in screen.iterrows():
        pid, stem = r["序号"], r["stem"]
        md = ROOT / stem / "parsed" / "paper.md"
        if not md.exists():
            results.append({"paper_id": pid, "stem": stem, "op_groups": r["op_groups"],
                            "title": r["英文标题"], "n_tables": 0, "max_rows": 0,
                            "best_signal": 0, "candidate_tables": 0, "parsed": False})
            continue
        info = scan_paper(md)
        results.append({"paper_id": pid, "stem": stem, "op_groups": r["op_groups"],
                        "title": r["英文标题"], "parsed": True, **info})
        if (i + 1) % 100 == 0:
            print(f"  进度 {i+1}/{len(screen)}")
    df = pd.DataFrame(results)
    df.to_csv(OUT / "scan_hm_op_table_signal.csv", index=False, encoding="utf-8-sig")

    # 候选 = candidate_tables >= 1 (主文至少1个采样点级表格)
    cand = df[(df["parsed"]) & (df["candidate_tables"] >= 1)]
    strong = df[(df["parsed"]) & (df["candidate_tables"] >= 1) & (df["best_signal"] >= 3)]
    print(f"\n=== 扫描结果 ===")
    print(f"总 HM+OP: {len(df)} (已解析 {df['parsed'].sum()})")
    print(f"主文有采样点级表格候选 (candidate_tables≥1): {len(cand)} 篇")
    print(f"强信号 (signal=3, 单位+采样点标识+污染物全有): {len(strong)} 篇")
    print(f"\n候选论文 op_groups 分布:")
    print(cand["op_groups"].value_counts().head(15).to_string())
    print(f"\n强信号 top 30 (按 candidate_tables 降序):")
    top = strong.sort_values(["candidate_tables", "max_rows"], ascending=False).head(30)
    for _, r in top.iterrows():
        print(f"  {r['paper_id']} | {r['candidate_tables']}表 {r['max_rows']}行 sig={r['best_signal']} | {r['op_groups'][:25]:25s} | {r['title'][:45]}")


if __name__ == "__main__":
    main()
