"""入库: ParsedSite -> sites / sampling_points / measurements(长表) + import_batches。

需 DB (SQLAlchemy)。可重复运行: 同 site_code 复用场地; 同一批导入新建 import_batch。
未登记因子自动登记到 factor_dictionary(来源标注), 不伪造、不改原始值。
"""
from __future__ import annotations

from datetime import date, datetime
import re

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    DatasetVersion, FactorDictionary, ImportBatch, Measurement, SamplingPoint, Site,
)
from app.services.import_service import ParsedSite
from app.services.versioning import (
    batch_data_version, compute_mapping_hash, compute_source_sha256,
)

SCRIPT_VERSION = "ingest_v0.1"


def _to_base26(n: int) -> str:
    """正整数转纯大写字母，用于不含数字的展示编号。"""
    n = max(int(n), 1)
    chars: list[str] = []
    while n:
        n, rem = divmod(n - 1, 26)
        chars.append(chr(ord("A") + rem))
    return "".join(reversed(chars))


def normalize_site_display_code(db: Session, site: Site, source_code: str | None) -> None:
    """保存原始业务编号，同时保证甲方界面使用的 site_code 不含数字。

    智能导入临时编号、含数字编号及包含非拉丁字符的编号都转换为
    `SRS-<Base26(site.id)>`。纯字母业务编号原样保留。
    """
    raw = str(source_code or "").strip()
    is_display_safe = bool(re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z]+)*", raw))
    requires_generated_code = not is_display_safe or raw.upper().startswith("AUTO")
    if not requires_generated_code:
        site.site_code = raw.upper()
        return
    if raw:
        site.original_site_code = raw
    generated = f"SRS-{_to_base26(site.id)}"
    collision = db.query(Site.id).filter(
        Site.site_code == generated, Site.id != site.id
    ).first()
    if collision:
        raise ValueError(f"纯字母场地编号冲突: {generated}")
    site.site_code = generated


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
    code = str(site_meta.get("site_code") or "").strip()
    if not code:
        raise ValueError("场地编号不能为空")
    site = db.query(Site).filter(or_(
        Site.site_code == code,
        Site.original_site_code == code,
    )).first()
    if site is None:
        site = Site(site_code=code, name=site_meta.get("name") or code)
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
    normalize_site_display_code(db, site, code)
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


def _check_site_ownership(db: Session, site_code: str, user_org_id: int | None) -> None:
    """v0.2 P1-5: 校验用户有权操作该 site_code。若 site_code 已被其他组织占用, 拒绝导入。"""
    if user_org_id is None:
        return  # 管理员无组织限制
    existing = db.query(Site).filter_by(site_code=site_code).first()
    if existing and existing.organization_id is not None and existing.organization_id != user_org_id:
        raise ValueError(
            f"场地代码 '{site_code}' 已被其他组织占用 (org_id={existing.organization_id})。"
            f"当前用户组织 (org_id={user_org_id}) 无权导入该场地数据。"
        )


def _purge_site_data(db: Session, site_id: int) -> None:
    """删除场地全部检测数据(measurements/sampling_points/import_batches), 保留 site 行供 overwrite 复用。
    v0.2 P1-6: 仅删除测量数据和采样点, 保留诊断/评价/推荐/追溯记录。"""
    db.query(Measurement).filter_by(site_id=site_id).delete()
    db.query(SamplingPoint).filter_by(site_id=site_id).delete()
    db.query(ImportBatch).filter_by(site_id=site_id).delete()
    db.flush()


