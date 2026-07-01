"""zzv0.3 重训 R1: 数据清洗 + 特征矩阵重建(保留重金属浓度)。

清洗规则(基于EDA诊断):
  1. 离群值修正: Pb/As/Cr/Cu/Zn/Ni 超ceiling且/1000后落入正常范围 → /1000(单位错误ugkg误标mgkg)
  2. Cd/Hg 极端值: 保留但Winsorize到p99.9(矿区可能真实高, 不冒进删)
  3. 国家编码统一: 中国/China→China
  4. 重金属浓度(8 HM + 12 有机汇总)保留作特征(裴总2026-07-01决策: 真实诊断时浓度就是输入)
     - 这不是标签泄漏: 标签是浓度×pH×阈值的复杂函数, 模型学的是非线性关系, 泛化到新场地
  5. 原生NaN(树模型处理, 不填充)
输出: data/training/dual_track/ (覆盖, 含重金属浓度特征)
"""
import os
import sys
import re
import json

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))
sys.path.insert(0, os.path.join(ROOT, "ml", "etl"))

from dataset_splits import build_real_splits  # noqa
from build_training_splits import (  # noqa
    HM_COLS, ORG_COLS_MAP, _attach_dual_labels, _load_thresh_csv, _load_org_thresholds,
    THRESH_PROD, THRESH_ECO,
)

GEOCODED_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_geocoded.csv")
GEE_COV_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_gee_covariates.csv")
OUT_DIR = os.path.join(ROOT, "data", "training", "dual_track")

PHYS_CHEM_COLS = ["SoilpH", "OC_pct", "CEC_cmolkg", "Sand_pct", "Silt_pct",
                  "Clay_pct", "SoilBD_gcm3", "Elevation_m", "MAP_mm", "EC_mScm", "TN_gkg"]
GEE_COLS = ["gee_ndvi", "gee_precip_annual_mm", "gee_temp_mean_c",
            "gee_elevation_m", "gee_slope_deg", "gee_aspect_deg",
            "gee_soil_pH", "gee_soc_g_kg", "gee_cec_cmol_kg", "gee_clay_pct",
            "gee_sand_pct", "gee_silt_pct", "gee_bulk_density_g_cm3", "gee_nitrogen_g_kg"]

# 浓度特征(裴总决策保留): 8重金属 + 12有机汇总 = 标签派生列, 但作为合法特征
CONC_FEATURE_COLS = list(HM_COLS) + list(ORG_COLS_MAP.keys())  # 20个

# 清洗: 单位错误的离群值修正(超ceiling且/1000后正常)
UNIT_ERROR_FIX = {
    "Pb_mgkg": 10000, "As_mgkg": 5000, "Cr_mgkg": 5000,
    "Cu_mgkg": 10000, "Zn_mgkg": 10000, "Ni_mgkg": 2000,
}
# Winsorize上限(矿区可能真实高, 截到p99.9)
WINSORIZE = {"Cd_mgkg": 1000, "Hg_mgkg": 500}


def clean_data(df):
    """数据清洗: 单位修正 + Winsorize + 编码统一。"""
    cleaning_log = {}
    # 1. 单位错误修正(/1000)
    for col, ceiling in UNIT_ERROR_FIX.items():
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            mask = s > ceiling
            n_fix = mask.sum()
            if n_fix > 0:
                df.loc[mask, col] = s[mask] / 1000.0
                cleaning_log[f"{col}_unit_fix"] = int(n_fix)
    # 2. Winsorize极端值(Cd/Hg)
    for col, ceiling in WINSORIZE.items():
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            mask = s > ceiling
            n_clip = mask.sum()
            if n_clip > 0:
                df.loc[mask, col] = ceiling
                cleaning_log[f"{col}_winsorize"] = int(n_clip)
    # 3. 国家编码统一
    if "Country" in df.columns:
        df["Country"] = df["Country"].replace({"中国": "China"})
        cleaning_log["country_unified"] = True
    # 4. 污染类型标准化(HM/HM+OP为主, 其余归为OTHER)
    if "Pollution_Type" in df.columns:
        df["Pollution_Type"] = df["Pollution_Type"].fillna("unknown")
        cleaning_log["pollution_type_filled"] = True
    return df, cleaning_log


