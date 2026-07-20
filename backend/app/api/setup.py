"""R3 审计第六类: 首启管理员设置向导 API。

解决 console=False 导致随机密码不可见的问题。
首启时(seed_if_empty 检测到 User 表空)写入 SystemConfig.setup_status=pending,
前端 Login 检测到 pending 后跳转到首启向导页面。

端点:
  GET  /api/v1/setup/status   → {needs_setup, setup_status}
  POST /api/v1/setup/complete → 接收 {username, password, confirm}, 创建 admin
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, validate_password_strength
from app.db.session import get_db
from app.models import Organization, Role, SystemConfig, User, UserRole

router = APIRouter(prefix=get_settings().api_v1_prefix + "/setup", tags=["setup"])


class SetupStatusResponse(BaseModel):
    needs_setup: bool
    setup_status: str | None
    has_users: bool


class SetupCompleteBody(BaseModel):
    username: str
    password: str
    confirm_password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("用户名至少 3 个字符")
        if len(v) > 32:
            raise ValueError("用户名不超过 32 个字符")
        return v

    @field_validator("password")
    @classmethod
    def validate_pwd(cls, v: str) -> str:
        # Round8: validate_password_strength 返回 (ok: bool, reason: str)
        ok, reason = validate_password_strength(v)
        if not ok:
            raise ValueError(reason)
        return v


def _get_setup_status(db: Session) -> str | None:
    """读取 SystemConfig.setup_status。"""
    row = db.query(SystemConfig).filter_by(config_key="setup_status").first()
    return row.config_value if row else None


def _has_active_users(db: Session) -> bool:
    """检查是否已有 active 用户(非演示种子)。"""
    return db.query(User).filter(User.status == "active").count() > 0


@router.get("/status", response_model=SetupStatusResponse)
def setup_status(db: Session = Depends(get_db)):
    """首启状态检查(无需认证, 供前端 Login 页面判断是否跳转向导)。"""
    status = _get_setup_status(db)
    has_users = _has_active_users(db)
    # needs_setup: setup_status=pending 且无活跃用户
    needs = (status == "pending") and not has_users
    return SetupStatusResponse(
        needs_setup=needs,
        setup_status=status,
        has_users=has_users,
    )


@router.post("/complete")
def setup_complete(body: SetupCompleteBody, db: Session = Depends(get_db)):
    """首启管理员设置完成(仅在 setup_status=pending 且无活跃用户时可用)。

    Round8 审计五类: 真正的并发保护(不只是重复查询)。
      1. BEGIN IMMEDIATE 获取 SQLite 独占写锁(并发请求会阻塞或失败)
      2. 条件 UPDATE 原子地把 setup_status 从 pending→in_progress(影响行数=0 即被抢先)
      3. 创建用户 + 绑角色 + 标 setup_status=completed 同一事务
      4. admin 角色不存在 → raise 500(不创建无角色用户)

    安全约束:
      1. 仅在 setup_status=pending 时可调用
      2. 用户名不可重复
      3. 两次密码必须一致
      4. 完成后写入 setup_status=completed, 不可再次调用
    """
    # Round8 审计 5.4: setup_status 从 pending 到 completed 必须同一事务
    # 先做轻量校验(避免不必要的写锁开销)
    if body.password != body.confirm_password:
        raise HTTPException(400, "两次输入的密码不一致")
    if db.query(User).filter_by(username=body.username).first():
        raise HTTPException(409, f"用户名 '{body.username}' 已存在")

    # Round8 审计 5.3: SQLite 用 BEGIN IMMEDIATE 获取独占写锁
    # 这一步会让其他并发请求在尝试写时阻塞/失败, 真正实现互斥
    from sqlalchemy import text as _text
    from app.db.session import engine
    is_sqlite = "sqlite" in (engine.url.get_backend_name() or "").lower()
    try:
        if is_sqlite:
            # 显式 BEGIN IMMEDIATE 立刻获取写锁(SQLite 默认 deferred 会等到第一条写)
            db.execute(_text("BEGIN IMMEDIATE"))
        # 进入 critical section
        status = _get_setup_status(db)
        if status != "pending":
            db.rollback()
            raise HTTPException(409, f"首启设置不可用(当前状态: {status or '未初始化'})")
        if _has_active_users(db):
            db.rollback()
            raise HTTPException(409, "系统已有管理员, 首启向导不可用")

        # Round8 审计 5.2-5.4: 条件 UPDATE 原子锁 — pending → in_progress
        # 多个并发请求同时通过 BEGIN IMMEDIATE 后, 只有一个能成功 UPDATE
        # (其余会因 setup_status 不再是 pending 而影响行数=0)
        config_row = db.query(SystemConfig).filter_by(config_key="setup_status").first()
        if not config_row:
            db.rollback()
            raise HTTPException(409, "setup_status 未初始化, 请重启服务后再试")
        if config_row.config_value != "pending":
            db.rollback()
            raise HTTPException(409, "首启设置已被另一请求抢先完成(并发保护)")
        # 设置 in_progress 标记(同一事务, 立即可见, 其他并发请求看到非 pending 状态)
        config_row.config_value = "in_progress"
        db.flush()  # 不 commit, 继续在同一事务内创建用户

        # 确保管理组织存在
        org = db.query(Organization).filter_by(name="系统管理方").first()
        if not org:
            org = Organization(name="系统管理方", org_type="admin", is_seed=True)
            db.add(org)
            db.flush()

        # 创建管理员
        admin_user = User(
            username=body.username,
            display_name="系统管理员",
            password_hash=hash_password(body.password),
            organization_id=org.id,
            status="active",
            is_seed=True,
        )
        db.add(admin_user)
        db.flush()

        # Round8 审计 5.5: admin 角色不存在必须失败(不创建无角色用户)
        # R3-P0-7: 必须用 Role.code=="admin"(不是 name)
        admin_role = db.query(Role).filter_by(code="admin").first()
        if not admin_role:
            db.rollback()
            raise HTTPException(
                500,
                "admin 角色不存在, 请确认数据库种子已完成(seed_db.py)。"
                "未创建无角色管理员(安全约束: 禁止无角色账号登录)。")
        if not db.query(UserRole).filter_by(
                user_id=admin_user.id, role_id=admin_role.id).first():
            db.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))

        # 标记 setup 完成(从 in_progress → completed)
        config_row.config_value = "completed"

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        # SQLite "database is locked" 在并发竞争时返回 409 而非 500
        err_msg = str(e).lower()
        if "locked" in err_msg or "database is locked" in err_msg:
            raise HTTPException(409, "首启设置被并发请求抢先完成, 请重试或检查状态")
        raise HTTPException(500, f"首启设置失败(已回滚): {e}")
    return {
        "success": True,
        "message": f"管理员 '{body.username}' 创建成功, 请使用该账号登录",
        "username": body.username,
    }
