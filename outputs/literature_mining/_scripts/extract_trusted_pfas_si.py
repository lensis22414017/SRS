"""从原生 SI 表格提取可追溯的全国土壤 PFAS 数据。"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from openpyxl.utils import get_column_letter


SOURCE_ID = "PFAS_SURFACE_SOILS_CHINA_SI_TABLE2"
TITLE = (
    "Legacy and Novel Per- and Polyfluoroalkyl Substances in Surface Soils "
    "across China: Source Tracking and Main Drivers for the Spatial Variation"
)


def extract_surface_soil_pfas(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_excel(path, sheet_name="Table 2", header=3)
    raw = raw.dropna(subset=["Sample number"]).copy()
    raw["Province"] = raw["Province"].ffill()

    metadata = ["Province", "Sample city", "Sample number", "Longitude", "Latitude", "Crop type"]
    analytes = [column for column in raw.columns if column not in metadata]
    if len(raw) != 124 or len(analytes) != 74:
        raise ValueError(f"SI结构变化：预期124样本×74因子，实际{len(raw)}×{len(analytes)}")

    records = []
    for row_offset, (_, row) in enumerate(raw.iterrows(), start=5):
        sample_number = str(row["Sample number"]).strip()
        sample_id = f"{SOURCE_ID}_{sample_number.lstrip('#')}"
        for column_index, analyte in enumerate(analytes, start=7):
            value = pd.to_numeric(row[analyte], errors="coerce")
            if pd.isna(value) or value < 0:
                raise ValueError(f"非法浓度：{sample_number}/{analyte}={row[analyte]!r}")
            records.append({
                "source_id": SOURCE_ID,
                "paper_id": SOURCE_ID,
                "title": TITLE,
                "sample_id": sample_id,
                "province": row["Province"],
                "city_or_region": row["Sample city"],
                "latitude": row["Latitude"],
                "longitude": row["Longitude"],
                "matrix": "soil",
                "pollution_type": "OP",
                "pollutant_family": "PFAS",
                "pollutant_name_original": analyte,
                "pollutant_name_std": str(analyte).strip(),
                "value_original": float(value),
                "unit_original": "ng/g",
                "value_std": float(value),
                "unit_std": "ng/g",
                "censoring_flag": "below_detection" if value == 0 else "measured",
                "evidence_level": "A_sample_table",
                "evidence_location": f"Table 2!{get_column_letter(column_index)}{row_offset}",
                "source_file": str(path),
                "qa_flag": "verified_native_si",
            })

    long_df = pd.DataFrame.from_records(records)
    measured = long_df[long_df["censoring_flag"] == "measured"]
    sums = measured.groupby("sample_id", as_index=False)["value_std"].sum().rename(
        columns={"value_std": "x_measured_SumPFAS_ngg"}
    )
    sample_meta = long_df.drop_duplicates("sample_id")[[
        "sample_id", "source_id", "paper_id", "province", "city_or_region",
        "latitude", "longitude", "matrix",
    ]]
    wide_df = sample_meta.merge(sums, on="sample_id", how="left")
    wide_df["audit_flag"] = "si_native_table_verified"
    return long_df, wide_df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    long_df, wide_df = extract_surface_soil_pfas(args.input)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(args.output_dir / "pfas_surface_soil_trusted_long.csv", index=False, encoding="utf-8-sig")
    wide_df.to_csv(args.output_dir / "pfas_surface_soil_trusted_wide.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
