"""v1.2 API: 课题二 28 项重构可行性指标导入(修复前) + 冻结方法基线查询。"""
from __future__ import annotations

import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import assert_site_access, get_current_user, require_permission
from app.db.session import get_db
from app.models import EvaluationResult, ReconImportBatch, Site, User
from app.services import recon_import_service as RI

router = APIRouter(prefix=get_settings().api_v1_prefix, tags=["v1.2"])
MAX_UPLOAD = 20 * 1024 * 1024
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _site(db: Session, user: User, site_id: int) -> Site:
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    return s


def _xlsx(data: bytes, name: str) -> StreamingResponse:
    return StreamingResponse(io.BytesIO(data), media_type=_XLSX,
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})


@router.get("/templates/recon-pre")
def download_recon_template(site_code: str = "", user: User = Depends(get_current_user)):
    return _xlsx(RI.build_template(site_code), f"SRS_课题二重构指标导入模板_{RI.TEMPLATE_VERSION}.xlsx")


@router.get("/methods/reconstruction-baseline")
def reconstruction_baseline(user: User = Depends(get_current_user)):
    M = RI.M
    return {"method_version": M.METHOD_VERSION, "source": M.METHOD_SOURCE, "threshold": M.FEASIBLE_THRESHOLD,
            "weights": {"table_2_18": M.T218, "table_2_19": M.T219, "table_2_21": M.T221,
                        "sum_2_18": round(sum(M.T218.values()), 4), "sum_2_19": round(sum(M.T219.values()), 4),
                        "sum_2_21": round(sum(M.T221.values()), 4)},
            "features": [{"id": f, "cn": M.FEATURES[f]["cn"], "unit": M.FEATURES[f]["unit"], "kind": M.FEATURES[f]["kind"]}
                         for f in M.RECON_28],
            "deferred": M.DEFERRED}


@router.post("/sites/{site_id}/recon/preview")
async def recon_preview(site_id: int, file: UploadFile = File(...),
                        data_origin: str | None = Form(None), provenance_status: str | None = Form(None),
                        land_subtype: str | None = Form(None), eco_land_class: str | None = Form(None),
                        user: User = Depends(require_permission("data:input")), db: Session = Depends(get_db)):
    site = _site(db, user, site_id)
    content = await file.read()
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, "文件超过 20 MB")
    name = file.filename or "upload.xlsx"
    if not name.lower().endswith((".xlsx", ".xlsm", ".csv")):
        raise HTTPException(422, "仅支持 .xlsx / .csv")
    try:
        return RI.preview(db, site, content, name, user.id,
                          {"data_origin": data_origin, "provenance_status": provenance_status,
                           "land_subtype": land_subtype, "eco_land_class": eco_land_class})
    except RI.ReconImportError as e:
        raise HTTPException(422, str(e))


def _batch(db: Session, user: User, batch_id: int) -> ReconImportBatch:
    b = db.get(ReconImportBatch, batch_id)
    if not b:
        raise HTTPException(404, "批次不存在")
    _site(db, user, b.site_id)
    return b


@router.post("/recon/batches/{batch_id}/confirm")
def recon_confirm(batch_id: int, user: User = Depends(require_permission("data:input")), db: Session = Depends(get_db)):
    _batch(db, user, batch_id)
    try:
        return RI.confirm(db, batch_id, user.id)
    except RI.ReconImportError as e:
        raise HTTPException(409, str(e))


@router.post("/recon/batches/{batch_id}/reject")
def recon_reject(batch_id: int, user: User = Depends(require_permission("data:input")), db: Session = Depends(get_db)):
    b = _batch(db, user, batch_id)
    if b.status != "previewed":
        raise HTTPException(409, f"批次状态为 {b.status}, 不可放弃")
    b.status = "rejected"; db.commit()
    return {"batch_id": b.id, "status": b.status}


@router.get("/sites/{site_id}/recon/batches")
def recon_batches(site_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _site(db, user, site_id)
    out = []
    for b in db.query(ReconImportBatch).filter_by(site_id=site_id).order_by(ReconImportBatch.id.desc()).all():
        evs = {e.eval_type: e for e in db.query(EvaluationResult).filter_by(source_batch_id=b.id, subproject="S2")
               .order_by(EvaluationResult.id).all()}
        out.append({"batch_id": b.id, "status": b.status, "source_file": b.source_file, "sha256": b.source_sha256,
                    "template_version": b.template_version, "data_origin": b.data_origin,
                    "data_origin_label": RI.DATA_ORIGINS.get(b.data_origin, b.data_origin),
                    "provenance_status": b.provenance_status, "provenance_label": RI.PROVENANCE.get(b.provenance_status),
                    "land_subtype": b.land_subtype, "eco_land_class": b.eco_land_class,
                    "point_count": b.point_count, "error_count": b.error_count, "warning_count": b.warning_count,
                    "method_version": b.method_version,
                    "created_at": b.created_at.isoformat() if b.created_at else None,
                    "confirmed_at": b.confirmed_at.isoformat() if b.confirmed_at else None,
                    "production": ({"score": evs["reconstruction_prod"].score, "grade": evs["reconstruction_prod"].grade}
                                   if "reconstruction_prod" in evs else None),
                    "ecology": ({"score": evs["reconstruction_eco"].score, "grade": evs["reconstruction_eco"].grade}
                                if "reconstruction_eco" in evs else None)})
    return {"site_id": site_id, "batches": out}


@router.get("/recon/batches/{batch_id}")
def recon_batch_detail(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = _batch(db, user, batch_id)
    evs = (db.query(EvaluationResult).filter_by(source_batch_id=b.id, subproject="S2")
           .order_by(EvaluationResult.id.desc()).all())
    seen, ev_out = set(), {}
    for e in evs:
        if e.eval_type in seen:
            continue
        seen.add(e.eval_type)
        ev_out["production" if e.eval_type == "reconstruction_prod" else "ecology"] = {
            "score": e.score, "grade": e.grade, "explanation": e.explanation, "limiting_factors": e.limiting_factors,
            "dimensions": e.dimensions, "weights": e.weights, "method_version": e.method_version}
    rep = b.validation_report or {}
    return {"batch_id": b.id, "status": b.status, "source_file": b.source_file, "sha256": b.source_sha256,
            "data_origin_label": RI.DATA_ORIGINS.get(b.data_origin, b.data_origin),
            "provenance_label": RI.PROVENANCE.get(b.provenance_status), "point_count": b.point_count,
            "errors": rep.get("errors", []), "warnings": rep.get("warnings", [])[:200],
            "absent_features": rep.get("absent_features", []), "mapping": b.mapping_snapshot,
            "cleaning_log": b.cleaning_log, "evaluation": ev_out}


@router.get("/recon/batches/{batch_id}/export")
def recon_export(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = _batch(db, user, batch_id)
    if b.status not in ("confirmed", "superseded"):
        raise HTTPException(409, "仅已确认批次可导出")
    return _xlsx(RI.export_batch(db, b), f"SRS_课题二重构评价_批次{b.id}.xlsx")
