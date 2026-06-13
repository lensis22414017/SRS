"""认证 API: 登录、当前用户信息。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, user_permissions, user_role_codes
from app.core.security import create_access_token, verify_password
from app.db.session import get_db
from app.models import Organization, User
from app.services.audit_service import log

router = APIRouter(prefix=get_settings().api_v1_prefix + "/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=body.username).first()
    ip = request.client.host if request.client else None
    if user is None or not verify_password(body.password, user.password_hash):
        log(db, action="login", user_id=user.id if user else None,
            result="fail", detail={"username": body.username}, ip=ip)
        raise HTTPException(401, "用户名或密码错误")
    if user.status != "active":
        log(db, action="login", user_id=user.id, result="denied", ip=ip)
        raise HTTPException(403, "用户已禁用")
    roles = sorted(user_role_codes(db, user))
    token = create_access_token(user.username, extra={"roles": roles})
    user.last_login_at = datetime.now(timezone.utc)
    log(db, action="login", user_id=user.id, result="success", ip=ip,
        detail={"roles": roles})
    return {"access_token": token, "token_type": "bearer",
            "user": {"username": user.username, "display_name": user.display_name,
                     "roles": roles, "organization_id": user.organization_id}}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    return {"username": user.username, "display_name": user.display_name,
            "organization": org.name if org else None,
            "organization_id": user.organization_id,
            "roles": sorted(user_role_codes(db, user)),
            "permissions": sorted(user_permissions(db, user))}
