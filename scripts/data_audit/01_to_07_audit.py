"""P0-1~7: 数据审计(概况/缺失/轨道覆盖/单位/检出限/异常/model-ready)。
只读原始数据, 输出审计报告。"""
import os
import sys
import json
import re
import numpy as np
import pandas as pd
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_geocoded.csv")
OUT = os.path.join(ROOT, "data", "reports")

# 因子分类
HM_COLS = ["Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cr_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg"]
ORG_COLS = ["Sum_PAH_ngg", "BaP_ngg", "SumOCP_ngg", "SumDDTs_ngg", "SumPCB_ngg",
            "SumHCHs_ngg", "SumPAE_ugkg", "SumPBDE_ngg", "SumPFAS_ngg", "TPH_ngg",
            "HMWPAH_ngg", "LMWPAH_ngg"]
PHYS_COLS = ["SoilpH", "OC_pct", "CEC_cmolkg", "Sand_pct", "Silt_pct", "Clay_pct",
             "SoilBD_gcm3", "Elevation_m", "MAP_mm", "EC_mScm", "TN_gkg"]
GEE_COLS = [f"gee_{g}" for g in ["ndvi", "precip_annual_mm", "temp_mean_c", "elevation_m",
                                  "slope_deg", "aspect_deg", "soil_pH", "soc_g_kg",
                                  "cec_cmol_kg", "clay_pct", "sand_pct", "silt_pct",
                                  "bulk_density_g_cm3", "nitrogen_g_kg"]]

PRODUCTION_CORE = HM_COLS + ["SoilpH", "OC_pct", "CEC_cmolkg", "SoilBD_gcm3"]
ECOLOGY_CORE = HM_COLS + ["SoilpH", "OC_pct", "CEC_cmolkg", "SoilBD_gcm3"]


