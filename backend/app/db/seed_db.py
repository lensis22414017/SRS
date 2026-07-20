"""种子数据: 参考 vs 演示分离 (GPT 审计第一节 + v1.0.2)。

参考数据(生产首启必须初始化, 幂等):
  - 角色 + 权限 + 角色权限
  - 系统配置
  - 技术库
  - 因子字典 (FactorDictionary, 从知识库 CSV)
  - 标准阈值 (StandardThreshold, GB15618 + GB36600)
  - 阈值规则 (ThresholdRule, 旧表, 兼容)

演示数据(仅 SRS_DEMO_SEED=1 时初始化, 默认关闭):
  - 4 个演示组织
  - 4 个演示用户

关键改动(v1.0.2):
  1. seed_if_empty() 只调 seed_reference(), 不再种演示数据
  2. 每个参考表单独判空(不靠 Organization), 幂等
  3. seed_reference() 纳入 FactorDictionary + StandardThreshold (修复首启阈值空缺)
"""
from __future__ import annotations

import csv
import os

from app.core.security import hash_password
from app.db.init_db import create_all
from app.db.session import SessionLocal
from app.models import (
    Organization, Permission, Role, RolePermission, SystemConfig, TechnologyLibrary, User, UserRole,
)

DEMO_PASSWORD = os.environ.get("SRS_DEMO_PASSWORD", "Demo@2026")

ROLES = [
    ("admin", "系统管理员", "全功能访问"),
    ("enterprise", "企业用户", "本企业数据录入/方案/流程上传"),
    ("agency", "第三方机构", "授权项目检测/评估上传"),
    ("regulator", "监管人员", "监管范围内查看与追溯"),
]

PERMISSIONS = [
    ("data:input", "数据录入", "数据"), ("data:query", "数据查询", "数据"),
    ("data:export", "数据导出", "数据"), ("data:archive", "数据归档", "数据"),
    ("data:delete", "场地删除", "数据"),  # v1.0.2 新增: 场地删除权限
    ("report:generate", "报告生成", "报告"), ("map:view", "地图查看", "数据"),
    ("workflow:view", "全流程查看", "追溯"), ("file:download", "文档下载", "文件"),
    ("user:manage", "用户管理", "系统"), ("role:manage", "角色管理", "系统"),
    ("audit:view", "日志审计", "系统"), ("param:config", "参数设置", "系统"),
    ("model:manage", "模型管理", "算法"), ("tech:manage", "技术库管理", "决策"),
    ("system:backup", "备份恢复", "系统"),  # v1.0.2 新增: 备份恢复权限
]

ROLE_PERMS = {
    "admin": [p[0] for p in PERMISSIONS],
    "enterprise": ["data:input", "data:query", "data:export", "report:generate",
                   "map:view", "workflow:view", "file:download"],
    "agency": ["data:input", "data:query", "workflow:view", "file:download"],
    "regulator": ["data:query", "map:view", "workflow:view", "file:download",
                  "report:generate", "audit:view"],
}

# v1.0.2: 演示数据(仅 SRS_DEMO_SEED=1 时初始化, 默认关闭)
DEMO_ORGS = [
    ("系统管理方", "admin"),
    ("示范企业(个旧场地)", "enterprise"),
    ("第三方检测机构", "agency"),
    ("属地监管单位", "regulator"),
]

DEMO_USERS = [
    ("admin", "系统管理员", "admin", "系统管理方"),
    ("enterprise", "示范企业用户", "enterprise", "示范企业(个旧场地)"),
    ("agency", "第三方检测机构用户", "agency", "第三方检测机构"),
    ("regulator", "监管人员", "regulator", "属地监管单位"),
]

# 系统配置初始值
SYSTEM_CONFIG_DEFAULTS = [
    ("admin_contact_phone", "", "管理员联系电话"),
    ("admin_contact_email", "", "管理员联系邮箱"),
    ("admin_display_name", "系统管理方", "管理员显示名称"),
]


# ── 参考数据初始化 (生产首启必须, 幂等) ──────────────────────────────

