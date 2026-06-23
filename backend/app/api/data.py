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
    FactorDictionary, ImportBatch, Measurement, SamplingPoint, Site, ThresholdRule, User,
)
from app.services.audit_service import log
from app.services.import_service import load_mapping, read_table, resolve_mapping_for_file
from app.services.pipeline import run_import_with_mapping

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
    # ── 解析映射: auto=按文件 sheet/列签名自动识别; 否则按 mapping_id 加载 ──
    used_id, mapping, det_report = _resolve_mapping(mapping_id, dest)
    try:
        result = run_import_with_mapping(db, dest, mapping, imported_by=user.id)
        result["stored_filename"] = canonical
        result["original_filename"] = file.filename
        result["mapping_id"] = used_id
        result["mapping_label"] = (mapping.get("site") or {}).get("name")
        result["detection_report"] = det_report
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"导入失败 [{type(e).__name__}]: {e}")
    log(db, action="import", user_id=user.id, resource_type="sites",
        resource_id=result.get("site_id"), detail={"mapping_id": used_id, "requested": mapping_id})
    return result


def _resolve_mapping(mapping_id: str, dest: str) -> tuple[str, dict, dict]:
    """auto/空 → 统一自动识别(预设→smart); 否则按 mapping_id 加载。

    单文件/批量共用 resolve_mapping_for_file(brief 4.1), 保证同文件两路径同决策。
    低置信/缺必需字段 → 转为 review_required(400), 引导 Wizard, 不硬导入正式链路。
    返回 (used_id, mapping, detection_report)。
    """
    used_id, mapping, report = resolve_mapping_for_file(mapping_id, dest)
    if report.get("confidence", 1.0) < 0.5:
        warnings = report.get("warnings") or ["未识别到关键列"]
        raise HTTPException(
            400,
            "字段映射置信度不足，已转为待复核(review_required)。请使用『自定义字段映射 Wizard』手动映射后导入。"
            f" used_id={used_id}; confidence={report.get('confidence')}; "
            f"识别到: 点位列={report.get('point_code_column')}; "
            f"问题: {'; '.join(warnings)}。")
    return used_id, mapping, report


@router.post("/import/columns")
async def get_file_columns(file: UploadFile = File(...),
                           _user: User = Depends(require_permission("data:input"))):
    """读取上传文件的列名，供字段映射 wizard 使用。不写库。"""
    import tempfile as _tmp
    suffix = os.path.splitext(file.filename or "data.xlsx")[1] or ".xlsx"
    with _tmp.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        df = read_table(tmp_path, {"sheet": None})
        columns = [str(c).strip() for c in df.columns.tolist()]
        preview = df.head(3).fillna("").astype(str).to_dict(orient="records")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"文件解析失败: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return {"columns": columns, "preview": preview, "n_rows": len(df)}


@router.post("/import/wizard")
async def import_wizard(mapping: str = Form(...), file: UploadFile = File(...),
                        user: User = Depends(require_permission("data:input")),
                        db: Session = Depends(get_db)):
    """字段映射 wizard 导入: 前端传入内联 mapping JSON + 文件, 不依赖预定义 mapping_id。"""
    import datetime as _dt
    import json as _json

    try:
        mapping_dict = _json.loads(mapping)
    except Exception:
        raise HTTPException(400, "mapping 不是合法 JSON")

    settings = get_settings()
    os.makedirs(settings.file_storage_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "data.xlsx")[1] or ".xlsx"
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    canonical = f"{ts}_wizard{ext}"
    dest = os.path.join(settings.file_storage_dir, canonical)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = run_import_with_mapping(db, dest, mapping_dict, imported_by=user.id)
        result["stored_filename"] = canonical
        result["original_filename"] = file.filename
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"导入失败: {e}")
    log(db, action="import", user_id=user.id, resource_type="sites",
        resource_id=result.get("site_id"), detail={"mapping_id": "wizard"})
    return result