def main():
    print("=" * 64)
    print("P0-1~7 数据审计")
    print("=" * 64)
    df = pd.read_csv(RAW_CSV, low_memory=False)
    N = len(df)
    cols = list(df.columns)

    # P0-1 概况
    profile = {
        "n_rows": N, "n_cols": len(cols),
        "n_sites": int(df["site_id"].nunique()) if "site_id" in cols else None,
        "n_dois": int(df["DOI"].nunique()) if "DOI" in cols else None,
        "n_sources": int(df["Source"].nunique()) if "Source" in cols else None,
        "n_provinces": int(df["Province"].nunique()) if "Province" in cols else None,
        "pollution_type_dist": df["Pollution_Type"].value_counts().to_dict() if "Pollution_Type" in cols else {},
    }
    json.dump(profile, open(os.path.join(OUT, "dataset_profile.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"[P0-1] 概况: {N}行/{len(cols)}列, 场地{profile['n_sites']}, 省份{profile['n_provinces']}")

    # P0-2 缺失率(每列)
    missing_rate = (df.isna().mean() * 100).round(2)
    missing_df = pd.DataFrame({"column": missing_rate.index, "missing_pct": missing_rate.values})
    missing_df.to_csv(os.path.join(OUT, "field_missingness.csv"), index=False, encoding="utf-8-sig")
    fully_empty = int((missing_rate == 100).sum())
    print(f"[P0-2] 缺失率: {fully_empty}列完全空, {(missing_rate<5).sum()}列缺失<5%")

    # 因子覆盖率(HM/OP/物理/GEE)
    all_factors = HM_COLS + ORG_COLS + PHYS_COLS
    factor_cov = []
    for f in all_factors:
        if f in cols:
            nn = df[f].notna().sum()
            factor_cov.append({"factor": f, "non_null": int(nn), "coverage_pct": round(nn / N * 100, 2)})
        else:
            factor_cov.append({"factor": f, "non_null": 0, "coverage_pct": 0.0, "note": "列不存在"})
    pd.DataFrame(factor_cov).to_csv(os.path.join(OUT, "factor_coverage.csv"), index=False, encoding="utf-8-sig")
    print(f"[P0-2b] 因子覆盖率已输出")

    # P0-3 轨道覆盖
    hm_mask = df["Pollution_Type"] == "HM" if "Pollution_Type" in cols else None
    op_mask = df["Pollution_Type"] == "OP" if "Pollution_Type" in cols else None
    track_cov = []
    for f in PRODUCTION_CORE + ORG_COLS:
        if f not in cols:
            continue
        row = {"factor": f, "overall_pct": round(df[f].notna().mean() * 100, 2)}
        if hm_mask is not None:
            row["HM_pct"] = round(df.loc[hm_mask, f].notna().mean() * 100, 2)
        if op_mask is not None:
            row["OP_pct"] = round(df.loc[op_mask, f].notna().mean() * 100, 2)
        track_cov.append(row)
    pd.DataFrame(track_cov).to_csv(os.path.join(OUT, "factor_coverage_by_track.csv"),
                                   index=False, encoding="utf-8-sig")
    prod_diagnosable = sum(1 for f in PRODUCTION_CORE if f in cols and df[f].notna().mean() > 0.1)
    eco_diagnosable = sum(1 for f in ECOLOGY_CORE if f in cols and df[f].notna().mean() > 0.1)
    print(f"[P0-3] 生产轨可诊断指标: {prod_diagnosable}/{len(PRODUCTION_CORE)}, 生态轨: {eco_diagnosable}/{len(ECOLOGY_CORE)}")

    # P0-4 单位统一记录
    unit_log = []
    conc_suffix = re.compile(r"(_mgkg|_ngg|_ugkg)$")
    for c in cols:
        if conc_suffix.search(c):
            unit_log.append({"column": c, "detected_unit": c.split("_")[-1],
                             "canonical": c.split("_")[-1], "conflict": False})
        elif c in ["SoilpH", "pH"]:
            unit_log.append({"column": c, "detected_unit": "dimensionless", "canonical": "dimensionless", "conflict": False})
        elif c == "OC_pct":
            unit_log.append({"column": c, "detected_unit": "percent", "canonical": "percent", "conflict": False})
    pd.DataFrame(unit_log).to_csv(os.path.join(OUT, "unit_harmonization_log.csv"),
                                  index=False, encoding="utf-8-sig")
    print(f"[P0-4] 单位统一记录: {len(unit_log)}列")

    # P0-5 检出限语义
    censored = []
    for c in HM_COLS + ORG_COLS:
        if c not in cols:
            continue
        s = df[c].astype(str)
        is_nd = s.str.match(r"^(ND|nd|未检出|<.*|小于.*)", na=False)
        n_censored = int(is_nd.sum())
        if n_censored > 0:
            censored.append({"column": c, "n_censored": n_censored, "censored_pct": round(n_censored / N * 100, 2)})
        # 数值化检查: 是否有非数值
        s_num = pd.to_numeric(df[c], errors="coerce")
        n_non_numeric = int(df[c].notna().sum() - s_num.notna().sum())
        if n_non_numeric > 0:
            censored.append({"column": c, "n_non_numeric": n_non_numeric,
                             "note": "存在非数值文本(可能是检出限语义), 需保留原文"})
    pd.DataFrame(censored).to_csv(os.path.join(OUT, "censored_value_audit.csv"),
                                  index=False, encoding="utf-8-sig")
    print(f"[P0-5] 检出限语义: {len(censored)}条记录")

    # P0-6 异常值清单(全浓度列, 不只8重金属)
    outliers = []
    all_conc = [c for c in cols if conc_suffix.search(c)]
    for c in all_conc:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().sum() < 10:
            continue
        q999 = s.quantile(0.999)
        mx = s.max()
        if mx > q999 * 100 and mx > 1000:  # 比99.9分位高100倍且>1000
            outliers.append({"column": c, "max": round(float(mx), 1),
                             "p999": round(float(q999), 1), "ratio": round(float(mx / q999), 1),
                             "type": "疑似单位错误(ugkg误标mgkg)或极端污染"})
    pd.DataFrame(outliers).to_csv(os.path.join(OUT, "outlier_candidates.csv"),
                                  index=False, encoding="utf-8-sig")
    print(f"[P0-6] 异常值清单: {len(outliers)}列有极端值")

    # P0-7 model-ready schema
    forbidden_patterns = ["B_", "R_", "KOS", "OI_", "threshold", "exceedance",
                          "标签", "超标", "severity", "rule_"]
    model_ready_cols = []
    excluded_cols = []
    for c in cols:
        is_forbidden = any(p in c for p in forbidden_patterns)
        is_meta = c in ["DOI", "Source", "Year", "Journal", "SampleID", "site_id",
                        "Latitude", "Longitude", "Latitude_range", "Longitude_range",
                        "Pollution_Type", "LandUseType", "LandUse", "SamplingYear",
                        "SamplingDepth", "SiteDescription", "Country", "Province", "City",
                        "SoilTexture", "SoilType", "pH_merged", "Glucosinolate_umol_g",
                        "OC_pct_calculated_by"]
        if is_forbidden or is_meta:
            excluded_cols.append({"column": c, "reason": "规则派生/后验" if is_forbidden else "元数据"})
        else:
            model_ready_cols.append(c)

    schema = {
        "n_model_ready_cols": len(model_ready_cols),
        "n_excluded_cols": len(excluded_cols),
        "model_ready_sample": model_ready_cols[:30],
        "excluded_sample": [e["column"] for e in excluded_cols[:20]],
        "total_original_cols": len(cols),
    }
    json.dump(schema, open(os.path.join(OUT, "model_ready_schema.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"[P0-7] model-ready: {len(model_ready_cols)}列可入模, {len(excluded_cols)}列排除")

    print(f"\n✅ P0-1~7 审计完成。所有输出在 data/reports/")


if __name__ == "__main__":
    main()
