"""将通过证据门控的新SI样本合并为三份版本化训练候选表。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "training_v2"
PAH_COLUMN_MAP = {
    "NaP": "x_measured_Nap_ngg", "NAP": "x_measured_Nap_ngg",
    "Acy": "x_measured_Acy_ngg", "ACY": "x_measured_Acy_ngg",
    "Ace": "x_measured_Ace_ngg", "Flu": "x_measured_Flu_ngg",
    "FLO": "x_measured_Flu_ngg", "Phe": "x_measured_Phe_ngg",
    "PHE": "x_measured_Phe_ngg", "Ant": "x_measured_Ant_ngg",
    "ANT": "x_measured_Ant_ngg", "Flua": "x_measured_Fla_ngg",
    "FLA": "x_measured_Fla_ngg", "Pyr": "x_measured_Pyr_ngg",
    "PYR": "x_measured_Pyr_ngg", "BaA": "x_measured_BaA_ngg",
    "Chr": "x_measured_Chr_ngg", "CHR": "x_measured_Chr_ngg",
    "BbF": "x_measured_BbF_ngg", "BkF": "x_measured_BkF_ngg",
    "BaP": "x_measured_BaP_ngg", "InP": "x_measured_Ind_ngg",
    "IcP": "x_measured_Ind_ngg", "DbA": "x_measured_DahA_ngg",
    "DhA": "x_measured_DahA_ngg", "BghiP": "x_measured_BghiP_ngg",
    "BgP": "x_measured_BghiP_ngg", "SumPAH": "x_measured_Sum_PAH_ngg",
}
HM_COLUMN_MAP = {name: f"x_measured_{name}_mgkg" for name in ("Cd", "Pb", "As", "Cr", "Hg", "Cu", "Zn", "Ni")}


def append_metadata(frame: pd.DataFrame, source_id: str, sample_id: str) -> dict:
    return {
        column: None for column in frame.columns
    } | {
        "sample_id": sample_id, "source_id": source_id, "paper_id": source_id,
        "matrix": "soil", "site_type": "field", "province": None,
        "latitude": None, "longitude": None, "audit_flag": "si_native_table_verified",
    }


def build_op_v2(base: Path = BASE) -> pd.DataFrame:
    current = pd.read_csv(base / "train_table_op_only_SOIL_CLEAN.csv", low_memory=False)
    if "x_measured_SumPFAS_ngg" not in current:
        current["x_measured_SumPFAS_ngg"] = None
    pfas = pd.read_csv(base / "trusted_reextract" / "pfas_surface_soil_trusted_wide.csv")
    pfas_rows = []
    for _, source in pfas.iterrows():
        row = append_metadata(current, source.source_id, source.sample_id)
        for key in ("paper_id", "province", "latitude", "longitude", "matrix", "audit_flag"):
            row[key] = source.get(key)
        row["x_measured_SumPFAS_ngg"] = source.x_measured_SumPFAS_ngg
        row["n_hm"], row["n_op"] = 0, 1
        pfas_rows.append(row)
    coal = pd.read_csv(base / "trusted_reextract" / "coal_mining_pah_trusted_long.csv")
    coal_rows = []
    for sample_id, group in coal.groupby("sample_id", sort=False):
        row = append_metadata(current, group.source_id.iloc[0], f"coal_mining_pah_si_{sample_id}")
        mapped = 0
        for _, observation in group.iterrows():
            column = PAH_COLUMN_MAP.get(observation.analyte)
            if column in current.columns:
                row[column] = observation.value
                mapped += 1
        row["n_hm"], row["n_op"] = 0, mapped
        coal_rows.append(row)
    result = pd.concat([current, pd.DataFrame(pfas_rows), pd.DataFrame(coal_rows)], ignore_index=True)
    result["data_version"] = "v2_trusted_augmented_20260715"
    return result


def build_hmop_v2(base: Path = BASE) -> pd.DataFrame:
    current = pd.read_csv(base / "train_table_hm_op_SOIL_CLEAN.csv", low_memory=False)
    data = pd.read_csv(base / "trusted_reextract" / "industrial_hm_pah_trusted_long.csv")
    rows = []
    for sample_id, group in data.groupby("sample_id", sort=False):
        source_id = group.source_id.iloc[0]
        row = append_metadata(current, source_id, f"{source_id}_{sample_id}")
        n_hm = n_op = 0
        for _, observation in group.iterrows():
            if observation.pollutant_family == "HM":
                column = HM_COLUMN_MAP.get(observation.analyte)
                factor = 1.0
                n_hm += column in current.columns
            else:
                column = PAH_COLUMN_MAP.get(observation.analyte)
                factor = 1000.0  # mg/kg与ng/g的量纲换算
                n_op += column in current.columns
            if column in current.columns:
                row[column] = observation.value * factor
        row["n_hm"], row["n_op"] = n_hm, n_op
        rows.append(row)
    result = pd.concat([current, pd.DataFrame(rows)], ignore_index=True)
    result["data_version"] = "v2_trusted_augmented_20260715"
    return result


def write_outputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    op = build_op_v2()
    hmop = build_hmop_v2()
    hm = pd.read_csv(BASE / "train_table_hm_SOIL_CLEAN.csv", low_memory=False)
    hm["data_version"] = "v2_audited_20260715"
    op.to_csv(OUT / "train_table_op_only_SOIL_CLEAN_V2.csv", index=False, encoding="utf-8-sig")
    hmop.to_csv(OUT / "train_table_hm_op_SOIL_CLEAN_V2.csv", index=False, encoding="utf-8-sig")
    hm.to_csv(OUT / "train_table_hm_SOIL_CLEAN_V2.csv", index=False, encoding="utf-8-sig")
    print(f"OP-only V2: {op.shape}; HM+OP V2: {hmop.shape}; HM V2: {hm.shape}")


if __name__ == "__main__":
    write_outputs()
