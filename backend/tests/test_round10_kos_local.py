from __future__ import annotations

import pandas as pd
from pathlib import Path

from app.api.diagnosis import _kos_canonical_payload
from app.services import kos_service


def test_decision_point_is_one_real_point_with_worst_rule_evidence():
    points = {
        101: {"Cd_mgkg": 2.0, "Pb_mgkg": 80.0},
        202: {"Cd_mgkg": 0.2, "Pb_mgkg": 1000.0},
    }
    thresholds = {
        "Cd_mgkg": {"type": "upper", "limit": 1.0},
        "Pb_mgkg": {"type": "upper", "limit": 100.0},
    }

    selected = kos_service._select_decision_point(points, thresholds)

    assert selected is not None
    assert selected["point_id"] == 202
    assert selected["factor_values"] == points[202]
    assert selected["exceedance_evidence"][0]["factor"] == "Pb_mgkg"


def test_point_specific_thresholds_control_selection_and_statistics():
    points = {
        1: {"Cd_mgkg": 2.0},
        2: {"Cd_mgkg": 3.0},
    }
    point_thresholds = {
        1: {"Cd_mgkg": {"type": "upper", "limit": 1.0}},
        2: {"Cd_mgkg": {"type": "upper", "limit": 6.0}},
    }
    point_meta = {
        1: {"Cd_mgkg": {"threshold_value": 1.0, "threshold_resolution_status": "resolved"}},
        2: {"Cd_mgkg": {"threshold_value": 6.0, "threshold_resolution_status": "resolved"}},
    }

    selected = kos_service._select_decision_point(
        points,
        {"Cd_mgkg": {"type": "upper", "limit": 1.0}},
        point_thresholds,
    )
    statistics = kos_service._compute_per_point_stats_dynamic(
        points, point_thresholds, point_meta
    )

    assert selected["point_id"] == 1
    assert statistics["Cd_mgkg"]["n_exceed_points"] == 1
    assert statistics["Cd_mgkg"]["max_exceedance_ratio"] == 2.0


def test_kos_local_contribution_uses_selected_point(monkeypatch, tmp_path):
    shap_dir = tmp_path / "shap_filtered"
    shap_dir.mkdir()
    pd.DataFrame(
        [
            {"group": "Cd_mgkg", "mean_abs_shap": 0.6, "direction": "positive"},
            {"group": "Pb_mgkg", "mean_abs_shap": 0.4, "direction": "positive"},
        ]
    ).to_csv(shap_dir / "all_prod_measured_contribution_global.csv", index=False)

    monkeypatch.setattr(kos_service, "_OUT_BASE", str(tmp_path))
    monkeypatch.setattr(
        kos_service,
        "load_registry",
        lambda: {
            "models": {
                "all_prod_Full_RandomForest": {
                    "status": "production",
                    "limitations": [],
                    "version": "test-v1",
                    "feature_list": ["Cd_mgkg", "Pb_mgkg"],
                }
            }
        },
    )
    monkeypatch.setattr(
        kos_service._kos_engine,
        "load_model_and_shap",
        lambda subset, track: {
            "model": object(),
            "feature_cols": ["x_measured_Cd_mgkg", "x_measured_Pb_mgkg"],
        },
    )

    from ml.explain import shap_service

    seen = {}

    def fake_local(_model, _feature_cols, point_values):
        seen.update(point_values)
        return {"Cd_mgkg": -1.0, "Pb_mgkg": 9.0}

    monkeypatch.setattr(shap_service, "compute_local_shap_for_point", fake_local)

    result = kos_service.run_kos_diagnosis(
        {"Cd_mgkg": 2.0, "Pb_mgkg": 1000.0},
        track="prod",
        subset="all",
        per_point_data={
            101: {"Cd_mgkg": 2.0, "Pb_mgkg": 80.0},
            202: {"Cd_mgkg": 0.2, "Pb_mgkg": 1000.0},
        },
    )

    assert result["decision_point_id"] == 202
    assert seen == {"Cd_mgkg": 0.2, "Pb_mgkg": 1000.0}
    assert result["model_contribution_scope"] == "local_point"
    assert result["model_feature_names"] == ["Cd_mgkg", "Pb_mgkg"]
    assert result["model_contribution"][0]["factor"] == "Pb_mgkg"
    assert result["model_contribution"][0]["contribution"] == 0.9
    assert all(
        item["decision_point_id"] == 202
        for item in result["model_contribution"]
    )


def test_canonical_payload_preserves_new_audit_fields():
    result = {
        "track": "prod",
        "key_obstacles": [],
        "decision_point_id": 7,
        "model_contribution_scope": "local_point",
        "future_audit_field": {"kept": True},
    }

    payload = _kos_canonical_payload(result)

    assert payload["decision_point_id"] == 7
    assert payload["model_contribution_scope"] == "local_point"
    assert payload["future_audit_field"] == {"kept": True}


