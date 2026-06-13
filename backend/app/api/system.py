"""系统管理 API: 改密码、操作日志、用户/角色查询。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, require_permission, user_role_codes
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import AuditLog, Organization, Role, User, UserRole
from app.services.audit_service import log

router = APIRouter(prefix=get_settings().api_v1_prefix + "/system", tags=["system"])


class ChangePwd(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
def change_password(body: ChangePwd, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    if not verify_password(body.old_password, user.password_hash):
        log(db, action="change_password", user_id=user.id, result="fail")
        raise HTTPException(400, "原密码错误")
    if len(body.new_password) < 6:
        raise HTTPException(400, "新密码至少 6 位")
    user.password_hash = hash_password(body.new_password)
    log(db, action="change_password", user_id=user.id, result="success")
    db.commit()
    return {"ok": True, "message": "密码已更新"}


@router.get("/audit-logs")
def audit_logs(action: str | None = None, result: str | None = None,
               page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=200),
               user: User = Depends(require_permission("audit:view")),
               db: Session = Depends(get_db)):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if result:
        q = q.filter(AuditLog.result == result)
    total = q.count()
    rows = q.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size).all()
    user_map = {u.id: u.display_name for u in db.query(User).all()}
    items = [{
        "id": a.id, "time": str(a.created_at), "user": user_map.get(a.user_id, "—"),
        "action": a.action, "resource": f"{a.resource_type or ''}#{a.resource_id or ''}",
        "result": a.result, "ip": a.ip, "detail": a.detail,
    } for a in rows]
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/users")
def list_users(user: User = Depends(require_permission("user:manage")),
               db: Session = Depends(get_db)):
    orgs = {o.id: o.name for o in db.query(Organization).all()}
    out = []
    for u in db.query(User).all():
        roles = sorted(user_role_codes(db, u))
        out.append({"id": u.id, "username": u.username, "display_name": u.display_name,
                    "organization": orgs.get(u.organization_id), "roles": roles,
                    "status": u.status, "last_login_at": str(u.last_login_at) if u.last_login_at else None})
    return {"items": out}


@router.get("/config")
def system_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """系统配置概览(只读): 角色/权限矩阵、参数版本等。"""
    s = get_settings()
    roles = [{"code": r.code, "name": r.name,
              "permissions": sorted(p.code for p in r.permissions)}
             for r in db.query(Role).all()]
    return {
        "app_name": s.app_name,
        "ai_configured": bool(s.ai_base_url and s.ai_api_key),
        "ai_model": s.ai_model if s.ai_base_url else None,
        "roles": roles,
        "param_version": "evaluation_params_v0.1",
        "knowledge_base_version": "V1.0",
    }
