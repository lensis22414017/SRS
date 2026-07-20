from __future__ import annotations

import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REAL_FILES = [
    (
        ROOT / "data/raw/1.20250731_复合污染场地数据表(乡村建设用地)_完整版.xlsx",
        "composite",
        8,
    ),
    (
        ROOT / "data/raw/2.20250731_有机污染场地数据表(南京栖霞)_完整版.xlsx",
        "organic",
        49,
    ),
    (
        ROOT / "data/raw/3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx",
        "heavy_metal",
        134,
    ),
]


def _kos_summary(result: dict) -> dict:
    return {
        "track": result.get("track"),
        "subset": result.get("subset"),
        "model_id": result.get("model_id"),
        "model_version": result.get("model_version"),
        "model_contribution_scope": result.get("model_contribution_scope"),
        "decision_point_id": result.get("decision_point_id"),
        "decision_point_code": result.get("decision_point_code"),
        "n_sampling_points": result.get("n_sampling_points"),
        "coverage": result.get("coverage"),
        "review_required": result.get("review_required"),
        "open_set_summary": result.get("open_set_summary"),
        "key_obstacles": result.get("key_obstacles", []),
        "model_contribution": result.get("model_contribution", []),
        "per_point_stats": result.get("per_point_stats", {}),
        "data_quality_flags": result.get("data_quality_flags", []),
        "limitations": result.get("limitations", []),
    }


def test_three_real_sites_full_source_gate():
    """三份甲方原始数据必须完成当前可用业务链路，并输出真实状态。

    经济数据本来就不在三份土壤检测表内，所以 SSUI 的正确结果是
    blocked/needs_input，而不是用测试夹具或区域代理值伪造正式分数。
    """
    assert all(path.is_file() for path, _, _ in REAL_FILES)

    from app.api.diagnosis import trigger_kos_diagnosis
    from app.main import _check_model_integrity, app
    from app.models import SamplingPoint, Site, User
    from app.services.evaluation_service import run_evaluation
    from app.services.import_service import smart_detect_and_map
    from app.services.pipeline import run_import_with_mapping
    from app.services.recommend_service import run_recommendation
    from app.services.report_service import collect, render_html
    from app.db.session import SessionLocal

    app.state.model_health = _check_model_integrity(str(ROOT))
    assert app.state.model_health["ok"] is True, app.state.model_health

    db = SessionLocal()
    evidence: dict = {
        "source_gate": "round10",
        "model_health": app.state.model_health,
        "sites": [],
    }
    local_signatures = []
    try:
        user = db.query(User).filter_by(username="admin").one()
        for path, expected_type, expected_points in REAL_FILES:
            _, mapping, mapping_report = smart_detect_and_map(str(path))
            imported = run_import_with_mapping(
                db,
                str(path),
                mapping,
                imported_by=user.id,
                on_conflict="skip",
            )
            site = db.get(Site, imported["site_id"])
            assert site is not None
            assert site.pollution_type == expected_type
            assert not re.search(r"[0-9]", site.site_code), site.site_code
            point_count = db.query(SamplingPoint).filter_by(site_id=site.id).count()
            assert point_count == expected_points

            subset = {
                "composite": "hm_op",
                "organic": "op",
                "heavy_metal": "hm",
            }[expected_type]
            kos_prod = trigger_kos_diagnosis(
                site.id,
                track="prod",
                subset=subset,
                top_n=10,
                user=user,
                db=db,
            )
            kos_eco = trigger_kos_diagnosis(
                site.id,
                track="eco",
                subset=subset,
                top_n=10,
                user=user,
                db=db,
            )
            for kos_result in (kos_prod, kos_eco):
                assert kos_result.get("model_contribution_scope") == "local_point"
                assert kos_result.get("decision_point_id") is not None
                assert kos_result.get("n_sampling_points") == expected_points
                signature = tuple(
                    (item.get("factor"), round(float(item.get("contribution", 0)), 6))
                    for item in kos_result.get("model_contribution", [])[:5]
                )
                assert signature
                local_signatures.append((site.id, kos_result["track"], signature))

            evaluation = run_evaluation(
                db,
                site.id,
                evaluation_year=0,
                scenario="production",
                scope="production",
                allow_proxy=False,
            )
            recommendation = run_recommendation(db, site.id, top_k=5)
            report_context = collect(db, site.id, "round10-source-gate")
            report_html = render_html(report_context)
            assert site.name in report_html
            assert "KOS" in report_html

            serialized_eval = json.dumps(evaluation, ensure_ascii=False, default=str)
            if expected_type == "heavy_metal":
                contradictory = ("总体评价为优", "整体状况良好", "低风险污染")
                assert not any(text in serialized_eval for text in contradictory)
                top_factors = {
                    item.get("factor") for item in kos_prod.get("key_obstacles", [])
                }
                assert top_factors & {"As_mgkg", "Pb_mgkg", "Cu_mgkg", "Zn_mgkg"}

            ssui_detail = evaluation.get("details", {}).get("ssui", {})
            if ssui_detail:
                assert ssui_detail.get("ssui") is None
                assert ssui_detail.get("is_blocked") is True

            evidence["sites"].append(
                {
                    "source_file": path.name,
                    "mapping": {
                        "mapping_id": mapping.get("mapping_id") if isinstance(mapping, dict) else None,
                        "confidence": getattr(mapping_report, "confidence", None),
                        "warnings": getattr(mapping_report, "warnings", None),
                    },
                    "site": {
                        "id": site.id,
                        "site_code": site.site_code,
                        "name": site.name,
                        "pollution_type": site.pollution_type,
                        "land_use_type": site.land_use_type,
                        "sampling_points": point_count,
                        "measurements": imported.get("n_measurements"),
                    },
                    "kos_production": _kos_summary(kos_prod),
                    "kos_ecology": _kos_summary(kos_eco),
                    "evaluation": evaluation,
                    "recommendation": recommendation,
                    "report": {
                        "context_has_kos": bool(
                            report_context.get("diagnosis", {}).get("kos")
                        ),
                        "html_size": len(report_html.encode("utf-8")),
                    },
                }
            )

        signature_values = {signature for _, _, signature in local_signatures}
        assert len(signature_values) >= 3, local_signatures

        output_dir = os.environ.get("SRS_EVIDENCE_DIR")
        if output_dir:
            evidence_path = Path(output_dir)
            evidence_path.mkdir(parents=True, exist_ok=True)
            (evidence_path / "three_real_sites_e2e.json").write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            for site_evidence in evidence["sites"]:
                pollution_type = site_evidence["site"]["pollution_type"]
                (evidence_path / f"site_{pollution_type}.json").write_text(
                    json.dumps(site_evidence, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )
    finally:
        db.close()
