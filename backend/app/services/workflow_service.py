"""五阶段全流程追溯服务: 调查评估→方案审批→施工监理→效果评估→后期管护。需 DB。"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import FileObject, Site, User, WorkflowAttachment, WorkflowRecord
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
        # 关联 FileObject 和 User 获取文件元数据和上传者信息
        att_data = []
        for a in atts:
            fo = db.query(FileObject).filter_by(id=a.file_object_id).first()
            uploader = db.query(User).filter_by(id=fo.uploaded_by).first() if fo and fo.uploaded_by else None
            att_data.append({
                "id": a.id, "file_object_id": a.file_object_id,
                "file_role": a.file_role,
                "original_name": fo.original_name if fo else "",
                "size_bytes": fo.size_bytes if fo else 0,
                "content_type": fo.content_type if fo else "",
                "uploaded_by_name": uploader.display_name if uploader else "",
                "uploaded_by_role": "",  # 前端通过 display_name 即可识别
                "uploaded_at": str(fo.created_at) if fo and fo.created_at else "",
            })
        out.append({
            "id": w.id, "stage": w.stage, "stage_name": STAGE_NAME.get(w.stage),
            "status": w.status, "operator_id": w.operator_id,
            "operated_at": str(w.operated_at) if w.operated_at else None,
            "review_comment": w.review_comment, "version": w.version,
            "data_source": w.data_source, "is_completed": w.is_completed,
            "is_returned": w.is_returned, "advanced_to_next": w.advanced_to_next,
            "payload": w.payload, "n_attachments": len(atts),
            "attachments": att_data,
        })
    return out


# ── 五阶段状态转移矩阵 ──
# 合法转移: {当前状态: [允许的目标状态]}
VALID_TRANSITIONS = {
    "not_started": ["in_progress"],
    "in_progress": ["completed", "returned"],
    "returned":    ["in_progress"],               # 退回后只能重新进入进行中
    "completed":   ["in_progress"],               # v0.2 P1-7: 已完成可重新打开(需要原因)
}

STAGE_ORDER = ["survey", "approval", "construction", "effect", "maintenance"]


def _validate_transition(current_status: str, new_status: str, stage: str,
                         is_returned: bool | None, review_comment: str | None = None) -> None:
    """校验状态转移是否合法。不合法抛出 ValueError。"""
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        raise ValueError(
            f"阶段「{stage}」不允许从「{current_status}」直接变更为「{new_status}」。"
            f"允许的变更为: {allowed}"
        )
    # 退回操作必须有退回原因
    if new_status == "returned" and not is_returned:
        raise ValueError("退回操作必须设置 is_returned=True")
    # v0.2 P1-7: 已完成重新打开必须填写原因
    if current_status == "completed" and new_status == "in_progress":
        if not review_comment or not review_comment.strip():
            raise ValueError("重新打开已完成阶段必须填写审核意见(review_comment)")


def _validate_advance_chain(db, site_id: int, stage: str, advance: bool) -> None:
    """进入下一阶段前，校验前一阶段已完成。"""
    if not advance:
        return
    idx = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else -1
    if idx <= 0:
        return  # 第一阶段无需前置
    prev_stage = STAGE_ORDER[idx - 1]
    prev = db.query(WorkflowRecord).filter_by(site_id=site_id, stage=prev_stage).first()
    if not prev or not prev.is_completed:
        raise ValueError(
            f"无法进入阶段「{stage}」：前置阶段「{prev_stage}」尚未完成。"
            f"请先完成「{prev_stage}」后再推进。"
        )


def update_stage(db: Session, site_id: int, stage: str, *,
                 status: str | None = None, operator_id: int | None = None,
                 review_comment: str | None = None, data_source: str | None = None,
                 payload: dict | None = None, is_completed: bool | None = None,
                 is_returned: bool | None = None, advance: bool | None = None) -> dict:
    w = db.query(WorkflowRecord).filter_by(site_id=site_id, stage=stage).first()
    if w is None:
        raise ValueError(f"阶段不存在: {stage}(请先初始化五阶段)")

    # 状态转移校验
    if status is not None and status != w.status:
        _validate_transition(w.status, status, stage, is_returned, review_comment)

    # 推进下一阶段前校验前置
    if advance:
        _validate_advance_chain(db, site_id, stage, advance)

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
            # v1.0 P0-1: 统一状态入口 — is_completed 隐式变更也必须经过转移校验, 禁止绕过
            if w.status != "completed":
                _validate_transition(w.status, "completed", stage, None, review_comment)
            w.status = "completed"
    if is_returned is not None:
        w.is_returned = is_returned
        if is_returned:
            # v1.0 P0-1: 同样校验 returned 转移
            if w.status != "returned":
                _validate_transition(w.status, "returned", stage, is_returned, review_comment)
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
