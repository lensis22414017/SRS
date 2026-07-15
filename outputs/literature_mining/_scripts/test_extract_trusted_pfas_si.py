import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("extract_trusted_pfas_si.py")
SPEC = importlib.util.spec_from_file_location("extract_trusted_pfas_si", MODULE_PATH)
extractor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extractor)


PFAS_SI = Path(r"G:\所有文献\14.第十阶段小补充 4") / (
    "Legacy and Novel Per- and Polyfluoroalkyl Substances in Surface Soils "
    "across China Source Tracking and Main Drivers for the Spatial Variation_si_002.xlsx"
)


def test_surface_soil_si_yields_124_traceable_samples_and_74_analytes():
    long_df, wide_df = extractor.extract_surface_soil_pfas(PFAS_SI)
    assert long_df["sample_id"].nunique() == 124
    assert long_df["pollutant_name_std"].nunique() == 74
    assert len(long_df) == 124 * 74
    assert len(wide_df) == 124
    assert long_df["unit_std"].eq("ng/g").all()
    assert long_df["matrix"].eq("soil").all()
    assert long_df["evidence_location"].str.match(r"Table 2![A-Z]+\d+").all()


def test_zero_values_are_censored_not_treated_as_measured_concentrations():
    long_df, _ = extractor.extract_surface_soil_pfas(PFAS_SI)
    zero = long_df[long_df["value_original"] == 0]
    positive = long_df[long_df["value_original"] > 0]
    assert zero["censoring_flag"].eq("below_detection").all()
    assert positive["censoring_flag"].eq("measured").all()


def test_wide_table_contains_measured_family_sum_and_source_group():
    _, wide_df = extractor.extract_surface_soil_pfas(PFAS_SI)
    assert "x_measured_SumPFAS_ngg" in wide_df
    assert wide_df["x_measured_SumPFAS_ngg"].gt(0).all()
    assert wide_df["source_id"].nunique() == 1
    assert wide_df["audit_flag"].eq("si_native_table_verified").all()
