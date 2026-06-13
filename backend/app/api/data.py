"""数据管理 API: 导入、场地列表/详情、采样点、检测值长表查询、校验报告。"""
from __future__ import annotations

import os
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import (
    assert_site_access, get_current_user, require_permission, scope_sites_query,
)
from app.db.session import get_db
from app.models import (
    FactorDictionary, ImportBatch, Measurement, SamplingPoint, Site, User,
)
from app.services.audit_service import log
from app.services.pipeline import run_import

router = APIRouter(prefix=get_settings().api_v1_prefix, tags=["data"])


@router.post("/import")
async def import_data(mapping_id: str = Form(...), file: UploadFile = File(...),
                      user: User = Depends(require_permission("data:input")),
                      db: Session = Depends(get_db)):
    import datetime as _dt
    import json as _json

    settings = get_settings()
    os.makedirs(settings.file_storage_dir, exist_ok=True)
    # 自动重命名: 时间戳_区域_污染类型.ext (便于管理)
    ext = os.path.splitext(file.filename or "data.xlsx")[1] or ".xlsx"
    region = pollution = ""
    try:
        mp = os.path.join(os.path.dirname(__file__), "..", "services", "mappings", f"{mapping_id}.json")
        if os.path.exists(mp):
            meta = _json.load(open(mp, encoding="utf-8")).get("site", {})
            region = (meta.get("city") or meta.get("province") or "").replace("市", "").replace("省", "")
            pollution = {"heavy_metal": "重金属", "organic": "有机", "composite": "复合"}.get(meta.get("pollution_type", ""), "")
    except Exception:  # noqa: BLE001
        pass
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    canonical = f"{ts}_{region or '场地'}_{pollution or '污染'}{ext}"
    dest = os.path.join(settings.file_storage_dir, canonical)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = run_import(db, dest, mapping_id, imported_by=user.id)
        result["stored_filename"] = canonical
        result["original_filename"] = file.filename
    except FileNotFoundError:
        raise HTTPException(404, f"映射配置不存在: {mapping_id}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"导入失败: {e}")
    log(db, action="import", user_id=user.id, resource_type="sites",
        resource_id=result.get("site_id"), detail={"mapping_id": mapping_id})
    return result


@router.get("/sites")
def list_sites(q: str | None = None, pollution_type: str | None = None,
               page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=200),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = scope_sites_query(db, user, db.query(Site))
    if q:
        query = query.filter(Site.name.contains(q) | Site.site_code.contains(q))
    if pollution_type:
        query = query.filter(Site.pollution_type == pollution_type)
    total = query.count()
    rows = query.order_by(Site.id).offset((page - 1) * size).limit(size).all()
    items = [{
        "id": s.id, "site_code": s.site_code, "name": s.name,
        "pollution_type": s.pollution_type, "land_use_type": s.land_use_type,
        "province": s.province, "city": s.city,
        "longitude": float(s.longitude) if s.longitude is not None else None,
        "latitude": float(s.latitude) if s.latitude is not None else None,
        "n_points": db.query(func.count(SamplingPoint.id)).filter_by(site_id=s.id).scalar(),
    } for s in rows]
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/sites/{site_id}")
def site_detail(site_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    n_points = db.query(func.count(SamplingPoint.id)).filter_by(site_id=site_id).scalar()
    n_meas = db.query(func.count(Measurement.id)).filter_by(site_id=site_id).scalar()
    return {
        "id": s.id, "site_code": s.site_code, "name": s.name,
        "pollution_type": s.pollution_type, "land_use_type": s.land_use_type,
        "province": s.province, "city": s.city,
        "longitude": float(s.longitude) if s.longitude is not None else None,
        "latitude": float(s.latitude) if s.latitude is not None else None,
        "n_points": n_points, "n_measurements": n_meas,
    }


@router.get("/sites/{site_id}/points")
def site_points(site_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    pts = db.query(SamplingPoint).filter_by(site_id=site_id).order_by(SamplingPoint.id).all()
    return [{
        "id": p.id, "point_code": p.point_code, "region": p.region,
        "longitude": float(p.longitude) if p.longitude is not None else None,
        "latitude": float(p.latitude) if p.latitude is not None else None,
        "depth_top_cm": p.depth_top_cm, "depth_bottom_cm": p.depth_bottom_cm,
        "soil_type": p.soil_type,
    } for p in pts]


@router.get("/sites/{site_id}/points-wide")
def site_points_wide(site_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """采样点宽表: 每行=采样点, 列=全部实测因子值 + 元数据。供前端横向滚动表格。"""
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    pts = db.query(SamplingPoint).filter_by(site_id=site_id).order_by(SamplingPoint.id).all()
    rows = (db.query(Measurement, FactorDictionary)
            .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id).all())
    by_point: dict[int, dict] = {}
    factor_order: list[str] = []
    for m, fd in rows:
        by_point.setdefault(m.sampling_point_id, {})[fd.factor_code] = m.value
        if fd.factor_code not in factor_order:
            factor_order.append(fd.factor_code)
    items = []
    for i, p in enumerate(pts, 1):
        row = {"seq": i, "point_code": p.point_code, "region": p.region,
               "longitude": float(p.longitude) if p.longitude is not None else None,
               "latitude": float(p.latitude) if p.latitude is not None else None,
               "depth": f"{p.depth_top_cm or 0}-{p.depth_bottom_cm or 0}",
               "soil_type": p.soil_type}
        row.update(by_point.get(p.id, {}))
        items.append(row)
    return {"factors": factor_order, "items": items, "total": len(items)}


@router.get("/sites/{site_id}/measurements")
def site_measurements(site_id: int, factor: str | None = None,
                      page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=500),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    query = (db.query(Measurement, FactorDictionary, SamplingPoint)
             .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
             .join(SamplingPoint, Measurement.sampling_point_id == SamplingPoint.id)
             .filter(Measurement.site_id == site_id))
    if factor:
        query = query.filter(FactorDictionary.factor_code == factor)
    total = query.count()
    rows = query.order_by(Measurement.id).offset((page - 1) * size).limit(size).all()
    items = [{
        "point_code": sp.point_code, "factor_code": fd.factor_code,
        "factor_name": fd.factor_name, "category": fd.level1_category,
        "value": m.value, "unit": m.unit,
    } for m, fd, sp in rows]
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/sites/{site_id}/eda")
def site_eda(site_id: int, user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """场地进入模型前的 EDA 数据分析: 各因子统计体检 + 直方图(真实数据)。"""
    import os
    import sys
    import pandas as pd
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    ml_eda = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "eda"))
    if ml_eda not in sys.path:
        sys.path.insert(0, ml_eda)
    from profile import column_stats, histogram  # type: ignore

    rows = (db.query(FactorDictionary.factor_code, Measurement.value)
            .join(Measurement, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id).all())
    if not rows:
        raise HTTPException(404, "该场地无检测数据")
    df = pd.DataFrame(rows, columns=["factor", "value"])
    factors = []
    for fc, sub in df.groupby("factor"):
        st = column_stats(sub["value"])
        factors.append({"factor": fc, "stats": st, "histogram": histogram(sub["value"], bins=15)})
    factors.sort(key=lambda x: x["factor"])
    return {"site_id": site_id, "n_factors": len(factors), "factors": factors}


@router.get("/import-batches/{batch_id}/validation-report")
def validation_report(batch_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    b = db.get(ImportBatch, batch_id)
    if not b:
        raise HTTPException(404, "导入批次不存在")
    return {
        "batch_id": b.id, "site_id": b.site_id, "source_file": b.source_file,
        "row_count": b.row_count, "valid_count": b.valid_count,
        "invalid_count": b.invalid_count, "status": b.status,
        "report": b.validation_report,
    }
