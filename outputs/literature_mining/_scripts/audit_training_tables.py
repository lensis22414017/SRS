from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parents[1]
TABLES = (
    "train_table_op_only_SOIL_CLEAN.csv",
    "train_table_hm_op_SOIL_CLEAN.csv",
    "train_table_hm_SOIL_CLEAN.csv",
)


def main() -> None:
    for name in TABLES:
        data = pd.read_csv(BASE / name, low_memory=False)
        raw_path = BASE.parents[1] / "data" / "raw" / "literature_mining" / name
        raw_shape = pd.read_csv(raw_path, low_memory=False).shape if raw_path.exists() else None
        missing = data.isna().mean()
        constant = data.nunique(dropna=False) <= 1
        print(f"\n{name}: rows={len(data)}, cols={len(data.columns)}, raw_shape={raw_shape}")
        print(
            f"full_duplicates={data.duplicated().sum()}, "
            f"missing_ge_80pct={(missing >= 0.8).sum()}, "
            f"constant_cols={constant.sum()}, "
            f"median_missing={missing.median():.3f}"
        )
        for column in (
            "source_id", "source_group", "doi", "paper_id", "sample_id",
            "pollution_type", "track", "target", "label", "risk_level",
        ):
            if column in data:
                top = data[column].value_counts(dropna=False).head(3).to_dict()
                print(f"{column}: unique={data[column].nunique(dropna=True)}, top={top}")
        print("most_missing:", missing.sort_values(ascending=False).head(10).round(3).to_dict())


if __name__ == "__main__":
    main()
