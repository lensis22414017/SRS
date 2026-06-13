"""种子数据: 角色、权限、4 类演示账号、技术库。

演示账号密码统一为环境变量 DEMO_PASSWORD (默认 'Demo@2026'), 哈希存储。
可重复运行 (按唯一键幂等)。需在安装 backend 依赖的环境中执行。
"""
from __future__ import annotations

import csv
import json
import os

from app.core.security import hash_password
from app.db.init_db import create_all
from app.db.session import SessionLocal
from app.models import (
    Organization, Permission, Role, RolePermission, TechnologyLibrary, User, UserRole,
)

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "Demo@2026")

ROLES = [
    ("admin", "系统管理员", "全功能访问"),
    ("enterprise", "企业用户", "本企业数据录入/方案/流程上传"),
    ("agency", "第三方机构", "授权项目检测/评估上传"),
    ("regulator", "监管人员", "监管范围内查看与追溯"),
]

PERMISSIONS = [
    ("data:input", "数据录入", "数据"), ("data:query", "数据查询", "数据"),
    ("data:export", "数据导出", "数据"), ("data:archive", "数据归档", "数据"),
    ("report:generate", "报告生成", "报告"), ("map:view", "地图查看", "数据"),
    ("workflow:view", "全流程查看", "追溯"), ("file:download", "文档下载", "文件"),
    ("user:manage", "用户管理", "系统"), ("role:manage", "角色管理", "系统"),
    ("audit:view", "日志审计", "系统"), ("param:config", "参数设置", "系统"),
    ("model:manage", "模型管理", "算法"), ("tech:manage", "技术库管理", "决策"),
]

ROLE_PERMS = {
    "admin": [p[0] for p in PERMISSIONS],
    "enterprise": ["data:input", "data:query", "data:export", "report:generate",
                   "map:view", "workflow:view", "file:download"],
    "agency": ["data:input", "data:query", "workflow:view", "file:download"],
    "regulator": ["data:query", "map:view", "workflow:view", "file:download",
                  "report:generate", "audit:view"],
}

ORGS = [
    ("系统管理方", "admin"),
    ("示范企业A(个旧场地)", "enterprise"),
    ("第三方检测机构B", "agency"),
    ("属地监管单位C", "regulator"),
]

# username, display, role_code, org_name
USERS = [
    ("admin", "系统管理员", "admin", "系统管理方"),
    ("enterprise", "企业用户(示范企业A)", "enterprise", "示范企业A(个旧场地)"),
    ("agency", "第三方机构B", "agency", "第三方检测机构B"),
    ("regulator", "监管人员C", "regulator", "属地监管单位C"),
]


def seed():
    create_all()
    db = SessionLocal()
    try:
        # 组织
        org_map = {}
        for name, otype in ORGS:
            o = db.query(Organization).filter_by(name=name).first()
            if not o:
                o = Organization(name=name, org_type=otype)
                db.add(o); db.flush()
            org_map[name] = o.id
        # 权限
        perm_map = {}
        for code, name, cat in PERMISSIONS:
            p = db.query(Permission).filter_by(code=code).first()
            if not p:
                p = Permission(code=code, name=name, category=cat)
                db.add(p); db.flush()
            perm_map[code] = p.id
        # 角色 + 角色权限
        role_map = {}
        for code, name, desc in ROLES:
            r = db.query(Role).filter_by(code=code).first()
            if not r:
                r = Role(code=code, name=name, description=desc)
                db.add(r); db.flush()
            role_map[code] = r.id
            for pc in ROLE_PERMS[code]:
                if not db.query(RolePermission).filter_by(role_id=r.id, permission_id=perm_map[pc]).first():
                    db.add(RolePermission(role_id=r.id, permission_id=perm_map[pc]))
        # 用户 + 角色绑定
        for uname, disp, rcode, oname in USERS:
            u = db.query(User).filter_by(username=uname).first()
            if not u:
                u = User(username=uname, display_name=disp,
                         password_hash=hash_password(DEMO_PASSWORD),
                         organization_id=org_map[oname])
                db.add(u); db.flush()
            if not db.query(UserRole).filter_by(user_id=u.id, role_id=role_map[rcode]).first():
                db.add(UserRole(user_id=u.id, role_id=role_map[rcode]))
        # 技术库
        seed_tech(db)
        db.commit()
        print(f"种子完成: 组织 {len(ORGS)}, 角色 {len(ROLES)}, 权限 {len(PERMISSIONS)}, "
              f"用户 {len(USERS)} (密码={DEMO_PASSWORD})")
    finally:
        db.close()


def seed_tech(db):
    path = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                        "data", "knowledge_base", "technology_library_seed.csv")
    path = os.path.abspath(path)
    if not os.path.exists(path):
        print("跳过技术库(未找到 seed csv)"); return
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    n = 0
    for r in rows:
        if db.query(TechnologyLibrary).filter_by(tech_name=r["tech_name"]).first():
            continue
        db.add(TechnologyLibrary(
            tech_name=r["tech_name"],
            applicable_pollutants=[s.strip() for s in r["applicable_pollutants"].split(",")],
            applicable_soil=r["applicable_soil"],
            applicable_land_type=[s.strip() for s in r["applicable_land_type"].split(",")],
            applicable_stage=r["applicable_stage"],
            advantages=r["advantages"], limitations=r["limitations"],
            cost_level=r["cost_level"], duration_level=r["duration_level"],
            secondary_risk=r["secondary_risk"], forbidden_conditions=r["forbidden_conditions"],
            source=r["source"],
        ))
        n += 1
    print(f"技术库新增 {n} 条")


def seed_if_empty():
    """仅在组织表为空时执行 seed(); 已有数据则跳过 (桌面首次启动安全)。"""
    db = SessionLocal()
    try:
        if db.query(Organization).first() is not None:
            print("seed_if_empty: 数据库已有组织记录, 跳过种子数据。")
            return
    finally:
        db.close()
    seed()


if __name__ == "__main__":
    seed()
