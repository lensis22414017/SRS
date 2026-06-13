"""导入流水线: 解析 -> 校验 -> 入库, 一步到位。需 DB。"""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.services.import_service import load_mapping, parse
from app.services.ingest_service import ingest
from app.services.threshold_resolver import build_pollutant_limits
from app.services.validation_service import validate

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KB_CSV = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")

_LIMITS_CACHE: dict | None = None


def get_pollutant_limits() -> dict:
    global _LIMITS_CACHE
    if _LIMITS_CACHE is None:
        _LIMITS_CACHE = build_pollutant_limits(KB_CSV)
    return _LIMITS_CACHE


def run_import(db: Session, file_path: str, mapping_id: str,
               imported_by: int | None = None,
               scope: str = "production", land_subtype: str = "其他用地") -> dict:
    mapping = load_mapping(mapping_id)
    parsed = parse(file_path, mapping)
    report = validate(parsed, mapping, pollutant_limits=get_pollutant_limits(),
                      scope=scope, land_subtype=land_subtype)
    result = ingest(db, parsed, validation_report=report, imported_by=imported_by)
    result["validation"] = {
        "n_points": report["n_points"], "n_measurements": report["n_measurements"],
        "n_errors": report["n_errors"], "n_warnings": report["n_warnings"],
        "n_exceed": report["n_exceed"], "passed": report["passed"],
        "exceed_factors": report["summary"]["exceed_factors"],
    }
    return result
