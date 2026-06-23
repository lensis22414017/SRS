"""导入流水线: 解析 -> 校验 -> 入库, 一步到位。需 DB。"""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.services.import_service import load_mapping, parse
from app.services.ingest_service import ingest
from app.services.threshold_resolver import build_pollutant_limits
from app.services.validation_service import validate

from app.core.config import resource_root

ROOT = resource_root()
KB_CSV = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")

_LIMITS_CACHE: dict | None = None


def get_pollutant_limits() -> dict:
    global _LIMITS_CACHE
    if _LIMITS_CACHE is None:
        _LIMITS_CACHE = build_pollutant_limits(KB_CSV)
    return _LIMITS_CACHE


def run_import_with_mapping(db: Session, file_path: str, mapping: dict,
                             imported_by: int | None = None,
                             scope: str = "production",
                             land_subtype: str = "其他用地") -> dict:
    """直接接受 mapping 字典（无需磁盘 JSON 文件）。供 wizard 接口和 run_import 共用。"""
    parsed = parse(file_path, mapping)
    report = validate(parsed, mapping, pollutant_limits=get_pollutant_limits(),
                      scope=scope, land_subtype=land_subtype)
    # 透传 mapping + source_path: 入库时保存 mapping_snapshot、计算 source_sha256/
    # mapping_hash 做幂等判重, 写入 data_version(brief 4.2)
    result = ingest(db, parsed, mapping=mapping, validation_report=report,
                    imported_by=imported_by, source_path=file_path)
    result["validation"] = {
        "n_points": report["n_points"], "n_measurements": report["n_measurements"],
        "n_errors": report["n_errors"], "n_warnings": report["n_warnings"],
        "n_exceed": report["n_exceed"], "passed": report["passed"],
        "exceed_factors": report["summary"]["exceed_factors"],
    }
    return result


def run_import(db: Session, file_path: str, mapping_id: str,
               imported_by: int | None = None,
               scope: str = "production", land_subtype: str = "其他用地") -> dict:
    mapping = load_mapping(mapping_id)
    return run_import_with_mapping(db, file_path, mapping,
                                   imported_by=imported_by,
                                   scope=scope, land_subtype=land_subtype)
