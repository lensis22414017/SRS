"""阶段1 只读数据剖面: 双数据集字段级 + 分组缺失率 -> missingness_profile.csv。

红线: 只读, 不改原始文件, 不生成任何模拟数据。运行前后校验原始 SHA256 不变。
产物(按 proposed_plan 路径):
  data/processed/missingness_profile.csv
  docs/data/data_cleaning_report.md
"""
import hashlib
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "eda"))
from profile import column_stats, table_overview  # noqa: E402

REAL = os.path.join(ROOT, "data", "raw", "真实数据集.csv")
MERGED = os.path.join(ROOT, "data", "raw", "merged_std33,zh .xlsx")
OUT_CSV = os.path.join(ROOT, "data", "processed", "missingness_profile.csv")
OUT_MD = os.path.join(ROOT, "docs", "data", "data_cleaning_report.md")

GROUP_COLS = ["Pollution_Type", "LandUse", "Province", "Region", "Source"]


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def field_rows(df, dataset):
    rows = []
    n = len(df)
    for c in df.columns:
        miss = int(df[c].isna().sum())
        rows.append({"dataset": dataset, "scope": "field", "group_key": str(c),
                     "n_rows": n, "missing_pct": round(miss / n * 100, 2) if n else 0,
                     "valid": n - miss})
    return rows


def group_rows(df, dataset):
    rows = []
    for gc in GROUP_COLS:
        if gc not in df.columns:
            continue
        for key, sub in df.groupby(gc):
            cells = sub.size
            miss = int(sub.isna().sum().sum())
            rows.append({"dataset": dataset, "scope": f"group:{gc}", "group_key": str(key),
                         "n_rows": len(sub), "missing_pct": round(miss / cells * 100, 2) if cells else 0,
                         "valid": len(sub)})
    return rows


def main():
    before = {REAL: sha(REAL), MERGED: sha(MERGED)}

    real = pd.read_csv(REAL); real.columns = [c.strip() for c in real.columns]
    merged = pd.read_excel(MERGED, sheet_name="china")

    ov_real = table_overview(real)
    ov_merged = table_overview(merged)

    all_rows = (field_rows(real, "真实数据集") + group_rows(real, "真实数据集")
                + field_rows(merged, "merged_std33") + group_rows(merged, "merged_std33"))
    prof = pd.DataFrame(all_rows)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    prof.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    # 报告
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)

    def high_miss(df, thr=80):
        n = len(df)
        return [(c, round(df[c].isna().sum() / n * 100, 1)) for c in df.columns
                if df[c].isna().sum() / n * 100 > thr]

    hm_real = high_miss(real)
    hm_merged = high_miss(merged)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(f"""# 数据清洗与剖面报告（双数据集，阶段1只读）

> 自动生成: `scripts/run_data_profiling.py` ｜ 真实数据, 未插补、未改原值、未生成模拟数据
> 逐列/分组缺失率明细见 `data/processed/missingness_profile.csv`

## 一、数据资产概览
| 数据集 | 行 | 列 | 数值列 | 整体缺失率 |
|---|---|---|---|---|
| 真实数据集.csv（训练主表） | {ov_real['rows']} | {ov_real['cols']} | {ov_real['numeric_cols']} | {ov_real['overall_missing_pct']}% |
| merged_std33（数据湖） | {ov_merged['rows']} | {ov_merged['cols']} | {ov_merged['numeric_cols']} | {ov_merged['overall_missing_pct']}% |

merged_std33 为**宽稀疏数据湖**（719 列、缺失 {ov_merged['overall_missing_pct']}%），**禁止整表统一插补/训练**，
必须先派生 model_ready 子表（见 `data/model_ready/model_ready_schema.csv`），再做 DOI/Source/Region 分组切分。

## 二、merged_std33 列分组
- 标识/地理: ID/DOI/Source/Year/Journal/Country/Province/City/Region/Latitude/Longitude/LandUse/Pollution_Type/SampleID 等（17）
- 理化协变量: SoilpH/pH/pH_merged/OC_pct/SoilBD/CEC/Sand/Silt/Clay/SoilTexture/SoilType（11）
- 重金属(measured_*): Cd/Pb/As/Cu/Zn/Ni/Cr/Hg/Co/Mn/Fe/Sb… `*_mgkg`（约 28 列）
- 有机物(measured_*): HCH/DDT/PAH/PCB/OCP/PFAS/TPH 族 `*_ngg`/`*_mgkg`（约 142 列）

## 三、关键列覆盖（merged_std33）
DOI 99.2%、Source 100%、Province 63.4%、经纬度 ~57.5%、LandUse 52.6%、SoilpH 21.8%、Region 21.9%。
**Pollution_Type 分布**: HM 24436、OP 5226、HM+OP 2104、PAH 1843、OCP 414…（适合派生 HM/OP/HM+OP 视图）。
**LandUse/Province 取值脏**（中英混杂、392 个 Province 取值），需 `unit_conversion_rules`/标准化映射后才能分组建模。

## 四、高缺失列（> 80%）
- 真实数据集: 共 {len(hm_real)} 列，如 {', '.join(f'{c}({p}%)' for c, p in hm_real[:8])}
- merged_std33: 共 {len(hm_merged)} 列（719 列里绝大多数有机物单指标列高度稀疏，属正常——单篇文献只测部分污染物）

## 五、使用红线（强制）
1. 原始文件 immutable，只读;所有派生写入 cleaned/model_ready/synthetic 分层并带 `source_file_sha256`。
2. 未测污染物**不得当 0**;缺失按真实机制处理，建模用中位数填充+`*_missing` 标记，**绝不补满 719 列**。
3. 模拟/插补数据带 `is_synthetic`/`evidence_level`，**永不进入 real 验证集**。
4. 主验证禁止行级随机切分，必须 DOI/Source group split（见 `docs/validation/leakage_prevention_checklist.md`）。
""")
    after = {REAL: sha(REAL), MERGED: sha(MERGED)}
    assert before == after, "原始文件被改动!"
    print("已生成:", OUT_CSV, "(", len(prof), "行)")
    print("已生成:", OUT_MD)
    print("原始文件 SHA256 校验: 未变 ✅")
    print(f"真实数据集 {ov_real['rows']}×{ov_real['cols']} 缺失{ov_real['overall_missing_pct']}% | "
          f"merged {ov_merged['rows']}×{ov_merged['cols']} 缺失{ov_merged['overall_missing_pct']}%")


if __name__ == "__main__":
    main()