def seed_reference():
    """初始化参考数据: 角色/权限/系统配置/技术库/因子字典/标准阈值。

    每个表单独判空(不靠 Organization), 幂等, 可重复运行。
    生产首启只调这个, 不种任何业务/演示数据。
    """
    create_all()
    db = SessionLocal()
    try:
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
                pid = perm_map.get(pc)
                if pid and not db.query(RolePermission).filter_by(
                        role_id=r.id, permission_id=pid).first():
                    db.add(RolePermission(role_id=r.id, permission_id=pid))

        # 系统配置初始值
        for key, value, desc in SYSTEM_CONFIG_DEFAULTS:
            if not db.query(SystemConfig).filter_by(config_key=key).first():
                db.add(SystemConfig(config_key=key, config_value=value,
                                    description=desc, updated_by="system"))

        # 技术库
        seed_tech(db)

        # v1.0.2: 因子字典 + 标准阈值 (修复首启阈值空缺, GPT 4.10)
        seed_factor_dictionary(db)
        seed_standard_thresholds(db)

        # v1.0.2(GPT P0-5): 首启管理员初始化
        # R3 审计第六类: 不再随机生成密码打印控制台(console=False 看不到)
        # 改为标记 setup_status=pending, 由前端首启向导设置管理员密码
        if db.query(User).count() == 0 and os.environ.get("SRS_DEMO_SEED", "0") != "1":
            _mark_setup_pending(db)

        db.commit()
        print(f"参考数据初始化完成: 角色 {len(ROLES)}, 权限 {len(PERMISSIONS)}, "
              f"技术库 + 因子字典 + 标准阈值 (幂等)")
    finally:
        db.close()


def _mark_setup_pending(db):
    """R3 审计第六类: 首启标记 setup_status=pending。

    不再创建随机密码 admin(console=False 看不到密码)。
    在 SystemConfig 写入 setup_status=pending, 由前端首启向导设置管理员。
    若设置了 SRS_FIRST_ADMIN_PASSWORD 环境变量, 则直接种 admin(向后兼容部署脚本)。
    """
    # 向后兼容: 若设置了 SRS_FIRST_ADMIN_PASSWORD, 仍直接种 admin(供自动化部署用)
    preset_password = os.environ.get("SRS_FIRST_ADMIN_PASSWORD", "")
    if preset_password:
        _seed_first_admin_with_password(db, preset_password)
        return

    # 否则标记 setup_status=pending, 等前端首启向导
    from app.models import SystemConfig
    existing = db.query(SystemConfig).filter_by(config_key="setup_status").first()
    if not existing:
        db.add(SystemConfig(
            config_key="setup_status",
            config_value="pending",
            description="首启设置状态: pending=待设置管理员, completed=已完成"
        ))
    # 确保管理组织存在(首启向导创建 admin 时需要)
    org = db.query(Organization).filter_by(name="系统管理方").first()
    if not org:
        org = Organization(name="系统管理方", org_type="admin", is_seed=True)
        db.add(org)
    print("=" * 60)
    print("🔐 SRS 首次启动: 系统尚未初始化")
    print("   请通过浏览器访问系统, 完成首启管理员设置向导")
    print("   (setup_status=pending, 等待前端向导设置管理员密码)")
    print("=" * 60)


def _seed_first_admin_with_password(db, password: str):
    """向后兼容: SRS_FIRST_ADMIN_PASSWORD 环境变量设置时直接种 admin(自动化部署)。"""
    # 创建默认管理组织
    org = db.query(Organization).filter_by(name="系统管理方").first()
    if not org:
        org = Organization(name="系统管理方", org_type="admin", is_seed=True)
        db.add(org); db.flush()

    admin_user = User(
        username="admin",
        display_name="系统管理员",
        password_hash=hash_password(password),
        organization_id=org.id,
        status="active",
        is_seed=True,
    )
    db.add(admin_user); db.flush()

    # 分配 admin 角色
    # R3-P0-7 修复: 必须用 code(不是 name), seed 中 admin 的 code="admin"
    roles = {r.code: r.id for r in db.query(Role).all()}
    admin_role_id = roles.get("admin")
    # Round8 审计 5.5: admin 角色不存在必须失败(不创建无角色用户)
    if not admin_role_id:
        db.rollback()
        raise RuntimeError(
            "admin 角色不存在, 无法为环境变量首管理员绑定角色。"
            "请确认 seed_roles() 已在 seed_db.py 调用顺序中先执行。"
            "禁止创建无角色管理员(安全约束)。")
    if not db.query(UserRole).filter_by(
            user_id=admin_user.id, role_id=admin_role_id).first():
        db.add(UserRole(user_id=admin_user.id, role_id=admin_role_id))

    # 标记 setup 完成
    from app.models import SystemConfig
    existing = db.query(SystemConfig).filter_by(config_key="setup_status").first()
    if not existing:
        db.add(SystemConfig(
            config_key="setup_status",
            config_value="completed",
            description="首启设置状态(由 SRS_FIRST_ADMIN_PASSWORD 环境变量完成)"
        ))
    elif existing.config_value != "completed":
        existing.config_value = "completed"
    print("=" * 60)
    print("🔐 SRS 首次启动: 管理员账户已创建(来自 SRS_FIRST_ADMIN_PASSWORD)")
    print("   用户名: admin")
    print("=" * 60)


