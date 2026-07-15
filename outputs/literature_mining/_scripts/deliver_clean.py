"""Generate 干净土壤训练交付版 (裴总: 两份土壤 OP / OP+HM 数据集).

从 build_wide 的 wide 表过滤:
- matrix == "soil" (排除 sediment 沉积物 + peat 泥炭, 裴总要"土壤")
- 加 audit_flag 列: single_point / site_Mean_downgrade(裴总接受降级)
输出: train_table_op_only_SOIL_CLEAN.csv / train_table_hm_op_SOIL_CLEAN.csv
"""
import sys
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining"

# site-Mean/composite 降级样本(裴总P07067方向接受, 真实场地测定)
DOWNGRADE_PID = {"P02317", "P07067", "P00242"}

for name, src in [("op_only", "train_table_op_only_manual.csv"),
                  ("hm_op", "train_table_hm_op_manual.csv")]:
    df = pd.read_csv(f"{OUT}/{src}", dtype=str, keep_default_na=False)
    total = len(df)
    mat_before = df["matrix"].value_counts().to_dict()

    # 过滤纯土壤
    soil = df[df["matrix"] == "soil"].copy()
    soil["audit_flag"] = soil["source_id"].apply(
        lambda x: "site_Mean_downgrade" if x in DOWNGRADE_PID else "single_point")

    out = f"{OUT}/train_table_{name}_SOIL_CLEAN.csv"
    soil.to_csv(out, index=False, encoding="utf-8-sig")

    n_src = soil["source_id"].nunique()
    n_down = (soil["audit_flag"] == "site_Mean_downgrade").sum()
    conc_cols = [c for c in soil.columns if c.startswith("x_measured_")]

    print(f"\n=== {name} 纯土壤干净版 ===")
    print(f"  输出: {out}")
    print(f"  总{total} (matrix: {mat_before}) → 纯土壤 {len(soil)} sample / {n_src} source")
    print(f"  audit_flag: single_point {len(soil)-n_down} + site_Mean_downgrade {n_down}")
    print(f"  浓度列({len(conc_cols)}), site_type: {soil['site_type'].value_counts().to_dict()}")
    # 主干污染物填充率(非空)
    fill = {c: int((soil[c].astype(str).str.strip() != "").sum()) for c in conc_cols}
    top = sorted(fill.items(), key=lambda x: -x[1])[:10]
    print(f"  主干填充(top10): {dict(top)}")
