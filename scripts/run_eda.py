"""对训练特征表做 EDA 体检, 输出报告与缺失率剖面(如实标注: 当前为模拟特征表)。
用法: python scripts/run_eda.py
产物: docs/data/training_eda_report.md, data/processed/training_eda_profile.csv
"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "eda"))
from profile import column_stats, table_overview  # noqa: E402

# ⚠️ 当前为模拟特征表 (非真实); 真实数据为 merged_std33,zh .xlsx (P0 正名后)
CSV = os.path.join(ROOT, "data", "raw", "模拟特征表_F127_n11690.csv")
OUT_REPORT = os.path.join(ROOT, "docs", "data", "training_eda_report.md")
OUT_PROFILE = os.path.join(ROOT, "data", "processed", "training_eda_profile.csv")


def main():
    df = pd.read_csv(CSV)
    df.columns = [c.strip() for c in df.columns]
    ov = table_overview(df)

    rows = []
    for c in df.columns:
        st = column_stats(df[c])
        rows.append({"column": c, **{k: st.get(k) for k in
                     ["count", "missing", "missing_pct", "zeros", "outliers", "outlier_pct",
                      "mean", "median", "std", "cv", "skew", "skew_flag", "min", "max"]}})
    prof = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT_PROFILE), exist_ok=True)
    prof.to_csv(OUT_PROFILE, index=False, encoding="utf-8-sig")

    high_miss = prof[prof["missing_pct"] > 50].sort_values("missing_pct", ascending=False)
    skewed = prof[prof["skew_flag"].isin(["右偏", "左偏"])]
    os.makedirs(os.path.dirname(OUT_REPORT), exist_ok=True)
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write(f"""# 数据清洗与 EDA 体检报告（训练特征表 · 模拟数据）

> 数据源: `data/raw/模拟特征表_F127_n11690.csv` (⚠️ 模拟特征表, 非真实; is_real_data=False) ｜ 自动生成: `scripts/run_eda.py` ｜ 未插补

## 一、数据概览
- 行数 × 列数: **{ov['rows']} × {ov['cols']}**（数值列 {ov['numeric_cols']}）
- 整体缺失率: **{ov['overall_missing_pct']}%**
- 全空列: {', '.join(ov['fully_empty_cols']) or '无'}

## 二、高缺失列（缺失率 > 50%，共 {len(high_miss)} 列）
| 列 | 缺失率% | 有效数 |
|---|---|---|
""")
        for _, r in high_miss.iterrows():
            f.write(f"| {r['column']} | {r['missing_pct']} | {r['count']} |\n")
        f.write(f"""
## 三、偏态列（建议用中位数，共 {len(skewed)} 列）
| 列 | 偏度 | 形态 | 均值 | 中位数 | CV |
|---|---|---|---|---|---|
""")
        for _, r in skewed.iterrows():
            f.write(f"| {r['column']} | {r['skew']} | {r['skew_flag']} | {r['mean']} | {r['median']} | {r['cv']} |\n")
        f.write("""
## 四、数据使用建议
1. 缺失率 > 95% 的列建模前剔除（如 CEC/EC_T/BS_T 等），其余数值列中位数填充并保留 `*_missing` 标记。
2. 偏态明显的列优先用中位数代表集中趋势；建模可考虑对数变换。
3. 异常点（IQR 法）需人工复核，污染场地高值多为真实超标而非错误，**不可一律剔除**。
4. 完整逐列指标见 `data/processed/training_eda_profile.csv`。
""")
    print("已生成:", OUT_REPORT)
    print("已生成:", OUT_PROFILE)
    print(f"概览: {ov['rows']}×{ov['cols']}, 整体缺失 {ov['overall_missing_pct']}%, 高缺失列 {len(high_miss)}, 偏态列 {len(skewed)}")


if __name__ == "__main__":
    main()