def test_report_renders_local_kos_five_components_and_point_stats():
    from app.db.session import SessionLocal
    from app.models import DiagnosisResult, Site
    from app.services import report_service

    db = SessionLocal()
    try:
        site = Site(
            site_code="SRS-KOSLOCAL",
            name="局部解释测试场地",
            pollution_type="heavy_metal",
            land_use_type="生产用地",
        )
        db.add(site)
        db.flush()
        payload = {
        "key_obstacles": [
            {
                "rank": 1,
                "factor": "Cd_mgkg",
                "KOS": 0.88,
                "components": {"R": 1.0, "W": 0.9, "M": 0.2, "S": 0.8, "E": "A"},
                "value": 12.0,
                "threshold_value": 0.6,
                "threshold_standard": "GB 15618—2018",
            }
        ],
        "model_contribution": [
            {
                "factor": "Cd_mgkg",
                "contribution": 1.0,
                "direction": "positive",
                "local_shap_value": 2.5,
                "contribution_scope": "local_point",
            }
        ],
        "model_contribution_scope": "local_point",
        "decision_point_id": 9,
        "decision_point_code": "P-KOS",
        "interpretation_note": "局部 SHAP，非因果",
        "per_point_stats": {
            "Cd_mgkg": {
                "n_exceed_points": 2,
                "n_total_points": 3,
                "exceed_rate": 0.6667,
                "max_value": 12.0,
                "p95": 12.0,
                "median": 2.0,
                "max_exceedance_ratio": 20.0,
            }
        },
        "n_sampling_points": 3,
        "open_set": {},
        "open_set_summary": {},
        "review_required": False,
        "coverage": 1.0,
        }
        db.add(
            DiagnosisResult(
                site_id=site.id,
                data_version="test-data-v1",
                top_n=10,
                summary="KOS局部解释测试",
                diagnosis_method="kos",
                track="prod",
                subset="all",
                model_version="test-model-v1",
                result_payload=payload,
                status="kos_done",
            )
        )
        db.commit()

        context = report_service.collect(db, site.id, "round10")
        html = report_service.render_html(context)

        assert context["diagnosis"]["top_factors"][0]["kos_score"] == 0.88
        assert context["diagnosis"]["kos"]["decision_point_code"] == "P-KOS"
        assert "真实采样点 P-KOS 的局部 SHAP" in html
        assert "R=1.0 / W=0.9 / M=0.2 / S=0.8 / E=A" in html
        assert "2/3" in html
        assert "20.0" in html
    finally:
        db.close()


def test_three_real_sites_produce_distinct_local_contributions():
    from app.db.session import SessionLocal
    from app.models import FactorDictionary, Measurement, Site, User
    from app.services.import_service import smart_detect_and_map
    from app.services.pipeline import run_import_with_mapping

    root = Path(__file__).resolve().parents[2]
    files = [
        root / "data/raw/1.20250731_复合污染场地数据表(乡村建设用地)_完整版.xlsx",
        root / "data/raw/2.20250731_有机污染场地数据表(南京栖霞)_完整版.xlsx",
        root / "data/raw/3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx",
    ]
    assert all(path.exists() for path in files)

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username="admin").first()
        signatures = []
        for path in files:
            _, mapping, _ = smart_detect_and_map(str(path))
            imported = run_import_with_mapping(
                db,
                str(path),
                mapping,
                imported_by=user.id if user else None,
                on_conflict="skip",
            )
            site_id = imported["site_id"]
            site = db.get(Site, site_id)
            rows = (
                db.query(
                    Measurement.value_used_for_model,
                    Measurement.value,
                    Measurement.sampling_point_id,
                    FactorDictionary.factor_name,
                )
                .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
                .filter(Measurement.site_id == site_id)
                .all()
            )
            site_values = {}
            point_values = {}
            for value_used, value, point_id, factor_name in rows:
                raw_value = value_used if value_used is not None else value
                if raw_value is None:
                    continue
                numeric = float(raw_value)
                site_values[factor_name] = max(
                    site_values.get(factor_name, numeric), numeric
                )
                if point_id is not None:
                    point_values.setdefault(point_id, {})[factor_name] = numeric

            subset = {
                "composite": "hm_op",
                "organic": "op",
                "heavy_metal": "hm",
            }.get(site.pollution_type, "all")
            result = kos_service.run_kos_diagnosis(
                site_values,
                track="prod",
                subset=subset,
                site_pH=site_values.get("pH"),
                land_use_type="其他用地",
                db_session=db,
                per_point_data=point_values,
            )
            assert result["model_contribution_scope"] == "local_point", (
                path.name,
                result.get("local_shap_status"),
            )
            signature = tuple(
                (item["factor"], round(item["contribution"], 6))
                for item in result["model_contribution"][:5]
            )
            assert signature
            signatures.append(signature)

        assert len(set(signatures)) == 3, signatures
    finally:
        db.close()
