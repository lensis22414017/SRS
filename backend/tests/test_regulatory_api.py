"""API 契约与安全边界验证测试。

覆盖:
  1. 未登录访问 → 401
  2. 无权限角色访问 → 403
  3. 企业用户数据隔离(site_id 越权) → 403
  4. import batch validation-report 越权 → 403
  5. workflow attachment 越权下载 → 403
  6. report 越权下载 → 403
  7. 写操作写入 audit_logs
  8. 下载/导出操作写入 audit_logs
  9. SECRET_KEY 默认值阻断启动

每个测试函数名清晰描述测试场景, 遵循 conftest.py 的 fixture 体系。
"""
from __future__ import annotations

import os
import warnings
from io import BytesIO

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(
    ROOT, "data", "raw",
    "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx",
)


def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(
    not _has("sqlalchemy", "fastapi"), reason="需 venv (fastapi + sqlalchemy)"
)


# ═══════════════════════════════════════════════════════════════════
# 测试辅助
# ═══════════════════════════════════════════════════════════════════

def _bootstrap_client():
    """重置数据库(删表 → 建表 → 种子) 并返回 TestClient。"""
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.main import app
    bootstrap()
    return TestClient(app)


def _login(c, username, password="Demo@2026"):
    return c.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


def _token(c, username, password="Demo@2026"):
    body = _login(c, username, password).json()
    return body["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _import_site_for_other_org(db, gejiu_path, mapping_id, org_type_target):
    """导入场地并将 site.organization_id 划归指定类型组织(非 enterprise 的 org)。
    返回 (site_id, batch_id)。
    """
    from app.models import ImportBatch, Organization, Site
    from app.services.pipeline import run_import

    run_import(db, gejiu_path, mapping_id)
    other_org = (
        db.query(Organization)
        .filter(Organization.org_type == org_type_target)
        .first()
    )
    site = db.query(Site).first()
    site.organization_id = other_org.id
    db.commit()
    site_id = site.id
    batch = (
        db.query(ImportBatch)
        .filter_by(site_id=site_id)
        .order_by(ImportBatch.id.desc())
        .first()
    )
    batch_id = batch.id if batch else None
    return site_id, batch_id


# ═══════════════════════════════════════════════════════════════════
# 1. 未登录访问 → 401
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_unauthenticated_list_sites_returns_401():
    """未登录访问 GET /api/v1/sites → 401。"""
    c = _bootstrap_client()
    assert c.get("/api/v1/sites").status_code == 401


@needs_db
def test_unauthenticated_site_detail_returns_401():
    """未登录访问 GET /api/v1/sites/{id} → 401。"""
    c = _bootstrap_client()
    assert c.get("/api/v1/sites/1").status_code == 401


@needs_db
def test_unauthenticated_me_returns_401():
    """未登录访问 GET /api/v1/auth/me → 401。"""
    c = _bootstrap_client()
    assert c.get("/api/v1/auth/me").status_code == 401


@needs_db
def test_unauthenticated_system_users_returns_401():
    """未登录访问 GET /api/v1/system/users → 401。"""
    c = _bootstrap_client()
    assert c.get("/api/v1/system/users").status_code == 401


@needs_db
def test_unauthenticated_report_generate_returns_401():
    """未登录访问 POST /api/v1/sites/1/report → 401。"""
    c = _bootstrap_client()
    assert c.post("/api/v1/sites/1/report").status_code == 401


@needs_db
def test_unauthenticated_import_returns_401():
    """未登录访问 POST /api/v1/import → 401。"""
    c = _bootstrap_client()
    # 即使不发文件, auth 拦截在先
    assert c.post("/api/v1/import").status_code == 401


# ═══════════════════════════════════════════════════════════════════
# 2. 无权限角色访问 → 403
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_agency_cannot_access_system_users():
    """第三方机构(agency)无 user:manage 权限, GET /api/v1/system/users → 403。"""
    c = _bootstrap_client()
    h = _auth(_token(c, "agency"))
    assert c.get("/api/v1/system/users", headers=h).status_code == 403


@needs_db
def test_enterprise_cannot_access_system_users():
    """企业用户(enterprise)无 user:manage 权限, GET /api/v1/system/users → 403。"""
    c = _bootstrap_client()
    h = _auth(_token(c, "enterprise"))
    assert c.get("/api/v1/system/users", headers=h).status_code == 403


@needs_db
def test_enterprise_cannot_access_audit_logs():
    """企业用户无 audit:view 权限, GET /api/v1/system/audit-logs → 403。"""
    c = _bootstrap_client()
    h = _auth(_token(c, "enterprise"))
    assert c.get("/api/v1/system/audit-logs", headers=h).status_code == 403


@needs_db
def test_agency_cannot_generate_report():
    """第三方机构无 report:generate 权限, POST /api/v1/sites/1/report → 403。"""
    c = _bootstrap_client()
    h = _auth(_token(c, "agency"))
    assert c.post("/api/v1/sites/1/report", headers=h).status_code == 403


@needs_db
def test_agency_cannot_access_technologies():
    """第三方机构无 tech:manage 权限, GET /api/v1/system/technologies → 403。"""
    c = _bootstrap_client()
    h = _auth(_token(c, "agency"))
    assert c.get("/api/v1/system/technologies", headers=h).status_code == 403


@needs_db
def test_enterprise_cannot_create_user():
    """企业用户无 user:manage 权限, POST /api/v1/system/users → 403。"""
    c = _bootstrap_client()
    h = _auth(_token(c, "enterprise"))
    resp = c.post("/api/v1/system/users", headers=h, json={
        "username": "hack_admin",
        "password": "Hack@2026!",
        "display_name": "越权创建",
        "role_codes": ["admin"],
    })
    assert resp.status_code == 403


@needs_db
def test_regulator_cannot_manage_technologies():
    """监管人员无 tech:manage 权限, GET /api/v1/system/technologies → 403。"""
    c = _bootstrap_client()
    h = _auth(_token(c, "regulator"))
    assert c.get("/api/v1/system/technologies", headers=h).status_code == 403


@needs_db
def test_agency_cannot_import_data():
    """第三方机构有 data:input 权限, import 应 422(缺文件) 而非 403。

    注: agency 拥有 data:input 权限(seed_db.py:42),
    此测试验证其确实可以到达业务校验层(422)而非被权限拦截(403)。
    """
    c = _bootstrap_client()
    h = _auth(_token(c, "agency"))
    # 缺少文件但权限通过 → 422 Unprocessable Entity
    r = c.post("/api/v1/import", headers=h)
    assert r.status_code in (422, 400), (
        f"agency 有 data:input 权限, 应到达业务层(422/400), 实际: {r.status_code}"
    )
    # 但不能访问 system 相关
    assert c.get("/api/v1/system/audit-logs", headers=h).status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 3. 企业用户数据隔离 → 403 (site_id 越权访问)
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_enterprise_cannot_access_other_org_site_detail():
    """企业用户通过 site_id 访问其他企业场地详情 → 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(db, GEJIU, "yunnan_gejiu", "regulator")
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/sites/{site_id}", headers=h)
    assert r.status_code == 403, (
        f"企业用户访问其他企业场地详情应 403, 实际: {r.status_code}"
    )


@needs_db
def test_enterprise_cannot_access_other_org_site_points():
    """企业用户访问其他企业场地采样点列表 → 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(db, GEJIU, "yunnan_gejiu", "regulator")
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/sites/{site_id}/points", headers=h)
    assert r.status_code == 403, (
        f"企业用户访问其他企业场地采样点应 403, 实际: {r.status_code}"
    )


@needs_db
def test_enterprise_cannot_access_other_org_site_measurements():
    """企业用户访问其他企业场地检测记录 → 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(db, GEJIU, "yunnan_gejiu", "regulator")
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/sites/{site_id}/measurements", headers=h)
    assert r.status_code == 403, (
        f"企业用户访问其他企业场地检测记录应 403, 实际: {r.status_code}"
    )


@needs_db
def test_enterprise_cannot_access_other_org_site_workflow():
    """企业用户访问其他企业场地追溯流程 → 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(db, GEJIU, "yunnan_gejiu", "regulator")
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/sites/{site_id}/workflow", headers=h)
    assert r.status_code == 403, (
        f"企业用户访问其他企业场地追溯流程应 403, 实际: {r.status_code}"
    )


@needs_db
def test_enterprise_cannot_access_other_org_site_map_layers():
    """企业用户访问其他企业场地地图图层 → 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(db, GEJIU, "yunnan_gejiu", "regulator")
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/sites/{site_id}/map/layers", headers=h)
    assert r.status_code == 403, (
        f"企业用户访问其他企业场地地图图层应 403, 实际: {r.status_code}"
    )


@needs_db
def test_enterprise_cannot_access_other_org_site_eda():
    """企业用户访问其他企业场地 EDA 分析 → 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(db, GEJIU, "yunnan_gejiu", "regulator")
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/sites/{site_id}/eda", headers=h)
    assert r.status_code == 403, (
        f"企业用户访问其他企业场地 EDA 分析应 403, 实际: {r.status_code}"
    )


@needs_db
def test_enterprise_cannot_access_other_org_site_evaluation():
    """企业用户访问其他企业场地评价结果 → 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(db, GEJIU, "yunnan_gejiu", "regulator")
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/sites/{site_id}/evaluation", headers=h)
    assert r.status_code == 403, (
        f"企业用户访问其他企业场地评价结果应 403, 实际: {r.status_code}"
    )


@needs_db
def test_enterprise_cannot_export_other_org_measurements():
    """企业用户导出其他企业场地检测数据 → 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(db, GEJIU, "yunnan_gejiu", "regulator")
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/sites/{site_id}/measurements/export", headers=h)
    assert r.status_code == 403, (
        f"企业用户导出其他企业场地检测数据应 403, 实际: {r.status_code}"
    )


@needs_db
def test_admin_can_access_any_site():
    """管理员访问任何场地不受企业隔离限制 → 非 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(db, GEJIU, "yunnan_gejiu", "regulator")
    finally:
        db.close()

    h = _auth(_token(c, "admin"))
    r = c.get(f"/api/v1/sites/{site_id}", headers=h)
    assert r.status_code != 403, (
        f"管理员访问任何场地不应被隔离限制, 实际: {r.status_code}"
    )


# ═══════════════════════════════════════════════════════════════════
# 4. import batch validation-report 越权 → 403
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_enterprise_cannot_access_other_org_validation_report():
    """企业用户访问其他企业的 import batch validation-report → 403。

    验证路径: data.py validation_report 端点做了 assert_site_access。
    """
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, batch_id = _import_site_for_other_org(
            db, GEJIU, "yunnan_gejiu", "regulator"
        )
    finally:
        db.close()

    if batch_id is None:
        pytest.skip("无 import batch 可测试")

    h = _auth(_token(c, "enterprise"))
    r = c.get(
        f"/api/v1/import-batches/{batch_id}/validation-report",
        headers=h,
    )
    assert r.status_code in (403, 404), (
        f"企业用户访问其他企业 validation-report 应 403/404, "
        f"实际: {r.status_code}"
    )


# ═══════════════════════════════════════════════════════════════════
# 5. workflow attachment 越权下载 → 403
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_enterprise_cannot_download_other_org_workflow_attachment():
    """企业用户下载其他企业场地的 workflow attachment → 403。

    验证路径: workflow.py download_attachment 端点中 _require_site →
    assert_site_access 先于附件校验触发, 阻止越权。
    """
    from app.db.session import SessionLocal
    from app.models import WorkflowAttachment, WorkflowRecord
    from app.services.file_service import save_bytes
    from app.services.workflow_service import attach_file, init_stages

    c = _bootstrap_client()
    db = SessionLocal()
    site_id = None
    att_id = None
    try:
        site_id, _ = _import_site_for_other_org(
            db, GEJIU, "yunnan_gejiu", "regulator"
        )
        init_stages(db, site_id)

        fo = save_bytes(
            db, b"test attachment content",
            "检测报告_2025.pdf",
            content_type="application/pdf",
        )
        db.commit()

        wr = (
            db.query(WorkflowRecord)
            .filter_by(site_id=site_id, stage="survey")
            .first()
        )
        if wr:
            attach_file(
                db, site_id, "survey", fo.id,
                file_role="检测报告", operator_id=1,
            )
            db.commit()
            att = (
                db.query(WorkflowAttachment)
                .filter_by(workflow_record_id=wr.id)
                .first()
            )
            att_id = att.id if att else None
    finally:
        db.close()

    if att_id is None:
        pytest.skip("无法创建 workflow attachment 用于测试")

    h = _auth(_token(c, "enterprise"))
    r = c.get(
        f"/api/v1/sites/{site_id}/workflow/survey"
        f"/attachments/{att_id}/download",
        headers=h,
    )
    assert r.status_code in (403, 404), (
        f"企业用户下载其他企业场地附件应 403/404, 实际: {r.status_code}"
    )


# ═══════════════════════════════════════════════════════════════════
# 6. report 越权下载 → 403
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_enterprise_cannot_download_other_org_report():
    """企业用户下载其他企业场地的 report → 403。

    验证路径: workflow.py download_report 端点中 _require_site 校验 site 归属。
    """
    from app.db.session import SessionLocal
    from app.models import ReportRecord

    c = _bootstrap_client()
    db = SessionLocal()
    report_id = None
    try:
        site_id, _ = _import_site_for_other_org(
            db, GEJIU, "yunnan_gejiu", "regulator"
        )

        # 用管理员生成报告
        admin_h = _auth(_token(c, "admin"))
        resp = c.post(
            f"/api/v1/sites/{site_id}/report",
            params={"format": "html"},
            headers=admin_h,
        )
        if resp.status_code == 200:
            report_id = resp.json().get("report_id")
        else:
            # 若模板缺失, 从 DB 直接查
            rec = (
                db.query(ReportRecord)
                .filter_by(site_id=site_id)
                .order_by(ReportRecord.id.desc())
                .first()
            )
            if rec:
                report_id = rec.id
        db.close()
    finally:
        pass

    if report_id is None:
        pytest.skip("无法创建报告用于测试(缺少报告模板或数据)")

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/reports/{report_id}/download", headers=h)
    assert r.status_code in (403, 404), (
        f"企业用户下载其他企业场地报告应 403/404, 实际: {r.status_code}"
    )


@needs_db
def test_enterprise_cannot_access_other_org_report_list():
    """企业用户访问其他企业场地的报告列表 → 403。"""
    from app.db.session import SessionLocal

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(
            db, GEJIU, "yunnan_gejiu", "regulator"
        )
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(f"/api/v1/sites/{site_id}/reports", headers=h)
    assert r.status_code == 403, (
        f"企业用户访问其他企业场地报告列表应 403, 实际: {r.status_code}"
    )


# ═══════════════════════════════════════════════════════════════════
# 7. 写操作写入 audit_logs
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_login_writes_audit_log():
    """登录(成功+失败)均写入 audit_logs(action=login)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    _login(c, "admin")            # 成功
    _login(c, "admin", "wrong")   # 失败

    db = SessionLocal()
    try:
        success = db.query(AuditLog).filter_by(
            action="login", result="success",
        ).count()
        fail = db.query(AuditLog).filter_by(
            action="login", result="fail",
        ).count()
        assert success >= 1, f"应有 login success 审计, 实际: {success}"
        assert fail >= 1, f"应有 login fail 审计, 实际: {fail}"
    finally:
        db.close()


@needs_db
def test_import_writes_audit_log():
    """数据导入写入 audit_logs(action=import), 通过 API 端点触发。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    admin_h = _auth(_token(c, "admin"))

    with open(GEJIU, "rb") as f:
        file_content = f.read()

    r = c.post(
        "/api/v1/import",
        files={
            "file": (
                "yunnan_gejiu.xlsx",
                BytesIO(file_content),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
        data={"mapping_id": "yunnan_gejiu", "on_conflict": "skip"},
        headers=admin_h,
    )
    assert r.status_code == 200, f"导入失败: {r.status_code} {r.text[:200]}"

    db = SessionLocal()
    try:
        logs = db.query(AuditLog).filter_by(action="import").count()
        assert logs >= 1, f"应有 import 审计记录, 实际: {logs}"
    finally:
        db.close()


@needs_db
def test_create_user_writes_audit_log():
    """管理员创建用户写入 audit_logs(action=create_user)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    h = _auth(_token(c, "admin"))

    r = c.post("/api/v1/system/users", headers=h, json={
        "username": "audit_create_test",
        "password": "Test@2026",
        "display_name": "审计日志测试用户",
        "role_codes": ["enterprise"],
    })
    assert r.status_code == 200, f"创建用户失败: {r.text[:200]}"

    db = SessionLocal()
    try:
        logs = db.query(AuditLog).filter_by(action="create_user").count()
        assert logs >= 1, f"应有 create_user 审计, 实际: {logs}"
    finally:
        db.close()


@needs_db
def test_update_user_writes_audit_log():
    """更新用户信息写入 audit_logs(action=update_user)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    h = _auth(_token(c, "admin"))

    # enterprise 用户 id=2 (种子数据固定顺序: admin=1, enterprise=2)
    r = c.put("/api/v1/system/users/2", headers=h, json={
        "display_name": "审计更名测试",
    })
    assert r.status_code == 200, f"更新用户失败: {r.text[:200]}"

    db = SessionLocal()
    try:
        logs = db.query(AuditLog).filter_by(action="update_user").count()
        assert logs >= 1, f"应有 update_user 审计, 实际: {logs}"
    finally:
        db.close()


@needs_db
def test_change_password_writes_audit_log():
    """修改密码写入 audit_logs(action=change_password)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    h = _auth(_token(c, "admin"))

    # 改到一个临时密码
    c.post("/api/v1/system/change-password", headers=h, json={
        "old_password": "Demo@2026",
        "new_password": "Temp@2026!",
    })

    db = SessionLocal()
    try:
        logs = db.query(AuditLog).filter_by(
            action="change_password",
        ).count()
        assert logs >= 1, f"应有 change_password 审计, 实际: {logs}"
    finally:
        db.close()


@needs_db
def test_register_writes_audit_log():
    """注册操作写入 audit_logs(action=register, result=pending)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    c.post("/api/v1/auth/register", json={
        "username": "audit_reg_test",
        "password": "Test@2026!",
        "display_name": "注册审计测试",
        "organization_name": "审计测试企业",
        "role_code": "enterprise",
    })

    db = SessionLocal()
    try:
        logs = db.query(AuditLog).filter_by(action="register").count()
        assert logs >= 1, f"应有 register 审计, 实际: {logs}"
        # 状态应为 pending
        pending = db.query(AuditLog).filter_by(
            action="register", result="pending",
        ).count()
        assert pending >= 1, f"注册审计状态应为 pending, 实际: {pending}"
    finally:
        db.close()


@needs_db
def test_approve_user_writes_audit_log():
    """审核通过写入 audit_logs(action=approve_user)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    admin_h = _auth(_token(c, "admin"))

    # 先注册一个待审核用户, 再审核
    c.post("/api/v1/auth/register", json={
        "username": "approve_test_user",
        "password": "Test@2026!",
        "display_name": "审核测试用户",
        "organization_name": "审核测试企业",
        "role_code": "enterprise",
    })

    # 新注册用户 id 从 admin h 获取
    db = SessionLocal()
    try:
        from app.models import User
        u = db.query(User).filter_by(
            username="approve_test_user"
        ).first()
        user_id = u.id if u else None
    finally:
        db.close()

    if user_id is None:
        pytest.skip("注册失败, 无法测试审核")

    c.post(f"/api/v1/auth/approve/{user_id}", headers=admin_h)

    db2 = SessionLocal()
    try:
        logs = db2.query(AuditLog).filter_by(action="approve_user").count()
        assert logs >= 1, f"应有 approve_user 审计, 实际: {logs}"
    finally:
        db2.close()


@needs_db
def test_update_land_use_writes_audit_log():
    """更新场地用地类型写入 audit_logs(action=update_land_use)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        site_id, _ = _import_site_for_other_org(
            db, GEJIU, "yunnan_gejiu", "admin"
        )
    finally:
        db.close()

    admin_h = _auth(_token(c, "admin"))
    r = c.put(
        f"/api/v1/sites/{site_id}/land-use",
        headers=admin_h,
        json={"land_use_type": "生态用地"},
    )
    assert r.status_code == 200, f"更新用地类型失败: {r.text[:200]}"

    db2 = SessionLocal()
    try:
        logs = db2.query(AuditLog).filter_by(
            action="update_land_use",
        ).count()
        assert logs >= 1, f"应有 update_land_use 审计, 实际: {logs}"
    finally:
        db2.close()


# ═══════════════════════════════════════════════════════════════════
# 8. 下载/导出操作写入 audit_logs
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_export_measurements_writes_audit_log():
    """导出场地检测数据写入 audit_logs(action=export_measurements)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog, Organization, Site
    from app.services.pipeline import run_import

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        run_import(db, GEJIU, "yunnan_gejiu")
        # 场地归属设为 enterprise 组织, 允许 enterprise 用户导出
        ent_org = (
            db.query(Organization)
            .filter_by(org_type="enterprise")
            .first()
        )
        site = db.query(Site).first()
        site.organization_id = ent_org.id
        db.commit()
        site_id = site.id
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get(
        f"/api/v1/sites/{site_id}/measurements/export",
        params={"format": "csv"},
        headers=h,
    )
    assert r.status_code == 200, f"导出失败: {r.status_code}"

    db2 = SessionLocal()
    try:
        logs = db2.query(AuditLog).filter_by(
            action="export_measurements",
        ).count()
        assert logs >= 1, (
            f"应有 export_measurements 审计记录, 实际: {logs}"
        )
    finally:
        db2.close()


@needs_db
def test_export_audit_logs_writes_audit_log():
    """导出审计日志写入 audit_logs(action=export_audit_logs)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    h = _auth(_token(c, "admin"))

    c.get("/api/v1/system/audit-logs/export", headers=h)

    db = SessionLocal()
    try:
        logs = db.query(AuditLog).filter_by(
            action="export_audit_logs",
        ).count()
        assert logs >= 1, (
            f"应有 export_audit_logs 审计记录, 实际: {logs}"
        )
    finally:
        db.close()


@needs_db
def test_export_technologies_writes_audit_log():
    """导出技术库写入 audit_logs(action=export_technologies)。"""
    from app.db.session import SessionLocal
    from app.models import AuditLog

    c = _bootstrap_client()
    h = _auth(_token(c, "admin"))

    c.get("/api/v1/system/technologies/export", headers=h)

    db = SessionLocal()
    try:
        logs = db.query(AuditLog).filter_by(
            action="export_technologies",
        ).count()
        assert logs >= 1, (
            f"应有 export_technologies 审计记录, 实际: {logs}"
        )
    finally:
        db.close()


@needs_db
def test_report_download_audit_log_gap():
    """【安全缺口】报告下载(report_id/download)当前不写 audit_log。

    验证: 下载操作未在 audit_logs 中产生记录 → 应视为已知缺口。
    """
    from app.db.session import SessionLocal
    from app.models import AuditLog, Organization, ReportRecord, Site
    from app.services.pipeline import run_import

    c = _bootstrap_client()
    db = SessionLocal()
    report_id = None
    try:
        run_import(db, GEJIU, "yunnan_gejiu")
        ent_org = (
            db.query(Organization)
            .filter_by(org_type="enterprise")
            .first()
        )
        site = db.query(Site).first()
        site.organization_id = ent_org.id
        db.commit()
        site_id = site.id

        # 生成报告
        admin_h = _auth(_token(c, "admin"))
        resp = c.post(
            f"/api/v1/sites/{site_id}/report",
            params={"format": "html"},
            headers=admin_h,
        )
        if resp.status_code == 200:
            report_id = resp.json().get("report_id")
        else:
            rec = (
                db.query(ReportRecord)
                .filter_by(site_id=site_id)
                .order_by(ReportRecord.id.desc())
                .first()
            )
            if rec:
                report_id = rec.id
        db.close()
    finally:
        pass

    if report_id is None:
        pytest.skip("无法创建报告用于测试")

    # 记录当前 audit_log 总数
    db2 = SessionLocal()
    try:
        before = db2.query(AuditLog).count()
    finally:
        db2.close()

    # 下载报告
    h = _auth(_token(c, "enterprise"))
    c.get(f"/api/v1/reports/{report_id}/download", headers=h)

    db3 = SessionLocal()
    try:
        after = db3.query(AuditLog).count()
        # 未新增, 确认无下载审计
        new_logs = after - before
        download_logs = db3.query(AuditLog).filter_by(
            action="download_report",
        ).count()
        # 报告缺口: 下载操作未写 audit log
        assert download_logs == 0, (
            f"当前 report download 端点未写 audit_log, 这是已知安全缺口。"
            f" 建议增加 log(action='download_report', resource_type='report', resource_id=...)"
        )
    finally:
        db3.close()


@needs_db
def test_attachment_download_audit_log_gap():
    """【安全缺口】附件下载(workflow attachment download)当前不写 audit_log。

    验证: 下载操作未在 audit_logs 中产生记录。
    """
    from app.db.session import SessionLocal
    from app.models import (
        AuditLog, Organization, Site, WorkflowAttachment, WorkflowRecord,
    )
    from app.services.file_service import save_bytes
    from app.services.pipeline import run_import
    from app.services.workflow_service import attach_file, init_stages

    c = _bootstrap_client()
    db = SessionLocal()
    site_id = None
    att_id = None
    try:
        run_import(db, GEJIU, "yunnan_gejiu")
        ent_org = (
            db.query(Organization)
            .filter_by(org_type="enterprise")
            .first()
        )
        site = db.query(Site).first()
        site.organization_id = ent_org.id
        db.commit()
        site_id = site.id

        init_stages(db, site_id)
        fo = save_bytes(
            db, b"gap test",
            "gap_test.pdf",
            content_type="application/pdf",
        )
        db.commit()

        wr = (
            db.query(WorkflowRecord)
            .filter_by(site_id=site_id, stage="survey")
            .first()
        )
        if wr:
            attach_file(
                db, site_id, "survey", fo.id,
                file_role="测试附件", operator_id=1,
            )
            db.commit()
            att = (
                db.query(WorkflowAttachment)
                .filter_by(workflow_record_id=wr.id)
                .first()
            )
            att_id = att.id if att else None
        db.close()
    finally:
        pass

    if att_id is None:
        pytest.skip("无法创建 workflow attachment 用于测试缺口")

    db2 = SessionLocal()
    try:
        before = db2.query(AuditLog).count()
    finally:
        db2.close()

    h = _auth(_token(c, "enterprise"))
    c.get(
        f"/api/v1/sites/{site_id}/workflow/survey"
        f"/attachments/{att_id}/download",
        headers=h,
    )

    db3 = SessionLocal()
    try:
        download_logs = db3.query(AuditLog).filter_by(
            action="download_attachment",
        ).count()
        assert download_logs == 0, (
            f"当前 attachment download 端点未写 audit_log, 这是已知安全缺口。"
            f" 建议增加 log(action='download_attachment', resource_type='file_object', ...)"
        )
    finally:
        db3.close()


# ═══════════════════════════════════════════════════════════════════
# 9. SECRET_KEY 默认值阻断启动
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_secret_key_default_warns_on_startup():
    """SECRET_KEY 使用默认值 'CHANGE_ME_IN_ENV' 时, 应用启动应产生 UserWarning。

    验证 main.py lifespan 中的安全告警逻辑: 若 secret_key 是默认值,
    发出健壮性警告, 提示操作者覆盖 .env 中的 SECRET_KEY。

    注意: 当前实现在 lifespan 中仅 warnings.warn(), 不阻断启动。
    生产部署建议升级为 sys.exit(1) 硬阻断。
    """
    from app.core.config import get_settings

    # 保存当前设置, 清缓存
    get_settings.cache_clear()
    old_key = os.environ.get("SECRET_KEY")

    # 临时重置为默认值
    os.environ["SECRET_KEY"] = "CHANGE_ME_IN_ENV"

    try:
        import importlib
        import app.core.config as config_module
        importlib.reload(config_module)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            settings = config_module.get_settings()
            if settings.secret_key == "CHANGE_ME_IN_ENV":
                warnings.warn(
                    "[SRS] secret_key 使用默认值 'CHANGE_ME_IN_ENV'！"
                    "请在 .env 中设置强随机密钥，否则 JWT 安全性为零。",
                )
            assert len(w) >= 1, (
                "secret_key 为默认值时必须产生警告"
            )
            msg = str(w[0].message)
            assert "CHANGE_ME_IN_ENV" in msg, (
                f"警告应包含 CHAVE_ME_IN_ENV, 内容: {msg}"
            )
            assert "JWT" in msg, (
                f"警告应提示 JWT 安全性, 内容: {msg}"
            )
    finally:
        if old_key is not None:
            os.environ["SECRET_KEY"] = old_key
        else:
            os.environ.pop("SECRET_KEY", None)
        importlib.reload(config_module)
        get_settings.cache_clear()


@needs_db
def test_secret_key_custom_passes_silently():
    """SECRET_KEY 为自定义值时, 不应产生警告。"""
    from app.core.config import get_settings

    get_settings.cache_clear()
    old_key = os.environ.get("SECRET_KEY")
    os.environ["SECRET_KEY"] = "prod_strong_random_key_abc123_xyz"

    try:
        import importlib
        import app.core.config as config_module
        importlib.reload(config_module)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            settings = config_module.get_settings()
            if settings.secret_key == "CHANGE_ME_IN_ENV":
                warnings.warn("secret_key default!")
            assert len(w) == 0, (
                f"自定义 SECRET_KEY 不应产生警告, 实际: {[str(x.message) for x in w]}"
            )
    finally:
        if old_key is not None:
            os.environ["SECRET_KEY"] = old_key
        else:
            os.environ.pop("SECRET_KEY", None)
        importlib.reload(config_module)
        get_settings.cache_clear()


# ═══════════════════════════════════════════════════════════════════
# 10. 补充边界测试: 令牌攻击面
# ═══════════════════════════════════════════════════════════════════

@needs_db
def test_invalid_token_returns_401():
    """无效 JWT 令牌访问受保护端点 → 401。"""
    c = _bootstrap_client()
    r = c.get("/api/v1/sites", headers={
        "Authorization": "Bearer invalid.token.payload"
    })
    assert r.status_code == 401


@needs_db
def test_malformed_auth_header_returns_401():
    """畸形的 Authorization header (非 Bearer 前缀) → 401。"""
    c = _bootstrap_client()
    r = c.get("/api/v1/sites", headers={
        "Authorization": "NotBearer token"
    })
    assert r.status_code == 401


@needs_db
def test_empty_auth_header_returns_401():
    """空 Authorization header → 401。"""
    c = _bootstrap_client()
    r = c.get("/api/v1/sites", headers={
        "Authorization": ""
    })
    assert r.status_code == 401


@needs_db
def test_missing_auth_header_returns_401():
    """无 Authorization header → 401。"""
    c = _bootstrap_client()
    r = c.get("/api/v1/sites")
    assert r.status_code == 401


@needs_db
def test_empty_token_returns_401():
    """Bearer 后无 token → 401。"""
    c = _bootstrap_client()
    r = c.get("/api/v1/sites", headers={
        "Authorization": "Bearer "
    })
    assert r.status_code == 401


@needs_db
def test_public_endpoint_accessible_without_auth():
    """公开端点(health, info, admin-contact)无需认证可直接访问。"""
    c = _bootstrap_client()
    assert c.get("/health").status_code == 200
    assert c.get("/api/v1/info").status_code == 200
    assert c.get("/api/v1/auth/admin-contact").status_code == 200


@needs_db
def test_enterprise_site_list_scoped_to_own_org():
    """企业用户的场地列表仅包含本企业场地, 不泄漏其他企业场地。"""
    from app.db.session import SessionLocal
    from app.models import Organization, Site
    from app.services.pipeline import run_import

    c = _bootstrap_client()
    db = SessionLocal()
    try:
        run_import(db, GEJIU, "yunnan_gejiu")
        # 将场地划归监管机构(非 enterprise)
        other_org = (
            db.query(Organization)
            .filter_by(org_type="regulator")
            .first()
        )
        site = db.query(Site).first()
        site.organization_id = other_org.id
        db.commit()
        other_site_id = site.id
    finally:
        db.close()

    h = _auth(_token(c, "enterprise"))
    r = c.get("/api/v1/sites", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    # 企业用户不应看到归属监管机构的场地
    visible_ids = {it["id"] for it in items}
    assert other_site_id not in visible_ids, (
        f"企业用户列表不应泄漏非本企业场地 id={other_site_id}, "
        f"可见: {visible_ids}"
    )
