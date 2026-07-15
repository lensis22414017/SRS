"""精准定位: 表格行或列结构是"采样点"的论文 (真正采样点级数据)

裴总铁律: 脚本只定位不提取。
检测两种采样点级表格结构:
  A. 行=采样点(第一列是S1/A/B/点位名), 列=污染物元素 → Table 2 式
  B. 列=采样点(表头列名是采样点), 行=PAH/PCB单体 → Table 3/4 式 (转置)
候选: 至少1个表有≥5个采样点行/列 + 含浓度单位
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
TH_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.DOTALL | re.IGNORECASE)
UNIT_RE = re.compile(r"mg\s*/?\s*kg|μg|ug\s*/?\s*kg|ng\s*/?\s*g|ppm|ppb|mg·kg|μg·kg", re.I)


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s).strip()


STAT_WORDS = {"mean", "max", "min", "median", "sd", "std", "sem", "range",
              "average", "cv", "skewness", "kurtosis", "sum", "total", "平均值",
              "最大值", "最小值", "标准差", "均值", "中位数", "总和", "极差", "范围"}


def is_sample_label(s: str) -> bool:
    """判断字符串是否像采样点标识(非浓度值/非统计量/非污染物)"""
    s = strip_tags(s).strip()
    if not s or len(s) > 40:
        return False
    low = s.lower()
    # 浓度值(小数/科学计数) → 不是采样点
    if re.match(r"^[\d.]+\d$", s) and "." in s:
        return False
    # 纯数字 1-3 位(采样点编号 S1/sample1/纯数字)
    if re.match(r"^\d{1,4}$", s):
        return True
    # S1/S01/sample1/site1/station1/Sample point
    if re.match(r"^(s|site|station|sample|sp|st|bh|p)\s*[-_]?\d{1,4}", low):
        return True
    # 单字母或字母+数字 (A/B/C/S1a/点A)
    if re.match(r"^[A-Za-z]\d{0,2}$", s) and len(s) <= 3:
        return True
    # 中文点位(村庄/地名/厂名) - 含中文且短
    if re.search(r"[一-鿿]", s) and len(s) <= 12:
        # 排除统计量/参数中文
        if not any(w in s for w in ["均值", "平均", "最大", "最小", "标准", "总和",
                                     "背景", "阈", "含量", "浓度", "深度", "编号", "项目",
                                     "处理", "对照", "空白", "性质", "类型", "样品"]):
            return True
    # 含 site/point/sample 英文词
    if re.search(r"\bsite\b|\bpoint\b|\bsample\b|\bstation\b", low) and len(s) <= 25:
        return True
    return False


def STAT_WORDS_pattern():
    return r""


def is_stat_or_pollutant(s: str) -> str:
    s = strip_tags(s).strip().lower()
    if not s:
        return "empty"
    if s in STAT_WORDS or any(w in s for w in ["均值", "平均", "最大", "最小", "标准", "背景", "阈"]):
        return "stat"
    if re.match(r"^(cd|pb|cr|as|hg|cu|zn|ni|co|mn|fe|al|v|se|sb|pah|pcb|ddt|hch|pbde|pfas|pae|ocp|tph|phc|bap|nap|ace|acy|fle|phe|ant|flt|pyr|baa|chr|bbf|bkf|icdp|daha|bghip|petroleum|naphthalene|phenanthrene|pyrene|benzo|石油烃|多环|重金属)", s):
        return "pollutant"
    return "other"


def scan_table(tbl: str) -> dict:
    rows = TR_RE.findall(tbl)
    if len(rows) < 4:
        return {"n_rows": len(rows), "row_samples": 0, "col_samples": 0}
    tbl_text = strip_tags(tbl)
    has_unit = bool(UNIT_RE.search(tbl_text))

    # 解析每行的单元格
    parsed = []
    for r in rows:
        cells = [strip_tags(c) for c in TH_RE.findall(r)]
        parsed.append(cells)
    if not parsed:
        return {"n_rows": len(rows), "row_samples": 0, "col_samples": 0}

    # 结构A: 行=采样点 (第一列是采样点标识)
    row_sample_cnt = 0
    for cells in parsed[1:]:  # 跳过表头
        if cells and is_sample_label(cells[0]):
            row_sample_cnt += 1

    # 结构B: 列=采样点 (表头列名是采样点标识, 行=单体)
    header = parsed[0] if parsed else []
    col_sample_cnt = sum(1 for c in header[1:] if is_sample_label(c)) if len(header) > 2 else 0
    # 行标签应为污染物单体(转置表特征)
    pollutant_rows = sum(1 for cells in parsed[1:] if cells and is_stat_or_pollutant(cells[0]) == "pollutant")

    # 列=采样点表: 表头多采样点 + 行标签多污染物
    is_transposed = col_sample_cnt >= 5 and pollutant_rows >= 3
    return {"n_rows": len(rows), "row_samples": row_sample_cnt,
            "col_samples": col_sample_cnt, "has_unit": has_unit,
            "is_transposed": is_transposed}


def scan_paper(md_path: Path) -> dict:
    try:
        txt = md_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {"n_tables": 0, "best_row_samples": 0, "best_col_samples": 0, "candidate": False}
    tables = TABLE_RE.findall(txt)
    best_row = best_col = 0
    candidate = False
    for tbl in tables:
        info = scan_table(tbl)
        if info.get("has_unit") and info["row_samples"] >= 5:
            candidate = True
            best_row = max(best_row, info["row_samples"])
        if info.get("is_transposed") and info.get("has_unit"):
            candidate = True
            best_col = max(best_col, info["col_samples"])
    return {"n_tables": len(tables), "best_row_samples": best_row,
            "best_col_samples": best_col, "candidate": candidate}


def scan_pool(pool: str, screen_file: str):
    v2 = pd.read_csv(OUT / screen_file, dtype=str, keep_default_na=False)
    print(f"\n>>> 精准扫描 {pool} (精确中国) {len(v2)} 篇...")
    results = []
    for i, r in v2.iterrows():
        pid, stem = r["序号"], r["stem"]
        md = ROOT / stem / "parsed" / "paper.md"
        if not md.exists():
            continue
        info = scan_paper(md)
        results.append({"paper_id": pid, "stem": stem, "op_groups": r["op_groups"],
                        "title": r["英文标题"], **info})
        if (i + 1) % 200 == 0:
            print(f"  进度 {i+1}/{len(v2)}")
    df = pd.DataFrame(results)
    df.to_csv(OUT / f"scan_sample_row_{pool}.csv", index=False, encoding="utf-8-sig")
    cand = df[df["candidate"] == True]
    strong = cand[(cand["best_row_samples"] >= 8) | (cand["best_col_samples"] >= 8)]
    print(f"  {pool}: 候选 {len(cand)} 篇, 强候选(≥8采样点) {len(strong)} 篇")
    return strong


def main():
    strong_hm = scan_pool("hmop", "screen_hm_op_china_v2.csv")
    strong_op = scan_pool("op_only", "screen_op_china_v2.csv")
    print(f"\n=== 强候选汇总 (排除修复/实验类) ===")
    for label, strong in [("HM+OP", strong_hm), ("OP-only", strong_op)]:
        strong = strong.copy()
        strong["title_low"] = strong["title"].str.lower()
        exc = strong["title_low"].str.contains("remediation|biochar|phyto|plant-microbial|consortium|immobili|review|biostimulant|bacterial|degrad|removal|simultaneous|bioremedi|sorption|adsorp|mycore|degradat")
        field = strong[~exc].sort_values(["best_row_samples", "best_col_samples"], ascending=False)
        print(f"\n--- {label} 场地实测强候选 ({len(field)} 篇) ---")
        for _, r in field.head(25).iterrows():
            print(f"  {r['paper_id']} | 行{r['best_row_samples']} 列{r['best_col_samples']} | {r['op_groups'][:18]:18s} | {r['title'][:42]}")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
