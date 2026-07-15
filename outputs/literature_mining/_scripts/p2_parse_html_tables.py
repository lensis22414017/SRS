"""P2 决定性验证: HTML 表格到底装了什么数据?

对 301 篇 html_table 候选用 pandas.read_html 程序化解析每个 <table>,
自动判断表格类型:
  - hm_data: 含 HM 元素 (Cd/Pb/As/Cr/Hg/Cu/Zn/Ni/重金属)
  - op_data: 含 OP 族群 (PAH/PCB/PBDE/PFAS/PAE/OCP/DDT/HCH/TPH/多环)
  - conc: 含浓度单位 (mg/kg, ng/g, ug/kg, 浓度, 含量)
  - phys: 含理化指标 (pH, SOC, CEC, 粘粒, clay, 有机质)
  - site: 含采样点/经纬度 (site, sample, lat, lon, 采样点)

输出 p2_html_tables_parsed.csv (每行一个表格) 供 P2 调度。
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, LIT_ROOT  # noqa: E402

import pandas as pd  # noqa: E402

HM_SIGNALS = ["cd", "pb", "as", "hg", "cr", "cu", "zn", "ni", "co", "mn",
              "重金属", "heavy metal", "metals"]
OP_SIGNALS = ["pah", "pcb", "pbde", "pfas", "pae", "ocp", "ddt", "hch",
              "tph", "petroleum", "多环芳烃", "多氯联苯", "多溴", "全氟",
              "邻苯二甲酸", "有机氯", "石油烃", "opfr", "有机磷阻燃"]
CONC_SIGNALS = ["mg/kg", "ng/g", "μg/kg", "ug/kg", "mg·kg", "ng·g",
                "concen", "浓度", "含量", "mg kg", "ng g"]
PHYS_SIGNALS = ["ph", "soc", "cec", "clay", "粘粒", "有机质", "organic matter",
                "阳离子交换", "cation", "土壤质地", "silt", "sand", "bulk density",
                "容重", "电导率", "ec ", "总氮", "tn ", "总磷", "tp "]
SITE_SIGNALS = ["site", "sample", "lat", "lon", "经度", "纬度", "采样点",
                "样点", "location", "province", "省份", "station"]


def classify_table(tbl: pd.DataFrame) -> dict:
    """判断单个表格的类型信号。"""
    try:
        cols = " ".join(str(c) for c in tbl.columns).lower()
    except Exception:
        cols = ""
    try:
        head = tbl.head(8).to_string(index=False, header=False).lower()
    except Exception:
        head = ""
    try:
        full_text = tbl.to_string(index=False, header=False).lower()
    except Exception:
        full_text = head

    full = cols + " " + full_text

    return {
        "hm": any(s in full for s in HM_SIGNALS),
        "op": any(s in full for s in OP_SIGNALS),
        "conc": any(s in full for s in CONC_SIGNALS),
        "phys": any(s in full for s in PHYS_SIGNALS),
        "site": any(s in full for s in SITE_SIGNALS),
        "n_rows": int(tbl.shape[0]),
        "n_cols": int(tbl.shape[1]),
        "cols_preview": str(list(tbl.columns))[:90],
    }


def main():
    probe = pd.read_csv(OUT_DIR / "p2_probe_v2.csv", dtype=str, keep_default_na=False)
    html_papers = probe[probe["extract_strategy"] == "html_table"].copy()
    print(f"待解析论文 (html_table): {len(html_papers)}")
    print(f"  A 级: {(html_papers['level']=='A').sum()}, B 级: {(html_papers['level']=='B').sum()}")

    rows = []
    errors = []
    for _, r in html_papers.iterrows():
        md = LIT_ROOT / r["stem"] / "parsed" / "paper.md"
        if not md.exists():
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        try:
            tables = pd.read_html(text)
        except Exception as e:
            errors.append((r["paper_id"], r["stem"], str(e)[:60]))
            continue

        for i, tbl in enumerate(tables):
            info = classify_table(tbl)
            is_data = info["hm"] or info["op"] or info["conc"]
            is_hm_op = info["hm"] and info["op"]  # 复合信号
            rows.append({
                "paper_id": r["paper_id"], "level": r["level"], "stem": r["stem"],
                "tbl_idx": i, "n_rows": info["n_rows"], "n_cols": info["n_cols"],
                "has_hm": info["hm"], "has_op": info["op"], "has_conc": info["conc"],
                "has_phys": info["phys"], "has_site": info["site"],
                "is_data_table": is_data, "is_hm_op_table": is_hm_op,
                "cols_preview": info["cols_preview"],
            })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "p2_html_tables_parsed.csv", index=False, encoding="utf-8-sig")

    # ===== 统计 =====
    print(f"\n=== 解析结果 ===")
    print(f"解析成功论文: {df['paper_id'].nunique()}/{len(html_papers)}")
    print(f"解析失败: {len(errors)}")
    print(f"表格总数: {len(df)}")

    data_tbls = df[df["is_data_table"]]
    hm_tbls = df[df["has_hm"] & df["has_conc"]]
    op_tbls = df[df["has_op"] & df["has_conc"]]
    hmop_tbls = df[df["is_hm_op_table"]]

    print(f"\n含 HM+浓度 的表格: {len(hm_tbls)} (涉及 {hm_tbls['paper_id'].nunique()} 论文)")
    print(f"含 OP+浓度 的表格: {len(op_tbls)} (涉及 {op_tbls['paper_id'].nunique()} 论文)")
    print(f"含 HM+OP 复合信号的表格: {len(hmop_tbls)} (涉及 {hmop_tbls['paper_id'].nunique()} 论文)")

    print(f"\n=== A 级复合污染表格候选 (P2 最高优先级) ===")
    a_hmop = hmop_tbls[hmop_tbls["level"] == "A"].sort_values("n_rows", ascending=False)
    print(f"A 级 HM+OP 表格: {len(a_hmop)}")
    for _, r in a_hmop.head(20).iterrows():
        print(f"  {r['paper_id']} tbl#{r['tbl_idx']} {r['n_rows']}行x{r['n_cols']}列 | {r['cols_preview'][:70]}")

    print(f"\n=== A 级纯 OP 数据表 (OP-only 补强) ===")
    a_op = op_tbls[(op_tbls["level"] == "A") & (~op_tbls["has_hm"])].sort_values("n_rows", ascending=False)
    print(f"A 级 OP-only 数据表: {len(a_op)}")
    for _, r in a_op.head(15).iterrows():
        print(f"  {r['paper_id']} tbl#{r['tbl_idx']} {r['n_rows']}行x{r['n_cols']}列 | {r['cols_preview'][:70]}")

    # 行数分布 (采样点数估计)
    print(f"\n=== 数据表行数分布 (采样点数代理) ===")
    if len(data_tbls):
        big = data_tbls[data_tbls["n_rows"] >= 10]
        print(f"数据表总数: {len(data_tbls)}")
        print(f"  行数 ≥10 (可能含多采样点): {len(big)}")
        print(f"  行数 ≥30: {(data_tbls['n_rows']>=30).sum()}")
        print(f"  行数 ≥50: {(data_tbls['n_rows']>=50).sum()}")

    if errors:
        print(f"\n解析错误样本 (前 3):")
        for e in errors[:3]:
            print(f"  {e[0]} | {e[2]}")

    print(f"\n输出: {OUT_DIR / 'p2_html_tables_parsed.csv'}")


if __name__ == "__main__":
    main()
