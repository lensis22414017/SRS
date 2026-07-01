"""认证 API: 登录、注册、审核、忘记密码、当前用户信息。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, require_permission, user_permissions, user_role_codes
from app.core.security import (
    create_access_token, generate_reset_token, hash_password,
    validate_password_strength, verify_password, verify_reset_token,
)
from app.db.session import get_db
from app.models import Organization, Role, SystemConfig, User, UserRole
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
    if user.status not in ("active",):
        reason = "待审核" if user.status == "pending" else "已禁用" if user.status == "inactive" else "已拒绝"
        log(db, action="login", user_id=user.id, result="denied", ip=ip)
        raise HTTPException(403, f"账户状态异常: {reason}")
    roles = sorted(user_role_codes(db, user))
    perms = sorted(user_permissions(db, user))
    token = create_access_token(user.username, extra={"roles": roles})
    user.last_login_at = datetime.now(timezone.utc)
    log(db, action="login", user_id=user.id, result="success", ip=ip,
        detail={"roles": roles})
    return {"access_token": token, "token_type": "bearer",
            "user": {"username": user.username, "display_name": user.display_name,
                     "roles": roles, "permissions": perms,
                     "organization_id": user.organization_id}}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    return {"username": user.username, "display_name": user.display_name,
            "organization": org.name if org else None,
            "organization_id": user.organization_id,
            "roles": sorted(user_role_codes(db, user)),
            "permissions": sorted(user_permissions(db, user))}


# ──────────────────────── 注册 ────────────────────────

class RegisterBody(BaseModel):
    username: str
    password: str
    display_name: str
    organization_name: str
    role_code: str   # enterprise / agency / regulator (不允许 admin)
    contact_email: str | None = None
    contact_phone: str | None = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 20:
            raise ValueError("用户名需 3-20 位")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名仅允许字母、数字、下划线、连字符")
        return v

    @field_validator("role_code")
    @classmethod
    def role_not_admin(cls, v: str) -> str:
        if v == "admin":
            raise ValueError("系统管理员不开放注册，请选择企业用户/第三方机构/监管人员")
        if v not in ("enterprise", "agency", "regulator"):
            raise ValueError("角色仅允许: enterprise / agency / regulator")
        return v


@router.post("/register")
def register(body: RegisterBody, request: Request, db: Session = Depends(get_db)):
    """注册新账户（管理员不开放注册）。状态=pending，等待管理员审核。"""
    # 校验用户名唯一
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(409, f"用户名 {body.username} 已存在")

    # 密码强度
    ok, msg = validate_password_strength(body.password)
    if not ok:
        raise HTTPException(400, msg)

    # 创建组织
    org = Organization(name=body.organization_name, org_type=body.role_code)
    db.add(org)
    db.flush()

    # 创建用户 (pending)
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        organization_id=org.id,
        email=body.contact_email,
        phone=body.contact_phone,
        status="pending",
    )
    db.add(user)
    db.flush()

    # 分配角色
    role = db.query(Role).filter_by(code=body.role_code).first()
    if not role:
        # 角色表尚未种子（极端情况），回滚
        db.rollback()
        raise HTTPException(500, "角色表未初始化，请联系管理员")
    db.add(UserRole(user_id=user.id, role_id=role.id))

    ip = request.client.host if request.client else None
    log(db, action="register", user_id=user.id, result="pending",
        detail={"username": body.username, "role": body.role_code,
                "organization": body.organization_name}, ip=ip, commit=False)
    db.commit()
    return {"message": "注册申请已提交，等待管理员审核", "user_id": user.id}


# ──────────────────────── 管理员审核 ────────────────────────

@router.get("/pending-approvals")
def pending_approvals(user: User = Depends(require_permission("user:manage")),
                      db: Session = Depends(get_db)):
    """列出待审核用户。"""
    rows = db.query(User).filter(User.status == "pending").order_by(User.id).all()
    return {"items": [{
        "user_id": u.id, "username": u.username, "display_name": u.display_name,
        "organization_name": db.get(Organization, u.organization_id).name if u.organization_id else None,
        "role_code": (sorted(user_role_codes(db, u)) or [None])[0],
        "contact_email": u.email, "contact_phone": u.phone,
        "created_at": str(u.created_at) if u.created_at else None,
    } for u in rows]}


class ApprovalAction(BaseModel):
    reason: str | None = None  # 拒绝时必填


@router.post("/approve/{user_id}")
def approve_user(user_id: int, body: ApprovalAction | None = None,
                 actor: User = Depends(require_permission("user:manage")),
                 db: Session = Depends(get_db)):
    """通过审核: pending → active。"""
    u = db.query(User).get(user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    if u.status != "pending":
        raise HTTPException(409, f"用户状态为 {u.status}，无需审核")
    u.status = "active"
    log(db, action="approve_user", user_id=actor.id,
        resource_type="user", resource_id=u.id,
        detail={"username": u.username}, commit=False)
    db.commit()
    return {"message": "账户已激活"}


@router.post("/reject/{user_id}")
def reject_user(user_id: int, body: ApprovalAction,
                actor: User = Depends(require_permission("user:manage")),
                db: Session = Depends(get_db)):
    """拒绝注册: pending → rejected。"""
    u = db.query(User).get(user_id)
    if not u:
        raise HTTPException(404, "用户不存在")
    if u.status != "pending":
        raise HTTPException(409, f"用户状态为 {u.status}，无法拒绝")
    u.status = "rejected"
    log(db, action="reject_user", user_id=actor.id,
        resource_type="user", resource_id=u.id,
        detail={"username": u.username, "reason": body.reason}, commit=False)
    db.commit()
    return {"message": "已拒绝"}


# ──────────────────────── 管理员联系方式 ────────────────────────

@router.get("/admin-contact")
def admin_contact(db: Session = Depends(get_db)):
    """获取系统管理员联系方式（注册页展示，无需登录）。"""
    phone_cfg = db.query(SystemConfig).filter_by(config_key="admin_contact_phone").first()
    email_cfg = db.query(SystemConfig).filter_by(config_key="admin_contact_email").first()
    return {
        "phone": phone_cfg.config_value if phone_cfg else "010-0000-0000",
        "email": email_cfg.config_value if email_cfg else "admin@srs-system.cn",
    }


# ──────────────────────── 忘记密码 / 重置密码 ────────────────────────

class ForgotPasswordBody(BaseModel):
    username: str


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordBody, request: Request,
                    db: Session = Depends(get_db)):
    """忘记密码: 生成重置令牌。MVP 阶段返回 token 由管理员交付。"""
    user = db.query(User).filter_by(username=body.username).first()
    ip = request.client.host if request.client else None
    if not user:
        # 不暴露用户是否存在
        log(db, action="forgot_password", result="fail",
            detail={"username": body.username, "reason": "not_found"}, ip=ip)
        return {"message": "若账户存在，重置令牌已生成", "reset_token": None}
    if user.status != "active":
        log(db, action="forgot_password", user_id=user.id, result="denied", ip=ip)
        return {"message": "账户状态异常，无法重置密码。请联系系统管理员。", "reset_token": None}
    token = generate_reset_token(user.id)
    log(db, action="forgot_password", user_id=user.id, result="success", ip=ip)
    return {"message": "若账户存在，重置令牌已生成。请联系系统管理员获取重置令牌。",
            "reset_token": token}


class ResetPasswordBody(BaseModel):
    token: str
    new_password: str


@router.post("/reset-password")
def reset_password(body: ResetPasswordBody, request: Request,
                   db: Session = Depends(get_db)):
    """重置密码: 验证 token → 更新密码。"""
    user_id = verify_reset_token(body.token)
    ip = request.client.host if request.client else None
    if user_id is None:
        log(db, action="reset_password", result="fail",
            detail={"reason": "invalid_token"}, ip=ip)
        raise HTTPException(400, "重置令牌无效或已过期（有效期为 15 分钟）")
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    ok, msg = validate_password_strength(body.new_password)
    if not ok:
        raise HTTPException(400, msg)
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(400, "新密码不能与旧密码相同")
    user.password_hash = hash_password(body.new_password)
    log(db, action="reset_password", user_id=user.id, result="success", ip=ip,
        commit=False)
    db.commit()
    return {"message": "密码已重置，请重新登录"}
