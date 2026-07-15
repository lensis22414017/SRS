from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).parent))
from extract_trusted_docx_si import extract_coal_pah, extract_industrial_hm_pah  # noqa: E402


COAL = Path(
    r"G:\所有文献\8.第八阶段挖掘\si\DataSheet1_Characterization of polycyclic "
    r"aromatic hydrocarbons in soil in a coal mining area, East China_ Spatial "
    r"distribution, sources, and carcinog.docx"
)
INDUSTRIAL = Path(__file__).resolve().parents[1] / "trusted_reextract" / (
    "industrial_hm_pah_si/1-s2.0-S2666498422000254-mmc3.docx"
)


def test_coal_pah_has_27_real_soil_samples_and_units():
    data = extract_coal_pah(COAL)
    assert data["sample_id"].nunique() == 27
    assert set(data["sample_id"]) >= {"US1", "US10", "CS1", "CS17"}
    assert set(data["unit"]) == {"ng/g"}
    assert set(data["matrix"]) == {"soil"}
    assert data["value"].notna().all()
    assert data.duplicated(["source_id", "sample_id", "analyte"]).sum() == 0


def test_industrial_data_are_strictly_paired_hm_pah_samples():
    data = extract_industrial_hm_pah(INDUSTRIAL)
    assert set(data["sample_id"]) == {"A", "B", "C", "D", "E"}
    assert set(data["unit"]) == {"mg/kg"}
    families = data.groupby("sample_id")["pollutant_family"].agg(set)
    assert families.map(lambda value: {"HM", "PAH"}.issubset(value)).all()
    assert data.duplicated(["source_id", "sample_id", "analyte"]).sum() == 0
    assert data["evidence_location"].str.match(r"DOCX:Table[01]:row\d+").all()


def test_industrial_known_values_are_not_shifted_by_merged_cells():
    data = extract_industrial_hm_pah(INDUSTRIAL)
    values = data.set_index(["sample_id", "analyte"])["value"]
    assert values["B", "Cd"] == 27.39
    assert values["D", "Cr"] == 348.61
    assert values["E", "SumPAH"] == 12558.06
    assert values["A", "SumPAH"] == 4.40

