"""精准扫描 OP-only 1328 篇 + HM+OP 弱候选, 找隐藏的 HM 采样点表 (可转 HM+OP)

检测 HM 采样点表特征:
  - 表格含 HM 元素 (Cd/Pb/Cr/As/Hg/Cu/Zn/Ni) 作列名或行标签
  - mg/kg 单位
  - 行采样点≥5 (行标签 S1/A/B/数字) 或列采样点≥5 (转置)
  - 排除统计行(Mean/Max)/标准阈值(Grade)/风险指数
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
HM_ELEM_RE = re.compile(r"\b(Cd|Pb|Cr|As|Hg|Cu|Zn|Ni|Cadmium|Lead|Chromium|Arsenic|Mercury|Copper|Zinc|Nickel)\b")
STAT_RE = re.compile(r"^(mean|max|min|median|sd|std|sem|range|average|cv|sum|total|背景|阈值|标准|grade)", re.I)


def strip(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s).strip()


def is_sample(s: str) -> bool:
    s = strip(s)
    if not s or len(s) > 30:
        return False
    if re.match(r"^[\d.]+\.\d", s):
        return False  # 浓度值
    if STAT_RE.match(s):
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


def scan_table_hm(tbl: str) -> dict:
    rows = TR_RE.findall(tbl)
    if len(rows) < 5:
        return {}
    parsed = [[strip(c) for c in CELL_RE.findall(r)] for r in rows]
    text = " ".join(c for r in parsed for c in r)
    has_mgkg = bool(re.search(r"mg\s*/?\s*kg|mg\s*kg|mg·kg|ppm", text, re.I))
    hm_mentions = len(HM_ELEM_RE.findall(text))
    if not has_mgkg or hm_mentions < 3:
        return {}
    # 行采样点 (第一列)
    row_samples = sum(1 for cells in parsed[1:] if cells and is_sample(cells[0]))
    # 列采样点 (表头)
    header = parsed[0] if parsed else []
    col_samples = sum(1 for c in header[1:] if is_sample(c)) if len(header) > 3 else 0
    # HM 元素作列名 (表头含 Cd/Pb/...)
    hm_in_header = sum(1 for c in header if HM_ELEM_RE.search(c))
    # HM 元素作行标签 (转置表, 行=单体)
    hm_in_rows = sum(1 for cells in parsed[1:] if cells and HM_ELEM_RE.search(cells[0]))
    return {"n_rows": len(rows), "row_samples": row_samples, "col_samples": col_samples,
            "hm_in_header": hm_in_header, "hm_in_rows": hm_in_rows, "hm_mentions": hm_mentions}


def scan_paper(md_path: Path) -> dict:
    try:
        txt = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    tables = TABLE_RE.findall(txt)
    best = {"n_tables": len(tables), "hm_row_best": 0, "hm_col_best": 0, "hm_tables": 0}
    for tbl in tables:
        info = scan_table_hm(tbl)
        if not info:
            continue
        # HM 采样点表: 行采样点≥5 + HM作列名, 或 列采样点≥5 + HM作行名(转置)
        is_hm_sample = (info["row_samples"] >= 5 and info["hm_in_header"] >= 3) or \
                       (info["col_samples"] >= 5 and info["hm_in_rows"] >= 3)
        if is_hm_sample:
            best["hm_tables"] += 1
            best["hm_row_best"] = max(best["hm_row_best"], info["row_samples"])
            best["hm_col_best"] = max(best["hm_col_best"], info["col_samples"])
    return best


def main():
    done = {'P01524','P01718','P02763','P00395','P03207','P10229','P01301','P04081','P11292','P03329','P00643','P08598','P03103','P01630','P01245','P01595','P11484','P04010','P11182','P00340','P01177','P11543','P11184','P08445','P04324','P01428','P01919','P03773','P11023','P00027','P03102','P04194','P11362','P00753','P11547','P10228','P06697','P10369','P00217','P01244','P09845','P03279','P11294','P11554','P03334','P01670','P01836','P01267','P01797','P01646','P01294','P00208','P06725','P02763'}
    results = []
    for pool, screen_file in [("OP-only 隐藏HM", "screen_op_china_v2.csv"), ("HM+OP 弱候选", "screen_hm_op_china_v2.csv")]:
        v2 = pd.read_csv(OUT / screen_file, dtype=str, keep_default_na=False)
        print(f"\n>>> 扫描 {pool} {len(v2)} 篇...")
        for i, r in v2.iterrows():
            pid, stem = r["序号"], r["stem"]
            if pid in done:
                continue
            md = ROOT / stem / "parsed" / "paper.md"
            if not md.exists():
                continue
            info = scan_paper(md)
            if info.get("hm_tables", 0) > 0:
                info["paper_id"] = pid
                info["stem"] = stem
                info["pool"] = pool
                info["title"] = r["英文标题"]
                info["op_groups"] = r["op_groups"]
                results.append(info)
            if (i + 1) % 300 == 0:
                print(f"  进度 {i+1}/{len(v2)}")
    df = pd.DataFrame(results)
    if df.empty:
        print("\n未找到含 HM 采样点表的候选")
        return
    df.to_csv(OUT / "scan_hm_hidden.csv", index=False, encoding="utf-8-sig")
    print(f"\n=== 隐藏 HM+OP 候选 (未读, 含 HM 采样点表) ===")
    print(f"总数: {len(df)} 篇")
    for _, r in df.sort_values(["hm_row_best", "hm_col_best"], ascending=False).head(30).iterrows():
        print(f"  {r['paper_id']} | 行{int(r['hm_row_best'])} 列{int(r['hm_col_best'])} {int(r['hm_tables'])}表 | {r['pool'][:12]} | {r['op_groups'][:18]:18s} | {r['title'][:42]}")


if __name__ == "__main__":
    main()