@router.post("/import/batch")
async def import_batch(mapping_id: str = Form(...),
                      files: list[UploadFile] = File(...),
                      user: User = Depends(require_permission("data:input")),
                      db: Session = Depends(get_db)):
    """批量导入: 多文件共用同一 mapping_id, 串行跑 pipeline 避免写库竞态。

    每个文件独立校验并返回结果; 单文件失败不阻断其余文件。
    返回 { total, succeeded, failed, results: [{filename, ok, ...}] }。
    """
    import datetime as _dt

    is_auto = mapping_id in ("auto", "", "detect", None)
    # 非 auto: 先校验映射文件(一次, 对所有文件共用); auto: 每个文件单独识别
    if not is_auto:
        try:
            mapping = load_mapping(mapping_id)
        except FileNotFoundError:
            raise HTTPException(404, f"映射配置不存在: {mapping_id}")

    settings = get_settings()
    os.makedirs(settings.file_storage_dir, exist_ok=True)
    results: list[dict] = []
    succeeded = failed = 0
    for idx, file in enumerate(files, 1):
        original_name = os.path.basename(file.filename or "data.xlsx")
        stem, ext = os.path.splitext(original_name)
        ext = ext or ".xlsx"
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        canonical = f"{ts}_{idx:02d}_{stem or 'batch'}{ext}"
        dest = os.path.join(settings.file_storage_dir, canonical)
        try:
            with open(dest, "wb") as f:
                shutil.copyfileobj(file.file, f)
            if is_auto:
                used_id, file_mapping, det_report = resolve_mapping_for_file(mapping_id, dest)
                # 低置信: 计 review_required, 该文件 failed, 不阻断批量其余文件(brief 4.1)
                if det_report.get("confidence", 1.0) < 0.5:
                    raise HTTPException(
                        400, "映射置信度不足(review_required): "
                        + "; ".join(det_report.get("warnings") or []))
            else:
                used_id, file_mapping = mapping_id, mapping
                det_report = {"used_id": mapping_id, "confidence": 1.0, "source": "preset"}
            res = run_import_with_mapping(db, dest, file_mapping, imported_by=user.id)
            res["stored_filename"] = canonical
            res["original_filename"] = original_name
            res["mapping_id"] = used_id
            res["mapping_label"] = (file_mapping.get("site") or {}).get("name")
            res["detection_report"] = det_report
            res["ok"] = True
            succeeded += 1
            log(db, action="import", user_id=user.id, resource_type="sites",
                resource_id=res.get("site_id"), detail={"mapping_id": used_id, "batch": True})
        except Exception as e:  # noqa: BLE001
            failed += 1
            results.append({"original_filename": original_name, "ok": False,
                            "error": f"导入失败 [{type(e).__name__}]: {e}"})
            continue
        results.append(res)
    return {"total": len(files), "succeeded": succeeded, "failed": failed, "results": results}


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
    # 批量统计: 该页每个场地的样点数/因子数/超标记录数(避免 N+1 查询)
    site_ids = [s.id for s in rows]
    factor_cnt: dict[int, int] = {}
    exceed_cnt: dict[int, int] = {}
    if site_ids:
        fc_rows = (db.query(Measurement.site_id, func.count(func.distinct(Measurement.factor_id)))
                   .filter(Measurement.site_id.in_(site_ids))
                   .group_by(Measurement.site_id).all())
        factor_cnt = {sid: int(c) for sid, c in fc_rows}
        # 超标记录: value > 该因子的正阈值上限(join ThresholdRule)
        # 超标按测量指标计: 每条 measurement 只要超过任意对应阈值档算1次(distinct去重, 避免pH档笛卡尔膨胀)
        ec_rows = (db.query(Measurement.site_id, func.count(func.distinct(Measurement.id)))
                   .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
                   .join(ThresholdRule, ThresholdRule.factor_id == FactorDictionary.id)
                   .filter(Measurement.site_id.in_(site_ids),
                           ThresholdRule.threshold_max != None,
                           Measurement.value > ThresholdRule.threshold_max)
                   .group_by(Measurement.site_id).all())
        exceed_cnt = {sid: int(c) for sid, c in ec_rows}
    items = [{
        "id": s.id, "site_code": s.site_code, "name": s.name,
        "pollution_type": s.pollution_type, "land_use_type": s.land_use_type,
        "province": s.province, "city": s.city,
        "longitude": float(s.longitude) if s.longitude is not None else None,
        "latitude": float(s.latitude) if s.latitude is not None else None,
        "n_points": db.query(func.count(SamplingPoint.id)).filter_by(site_id=s.id).scalar(),
        "n_factors": factor_cnt.get(s.id, 0),
        "n_exceed": exceed_cnt.get(s.id, 0),
        "data_quality": ("良好" if exceed_cnt.get(s.id, 0) == 0 else
                         "部分超标" if exceed_cnt.get(s.id, 0) < 10 else "大量超标"),
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
def site_eda(site_id: int,
             include: str | None = Query(None,
                 description="逗号分隔: distribution,correlation,qq,boxplot,grouped。默认全返回"),
             group_by: str | None = Query(None,
                 description="分组维度: region/depth/factor。需 grouped 才生效"),
             factor: str | None = Query(None,
                 description="仅分析指定因子 code(单因子深挖)"),
             max_points: int = Query(2000, ge=100, le=10000,
                 description="distribution 采样上限, 防响应爆炸"),
             user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """场地进入模型前的 EDA 数据分析: 各因子统计体检 + 直方图 + 科研级图件数据。

    按需返回: boxplot(箱线五数) / distribution(原始分布采样) / qq(正态Q-Q) /
    correlation(跨因子相关矩阵) / grouped(按 region/depth/factor 分层)。
    全部基于真实数据, 不插补。
    """
    import os
    import sys
    import pandas as pd
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    from app.core.config import resource_root
    ml_eda = os.path.join(resource_root(), "ml", "eda")
    if ml_eda not in sys.path:
        sys.path.insert(0, ml_eda)
    from eda_profile import (  # type: ignore
        boxplot_summary, column_stats, correlation_matrix, distribution_sample,
        grouped_stats, histogram, qq_points,
    )

    # 长表查询: factor_code + value + 真实采样点 id/区域/深度(用于 grouped/correlation pivot)
    rows = (db.query(FactorDictionary.factor_code, FactorDictionary.level1_category,
                     Measurement.sampling_point_id,
                     Measurement.value, SamplingPoint.region,
                     SamplingPoint.depth_top_cm, SamplingPoint.depth_bottom_cm)
            .join(Measurement, Measurement.factor_id == FactorDictionary.id)
            .join(SamplingPoint, Measurement.sampling_point_id == SamplingPoint.id)
            .filter(Measurement.site_id == site_id).all())
    if not rows:
        raise HTTPException(404, "该场地无检测数据")
    df = pd.DataFrame(rows, columns=["factor", "category", "point_id", "value", "region",
                                     "depth_top", "depth_bottom"])

    # 解析 include 参数(默认全返回, 兼容前端旧调用)
    inc = {x.strip() for x in include.split(",") if x.strip()} if include else {
        "distribution", "correlation", "qq", "boxplot", "grouped"}

    factors = []
    for fc, sub in df.groupby("factor"):
        if factor and fc != factor:
            continue
        st = column_stats(sub["value"])
        item = {"factor": fc, "category": sub["category"].iloc[0] if len(sub) else None,
                "stats": st, "histogram": histogram(sub["value"], bins=15)}
        if "boxplot" in inc:
            item["boxplot"] = boxplot_summary(sub["value"])
        if "distribution" in inc:
            item["distribution"] = distribution_sample(sub["value"], max_points=max_points)
        if "qq" in inc:
            item["qq"] = qq_points(sub["value"])
        factors.append(item)
    factors.sort(key=lambda x: x["factor"])

    resp: dict = {"site_id": site_id, "n_factors": len(factors), "factors": factors}

    if "correlation" in inc and len(factors) >= 2:
        # pivot 成宽表: 行=真实采样点 id, 列=因子。不能用 region/depth 这种弱键, 否则同区同层样点会被合并。
        pivot = df.pivot_table(index="point_id", columns="factor", values="value", aggfunc="mean")
        resp["correlation"] = correlation_matrix(pivot)

    if "grouped" in inc and group_by in ("region", "depth", "factor"):
        if group_by == "depth":
            df["depth_band"] = df.apply(
                lambda r: f"{int(r['depth_top'] or 0)}-{int(r['depth_bottom'] or 0)}cm", axis=1)
            gcol = "depth_band"
        elif group_by == "factor":
            gcol = "factor"
        else:
            gcol = "region"
        # 全因子整体分组 + 每个因子单独分组(便于按因子看分层差异)
        per_factor = {}
        for fc, sub in df.groupby("factor"):
            per_factor[fc] = grouped_stats(sub, "value", gcol)
        resp["grouped"] = {"group_by": group_by,
                           "overall": grouped_stats(df, "value", gcol),
                           "per_factor": per_factor}

    return resp


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
