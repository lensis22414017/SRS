"""企业数据隔离回归测试: diagnosis/evaluation/recommendation 接口必须做 assert_site_access。

修复前: 这些接口缺 assert_site_access, 企业用户可访问他企业场地(数据串台)。
本测试确保企业用户对非本企业场地的诊断/评价/推荐读接口返回 403。
需完整 venv(fastapi/sqlalchemy); 无则 skip。
"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_isolation.db")


def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has("sqlalchemy", "fastapi"), reason="需 venv")


@needs_db
def test_enterprise_cannot_access_other_org_analysis():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import Organization, Site
    from app.services.pipeline import run_import
    bootstrap()
    db = SessionLocal()
    try:
        run_import(db, GEJIU, "yunnan_gejiu")
        other = db.query(Organization).filter(Organization.org_type == "regulator").first()
        site = db.query(Site).first()
        site.organization_id = other.id  # 划归非企业A
        db.commit()
        site_id = site.id
    finally:
        db.close()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "enterprise", "password": "Demo@2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 三个分析接口的读端点都应 403(企业用户无权访问他企业场地)
    for path in (f"/api/v1/sites/{site_id}/diagnosis",
                 f"/api/v1/sites/{site_id}/evaluation",
                 f"/api/v1/sites/{site_id}/recommendation"):
        assert c.get(path, headers=h).status_code == 403, f"{path} 未做企业隔离"
    # 触发端点(POST)同样应 403
    assert c.post(f"/api/v1/sites/{site_id}/diagnosis", headers=h).status_code == 403


@needs_db
def test_admin_can_access():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.main import app
    bootstrap()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.get("/api/v1/sites", headers=h)
    if r.json()["total"] == 0:
        pytest.skip("无场地")
    sid = r.json()["items"][0]["id"]
    # 管理员访问不应 403(可能 404 暂无结果, 但不能 403)
    assert c.get(f"/api/v1/sites/{sid}/evaluation", headers=h).status_code != 403