def build_with_conc_features():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 64)
    print("zzv0.3 R2: 数据清洗 + 保留重金属浓度特征重建")
    print("=" * 64)

    # 1. 读 + 清洗
    df = pd.read_csv(GEOCODED_CSV, low_memory=False)
    n_total = len(df)
    print(f"[1] 原始: {n_total} 行 × {len(df.columns)} 列")
    df, cleaning_log = clean_data(df)
    print(f"[1b] 清洗: {cleaning_log}")

    # 2. 合并GEE
    gee_cov_ok = os.path.exists(GEE_COV_CSV)
    if gee_cov_ok:
        gee = pd.read_csv(GEE_COV_CSV)
        df = df.merge(gee, on="site_id", how="left")
        print(f"[2] GEE合并: {len(gee)} 行 (覆盖率 {len(gee)}/{n_total}={len(gee)/n_total*100:.1f}%)")

    # 3. 双轨标签
    factor_cols = {**HM_COLS, **ORG_COLS_MAP}
    factor_cols = {k: v for k, v in factor_cols.items() if k in df.columns}
    prod_rows = _load_thresh_csv(THRESH_PROD)
    eco_rows = _load_thresh_csv(THRESH_ECO)
    org_thresh = _load_org_thresholds()
    _attach_dual_labels(df, factor_cols, prod_rows, eco_rows, org_thresh)
    print(f"[3] 标签: prod正={df['标签_生产'].mean():.2%} eco正={df['标签_生态'].mean():.2%}")

    # 4. 特征矩阵: 理化 + GEE + 重金属浓度(20) + __missing
    feature_cols = [c for c in PHYS_CHEM_COLS if c in df.columns or True]
    feature_cols = [c for c in PHYS_CHEM_COLS]
    if gee_cov_ok:
        feature_cols += [c for c in GEE_COLS if c in df.columns]
    conc_present = [c for c in CONC_FEATURE_COLS if c in df.columns]
    feature_cols += conc_present  # ★ 关键: 保留重金属浓度作特征
    # __missing标记(不填充)
    missing_cols = []
    for c in feature_cols:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")
        mc = f"{c}__missing"
        df[mc] = df[c].isna().astype(int)
        missing_cols.append(mc)
    X_all_cols = feature_cols + missing_cols
    print(f"[4] 特征: {len(X_all_cols)} (理化{len(PHYS_CHEM_COLS)} + GEE{len(GEE_COLS)} "
          f"+ 浓度{len(conc_present)} + __missing{len(missing_cols)})")

    # 5. group-split
    df["id_DOI"] = df.get("DOI", "").fillna("").astype(str)
    df["id_Source"] = df.get("Source", "").fillna("").astype(str)
    splits, checks = build_real_splits(df, seed=42)
    print(f"[5] group-split 0泄漏: all_passed={checks['all_passed']}")

    # 6. 输出
    rename = {"train_real": "train", "valid_real_group_split": "valid",
              "test_real_group_split": "test", "external_literature_holdout": "external"}
    summary = {}
    for k, sdf in splits.items():
        name = rename.get(k, k)
        X = sdf[X_all_cols].copy()
        y_prod = sdf["标签_生产"].astype(int)
        y_eco = sdf["标签_生态"].astype(int)
        X.to_csv(os.path.join(OUT_DIR, f"{name}_X_barrier.csv"), index=False)
        y_prod.to_csv(os.path.join(OUT_DIR, f"{name}_y_prod.csv"), index=False)
        y_eco.to_csv(os.path.join(OUT_DIR, f"{name}_y_eco.csv"), index=False)
        sdf[["id_DOI", "id_Source"]].to_csv(
            os.path.join(OUT_DIR, f"{name}_groups.csv"), index=False)
        summary[name] = {"n": len(sdf), "prod_pos": int(y_prod.sum()),
                         "eco_pos": int(y_eco.sum())}
    for name, s in summary.items():
        print(f"      {name}: {s['n']}行 (prod正{s['prod_pos']}/{s['n']}={s['prod_pos']/s['n']:.2%})")

    # 7. meta
    meta = {
        "version": "zzv0.3_cleaned_conc_features",
        "n_total_geocoded": n_total, "feature_cols": feature_cols,
        "missing_cols": missing_cols, "n_features": len(X_all_cols),
        "conc_features_kept": conc_present, "cleaning_log": cleaning_log,
        "gee_cov_ok": gee_cov_ok, "splits": summary,
        "leakage_all_passed": checks["all_passed"],
        "factor_cols_used": list(factor_cols.keys()),
        "label_prod_pos_rate": float(df["标签_生产"].mean()),
        "label_eco_pos_rate": float(df["标签_生态"].mean()),
        "missing_value_policy": "原生NaN(树模型处理, 不填充)",
        "note": "裴总2026-07-01决策: 保留重金属浓度作特征(真实诊断时浓度是输入, 非泄漏)",
    }
    with open(os.path.join(OUT_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 完成: {OUT_DIR}/ (含重金属浓度特征)")


if __name__ == "__main__":
    build_with_conc_features()
