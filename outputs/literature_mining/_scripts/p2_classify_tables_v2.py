"""P2 表格二次分类: 区分真浓度表 vs 风险表/源解析表/统计汇总

v1 分类的 is_hm_op_table 假阳性严重:
  PMF 风险表/源解析表同时含 HM+PAH 风险值 → 被误判为复合数据表

v2 分类逻辑:
  1. 提取每个 <table> 前的表标题 (Table N. ... 文本, 前 600 字符)
  2. 浓度单位强信号: mg/kg, ng/g, μg/kg, ug/kg, ppb, dry wt, 干重, dw
  3. 风险词排除: risk, hazard, HQ, NCR, CR, carcinogen, PMF,
     source contribution, 源贡献, 风险, source-oriented
  4. 统计量列: Mean, SD, S.D., Median, Percentile, Min, Max, 平均, 标准差

输出分类:
  sample_conc    : 表标题含 concentration + 有单位 + 非风险 (P2 黄金目标)
  conc_like      : 无明确标题但有浓度单位 + 非风险非统计列
  summary_conc   : 浓度 + 统计量列为主 (site_summary 可用)
  risk_or_source : 含风险/源解析词 (排除, 不进训练)
  other          : 无浓度信号
"""
from __future__ import annotations
import sys
import re
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, LIT_ROOT  # noqa: E402

import pandas as pd  # noqa: E402

CONC_UNITS = [
    "mg/kg", "ng/g", "μg/kg", "ug/kg", "mg kg", "ng g", "µg/kg", "µg kg",
    "mg·kg", "ng·g", "mgkg", "ngg", "ugkg",
    "dry wt", "dry weight", "干重", "dw)", "(dw", "ppb", "ppm",
    "mg/kg dw", "ng/g dw",
]
RISK_WORDS = [
    "risk", "hazard quotient", "hq ", "ncr", "carcinogen", "非致癌", "致癌风险",
    "health risk", "ecological risk", "source-oriented", "source contribution",
    "pmf ", "positive matrix factorization", "源解析", "源贡献", "风险",
    "incremental lifetime", "ilcr", " 源 ", "pollution source",
]
SUMMARY_COLS = ["mean", "s.d.", " sd ", "sd)", "median", "percentile", " min ",
                " max ", "平均值", "标准差", "中位", "最小", "最大", "geoaccumulation",
                "i-geo", "igeo", "pli", "pollution load", "nemerow",
                "potential ecological risk", "eri ", "ri "]


def extract_title(text_before: str) -> str:
    """从 <table> 前的文本提取最近的 'Table N' / '表N' 标题行。"""
    lines = [l.strip() for l in text_before.split("\n") if l.strip()]
    # 从后往前找 Table N
    for l in reversed(lines[-12:]):
        if re.match(r"^(table\s*\d|表\s*\d|table\s*s\d|tables?\s+\d)", l, re.I):
            return l[:120]
        if re.match(r"^table\s", l, re.I):
            return l[:120]
    # 兜底: 返回最后 2 行
    return " | ".join(lines[-2:])[:120] if lines else "(无上下文)"


def classify_one(text: str, title: str) -> dict:
    low = text.lower()
    title_low = title.lower()

    has_unit = any(u in low for u in CONC_UNITS)
    has_unit_in_title = any(u in title_low for u in CONC_UNITS) or "concentration" in title_low or "浓度" in title or "含量" in title
    has_risk = any(w in low for w in RISK_WORDS)
    has_risk_in_title = any(w in title_low for w in RISK_WORDS)
    has_summary = any(c in low for c in SUMMARY_COLS)

    is_conc_titled = ("concentration" in title_low) or ("浓度" in title) or ("含量" in title) or has_unit_in_title

    # 分类决策
    if has_risk or has_risk_in_title:
        return {"category": "risk_or_source", "has_unit": has_unit,
                "is_conc_titled": is_conc_titled, "has_risk": True}
    if is_conc_titled and has_unit:
        if has_summary:
            return {"category": "summary_conc", "has_unit": True,
                    "is_conc_titled": True, "has_risk": False}
        return {"category": "sample_conc", "has_unit": True,
                "is_conc_titled": True, "has_risk": False}
    if has_unit and not has_summary:
        return {"category": "conc_like", "has_unit": True,
                "is_conc_titled": is_conc_titled, "has_risk": False}
    if has_unit and has_summary:
        return {"category": "summary_conc", "has_unit": True,
                "is_conc_titled": is_conc_titled, "has_risk": False}
    return {"category": "other", "has_unit": False,
            "is_conc_titled": is_conc_titled, "has_risk": False}


