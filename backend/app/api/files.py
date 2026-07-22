"""Round10: 独立文件管理 API — 跨场地文件库、分类、预览、下载。"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models import FILE_CATEGORIES, FileObject, Organization, Site, User
from app.services.file_service import abs_path, save_upload

router = APIRouter(prefix=get_settings().api_v1_prefix, tags=["files"])

# Round10: 文件分类中文标签（与 models.FILE_CATEGORIES 一致）
CATEGORY_LABEL = FILE_CATEGORIES


@router.get("/files")
def list_files(
    site_id: int | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_permission("file:read")),
    db: Session = Depends(get_db),
):
    """列出所有文件，支持按场地、分类、文件名搜索过滤。"""
    q = db.query(FileObject)
    if site_id is not None:
        # 通过 workflow_attachments 关联的场地过滤
        from app.models import WorkflowAttachment, WorkflowRecord
        site_file_ids = (
            db.query(WorkflowAttachment.file_object_id)
            .join(WorkflowRecord, WorkflowAttachment.workflow_record_id == WorkflowRecord.id)
            .filter(WorkflowRecord.site_id == site_id)
            .distinct()
            .subquery()
        )
        q = q.filter(FileObject.id.in_(site_file_ids))
    if category:
        q = q.filter(FileObject.category == category)
    if search:
        q = q.filter(FileObject.original_name.ilike(f"%{search}%"))

    total = q.count()
    rows = (
        q.order_by(FileObject.created_at.desc().nullslast())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 预加载关联信息
    org_map: dict[int, str] = {}
    user_map: dict[int, str] = {}
    site_map: dict[int, str] = {}
    for r in rows:
        if r.organization_id and r.organization_id not in org_map:
            org = db.get(Organization, r.organization_id)
            org_map[r.organization_id] = org.name if org else ""
        if r.uploaded_by and r.uploaded_by not in user_map:
            u = db.get(User, r.uploaded_by)
            user_map[r.uploaded_by] = u.display_name if u else ""
        # 场地关联
        from app.models import WorkflowAttachment, WorkflowRecord
        wa = (
            db.query(WorkflowAttachment)
            .filter(WorkflowAttachment.file_object_id == r.id)
            .first()
        )
        if wa:
            wr = db.get(WorkflowRecord, wa.workflow_record_id)
            if wr:
                s = db.get(Site, wr.site_id)
                if s:
                    site_map[r.id] = s.name

    items = []
    for r in rows:
        items.append({
            "id": r.id,
            "storage_key": r.storage_key,
            "original_name": r.original_name,
            "content_type": r.content_type,
            "size_bytes": r.size_bytes,
            "sha256": r.sha256,
            "category": r.category,
            "category_label": CATEGORY_LABEL.get(r.category or "", r.category or "—"),
            "description": r.description,
            "organization_id": r.organization_id,
            "organization_name": org_map.get(r.organization_id or 0, ""),
            "uploaded_by": r.uploaded_by,
            "uploaded_by_name": user_map.get(r.uploaded_by or 0, ""),
            "site_name": site_map.get(r.id, "—"),
            "created_at": str(r.created_at) if r.created_at else "",
        })
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/files/categories")
def list_categories(user: User = Depends(get_current_user)):
    """返回文件分类枚举（供前端下拉框使用）。"""
    return {"categories": [{"value": k, "label": v} for k, v in CATEGORY_LABEL.items()]}


@router.get("/files/{file_id}/preview")
def preview_file(
    file_id: int,
    user: User = Depends(require_permission("file:read")),
    db: Session = Depends(get_db),
):
    """返回文件流用于浏览器内预览（Content-Disposition: inline）。"""
    fo = db.get(FileObject, file_id)
    if not fo:
        raise HTTPException(404, "文件不存在")
    path = abs_path(fo.storage_key)
    if not os.path.exists(path):
        raise HTTPException(404, "文件物理存储丢失")
    return FileResponse(
        path,
        filename=fo.original_name,
        media_type=fo.content_type or "application/octet-stream",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{fo.original_name}"},
    )


@router.get("/files/{file_id}/download")
def download_file(
    file_id: int,
    user: User = Depends(require_permission("file:download")),
    db: Session = Depends(get_db),
):
    """返回文件流用于下载（Content-Disposition: attachment）。"""
    fo = db.get(FileObject, file_id)
    if not fo:
        raise HTTPException(404, "文件不存在")
    path = abs_path(fo.storage_key)
    if not os.path.exists(path):
        raise HTTPException(404, "文件物理存储丢失")
    return FileResponse(
        path,
        filename=fo.original_name,
        media_type=fo.content_type or "application/octet-stream",
    )


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form("other"),
    description: str = Form(""),
    site_id: int | None = Form(None),
    user: User = Depends(require_permission("data:input")),
    db: Session = Depends(get_db),
):
    """上传文件到全局文件库（可选关联场地）。"""
    # 校验分类
    if category not in CATEGORY_LABEL:
        raise HTTPException(400, f"不支持的文件分类: {category}，可选值: {list(CATEGORY_LABEL.keys())}")

    try:
        fo = save_upload(
            db, file.file, file.filename, file.content_type,
            uploaded_by=user.id,
            organization_id=user.organization_id,
            category=category,
            description=description or None,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    # 如果指定了场地，自动挂载到对应工作流的第一阶段
    if site_id is not None:
        site = db.get(Site, site_id)
        if not site:
            raise HTTPException(404, "场地不存在")
        from app.models import WorkflowAttachment, WorkflowRecord
        wr = (
            db.query(WorkflowRecord)
            .filter_by(site_id=site_id, stage="survey")
            .first()
        )
        if wr:
            db.add(WorkflowAttachment(
                workflow_record_id=wr.id,
                file_object_id=fo.id,
                file_role=CATEGORY_LABEL.get(category, ""),
            ))
    db.commit()

    return {
        "id": fo.id,
        "original_name": fo.original_name,
        "category": fo.category,
        "category_label": CATEGORY_LABEL.get(fo.category or "", ""),
        "size_bytes": fo.size_bytes,
        "storage_key": fo.storage_key,
    }


@router.put("/files/{file_id}")
def update_file_meta(
    file_id: int,
    category: str | None = Form(None),
    description: str | None = Form(None),
    user: User = Depends(require_permission("data:input")),
    db: Session = Depends(get_db),
):
    """更新文件分类和描述。"""
    fo = db.get(FileObject, file_id)
    if not fo:
        raise HTTPException(404, "文件不存在")
    if category is not None:
        if category not in CATEGORY_LABEL:
            raise HTTPException(400, f"不支持的文件分类: {category}")
        fo.category = category
    if description is not None:
        fo.description = description or None
    db.commit()
    return {"id": fo.id, "category": fo.category, "description": fo.description}


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    user: User = Depends(require_permission("data:input")),
    db: Session = Depends(get_db),
):
    """删除文件（同时删除物理存储和关联的 workflow_attachment）。"""
    fo = db.get(FileObject, file_id)
    if not fo:
        raise HTTPException(404, "文件不存在")
    # 删除关联的工作流附件记录
    from app.models import WorkflowAttachment
    db.query(WorkflowAttachment).filter_by(file_object_id=file_id).delete()
    # 删除物理文件
    path = abs_path(fo.storage_key)
    file_deleted = False
    if os.path.exists(path):
        os.remove(path)
        file_deleted = True
    # 删除数据库记录
    db.delete(fo)
    db.commit()
    return {"ok": True, "file_id": file_id, "file_deleted": file_deleted}
