"""D13 认证/授权/隔离测试 (覆盖 AC-01 登录, AC-16 日志, AC-17 权限拦截+企业隔离)。需 venv。"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_auth.db")


def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has("sqlalchemy", "fastapi"), reason="需 venv")


def _client():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.main import app
    bootstrap()
    return TestClient(app)


def _login(c, username, password="Demo@2026"):
    return c.post("/api/v1/auth/login", json={"username": username, "password": password})


@needs_db
def test_login_success_and_fail():
    c = _client()
    r = _login(c, "admin")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert "admin" in body["user"]["roles"]
    # 错误密码
    assert _login(c, "admin", "wrong").status_code == 401


@needs_db
def test_login_audit_logged():
    from app.db.session import SessionLocal
    from app.models import AuditLog
    c = _client()
    _login(c, "admin")
    _login(c, "admin", "wrong")
    db = SessionLocal()
    try:
        assert db.query(AuditLog).filter_by(action="login", result="success").count() >= 1
        assert db.query(AuditLog).filter_by(action="login", result="fail").count() >= 1
    finally:
        db.close()


@needs_db
def test_unauthenticated_rejected():
    c = _client()
    assert c.get("/api/v1/sites").status_code == 401
    assert c.post("/api/v1/sites/1/report").status_code == 401


@needs_db
def test_permission_denied_for_agency_report():
    """第三方机构无 report:generate 权限 -> 403 (AC-17 权限拦截)。"""
    c = _client()
    tok = _login(c, "agency").json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.post("/api/v1/sites/1/report", headers=h)
    assert r.status_code == 403  # 权限不足, 而非 401/404


@needs_db
def test_enterprise_data_isolation():
    """企业用户只能看到本企业场地 (AC-17 企业隔离)。"""
    from app.db.session import SessionLocal
    from app.models import Organization, Site
    from app.services.pipeline import run_import
    c = _client()
    # 管理员导入个旧(归属示范企业A)
    admin = _login(c, "admin").json()
    ah = {"Authorization": f"Bearer {admin['access_token']}"}
    # 直接用服务导入并把场地划归企业A
    db = SessionLocal()
    try:
        run_import(db, GEJIU, "yunnan_gejiu")
        other_org = db.query(Organization).filter(Organization.org_type == "regulator").first()
        site = db.query(Site).first()
        site.organization_id = other_org.id  # 划给非企业A
        db.commit()
        site_id = site.id
    finally:
        db.close()
    # 企业用户(属企业A)登录, 不应看到归属他人企业的场地
    ent = _login(c, "enterprise").json()
    eh = {"Authorization": f"Bearer {ent['access_token']}"}
    listing = c.get("/api/v1/sites", headers=eh).json()
    assert all(it["id"] != site_id for it in listing["items"])
    # 直接访问他企业场地详情 -> 403
    assert c.get(f"/api/v1/sites/{site_id}", headers=eh).status_code == 403
    # 管理员可访问
    assert c.get(f"/api/v1/sites/{site_id}", headers=ah).status_code == 200