def main():
    probe = pd.read_csv(OUT_DIR / "p2_probe_v2.csv", dtype=str, keep_default_na=False)
    html_papers = probe[probe["extract_strategy"] == "html_table"].copy()
    print(f"待二次分类论文: {len(html_papers)}")

    rows = []
    for _, r in html_papers.iterrows():
        md = LIT_ROOT / r["stem"] / "parsed" / "paper.md"
        if not md.exists():
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # 定位所有 <table> 位置
        positions = [(m.start(), m.end()) for m in re.finditer(r"<table[\s>]", text, re.I)]
        try:
            tables = pd.read_html(StringIO(text))
        except Exception:
            continue

        for i, tbl in enumerate(tables):
            tbl_pos = positions[i][0] if i < len(positions) else 0
            text_before = text[max(0, tbl_pos - 700):tbl_pos]
            title = extract_title(text_before)
            try:
                tbl_text = tbl.to_string(index=False, header=False)
            except Exception:
                tbl_text = ""
            info = classify_one(tbl_text, title)

            # HM/OP 信号 (表格内容)
            low_tbl = tbl_text.lower() + " " + title.lower()
            has_hm = any(s in low_tbl for s in ["cd", "pb", "as", "hg", "cr", "cu", "zn", "ni", "重金属", "heavy metal"])
            has_op = any(s in low_tbl for s in ["pah", "pcb", "pbde", "pfas", "pae", "ocp", "ddt", "hch",
                                                "tph", "多环", "石油烃", "opfr"])

            rows.append({
                "paper_id": r["paper_id"], "level": r["level"], "stem": r["stem"],
                "tbl_idx": i, "n_rows": int(tbl.shape[0]), "n_cols": int(tbl.shape[1]),
                "title": title[:90], "category": info["category"],
                "has_unit": info["has_unit"], "is_conc_titled": info["is_conc_titled"],
                "has_hm": has_hm, "has_op": has_op,
                "is_hm_op": has_hm and has_op,
            })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "p2_tables_classified.csv", index=False, encoding="utf-8-sig")

    # ===== 统计 =====
    print(f"\n=== 表格二次分类结果 (共 {len(df)} 表) ===")
    print(df["category"].value_counts().to_string())

    print(f"\n=== 黄金目标 sample_conc (表标题含浓度+单位+非风险) ===")
    sc = df[df["category"] == "sample_conc"]
    print(f"总数: {len(sc)} (涉及 {sc['paper_id'].nunique()} 论文)")
    print(f"  其中 HM+OP 同表: {((sc['is_hm_op'])).sum()}")
    print(f"  其中 A 级: {(sc['level']=='A').sum()}")
    sc_hmop = sc[sc["is_hm_op"] & (sc["level"] == "A")].sort_values("n_rows", ascending=False)
    print(f"\nA 级 HM+OP sample_conc 表 (P2 真金):")
    for _, r in sc_hmop.head(25).iterrows():
        print(f"  {r['paper_id']} tbl#{r['tbl_idx']} {r['n_rows']}x{r['n_cols']} | {r['title'][:65]}")

    print(f"\n=== summary_conc (统计汇总, site_summary 可用) ===")
    sm = df[df["category"] == "summary_conc"]
    print(f"总数: {len(sm)} (涉及 {sm['paper_id'].nunique()} 论文)")
    print(f"  其中 HM+OP: {(sm['is_hm_op']).sum()}")

    print(f"\n=== risk_or_source (排除, 不进训练) ===")
    rk = df[df["category"] == "risk_or_source"]
    print(f"总数: {len(rk)} ← v1 把这些误算进了 338 '复合信号' 表")

    print(f"\n=== 对比 v1 假阳性 ===")
    v1_hmop = df[df["is_hm_op"]]  # v1 信号: 含 HM 词 AND OP 词
    print(f"v1 'HM+OP 复合信号' 表: {len(v1_hmop)}")
    print(f"  其中实为 risk_or_source: {(v1_hmop['category']=='risk_or_source').sum()}")
    print(f"  其中实为 sample_conc:    {(v1_hmop['category']=='sample_conc').sum()}")
    print(f"  其中实为 summary_conc:   {(v1_hmop['category']=='summary_conc').sum()}")

    print(f"\n输出: {OUT_DIR / 'p2_tables_classified.csv'}")


if __name__ == "__main__":
    main()
