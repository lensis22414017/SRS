"""入库: ParsedSite -> sites / sampling_points / measurements(长表) + import_batches。

需 DB (SQLAlchemy)。可重复运行: 同 site_code 复用场地; 同一批导入新建 import_batch。
未登记因子自动登记到 factor_dictionary(来源标注), 不伪造、不改原始值。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import (
    FactorDictionary, ImportBatch, Measurement, SamplingPoint, Site,
)
from app.services.import_service import ParsedSite
from app.services.versioning import (
    batch_data_version, compute_mapping_hash, compute_source_sha256,
)

SCRIPT_VERSION = "ingest_v0.1"


def ensure_factor(db: Session, fdef: dict) -> int:
    obj = db.query(FactorDictionary).filter_by(factor_code=fdef["factor_code"]).first()
    if obj is None:
        obj = FactorDictionary(
            factor_code=fdef["factor_code"],
            factor_name=fdef.get("factor_name", fdef["factor_code"]),
            level1_category=fdef.get("level1_category"),
            factor_type=fdef.get("factor_type"),
            default_unit=fdef.get("default_unit"),
            source=("统一障碍因子知识库_V1.0" if fdef.get("in_kb")
                    else "场地数据导入登记"),
        )
        db.add(obj)
        db.flush()
    return obj.id


def _parse_date(s) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(s), fmt).date()
        except ValueError:
            continue
    return None


def upsert_site(db: Session, site_meta: dict) -> Site:
    code = site_meta.get("site_code")
    site = db.query(Site).filter_by(site_code=code).first()
    if site is None:
        site = Site(site_code=code)
        db.add(site)
    site.name = site_meta.get("name", site.name or code)
    site.pollution_type = site_meta.get("pollution_type", site.pollution_type)
    site.land_use_type = site_meta.get("land_use_type", site.land_use_type)
    site.province = site_meta.get("province", site.province)
    site.city = site_meta.get("city", site.city)
    if site_meta.get("longitude") is not None:
        site.longitude = site_meta["longitude"]
        site.latitude = site_meta["latitude"]
    if site_meta.get("organization_id"):
        site.organization_id = site_meta["organization_id"]
    db.flush()
    return site


def _slim_mapping_snapshot(mapping: dict | None) -> dict | None:
    """精简 mapping 用于持久化(brief 4.2, 避免宽表 JSON 过大超 sqlite binding)。

    只保留 site/point_columns/sheet + factor_columns 的 column/factor_code 摘要(限前 200)。
    完整 mapping 可由 mapping_hash + 源文件重建。
    """
    if not mapping:
        return None
    return {
        "mapping_id": mapping.get("mapping_id"),
        "sheet": mapping.get("sheet"),
        "site": mapping.get("site"),
        "point_columns": mapping.get("point_columns"),
        "factor_columns": [
            {"column": fc.get("column"), "factor_code": fc.get("factor_code")}
            for fc in (mapping.get("factor_columns") or [])[:200]
        ],
    }


def _purge_site_data(db: Session, site_id: int) -> None:
    """删除场地全部检测数据(measurements/sampling_points/import_batches), 保留 site 行供 overwrite 复用。"""
    db.query(Measurement).filter_by(site_id=site_id).delete()
    db.query(SamplingPoint).filter_by(site_id=site_id).delete()
    db.query(ImportBatch).filter_by(site_id=site_id).delete()
    db.flush()


def ingest(db: Session, parsed: ParsedSite, mapping: dict | None = None,
           validation_report: dict | None = None, imported_by: int | None = None,
           source_path: str | None = None,
           on_conflict: str = "skip") -> dict:
    """入库 ParsedSite。

    裴总 P1-3: 全局内容指纹(source_sha256 + mapping_hash)判重 — 在 upsert_site 之前拦截,
    同一份数据即使 site_code 不同也不重复造场地。on_conflict:
      skip(默认)→ 返回原场地, 不重写; overwrite → 清旧数据重导; new_version → 建新 site_code。
    """
    source_sha = compute_source_sha256(source_path) if source_path else None
    map_hash = compute_mapping_hash(mapping) if mapping else None

    # 全局判重(不限 site_id): 同 sha256 + mapping_hash = 同一份数据
    existing_batch = None
    if source_sha and map_hash:
        existing_batch = (db.query(ImportBatch)
                          .filter_by(source_sha256=source_sha, mapping_hash=map_hash)
                          .order_by(ImportBatch.id.desc()).first())

    if existing_batch:
        existing_site = db.get(Site, existing_batch.site_id)
        if on_conflict == "skip":
            n_meas = db.query(Measurement).filter_by(site_id=existing_site.id).count()
            return {"site_id": existing_site.id, "batch_id": existing_batch.id,
                    "n_points": existing_batch.row_count, "n_measurements": n_meas,
                    "reimported": True, "skipped": True, "action": "skipped",
                    "dedup_batch_id": existing_batch.id,
                    "source_sha256": source_sha, "data_version": existing_batch.data_version}
        if on_conflict == "overwrite" and existing_site:
            _purge_site_data(db, existing_site.id)  # 清旧, upsert_site 按 site_code 复用
        elif on_conflict == "new_version" and existing_site:
            base = parsed.site.get("site_code") or existing_site.site_code
            parsed.site["site_code"] = f"{base}_v{existing_batch.id + 1}"

    site = upsert_site(db, parsed.site)
    sampled_at = _parse_date(parsed.site.get("sampled_at"))

    batch = ImportBatch(
        site_id=site.id,
        source_file=parsed.source_file,
        source_sha256=source_sha,
        mapping_hash=map_hash,
        # brief 4.2: 保存实际 mapping 关键部分(site/point_columns/factor_columns 摘要),
        # 限制 factor_columns 数量避免宽表(如719列) JSON 超 sqlite binding 上限。
        mapping_snapshot=_slim_mapping_snapshot(mapping),
        row_count=parsed.n_points,
        valid_count=(parsed.n_points if (validation_report or {}).get("passed", True) else
                     parsed.n_points - (validation_report or {}).get("n_errors", 0)),
        invalid_count=(validation_report or {}).get("n_errors", 0),
        validation_report=validation_report,
        script_version=SCRIPT_VERSION,
        status="success" if (validation_report or {}).get("passed", True) else "partial",
        imported_by=imported_by,
    )
    db.add(batch)
    db.flush()

    # 幂等清理: 删除同场地同源文件的旧测量值(同文件旧批次/旧格式重导残留), 避免翻倍
    db.query(Measurement).filter_by(site_id=site.id,
                                    source_file=parsed.source_file).delete()
    db.flush()

    # 因子登记缓存
    factor_ids = {fd["factor_code"]: ensure_factor(db, fd) for fd in parsed.factor_defs}

    n_points = 0
    n_meas = 0
    for p in parsed.points:
        sp = db.query(SamplingPoint).filter_by(site_id=site.id, point_code=p.point_code).first()
        if sp is None:
            sp = SamplingPoint(site_id=site.id, point_code=p.point_code)
            db.add(sp)
        sp.longitude = p.longitude
        sp.latitude = p.latitude
        sp.region = p.region
        sp.depth_top_cm = p.depth_top_cm
        sp.depth_bottom_cm = p.depth_bottom_cm
        sp.soil_type = p.soil_type
        sp.sampled_at = sampled_at
        db.flush()
        n_points += 1
        for m in p.measurements:
            if m.value is None:
                continue  # 缺失值不入库, 已在校验报告体现
            db.add(Measurement(
                site_id=site.id,
                sampling_point_id=sp.id,
                factor_id=factor_ids[m.factor_code],
                value=m.value,
                unit=m.unit,
                is_below_detection=False,
                source_file=parsed.source_file,
                import_batch_id=batch.id,
                detected_at=sampled_at,
            ))
            n_meas += 1
    # 本批次数据版本(基于内容指纹, 替换旧 site{id}_n{count} 假指纹)
    batch.data_version = batch_data_version(source_sha, n_meas, site.id)
    db.commit()
    action = ("new_version" if (on_conflict == "new_version" and existing_batch)
              else "overwritten" if (on_conflict == "overwrite" and existing_batch)
              else "created")
    return {"site_id": site.id, "batch_id": batch.id,
            "n_points": n_points, "n_measurements": n_meas,
            "reimported": False, "action": action,
            "source_sha256": source_sha, "data_version": batch.data_version}
