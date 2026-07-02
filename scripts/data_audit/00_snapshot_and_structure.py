"""P0: 原始数据只读快照 + SHA256 + 数据结构识别(长表/宽表)。
不修改原始数据, 只读取并记录。"""
import os
import sys
import json
import hashlib
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_geocoded.csv")
OUT_DIR = os.path.join(ROOT, "data", "reports")
os.makedirs(OUT_DIR, exist_ok=True)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    print("=" * 64)
    print("P0: 原始数据只读快照 + SHA256 + 结构识别")
    print("=" * 64)

    # 1. 文件manifest(只读, SHA256)
    stat = os.stat(RAW_CSV)
    sha = file_sha256(RAW_CSV)
    manifest = {
        "filename": os.path.basename(RAW_CSV),
        "path": RAW_CSV,
        "size_bytes": stat.st_size,
        "size_mb": round(stat.st_size / 1024 / 1024, 2),
        "sha256": sha,
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "snapshot_time": datetime.now(timezone.utc).isoformat(),
        "readonly": True,
        "note": "原始数据只读快照, 不可修改",
    }
    manifest_path = os.path.join(OUT_DIR, "raw_file_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"[1] 文件manifest: {manifest_path}")
    print(f"    SHA256: {sha[:32]}...")
    print(f"    大小: {manifest['size_mb']} MB")

    # 2. 数据结构识别(长表 vs 宽表)
    df = pd.read_csv(RAW_CSV, low_memory=False, nrows=5)
    cols = list(df.columns)
    n_cols = len(cols)

    # 长表特征: 有 factor_name/factor/analyte/parameter 列 + value 列
    long_indicators = [c for c in cols if c.lower() in
                       ["factor_name", "factor", "analyte", "analyte_code",
                        "parameter", "indicator", "item", "污染物", "因子"]]
    value_indicators = [c for c in cols if c.lower() in
                        ["value", "val", "concentration", "result", "measured_value", "值"]]

    is_long = len(long_indicators) > 0 and len(value_indicators) > 0

    structure = {
        "is_long_format": is_long,
        "is_wide_format": not is_long,
        "n_columns": n_cols,
        "long_indicators_found": long_indicators,
        "value_indicators_found": value_indicators,
        "verdict": "长表(需pivot)" if is_long else "宽表(已是model-ready候选)",
    }
    print(f"\n[2] 数据结构识别:")
    print(f"    列数: {n_cols}")
    print(f"    长表指标列: {long_indicators}")
    print(f"    数值指标列: {value_indicators}")
    print(f"    判定: {structure['verdict']}")

    # 3. 完整读入统计行数
    print(f"\n[3] 统计完整行数...")
    df_full = pd.read_csv(RAW_CSV, low_memory=False)
    n_rows = len(df_full)
    print(f"    行数: {n_rows}, 列数: {n_cols}")

    # 4. 写结构报告
    report = {**manifest, **structure,
              "n_rows": n_rows,
              "columns_sample": cols[:30],
              "needs_pivot": is_long}
    with open(os.path.join(OUT_DIR, "data_structure_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[4] 结构报告: data/reports/data_structure_report.json")

    # 5. 如果是宽表, 输出列分类(实测/协变量/元数据)
    if not is_long:
        measured_prefix = []
        gee_cols = [c for c in cols if c.startswith("gee_")]
        meta_cols = [c for c in cols if c in
                     ["DOI", "Source", "Year", "Journal", "Country", "Province", "City",
                      "SiteDescription", "SamplingYear", "SamplingDepth", "LandUseType",
                      "LandUse", "Pollution_Type", "SampleID", "site_id", "Latitude",
                      "Longitude", "Latitude_range", "Longitude_range", "pH", "pH_merged",
                      "SoilTexture", "SoilType", "Glucosinolate_umol_g",
                      "OC_pct_calculated_by"]]
        conc_cols = [c for c in cols if c not in gee_cols and c not in meta_cols
                     and c not in ["SoilpH", "OC_pct", "CEC_cmolkg", "Sand_pct", "Silt_pct",
                                   "Clay_pct", "SoilBD_gcm3", "Elevation_m", "MAP_mm",
                                   "EC_mScm", "TN_gkg"]]
        phys_cols = [c for c in cols if c in
                     ["SoilpH", "pH", "pH_merged", "OC_pct", "CEC_cmolkg", "Sand_pct",
                      "Silt_pct", "Clay_pct", "SoilBD_gcm3", "Elevation_m", "MAP_mm",
                      "EC_mScm", "TN_gkg"]]

        print(f"\n[5] 宽表字段分类:")
        print(f"    GEE协变量: {len(gee_cols)}列")
        print(f"    元数据: {len(meta_cols)}列")
        print(f"    理化属性: {len(phys_cols)}列")
        print(f"    浓度+其他: {len(conc_cols)}列")

    print(f"\n✅ P0 快照完成。原始数据未被修改。")


if __name__ == "__main__":
    main()
