"""五阶段追溯 + 报告生成 API。"""
from __future__ import annotations

import os

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import assert_site_access, get_current_user, require_permission
from app.db.session import get_db
from app.models import FileObject, ReportRecord, Site, User, WorkflowAttachment, WorkflowRecord
from app.services import report_service, workflow_service
from app.services.file_service import abs_path, save_upload

router = APIRouter(prefix=get_settings().api_v1_prefix, tags=["workflow"])


def _require_site(db: Session, user: User, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if not site:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, site)
    return site


@router.post("/sites/{site_id}/workflow/init")
def init_workflow(site_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    try:
        workflow_service.init_stages(db, site_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"site_id": site_id, "stages": workflow_service.get_stages(db, site_id)}


@router.get("/sites/{site_id}/workflow")
def get_workflow(site_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    return {"site_id": site_id, "stages": workflow_service.get_stages(db, site_id)}


@router.post("/sites/{site_id}/workflow/{stage}")
def update_workflow(site_id: int, stage: str, body: dict = Body(default={}),
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    try:
        stages = workflow_service.update_stage(db, site_id, stage, **body)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, str(e))
    return {"site_id": site_id, "stages": stages}


@router.post("/sites/{site_id}/workflow/{stage}/attachment")
async def upload_attachment(site_id: int, stage: str, file: UploadFile = File(...),
                           file_role: str = Form(None),
                           user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    try:
        fo = save_upload(db, file.file, file.filename, file.content_type,
                         uploaded_by=user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    try:
        stages = workflow_service.attach_file(db, site_id, stage, fo.id,
                                              file_role=file_role, operator_id=user.id)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(404, str(e))
    return {"site_id": site_id, "file_object_id": fo.id, "stages": stages}


@router.get("/sites/{site_id}/workflow/{stage}/attachments/{attachment_id}/download")
def download_attachment(site_id: int, stage: str, attachment_id: int,
                        user: User = Depends(require_permission("file:download")),
                        db: Session = Depends(get_db)):
    """下载五阶段追溯的某阶段附件。

    权限: 校验 site 归属 + 该附件确实属于该 site+stage(防越权)。
    """
    _require_site(db, user, site_id)
    att = db.get(WorkflowAttachment, attachment_id)
    if not att:
        raise HTTPException(404, "附件不存在")
    # 反向校验: attachment → workflow_record → site_id + stage 必须匹配
    wr = db.get(WorkflowRecord, att.workflow_record_id)
    if not wr or wr.site_id != site_id or wr.stage != stage:
        raise HTTPException(404, "附件不属于该场地的该阶段")
    fo = db.get(FileObject, att.file_object_id)
    if not fo:
        raise HTTPException(404, "附件文件对象丢失")
    path = abs_path(fo.storage_key)
    if not os.path.exists(path):
        raise HTTPException(404, "附件文件丢失")
    return FileResponse(path, filename=fo.original_name,
                        media_type=fo.content_type or "application/octet-stream")


@router.post("/sites/{site_id}/report")
def generate_report(site_id: int,
                    format: str = Query("pdf", pattern="^(pdf|docx|html)$"),
                    user: User = Depends(require_permission("report:generate")),
                    db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    try:
        return report_service.generate(db, site_id, generated_by=user.id,
                                       report_format=format)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/sites/{site_id}/reports")
def list_reports(site_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    rows = (db.query(ReportRecord).filter_by(site_id=site_id)
            .order_by(ReportRecord.id.desc()).all())
    return {"site_id": site_id, "items": [{
        "report_id": r.id, "version": r.version, "template_version": r.template_version,
        "data_snapshot": r.data_snapshot, "generated_at": str(r.generated_at),
        "file_object_id": r.file_object_id} for r in rows]}


@router.get("/reports/{report_id}/download")
def download_report(report_id: int, user: User = Depends(require_permission("file:download")),
                    db: Session = Depends(get_db)):
    rec = db.get(ReportRecord, report_id)
    if not rec or not rec.file_object_id:
        raise HTTPException(404, "报告不存在")
    _require_site(db, user, rec.site_id)
    fo = db.get(FileObject, rec.file_object_id)
    path = abs_path(fo.storage_key)
    if not os.path.exists(path):
        raise HTTPException(404, "报告文件丢失")
    return FileResponse(path, filename=fo.original_name,
                        media_type=fo.content_type or "application/octet-stream")
