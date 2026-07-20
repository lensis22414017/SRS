"""Round10 SSUI 科学门禁与官方参照集回归。"""
from __future__ import annotations

import csv
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(BACKEND)
sys.path.insert(0, os.path.join(ROOT, "ml", "evaluation"))


def _full_safety_inputs():
    series = {
        "电导率": [0.2, 0.2], "碱化度": [5.0], "机械组成": [50.0], "含水率": [30.0],
        "阳离子交换量": [20.0], "盐基饱和度": [60.0], "pH": [7.0], "有机质": [30.0],
        "水稳性团聚体": [60.0], "有效锌": [2.0], "有效铁": [20.0], "有效锰": [5.0],
        "有效硼": [1.0], "有效钙": [500.0], "全氮": [1.5], "全磷": [1.0],
        "速效钾": [150.0], "过氧化氢酶": [1.0], "脲酶": [1.0], "磷酸酶": [1.0],
        "蔗糖酶": [1.0], "渗透率": [10.0], "有效土层": [100.0], "表面粗糙度": [1.0],
        "砷": [10.0], "苯并[a]芘": [0.1],
    }
    references = {}
    for factor, values in series.items():
        if factor in {"砷", "苯并[a]芘"}:
            continue
        value = float(values[0])
        references[factor] = {"min": 0.0, "max": max(2.0, value * 2.0),
                              "direction": "negative" if factor == "电导率" else "positive"}
    thresholds = {
        "砷": {"limit": 30.0, "resolution_status": "resolved", "standard": "GB15618-2018"},
        "苯并[a]芘": {"limit": 0.55, "resolution_status": "resolved", "standard": "GB36600-2018"},
    }
    statuses = {factor: "resolved" for factor in thresholds}
    groups = {"heavy_metals": ["砷"], "organics": ["苯并[a]芘"]}
    return series, references, thresholds, statuses, groups


def _full_economic(source_type="site_actual"):
    values = {
        "D18": 480.0, "D19": 188.0, "D20": 230.0, "D21": 260.0,
        "D22": 19800.0, "D23": 1.08, "D24": 14500.0, "D25": 7250.0,
    }
    return {code: {"value": value, "source_type": source_type,
                   "is_proxy": source_type != "site_actual"}
            for code, value in values.items()}


def test_official_reference_is_computed_from_48_observations():
    from reference_loader import load_economic_reference
    data = load_economic_reference()
    assert data["valid"] is True, data["errors"]
    assert data["sample_count"] == 48
    assert data["year_range"] == [2015, 2020]
    assert set(data["ranges"]) == {f"D{i}" for i in range(18, 26)}
    assert data["ranges"]["D18"]["min"] == 467.41
    assert data["ranges"]["D18"]["max"] == 508.59
    assert len(data["sha256"]) == 64


def test_reference_with_pending_source_is_rejected(tmp_path):
    from reference_loader import REQUIRED_COLUMNS, load_economic_reference
    path = tmp_path / "bad.csv"
    fields = sorted(REQUIRED_COLUMNS)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for code in ("D18", "D19", "D20", "D21", "D22", "D23", "D24", "D25"):
            for year, value in ((2019, 1), (2020, 2)):
                writer.writerow({
                    "indicator_code": code, "indicator_name": code, "scope": "production",
                    "crop": "rice", "region": "CN", "year": year,
                    "unit": {"D18": "元/亩·年", "D19": "元/亩·年", "D20": "元/亩·年",
                             "D21": "元/亩·年", "D22": "元/公顷·年", "D23": "无量纲",
                             "D24": "元/人·年", "D25": "kg/公顷·年"}[code],
                    "value": value, "direction": "negative" if code in {"D18", "D19", "D20", "D21"} else "positive",
                    "source_name": "待核查", "source_url": "https://example.invalid/source",
                    "source_document": "待核查", "table_or_page": "待核查", "is_proxy": "true",
                    "version": "v1", "effective_date": "2026-07-20", "derivation": "待核查",
                })
    result = load_economic_reference(str(path))
    assert result["valid"] is False
    assert result["ranges"] == {}
    assert any("可核查" in error for error in result["errors"])


def test_constant_site_values_use_external_reference_not_variance():
    from ssui import _normalize_against_external_reference
    reference = {"min": 0.0, "max": 100.0, "direction": "positive"}
    low = _normalize_against_external_reference([1.0, 1.0], reference)
    severe = _normalize_against_external_reference([90.0, 90.0], reference)
    assert low == 0.01
    assert severe == 0.9
    assert low != severe


def test_measured_pollutant_unknown_threshold_blocks():
    from ssui import _aggregate_pollutant_risk
    result = _aggregate_pollutant_risk(["镉"], {"镉": [5.0]}, {}, "D16_重金属污染物")
    assert result["status"] == "unresolved_threshold"
    assert result["score"] is None
    assert result["unresolved_factors"] == ["镉"]


def test_full_25_fixture_returns_deterministic_auditable_score():
    from reference_loader import load_economic_reference
    from ssui import evaluate
    series, safety_refs, thresholds, statuses, groups = _full_safety_inputs()
    kwargs = dict(
        series=series, scope="production", t=2.0, intensity="medium",
        economic_data=_full_economic(), safety_thresholds=thresholds,
        threshold_resolution_status=statuses, safety_reference_ranges=safety_refs,
        economic_reference_data=load_economic_reference(), pollutant_groups=groups,
    )
    first = evaluate(**kwargs)
    second = evaluate(**kwargs)
    assert first["is_blocked"] is False, first
    assert first["coverage"] == {
        "complete_25": True, "measured_total": 25, "required_total": 25,
        "economic_measured": 8, "economic_total": 8, "economic_complete": True,
    }
    assert first["ssui"] == second["ssui"]
    assert 0 <= first["bounded_score"] <= 1
    assert first["raw_score"] >= 0
    assert len(first["dimensions"]["parts"]) == 25


def test_incomplete_c1_cannot_be_called_complete_25():
    from ssui import evaluate
    result = evaluate(
        {"pH": [6.5], "砷": [5.0]}, economic_data=_full_economic(),
        safety_thresholds={"砷": {"limit": 30.0, "resolution_status": "resolved"}},
        threshold_resolution_status={"砷": "resolved"},
        pollutant_groups={"heavy_metals": ["砷"], "organics": []},
    )
    assert result["is_blocked"] is True
    assert result["ssui"] is None
    assert result["d_coverage"]["C1"] < 15
    assert "25" in result["explanation"]
