import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("phase14_batch2_pipeline.py")
SPEC = importlib.util.spec_from_file_location("phase14_pipeline", MODULE_PATH)
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)

EXTRACTOR_PATH = Path(__file__).with_name("phase14_extract_batch2.py")
EXTRACTOR_SPEC = importlib.util.spec_from_file_location("phase14_extractor", EXTRACTOR_PATH)
extractor = importlib.util.module_from_spec(EXTRACTOR_SPEC)
EXTRACTOR_SPEC.loader.exec_module(extractor)


def test_low_concentration_heavy_metals_are_not_discarded():
    assert pipeline.is_valid_value("0.12", "Cd_mgkg")
    assert pipeline.is_valid_value("0.03", "Hg_mgkg")


def test_matrix_without_source_evidence_is_unknown(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline, "BASE", tmp_path)
    assert pipeline.infer_matrix_from_md("missing-paper") == ("unknown", "no_dir")


def test_antibiotics_are_excluded_from_formal_op_scope():
    assert "SMZ_ngg" not in pipeline.FORMAL_OP_POLLUTANTS
    assert "CTC_ngg" not in pipeline.FORMAL_OP_POLLUTANTS
    assert "OTC_ngg" not in pipeline.FORMAL_OP_POLLUTANTS


def test_training_record_requires_traceable_evidence():
    record = {
        "paper_id": "P001",
        "sample_id": "S1",
        "pollutant_std": "Cd_mgkg",
        "value": "0.12",
        "unit": "mg/kg",
        "evidence_location": "table_p3_ri2_ci4",
        "matrix": "soil",
    }
    assert pipeline.is_training_evidence_complete(record)
    record["unit"] = "Unknown"
    assert not pipeline.is_training_evidence_complete(record)


def test_table_unit_is_propagated_to_extracted_values():
    table = {
        "page_idx": 2,
        "table_caption": ["Concentrations of metals in soil (mg/kg)"],
        "table_body": (
            "<table><tr><th>Sample</th><th>Cd</th></tr>"
            "<tr><td>S1</td><td>0.12</td></tr>"
            "<tr><td>S2</td><td>0.08</td></tr></table>"
        ),
    }
    rows = extractor.extract_from_table(table, "P001")
    assert rows
    assert {row["unit"] for row in rows} == {"mg/kg"}


def test_hm_op_requires_both_families_at_the_same_sample():
    rows = [
        {"sample_id": "S1", "pollutant_std": "Cd_mgkg"},
        {"sample_id": "S2", "pollutant_std": "BaP_ngg"},
    ]
    partitions = pipeline.partition_rows_by_sample(rows)
    assert partitions["hm_op"] == []
    assert [row["sample_id"] for row in partitions["op_only"]] == ["S2"]

    rows.append({"sample_id": "S1", "pollutant_std": "BaP_ngg"})
    partitions = pipeline.partition_rows_by_sample(rows)
    assert {row["pollutant_std"] for row in partitions["hm_op"]} == {"Cd_mgkg", "BaP_ngg"}
