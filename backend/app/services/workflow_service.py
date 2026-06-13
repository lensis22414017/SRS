"""五阶段全流程追溯服务: 调查评估→方案审批→施工监理→效果评估→后期管护。需 DB。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Site, WorkflowAttachment, WorkflowRecord
from app.services.audit_service import log

STAGES = [
    ("survey", "调查评估"),
    ("approval", "方案审批"),
    ("construction", "施工监理"),
    ("effect", "效果评估"),
    ("maintenance", "后期管护"),
]
STAGE_ORDER = [s[0] for s in STAGES]
STAGE_NAME = dict(STAGES)


def init_stages(db: Session, site_id: int) -> list[WorkflowRecord]:
    """为场地初始化五阶段(幂等)。"""
    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"场地不存在: {site_id}")
    existing = {w.stage for w in db.query(WorkflowRecord).filter_by(site_id=site_id).all()}
    created = []
    for stage in STAGE_ORDER:
        if stage in existing:
            continue
        w = WorkflowRecord(site_id=site_id, stage=stage, status="not_started",
                           version="v1", is_completed=False, is_returned=False,
                           advanced_to_next=False, payload={})
        db.add(w)
        created.append(w)
    db.commit()
    return created


def get_stages(db: Session, site_id: int) -> list[dict]:
    rows = db.query(WorkflowRecord).filter_by(site_id=site_id).all()
    order = {s: i for i, s in enumerate(STAGE_ORDER)}
    rows.sort(key=lambda w: order.get(w.stage, 99))
    out = []
    for w in rows:
        atts = db.query(WorkflowAttachment).filter_by(workflow_record_id=w.id).all()
        out.append({
            "id": w.id, "stage": w.stage, "stage_name": STAGE_NAME.get(w.stage),
            "status": w.status, "operator_id": w.operator_id,
            "operated_at": str(w.operated_at) if w.operated_at else None,
            "review_comment": w.review_comment, "version": w.version,
            "data_source": w.data_source, "is_completed": w.is_completed,
            "is_returned": w.is_returned, "advanced_to_next": w.advanced_to_next,
            "payload": w.payload, "n_attachments": len(atts),
            "attachments": [{"id": a.id, "file_object_id": a.file_object_id,
                             "file_role": a.file_role} for a in atts],
        })
    return out


def update_stage(db: Session, site_id: int, stage: str, *,
                 status: str | None = None, operator_id: int | None = None,
                 review_comment: str | None = None, data_source: str | None = None,
                 payload: dict | None = None, is_completed: bool | None = None,
                 is_returned: bool | None = None, advance: bool | None = None) -> dict:
    w = db.query(WorkflowRecord).filter_by(site_id=site_id, stage=stage).first()
    if w is None:
        raise ValueError(f"阶段不存在: {stage}(请先初始化五阶段)")
    if status is not None:
        w.status = status
    if operator_id is not None:
        w.operator_id = operator_id
    if review_comment is not None:
        w.review_comment = review_comment
    if data_source is not None:
        w.data_source = data_source
    if payload is not None:
        w.payload = {**(w.payload or {}), **payload}
    if is_completed is not None:
        w.is_completed = is_completed
        if is_completed:
            w.status = "completed"
    if is_returned is not None:
        w.is_returned = is_returned
        if is_returned:
            w.status = "returned"
    if advance is not None:
        w.advanced_to_next = advance
    w.operated_at = datetime.now(timezone.utc)
    log(db, action="workflow_update", user_id=operator_id,
        resource_type="workflow_records", resource_id=w.id,
        detail={"site_id": site_id, "stage": stage, "status": w.status}, commit=False)
    db.commit()
    return get_stages(db, site_id)


def attach_file(db: Session, site_id: int, stage: str, file_object_id: int,
                file_role: str | None = None, operator_id: int | None = None) -> dict:
    w = db.query(WorkflowRecord).filter_by(site_id=site_id, stage=stage).first()
    if w is None:
        raise ValueError(f"阶段不存在: {stage}")
    db.add(WorkflowAttachment(workflow_record_id=w.id, file_object_id=file_object_id,
                              file_role=file_role))
    log(db, action="workflow_attach", user_id=operator_id,
        resource_type="workflow_records", resource_id=w.id,
        detail={"site_id": site_id, "stage": stage, "file_object_id": file_object_id},
        commit=False)
    db.commit()
    return get_stages(db, site_id)
