"""model_ready 派生表与标准化红线测试。"""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, "ml", "cleaning")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_standardize_uses_full_region_names():
    from standardize import normalize_pollution_type, normalize_region, normalize_unit

    assert normalize_region("Qinghai") == "青藏高原区"
    assert normalize_region("Liaoning") == "东北平原区"
    assert normalize_region("Guangdong") == "华南/东南沿海区"
    assert normalize_pollution_type("PAH") == "OP"
    assert normalize_pollution_type("重金属-有机复合污染") == "HM+OP"
    assert normalize_unit("mg kg-1") == "mg/kg"


def test_build_model_ready_views_preserve_missing_and_watermark():
    from build_model_ready import build_views

    df = pd.DataFrame({
        "DOI": ["10.1/a", "10.1/a", "10.2/b"],
        "Source": ["paper-a", "paper-a", "paper-b"],
        "SampleID": ["S1", "S2", "S3"],
        "Province": ["Qinghai", "Liaoning", "Guangdong"],
        "City": ["Xining", "Shenyang", "Guangzhou"],
        "Latitude": [36.6, 41.8, 23.1],
        "Longitude": [101.8, 123.4, 113.2],
        "LandUse": ["farmland", "industrial land", "e-waste burning"],
        "Pollution_Type": ["HM", "PAH", "HM+OP"],
        "SamplingYear": [2020, 2021, 2022],
        "pH_merged": [7.2, None, 6.4],
        "CEC_cmolkg": [12.0, None, 8.0],
        "Cd_mgkg": [0.4, None, 1.2],
        "As_mgkg": [25.0, None, 80.0],
        "BaP_ngg": [None, 14.0, 23.0],
    })
    views, schema = build_views(df, source_sha256="abc123", op_limit=10)

    expected = {"shared", "hm", "op", "hm_op", "risk", "production", "ecology"}
    assert expected <= set(views)
    assert {"view", "column", "role", "evidence_level"} <= set(schema.columns)

    hm = views["hm"]
    assert len(hm) == 2
    assert hm["is_synthetic"].eq(False).all()
    assert hm["evidence_level"].eq("MEASURED").all()
    assert "covariate_pH_merged" in hm.columns
    assert "measured_Cd_mgkg" in hm.columns
    assert "missing_Cd_mgkg" in hm.columns
    assert hm.loc[hm["id_SampleID"] == "S1", "missing_Cd_mgkg"].iloc[0] == 0
    assert "measured_BaP_ngg" in views["op"].columns
    assert "measured_Cd_mgkg" not in views["op"].columns
    assert pd.isna(views["hm_op"].loc[views["hm_op"]["id_SampleID"] == "S1", "measured_BaP_ngg"]).iloc[0]

    first_ids = views["hm"]["row_uid"].tolist()
    second_ids = build_views(df, source_sha256="abc123", op_limit=10)[0]["hm"]["row_uid"].tolist()
    assert first_ids == second_ids
    assert not any(str(v).startswith("hm_0") for v in first_ids)
