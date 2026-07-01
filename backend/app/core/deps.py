"""认证与授权依赖: JWT 当前用户、权限校验、企业数据隔离。"""
from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import (
    Permission, ProjectAuthorization, Role, RolePermission, Site, User, UserRole,
)
from datetime import date

ADMIN_ROLE = "admin"
ENTERPRISE_ROLE = "enterprise"
AGENCY_ROLE = "agency"
REGULATOR_ROLE = "regulator"


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


def _check_agency_access(db: Session, user: User, site: Site) -> bool:
    """检查第三方机构是否通过 ProjectAuthorization 获得对该场地的授权。
    返回 True 表示有有效授权(未撤销、未过期)。"""
    today = date.today()
    auth = (
        db.query(ProjectAuthorization)
        .filter_by(site_id=site.id, authorized_org_id=user.organization_id, is_revoked=False)
        .filter(
            (ProjectAuthorization.valid_until.is_(None)) |
            (ProjectAuthorization.valid_until >= today)
        )
        .first()
    )
    return auth is not None


def assert_site_access(db: Session, user: User, site: Site) -> None:
    """场地级访问控制:
    - 管理员: 全部放行
    - 企业用户: 仅本企业场地
    - 第三方机构: 仅已授权(ProjectAuthorization)且未撤销/未过期的场地
    - 监管人员: 可查看所有场地(只读)
    """
    roles = user_role_codes(db, user)
    if ADMIN_ROLE in roles:
        return
    if ENTERPRISE_ROLE in roles:
        if site.organization_id != user.organization_id:
            raise HTTPException(403, "无权访问其他企业的场地数据")
    elif AGENCY_ROLE in roles:
        if not _check_agency_access(db, user, site):
            raise HTTPException(403, "未获得该场地的项目授权, 请联系管理员申请授权")
    # 监管人员(regulator): 可查看所有场地数据(符合政府监管职能定位)


def scope_sites_query(db: Session, user: User, query):
    """场地列表行级过滤:
    - 企业用户: 仅本企业场地
    - 第三方机构: 仅已授权且未撤销/未过期的场地
    - 管理员/监管: 全部场地
    """
    roles = user_role_codes(db, user)
    is_admin = ADMIN_ROLE in roles
    if ENTERPRISE_ROLE in roles and not is_admin:
        return query.filter(Site.organization_id == user.organization_id)
    if AGENCY_ROLE in roles and not is_admin:
        today = date.today()
        auth_site_ids = (
            db.query(ProjectAuthorization.site_id)
            .filter_by(authorized_org_id=user.organization_id, is_revoked=False)
            .filter(
                (ProjectAuthorization.valid_until.is_(None)) |
                (ProjectAuthorization.valid_until >= today)
            )
            .all()
        )
        site_ids = [r[0] for r in auth_site_ids]
        if not site_ids:
            return query.filter(Site.id == -1)  # 无授权时返回空集
        return query.filter(Site.id.in_(site_ids))
    return query
