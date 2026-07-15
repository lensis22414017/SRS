from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).parent))
from build_training_v2 import build_hmop_v2, build_op_v2  # noqa: E402


BASE = Path(__file__).resolve().parents[1]


def test_op_v2_adds_two_independent_trusted_sources():
    original = pd.read_csv(BASE / "train_table_op_only_SOIL_CLEAN.csv", low_memory=False)
    result = build_op_v2(BASE)
    assert len(result) == len(original) + 124 + 27
    assert result["source_id"].isin([
        "PFAS_SURFACE_SOILS_CHINA_SI_TABLE2", "coal_mining_east_china_pah_si"
    ]).sum() == 151
    assert result.loc[result.source_id == "PFAS_SURFACE_SOILS_CHINA_SI_TABLE2", "x_measured_SumPFAS_ngg"].notna().all()


def test_hmop_v2_adds_five_strictly_paired_samples_and_converts_pah_units():
    original = pd.read_csv(BASE / "train_table_hm_op_SOIL_CLEAN.csv", low_memory=False)
    result = build_hmop_v2(BASE)
    added = result[result.source_id == "industrial_sites_hm_pah_si"]
    assert len(result) == len(original) + 5
    assert set(added.sample_id) == {"industrial_sites_hm_pah_si_A", "industrial_sites_hm_pah_si_B", "industrial_sites_hm_pah_si_C", "industrial_sites_hm_pah_si_D", "industrial_sites_hm_pah_si_E"}
    row_d = added.set_index("sample_id").loc["industrial_sites_hm_pah_si_D"]
    assert row_d["x_measured_Cr_mgkg"] == 348.61
    assert row_d["x_measured_Sum_PAH_ngg"] == 698740.0
    assert (added.n_hm >= 7).all()
    assert (added.n_op >= 15).all()