def seed_tech(db):
    """技术库种子(幂等)。"""
    from app.core.config import resource_root
    path = os.path.join(resource_root(),
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


def seed_factor_dictionary(db):
    """因子字典种子(幂等)。复用 seed_gb15618.seed_domain 的 FACTORS 常量。"""
    from app.models import FactorDictionary
    if db.query(FactorDictionary).count() > 0:
        print("因子字典已有数据, 跳过")
        return
    # 复用 seed_gb15618 的 FACTORS 常量(pH + 8 重金属 + 肥力指标)
    try:
        from app.db.seed_gb15618 import FACTORS
        n = 0
        for code, name, cat, ftype, unit in FACTORS:
            if not db.query(FactorDictionary).filter_by(factor_code=code).first():
                db.add(FactorDictionary(factor_code=code, factor_name=name,
                                        level1_category=cat, factor_type=ftype,
                                        default_unit=unit))
                n += 1
        db.flush()
        print(f"因子字典新增 {n} 条(GB15618 seed)")
    except Exception as e:
        print(f"因子字典 seed 失败: {e}")


def seed_standard_thresholds(db):
    """标准阈值种子(幂等)。GB15618 + GB36600。"""
    from app.models import StandardThreshold
    if db.query(StandardThreshold).count() > 0:
        print("标准阈值已有数据, 跳过")
        return
    try:
        from app.db.load_standard_thresholds import load as load_std
        n = load_std(db)
        print(f"标准阈值新增 {n} 条(GB15618+GB36600)")
    except Exception as e:
        print(f"标准阈值初始化失败: {e} (KOS 诊断将依赖静态 fallback)")


# ── 演示数据初始化 (仅 SRS_DEMO_SEED=1, 默认关闭) ────────────────────

def seed_demo():
    """演示数据: 4 个演示组织 + 4 个演示用户。仅 SRS_DEMO_SEED=1 时调用。"""
    db = SessionLocal()
    try:
        org_map = {}
        for name, otype in DEMO_ORGS:
            o = db.query(Organization).filter_by(name=name).first()
            if not o:
                o = Organization(name=name, org_type=otype, is_seed=True)
                db.add(o); db.flush()
            org_map[name] = o.id

        role_map = {r.code: r.id for r in db.query(Role).all()}

        for uname, disp, rcode, oname in DEMO_USERS:
            u = db.query(User).filter_by(username=uname).first()
            if not u:
                u = User(username=uname, display_name=disp,
                         password_hash=hash_password(DEMO_PASSWORD),
                         organization_id=org_map[oname], is_seed=True)
                db.add(u); db.flush()
            if rcode in role_map and not db.query(UserRole).filter_by(
                    user_id=u.id, role_id=role_map[rcode]).first():
                db.add(UserRole(user_id=u.id, role_id=role_map[rcode]))

        db.commit()
        print(f"演示数据初始化: 组织 {len(DEMO_ORGS)}, 用户 {len(DEMO_USERS)} "
              f"(密码={DEMO_PASSWORD}, is_seed=True)")
    finally:
        db.close()


def seed_demo_if_requested():
    """仅 SRS_DEMO_SEED=1 时初始化演示数据。生产默认关闭。"""
    if os.environ.get("SRS_DEMO_SEED", "0") == "1":
        seed_demo()
    return os.environ.get("SRS_DEMO_SEED", "0") == "1"


# ── 兼容入口 ────────────────────────────────────────────────────────

def seed():
    """兼容旧调用: 参考数据 + 演示数据(如果 SRS_DEMO_SEED=1)。

    v1.0.2 推荐: 直接调 seed_reference() + seed_demo_if_requested()。
    """
    seed_reference()
    seed_demo_if_requested()


def seed_if_empty():
    """首启初始化: 只种参考数据, 不种演示数据。

    v1.0.2 关键改动(GPT 1.2):
      - 不再用"Organization 存在就跳过全部"
      - 每个参考表在 seed_reference() 内单独判空
      - 生产首启后业务表(sites/measurements/...)全部为空
      - 演示数据由 SRS_DEMO_SEED=1 显式开启
    """
    seed_reference()
    # 演示数据仅在显式请求时初始化
    if os.environ.get("SRS_DEMO_SEED", "0") == "1":
        seed_demo()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        os.environ["SRS_DEMO_SEED"] = "1"
    seed_if_empty()
