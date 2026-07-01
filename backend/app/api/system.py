"""系统管理 API: 改密码、操作日志、用户/角色查询、用户 CRUD、技术库 CRUD、联系方式。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, require_permission, user_role_codes
from app.core.security import hash_password, validate_password_strength, verify_password
from app.db.session import get_db
from app.models import AuditLog, Organization, Role, SystemConfig, TechnologyLibrary, User, UserRole
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
    ok, msg = validate_password_strength(body.new_password)
    if not ok:
        raise HTTPException(400, msg)
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(400, "新密码不能与旧密码相同")
    user.password_hash = hash_password(body.new_password)
    log(db, action="change_password", user_id=user.id, result="success")
    db.commit()
    return {"ok": True, "message": "密码已更新"}


@router.get("/health")
def system_health(db: Session = Depends(get_db)):
    """真实系统健康检查: DB 连接(SELECT 1 ping) + 模型产物 + AI 配置。

    替代前端 SystemHealth 此前硬编码的 ok:true(CLAUDE.md 禁伪造)。
    """
    import os
    from app.core.config import resource_root
    checks: dict = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = {"ok": True, "detail": "SQL 连接正常"}
    except Exception as e:
        checks["database"] = {"ok": False, "detail": f"连接失败: {str(e)[:80]}"}
    try:
        arts = os.path.join(resource_root(), "ml", "artifacts")
        n = len([f for f in os.listdir(arts) if f.endswith(".joblib")]) if os.path.isdir(arts) else 0
        checks["model"] = {"ok": n > 0, "detail": f"{n} 个 RF 模型产物"}
    except Exception as e:
        checks["model"] = {"ok": False, "detail": str(e)[:80]}
    s = get_settings()
    checks["ai"] = {"ok": bool(s.ai_api_key),
                    "detail": (f"{s.ai_model} 已启用" if s.ai_api_key else "未配置 AI_API_KEY")}
    return {"all_ok": all(c["ok"] for c in checks.values()), "checks": checks}


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


# ---------------- User CRUD ----------------
class CreateUser(BaseModel):
    username: str
    password: str
    display_name: str
    organization_id: int | None = None
    role_codes: list[str] = []

    @field_validator("username")
    @classmethod
    def username_min3(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("用户名至少 3 个字符")
        return v

    @field_validator("password")
    @classmethod
    def password_min6(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少 6 位")
        return v


class UpdateUser(BaseModel):
    display_name: str | None = None
    organization_id: int | None = None
    password: str | None = None
    status: str | None = None
    role_codes: list[str] | None = None

    @field_validator("password")
    @classmethod
    def password_min6(cls, v: str | None) -> str | None:
        if v is not None and len(v) < 6:
            raise ValueError("密码至少 6 位")
        return v


@router.post("/users")
def create_user(body: CreateUser, _actor: User = Depends(require_permission("user:manage")),
                db: Session = Depends(get_db)):
    """创建用户: 哈希密码, 分配组织与角色, 写审计日志。"""
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(409, f"用户名 {body.username} 已存在")
    if body.organization_id:
        org = db.query(Organization).get(body.organization_id)
        if not org:
            raise HTTPException(400, f"组织不存在: {body.organization_id}")
    # 校验角色存在
    role_objs = []
    if body.role_codes:
        role_objs = db.query(Role).filter(Role.code.in_(body.role_codes)).all()
        found = {r.code for r in role_objs}
        missing = set(body.role_codes) - found
        if missing:
            raise HTTPException(400, f"角色不存在: {', '.join(sorted(missing))}")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        organization_id=body.organization_id,
    )
    db.add(user)
    db.flush()  # 获取 user.id
    for role in role_objs:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    log(db, action="create_user", user_id=_actor.id,
        resource_type="user", resource_id=user.id,
        detail={"username": body.username, "display_name": body.display_name},
        commit=False)
    db.commit()
    return {
        "ok": True,
        "user": {"id": user.id, "username": user.username,
                 "display_name": user.display_name,
                 "roles": sorted(r.code for r in role_objs),
                 "organization_id": user.organization_id},
    }


@router.put("/users/{user_id}")
def update_user(user_id: int, body: UpdateUser,
                _actor: User = Depends(require_permission("user:manage")),
                db: Session = Depends(get_db)):
    """更新用户字段与角色; 若提供 password 则哈希后更新。"""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    detail: dict = {}

    if body.display_name is not None:
        detail["display_name"] = body.display_name
        user.display_name = body.display_name
    if body.organization_id is not None:
        detail["organization_id"] = body.organization_id
        user.organization_id = body.organization_id
    if body.password is not None:
        user.password_hash = hash_password(body.password)
        detail["password_changed"] = True
    if body.status is not None:
        if body.status not in ("active", "inactive"):
            raise HTTPException(400, "status 仅允许 active/inactive")
        detail["status"] = body.status
        user.status = body.status
    if body.role_codes is not None:
        detail["role_codes"] = list(body.role_codes)
        # 移除旧角色, 添加新角色
        db.query(UserRole).filter(UserRole.user_id == user.id).delete()
        if body.role_codes:
            role_objs = db.query(Role).filter(Role.code.in_(body.role_codes)).all()
            found = {r.code for r in role_objs}
            missing = set(body.role_codes) - found
            if missing:
                raise HTTPException(400, f"角色不存在: {', '.join(sorted(missing))}")
            for role in role_objs:
                db.add(UserRole(user_id=user.id, role_id=role.id))

    log(db, action="update_user", user_id=_actor.id,
        resource_type="user", resource_id=user.id,
        detail=detail, commit=False)
    db.commit()
    roles = sorted(user_role_codes(db, user))
    return {"ok": True, "user": {"id": user.id, "username": user.username,
                                  "display_name": user.display_name,
                                  "organization_id": user.organization_id,
                                  "status": user.status, "roles": roles}}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, _actor: User = Depends(require_permission("user:manage")),
                db: Session = Depends(get_db)):
    """软删除用户: 将 status 设为 inactive, 不在前端展示但保留审计记录。"""
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.status == "inactive":
        raise HTTPException(409, "用户已处于禁用状态")
    user.status = "inactive"
    log(db, action="soft_delete_user", user_id=_actor.id,
        resource_type="user", resource_id=user.id,
        detail={"username": user.username}, commit=False)
    db.commit()
    return {"ok": True, "message": f"用户 {user.username} 已禁用"}


# ---------------- Technology CRUD ----------------
class CreateTechnology(BaseModel):
    tech_name: str
    applicable_pollutants: dict | None = None
    applicable_soil: str | None = None
    applicable_land_type: dict | None = None
    applicable_stage: str | None = None
    advantages: str | None = None
    limitations: str | None = None
    cost_level: str | None = None
    duration_level: str | None = None
    secondary_risk: str | None = None
    forbidden_conditions: str | None = None
    source: str | None = None

    @field_validator("tech_name")
    @classmethod
    def tech_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("技术名称不能为空")
        return v


class UpdateTechnology(BaseModel):
    tech_name: str | None = None
    applicable_pollutants: dict | None = None
    applicable_soil: str | None = None
    applicable_land_type: dict | None = None
    applicable_stage: str | None = None
    advantages: str | None = None
    limitations: str | None = None
    cost_level: str | None = None
    duration_level: str | None = None
    secondary_risk: str | None = None
    forbidden_conditions: str | None = None
    source: str | None = None


@router.get("/technologies")
def list_technologies(q: str | None = Query(default=None, description="按技术名称模糊搜索"),
                      user: User = Depends(require_permission("tech:manage")),
                      db: Session = Depends(get_db)):
    """列出技术库条目, 支持 ?q= 模糊搜索技术名称。"""
    query = db.query(TechnologyLibrary)
    if q:
        query = query.filter(TechnologyLibrary.tech_name.ilike(f"%{q}%"))
    items = []
    for t in query.order_by(TechnologyLibrary.tech_name).all():
        items.append({
            "id": t.id, "tech_name": t.tech_name,
            "applicable_pollutants": t.applicable_pollutants,
            "applicable_soil": t.applicable_soil,
            "applicable_land_type": t.applicable_land_type,
            "applicable_stage": t.applicable_stage,
            "advantages": t.advantages, "limitations": t.limitations,
            "cost_level": t.cost_level, "duration_level": t.duration_level,
            "secondary_risk": t.secondary_risk,
            "forbidden_conditions": t.forbidden_conditions,
            "source": t.source,
        })
    return {"items": items, "total": len(items)}


@router.post("/technologies")
def create_technology(body: CreateTechnology,
                      _actor: User = Depends(require_permission("tech:manage")),
                      db: Session = Depends(get_db)):
    """新增技术库条目。"""
    tech = TechnologyLibrary(
        tech_name=body.tech_name,
        applicable_pollutants=body.applicable_pollutants,
        applicable_soil=body.applicable_soil,
        applicable_land_type=body.applicable_land_type,
        applicable_stage=body.applicable_stage,
        advantages=body.advantages,
        limitations=body.limitations,
        cost_level=body.cost_level,
        duration_level=body.duration_level,
        secondary_risk=body.secondary_risk,
        forbidden_conditions=body.forbidden_conditions,
        source=body.source,
    )
    db.add(tech)
    db.flush()
    log(db, action="create_technology", user_id=_actor.id,
        resource_type="technology_library", resource_id=tech.id,
        detail={"tech_name": body.tech_name}, commit=False)
    db.commit()
    return {"ok": True, "technology": _tech_dict(tech)}


@router.put("/technologies/{tech_id}")
def update_technology(tech_id: int, body: UpdateTechnology,
                      _actor: User = Depends(require_permission("tech:manage")),
                      db: Session = Depends(get_db)):
    """更新技术库条目。"""
    tech = db.query(TechnologyLibrary).get(tech_id)
    if not tech:
        raise HTTPException(404, "技术条目不存在")
    changed = {}
    for field in ("tech_name", "applicable_pollutants", "applicable_soil",
                  "applicable_land_type", "applicable_stage", "advantages",
                  "limitations", "cost_level", "duration_level",
                  "secondary_risk", "forbidden_conditions", "source"):
        val = getattr(body, field)
        if val is not None:
            setattr(tech, field, val)
            changed[field] = val
    log(db, action="update_technology", user_id=_actor.id,
        resource_type="technology_library", resource_id=tech.id,
        detail=changed, commit=False)
    db.commit()
    return {"ok": True, "technology": _tech_dict(tech)}


@router.delete("/technologies/{tech_id}")
def delete_technology(tech_id: int, _actor: User = Depends(require_permission("tech:manage")),
                      db: Session = Depends(get_db)):
    """删除技术库条目(硬删除)。"""
    tech = db.query(TechnologyLibrary).get(tech_id)
    if not tech:
        raise HTTPException(404, "技术条目不存在")
    db.delete(tech)
    log(db, action="delete_technology", user_id=_actor.id,
        resource_type="technology_library", resource_id=tech_id,
        detail={"tech_name": tech.tech_name}, commit=False)
    db.commit()
    return {"ok": True, "message": f"技术 {tech.tech_name} 已删除"}


def _tech_dict(t: TechnologyLibrary) -> dict:
    return {
        "id": t.id, "tech_name": t.tech_name,
        "applicable_pollutants": t.applicable_pollutants,
        "applicable_soil": t.applicable_soil,
        "applicable_land_type": t.applicable_land_type,
        "applicable_stage": t.applicable_stage,
        "advantages": t.advantages, "limitations": t.limitations,
        "cost_level": t.cost_level, "duration_level": t.duration_level,
        "secondary_risk": t.secondary_risk,
        "forbidden_conditions": t.forbidden_conditions,
        "source": t.source,
    }


@router.get("/config")
def system_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """系统配置概览(只读): 角色/权限矩阵、参数版本等。"""
    from app.core.ai_config import effective_ai
    s = get_settings()
    cfg = effective_ai()
    roles = [{"code": r.code, "name": r.name,
              "permissions": sorted(p.code for p in r.permissions)}
             for r in db.query(Role).all()]
    return {
        "app_name": s.app_name,
        "ai_configured": cfg["configured"],
        "ai_model": cfg["model"] if cfg["configured"] else None,
        "roles": roles,
        "param_version": "evaluation_params_v0.1",
        "knowledge_base_version": "V1.0",
    }


# ---------------- AI 模型配置 (管理员可改, key 仅存本机) ----------------
class AiConfigBody(BaseModel):
    base_url: str
    model: str
    provider: str = "custom"
    api_key: str | None = None  # 留空表示沿用已存 key, 仅改端点/模型


@router.get("/ai-config")
def get_ai_config(user: User = Depends(require_permission("param:config"))):
    """读取当前 AI 配置(key 脱敏)+ 可选服务商预设 + 最近一次连通性结果。"""
    from app.core.ai_config import (PROVIDER_PRESETS, connectivity_status,
                                    effective_ai, load_override, mask_key)
    cfg = effective_ai()
    ov = load_override()
    conn = connectivity_status()
    return {
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "provider": cfg["provider"],
        "configured": cfg["configured"],
        "source": cfg["source"],          # override / env / default
        "api_key_masked": mask_key(cfg["api_key"]),
        "has_key": bool(cfg["api_key"]),
        "is_override": bool(ov),
        "presets": PROVIDER_PRESETS,
        # 连通性(裴总 P0-2: 配置≠连通; ok=None 表示从未测试过)
        "connectivity_ok": conn["ok"],
        "connectivity_stale": conn["stale"],
        "connectivity_error": conn["error"],
        "last_checked": conn["last_checked"],
    }


@router.put("/ai-config")
def put_ai_config(body: AiConfigBody,
                  _actor: User = Depends(require_permission("param:config")),
                  db: Session = Depends(get_db)):
    """保存 AI 配置到本机覆盖文件(不入库、不进 Git)。审计日志不记录 key。"""
    from app.core.ai_config import effective_ai, save_override
    if not body.base_url.strip():
        raise HTTPException(400, "base_url 不能为空")
    save_override(body.base_url, body.api_key, body.model, body.provider)
    log(db, action="update_ai_config", user_id=_actor.id, resource_type="ai_config",
        detail={"provider": body.provider, "model": body.model,
                "base_url": body.base_url, "key_changed": bool(body.api_key)})
    # 保存后立即测一次连通性并落盘, 让 /ai/status 马上反映新配置是否真的可用(裴总 P0-2: 不假装成功)
    from app.core.ai_config import test_connectivity
    conn_ok, conn_err = test_connectivity()
    cfg = effective_ai()
    from app.core.ai_config import mask_key
    return {"ok": True, "configured": cfg["configured"], "model": cfg["model"],
            "base_url": cfg["base_url"], "api_key_masked": mask_key(cfg["api_key"]),
            "connectivity_ok": conn_ok, "connectivity_error": conn_err}


@router.post("/ai-config/test")
def test_ai_config(_actor: User = Depends(require_permission("param:config"))):
    """对当前生效 AI 配置做一次最小连通性测试(不写库); 结果落盘供 /ai/status 读取。"""
    import json
    import urllib.error
    import urllib.request
    from app.core.ai_config import effective_ai, save_connectivity
    cfg = effective_ai()
    if not cfg["base_url"] or not cfg["api_key"]:
        save_connectivity(False, "尚未配置 base_url 或 api_key")
        return {"ok": False, "message": "尚未配置 base_url 或 api_key。"}
    payload = json.dumps({"model": cfg["model"],
                          "messages": [{"role": "user", "content": "你好"}],
                          "max_tokens": 8, "temperature": 0}).encode("utf-8")
    req = urllib.request.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cfg['api_key']}"})
    try:
        with urllib.request.urlopen(req, timeout=get_settings().ai_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        save_connectivity(True, None)
        return {"ok": True, "model": cfg["model"],
                "message": f"连通正常, 模型已响应: {reply[:40] or '(空)'}"}
    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code}: {e.reason}"
        save_connectivity(False, msg)
        return {"ok": False, "message": f"{msg}。请检查 key/模型名/端点。"}
    except Exception as e:  # noqa: BLE001
        msg = f"连接失败: {e}"
        save_connectivity(False, msg)
        return {"ok": False, "message": f"{msg}。请检查 base_url 与网络。"}


# ---------------- 系统联系方式 CRUD ----------------

class ContactInfoBody(BaseModel):
    phone: str | None = None
    email: str | None = None


@router.get("/contact-info")
def get_contact_info(db: Session = Depends(get_db)):
    """获取系统管理员联系方式（公开，供注册页使用）。"""
    phone_cfg = db.query(SystemConfig).filter_by(config_key="admin_contact_phone").first()
    email_cfg = db.query(SystemConfig).filter_by(config_key="admin_contact_email").first()
    name_cfg = db.query(SystemConfig).filter_by(config_key="admin_display_name").first()
    return {
        "phone": phone_cfg.config_value if phone_cfg else "",
        "email": email_cfg.config_value if email_cfg else "",
        "display_name": name_cfg.config_value if name_cfg else "",
        "updated_at": str(phone_cfg.updated_at) if phone_cfg and phone_cfg.updated_at else None,
    }


@router.put("/contact-info")
def update_contact_info(body: ContactInfoBody,
                        actor: User = Depends(require_permission("param:config")),
                        db: Session = Depends(get_db)):
    """更新系统管理员联系方式（仅管理员）。修改后注册页即时生效。"""
    changes = {}
    if body.phone is not None:
        _upsert_config(db, "admin_contact_phone", body.phone.strip(),
                       "管理员联系电话", actor.username)
        changes["phone"] = body.phone
    if body.email is not None:
        _upsert_config(db, "admin_contact_email", body.email.strip(),
                       "管理员联系邮箱", actor.username)
        changes["email"] = body.email
    log(db, action="update_contact_info", user_id=actor.id,
        resource_type="system_config", detail=changes, commit=False)
    db.commit()
    return {"ok": True, "message": "联系方式已更新", "changes": changes}


def _upsert_config(db: Session, key: str, value: str, desc: str, updated_by: str):
    cfg = db.query(SystemConfig).filter_by(config_key=key).first()
    if cfg:
        cfg.config_value = value
        cfg.updated_by = updated_by
    else:
        db.add(SystemConfig(config_key=key, config_value=value,
                           description=desc, updated_by=updated_by))


# ---------------- 审计日志 / 技术库 CSV 导出 ----------------

@router.get("/audit-logs/export")
def export_audit_logs(action: str | None = None,
                      date_from: str | None = None,
                      date_to: str | None = None,
                      user: User = Depends(require_permission("audit:view")),
                      db: Session = Depends(get_db)):
    """导出审计日志为 CSV。支持按操作类型和日期范围筛选。"""
    import csv as _csv
    import io
    from datetime import datetime as _dt

    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if date_from:
        q = q.filter(AuditLog.created_at >= _dt.fromisoformat(date_from))
    if date_to:
        q = q.filter(AuditLog.created_at <= _dt.fromisoformat(date_to))
    rows = q.order_by(AuditLog.id.desc()).all()
    user_map = {u.id: u.display_name for u in db.query(User).all()}
    buf = io.StringIO()
    buf.write("﻿")  # BOM
    w = _csv.writer(buf)
    w.writerow(["ID", "时间", "操作人", "操作", "对象", "结果", "IP", "详情"])
    for a in rows:
        w.writerow([a.id, str(a.created_at), user_map.get(a.user_id, "—"),
                    a.action, f"{a.resource_type or ''}#{a.resource_id or ''}",
                    a.result, a.ip or "", str(a.detail or "")])
    log(db, action="export_audit_logs", user_id=user.id,
        resource_type="audit_logs", detail={"n_rows": len(rows)})
    return _csv_response(buf, "audit_logs")


@router.get("/technologies/export")
def export_technologies(user: User = Depends(require_permission("tech:manage")),
                        db: Session = Depends(get_db)):
    """导出技术库为 CSV。"""
    import csv as _csv
    import io
    import json as _json

    rows = db.query(TechnologyLibrary).order_by(TechnologyLibrary.tech_name).all()
    buf = io.StringIO()
    buf.write("﻿")
    w = _csv.writer(buf)
    w.writerow(["技术名称", "适用污染物", "适用土壤", "适用用地类型", "适用阶段",
                "优点", "局限", "成本等级", "工期等级", "二次风险", "禁用条件", "来源"])
    for t in rows:
        w.writerow([
            t.tech_name,
            _json.dumps(t.applicable_pollutants, ensure_ascii=False) if t.applicable_pollutants else "",
            t.applicable_soil or "",
            _json.dumps(t.applicable_land_type, ensure_ascii=False) if t.applicable_land_type else "",
            t.applicable_stage or "", t.advantages or "", t.limitations or "",
            t.cost_level or "", t.duration_level or "",
            t.secondary_risk or "", t.forbidden_conditions or "", t.source or "",
        ])
    log(db, action="export_technologies", user_id=user.id,
        resource_type="technology_library", detail={"n_rows": len(rows)})
    return _csv_response(buf, "technologies")


def _csv_response(buf, prefix: str):
    from fastapi import Response
    return Response(content=buf.getvalue().encode("utf-8-sig"),
                    media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             f'attachment; filename="{prefix}_{__import__("datetime").datetime.now().strftime("%Y%m%d")}.csv"'})
