"""构建 wide format 训练表 (基于 Agent 手动精读 CSV)

读 manual_extract/{hm_op,op_only}/*.csv → long → pivot wide → 两张训练表
  train_table_op_only_manual.csv  — OP-only 采样点
  train_table_hm_op_manual.csv    — HM+OP 同点复合
对齐 SRS x_measured_{pollutant} 命名 + 老师建议 schema (source_id/province/site_type/matrix)
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd

OUT = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining")
ME = OUT / "manual_extract"
HM_POLLUTANTS = {"Cd_mgkg", "Pb_mgkg", "Cr_mgkg", "As_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg"}


def load_all():
    rows = []
    for sub in ["hm_op", "op_only"]:
        d = ME / sub
        if not d.exists():
            continue
        for f in sorted(d.glob("*.csv")):
            try:
                df = pd.read_csv(f, dtype=str, keep_default_na=False, on_bad_lines="skip", engine="python")
            except Exception:
                continue
            if df.empty or "paper_id" not in df.columns:
                continue
            df["source_pool"] = sub
            rows.append(df)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def main():
    df = load_all()
    if df.empty:
        print("[build_wide] 无 manual CSV")
        return
    df["value_num"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[df["value_num"].notna() & (df["value_num"] >= 0)].copy()
    df["canonical"] = df["paper_id"] + "_" + df["sample_id"].astype(str)
    # 坐标: 取每个 canonical 的 lat/lon
    if "latitude" in df.columns and "longitude" in df.columns:
        coord_cols = ["latitude", "longitude"]
    else:
        coord_cols = []

    # long CSV
    keep = [c for c in ["paper_id", "sample_id", "canonical", "pollutant_std", "value",
                        "unit", "evidence_location", "matrix", "site_type", "province",
                        "extract_notes", "source_pool", "latitude", "longitude"] if c in df.columns]
    df[keep].to_csv(OUT / "manual_extract_long.csv", index=False, encoding="utf-8-sig")

    def family(p):
        return "HM" if p in HM_POLLUTANTS else "OP"
    df["family"] = df["pollutant_std"].apply(family)

    # 每 canonical 元信息 + HM/OP 判定
    meta = df.groupby("canonical").agg(
        paper_id=("paper_id", "first"),
        matrix=("matrix", "first"),
        site_type=("site_type", "first"),
        province=("province", "first"),
        n_hm=("family", lambda x: (x == "HM").sum()),
        n_op=("family", lambda x: (x == "OP").sum()),
        latitude=("latitude", "first") if "latitude" in df.columns else ("sample_id", "count"),
        longitude=("longitude", "first") if "longitude" in df.columns else ("sample_id", "count"),
    ).reset_index()
    meta["is_hm_op"] = (meta["n_hm"] > 0) & (meta["n_op"] > 0)
    meta["source_id"] = meta["paper_id"]

    def build(readiness_filter):
        sub = df[df["canonical"].isin(meta[readiness_filter]["canonical"])]
        if sub.empty:
            return pd.DataFrame()
        wide = sub.pivot_table(index="canonical", columns="pollutant_std",
                               values="value_num", aggfunc="first").reset_index()
        wide.columns = ["sample_id" if c == "canonical" else f"x_measured_{c}" for c in wide.columns]
        m = meta[meta["canonical"].isin(sub["canonical"])][
            ["canonical", "source_id", "paper_id", "matrix", "site_type", "province", "n_hm", "n_op"] +
            (["latitude", "longitude"] if "latitude" in meta.columns else [])].rename(
            columns={"canonical": "sample_id"})
        wide = wide.merge(m, on="sample_id", how="left")
        return wide

    # OP-only = 有OP无HM; 注: ~is_hm_op 会误纳入纯HM样本(n_op==0), 必须用严格条件
    op_wide = build((meta["n_op"] > 0) & (meta["n_hm"] == 0))
    hmop_wide = build(meta["is_hm_op"])  # HM+OP

    op_wide.to_csv(OUT / "train_table_op_only_manual.csv", index=False, encoding="utf-8-sig")
    hmop_wide.to_csv(OUT / "train_table_hm_op_manual.csv", index=False, encoding="utf-8-sig")

    print(f"=== 手动精读 Wide 训练表构建完成 ===")
    print(f"总观测: {len(df)}, 论文: {df['paper_id'].nunique()}, canonical: {df['canonical'].nunique()}")
    print(f"\n[OP-only] train_table_op_only_manual.csv")
    print(f"  样本: {len(op_wide)}, source: {op_wide['source_id'].nunique() if len(op_wide) else 0}")
    if len(op_wide):
        cols = [c for c in op_wide.columns if c.startswith("x_measured_")]
        filled = op_wide[cols].notna().sum()
        print(f"  浓度列({len(cols)}): {filled.to_dict()}")
        print(f"  matrix: {op_wide['matrix'].value_counts().to_dict()}")
        print(f"  site_type: {op_wide['site_type'].value_counts().to_dict()}")
    print(f"\n[HM+OP] train_table_hm_op_manual.csv")
    print(f"  样本: {len(hmop_wide)}, source: {hmop_wide['source_id'].nunique() if len(hmop_wide) else 0}")
    if len(hmop_wide):
        cols = [c for c in hmop_wide.columns if c.startswith("x_measured_")]
        filled = hmop_wide[cols].notna().sum()
        print(f"  浓度列({len(cols)}): {filled.to_dict()}")
        print(f"  matrix: {hmop_wide['matrix'].value_counts().to_dict()}")
        print(f"  site_type: {hmop_wide['site_type'].value_counts().to_dict()}")
    print(f"\n=== 门槛判定 (≥100 sample + ≥10 source) ===")
    for name, w in [("OP-only", op_wide), ("HM+OP 含沉积物", hmop_wide),
                    ("HM+OP 纯土壤", hmop_wide[hmop_wide["matrix"] == "soil"] if len(hmop_wide) else hmop_wide)]:
        n, s = len(w), w["source_id"].nunique() if len(w) else 0
        print(f"  {name}: {n} sample / {s} source → {'✅达标' if n>=100 and s>=10 else '❌未达'}")


if __name__ == "__main__":
    main()
