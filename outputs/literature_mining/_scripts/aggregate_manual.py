"""汇总所有 per-paper 手动精读 CSV → manual_extract_long.csv + 防伪复合检查

扫描 manual_extract/{hm_op,op_only}/*.csv，合并去重，输出:
  - manual_extract_long.csv (全量 long format)
  - manual_extract_summary.csv (每论文 sample 数 + 污染物覆盖)
  - 控制台: 防伪复合检查 + 门槛判定
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import pandas as pd

OUT_DIR = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining")
ME_DIR = OUT_DIR / "manual_extract"

HM_POLLUTANTS = ["Cd_mgkg", "Pb_mgkg", "Cr_mgkg", "As_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg"]


def load_all() -> pd.DataFrame:
    rows = []
    for sub in ["hm_op", "op_only"]:
        d = ME_DIR / sub
        if not d.exists():
            continue
        for f in sorted(d.glob("*.csv")):
            if f.name.startswith("summary") or f.name == "manual_extract_long.csv":
                continue
            try:
                df = pd.read_csv(f, dtype=str, keep_default_na=False,
                                 on_bad_lines="skip", engine="python")
                if df.empty or "paper_id" not in df.columns:
                    continue
                df["source_pool"] = sub
                rows.append(df)
            except Exception as e:
                print(f"  [警告] {f.name} 读取失败: {e}")
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def main():
    df = load_all()
    if df.empty:
        print("[aggregate] 未找到任何 manual_extract CSV。请先运行 Agent 精读。")
        return

    # 数值化
    df["value_num"] = pd.to_numeric(df["value"], errors="coerce")
    # 剔除无效
    n_before = len(df)
    df = df[df["value_num"].notna() & (df["value_num"] >= 0)].copy()
    n_invalid = n_before - len(df)

    # 输出 long
    long_cols = [c for c in ["paper_id", "sample_id", "pollutant_std", "value", "unit",
                             "evidence_location", "matrix", "site_type", "province",
                             "extract_notes", "source_pool"] if c in df.columns]
    df[long_cols].to_csv(OUT_DIR / "manual_extract_long.csv", index=False, encoding="utf-8-sig")

    # 标准化 sample_id (paper_id + sample_id)
    df["canonical"] = df["paper_id"] + "_" + df["sample_id"].astype(str)

    # === 防伪复合检查 (每 canonical 是否同时有 HM + OP) ===
    def family(p):
        if p in HM_POLLUTANTS:
            return "HM"
        return "OP"
    df["family"] = df["pollutant_std"].apply(family)

    canon_stats = df.groupby("canonical").agg(
        paper_id=("paper_id", "first"),
        n_hm=("family", lambda x: (x == "HM").sum()),
        n_op=("family", lambda x: (x == "OP").sum()),
        pollutants=("pollutant_std", lambda x: ",".join(sorted(set(x)))),
        matrix=("matrix", "first"),
        site_type=("site_type", "first"),
        province=("province", "first"),
    ).reset_index()
    canon_stats["has_hm"] = canon_stats["n_hm"] > 0
    canon_stats["has_op"] = canon_stats["n_op"] > 0
    canon_stats["is_hm_op"] = canon_stats["has_hm"] & canon_stats["has_op"]

    # 门槛判定
    hmop = canon_stats[canon_stats["is_hm_op"]]
    op_only = canon_stats[~canon_stats["has_hm"] & canon_stats["has_op"]]

    print(f"\n{'='*70}")
    print(f"=== 手动精读汇总 ===")
    print(f"{'='*70}")
    print(f"总观测: {len(df)} (剔除无效 {n_invalid})")
    print(f"总论文: {df['paper_id'].nunique()}")
    print(f"总 canonical (采样点): {canon_stats['canonical'].nunique()}")
    print(f"\n--- HM+OP 复合 (同点含 HM 族 + OP 族) ---")
    print(f"  sample 数: {len(hmop)}")
    print(f"  source_groups (论文): {hmop['paper_id'].nunique()}")
    if len(hmop):
        print(f"  matrix: {hmop['matrix'].value_counts().to_dict()}")
        print(f"  site_type: {hmop['site_type'].value_counts().to_dict()}")
        soil = hmop[hmop["matrix"] == "soil"]
        print(f"  纯土壤: {len(soil)} sample / {soil['paper_id'].nunique()} source")
    print(f"\n--- OP-only (无 HM 配对) ---")
    print(f"  sample 数: {len(op_only)}")
    print(f"  source_groups: {op_only['paper_id'].nunique()}")

    # 门槛
    print(f"\n--- 裴总门槛判定 (≥100 sample + ≥10 source) ---")
    for name, sub, col in [("HM+OP 含沉积物", hmop, None), ("HM+OP 纯土壤", hmop[hmop["matrix"] == "soil"], None), ("OP-only", op_only, None)]:
        n = len(sub)
        s = sub["paper_id"].nunique()
        ok = "✅达标" if n >= 100 and s >= 10 else "❌未达"
        print(f"  {name}: {n} sample / {s} source → {ok}")

    # 每论文贡献
    print(f"\n--- HM+OP 论文贡献 top 20 ---")
    contrib = hmop.groupby("paper_id").size().reset_index(name="n_sample")
    print(contrib.sort_values("n", ascending=False).head(20).to_string(index=False))

    # summary CSV
    canon_stats.to_csv(OUT_DIR / "manual_extract_summary.csv", index=False, encoding="utf-8-sig")
    print(f"\n输出: manual_extract_long.csv ({len(df)} 行), manual_extract_summary.csv ({len(canon_stats)} canonical)")


if __name__ == "__main__":
    main()
