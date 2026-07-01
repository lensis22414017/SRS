"""认证与授权依赖: JWT 当前用户、权限校验、企业数据隔离。"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Permission, Role, RolePermission, Site, User, UserRole

ADMIN_ROLE = "admin"
ENTERPRISE_ROLE = "enterprise"


def get_current_user(authorization: str | None = Header(default=None),
                     db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "未提供登录令牌")
    token = authorization.split(" ", 1)[1].strip()
    s = get_settings()
    try:
        payload = jwt.decode(token, s.secret_key, algorithms=[s.algorithm])
    except JWTError:
        raise HTTPException(401, "令牌无效或已过期")
    username = payload.get("sub")
    user = db.query(User).filter_by(username=username).first()
    if user is None or user.status != "active":
        raise HTTPException(401, "用户不存在或已禁用")
    return user


def user_role_codes(db: Session, user: User) -> set[str]:
    rows = (db.query(Role.code).join(UserRole, UserRole.role_id == Role.id)
            .filter(UserRole.user_id == user.id).all())
    return {r[0] for r in rows}


def user_permissions(db: Session, user: User) -> set[str]:
    rows = (db.query(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .filter(UserRole.user_id == user.id).all())
    return {r[0] for r in rows}


def is_admin(db: Session, user: User) -> bool:
    return ADMIN_ROLE in user_role_codes(db, user)


def require_permission(code: str):
    """返回一个依赖: 校验当前用户拥有指定权限。"""
    def _dep(user: User = Depends(get_current_user),
             db: Session = Depends(get_db)) -> User:
        if code not in user_permissions(db, user):
            raise HTTPException(403, f"缺少权限: {code}")
        return user
    return _dep


def assert_site_access(db: Session, user: User, site: Site) -> None:
    """企业用户仅能访问本企业场地; 管理员/监管/第三方按现有范围(放行非企业角色)。"""
    roles = user_role_codes(db, user)
    if ADMIN_ROLE in roles:
        return
    if ENTERPRISE_ROLE in roles:
        if site.organization_id != user.organization_id:
            raise HTTPException(403, "无权访问其他企业的场地数据")


def scope_sites_query(db: Session, user: User, query):
    """企业用户的场地列表仅返回本企业。"""
    roles = user_role_codes(db, user)
    if ENTERPRISE_ROLE in roles and ADMIN_ROLE not in roles:
        return query.filter(Site.organization_id == user.organization_id)
    return query