def ingest(db: Session, parsed: ParsedSite, mapping: dict | None = None,
           validation_report: dict | None = None, imported_by: int | None = None,
           source_path: str | None = None,
           on_conflict: str = "skip") -> dict:
    """入库 ParsedSite。

    全局内容指纹(source_sha256 + mapping_hash)判重 — 在 upsert_site 之前拦截,
    同一份数据即使 site_code 不同也不重复造场地。on_conflict:
      skip(默认)→ 返回原场地, 不重写; overwrite → 清旧数据重导; new_version → 建新 site_code。
    """
    source_sha = compute_source_sha256(source_path) if source_path else None
    map_hash = compute_mapping_hash(mapping) if mapping else None

    # v0.2 P1-5: 导入前校验 site_code 归属
    user_org_id = parsed.site.get("_user_org_id") or parsed.site.get("organization_id")
    target_code = parsed.site.get("site_code")
    if target_code:
        _check_site_ownership(db, target_code, user_org_id)

    # 全局判重(不限 site_id): 同 sha256 + mapping_hash = 同一份数据
    existing_batch = None
    if source_sha and map_hash:
        existing_batch = (db.query(ImportBatch)
                          .filter_by(source_sha256=source_sha, mapping_hash=map_hash)
                          .order_by(ImportBatch.id.desc()).first())

    if existing_batch:
        existing_site = db.get(Site, existing_batch.site_id)
        # v0.2 P1-6: overwrite 校验 — 防止因全局去重误删其他企业场地
        if existing_site and user_org_id is not None and existing_site.organization_id != user_org_id:
            raise ValueError(
                f"该文件此前已由组织 org_id={existing_site.organization_id} 导入为场地 "
                f"'{existing_site.site_code}'。当前组织无权覆盖。请使用 'new_version' 模式或联系管理员。"
            )
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
            # v1.0 P0-2: 不再修改 site_code 创建新场地, 改用 DatasetVersion 记录导入版本
            # 当前导入沿用同一 site, 后续在当前 site 下创建新 dataset_version 记录
            pass  # 标记: 下方 upsert_site 将复用 existing_site, 不创建新 site

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
            if m.value is None and not m.is_below_detection:
                continue  # 纯缺失值不入库; 低于检出限(ND)的保留
            db.add(Measurement(
                site_id=site.id,
                sampling_point_id=sp.id,
                factor_id=factor_ids[m.factor_code],
                value=m.value,
                unit=m.unit,
                # v0.2 P0-1: 检测限字段
                original_value_text=m.original_value_text,
                qualifier=m.qualifier,
                detection_limit=m.detection_limit,
                is_below_detection=m.is_below_detection,
                method=m.method,
                # v0.2 P1-1: 监管级数据契约字段
                value_used_for_model=m.value,           # 初始值=原始值; 模型预处理后再更新
                replicate_group_id=m.replicate_group_id,
                qa_status="raw",
                evidence_level="A",
                data_origin="field",
                # 元数据
                source_file=parsed.source_file,
                import_batch_id=batch.id,
                source_file_id=getattr(parsed, 'file_object_id', None),
                detected_at=sampled_at,
            ))
            n_meas += 1
    # 本批次数据版本(基于内容指纹, 替换旧 site{id}_n{count} 假指纹)
    batch.data_version = batch_data_version(source_sha, n_meas, site.id)
    db.commit()
    # v1.0 P0-2: new_version 创建 DatasetVersion 记录(同一 site 下)
    if on_conflict == "new_version" and existing_batch:
        version_code = f"v{existing_batch.id + 1}"
        dv = DatasetVersion(
            site_id=site.id,
            version_code=version_code,
            source_type="import",
            row_count=n_meas,
            factor_count=len(factor_ids),
            point_count=n_points,
            qa_summary={"source_sha256": source_sha, "import_batch_id": batch.id} if source_sha else None,
            created_by=imported_by,
            is_active=True,
        )
        # 将旧的 active 版本标记为非活跃
        db.query(DatasetVersion).filter_by(site_id=site.id, is_active=True).update({"is_active": False})
        db.add(dv)
        db.commit()
    action = ("new_version" if (on_conflict == "new_version" and existing_batch)
              else "overwritten" if (on_conflict == "overwrite" and existing_batch)
              else "created")
    return {"site_id": site.id, "batch_id": batch.id,
            "n_points": n_points, "n_measurements": n_meas,
            "reimported": False, "action": action,
            "source_sha256": source_sha, "data_version": batch.data_version}
