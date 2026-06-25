"""D3-D4 数据闭环测试 (覆盖 AC-02~AC-08)。

- 解析/校验类用例仅需 pandas。
- 入库/API 类用例需 backend 依赖 (sqlalchemy/fastapi), 在 venv/docker 环境运行:
    cd backend && DATABASE_URL=sqlite:///./test.db pytest -q
"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")
KB = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")



# ---------- 解析与校验 (pandas) ----------
def test_parse_gejiu_counts():
    from app.services.import_service import load_mapping, parse
    m = load_mapping("yunnan_gejiu")
    p = parse(GEJIU, m)
    assert p.n_points == 134, f"采样点应134, 实际{p.n_points}"
    assert p.n_measurements == 134 * 14, f"检测槽应1876, 实际{p.n_measurements}"
    assert p.site["site_code"] == "GJ-2025-001"
    assert p.site["longitude"] is not None  # 中心点已计算


def test_threshold_resolver_ph_segmented():
    from app.services.threshold_resolver import build_pollutant_limits, resolve_limit
    lim = build_pollutant_limits(KB)
    # 砷 其他用地: pH=6.8 应落在 6.5<pH≤7.5 段, 限值 30
    seg = resolve_limit(lim, "砷", 6.8, scope="production", land_subtype="其他用地")
    assert seg and seg["limit"] == 30.0, seg


def test_validation_flags_heavy_metal_exceed():
    from app.services.import_service import load_mapping, parse
    from app.services.threshold_resolver import build_pollutant_limits
    from app.services.validation_service import validate
    m = load_mapping("yunnan_gejiu")
    p = parse(GEJIU, m)
    rep = validate(p, m, pollutant_limits=build_pollutant_limits(KB))
    assert rep["passed"] is True          # 无阻断性错误
    assert rep["n_errors"] == 0
    assert rep["n_exceed"] > 100          # 个旧重金属大量超标
    assert set(rep["summary"]["exceed_factors"]) >= {"砷", "铅", "铜"}


# ---------- 入库与 API (需 sqlalchemy/fastapi) ----------
def _has_backend_deps():
    try:
        import sqlalchemy  # noqa: F401
        import fastapi  # noqa: F401
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has_backend_deps(),
                              reason="需 sqlalchemy/fastapi (venv/docker 环境)")
needs_data = pytest.mark.skipif(not os.path.exists(GEJIU),
                                reason="缺少个旧原始数据 data/raw/3.20250731_...(云南个旧)")


@needs_db
def test_full_import_to_longtable(tmp_path):
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.models import Measurement, SamplingPoint, Site
    from app.services.pipeline import run_import
    bootstrap()
    load_kb()
    db = SessionLocal()
    try:
        res = run_import(db, GEJIU, "yunnan_gejiu")
        assert res["n_points"] == 134
        assert res["n_measurements"] == 134 * 14  # 个旧无缺失值, 全入库
        assert res["validation"]["passed"] is True
        site = db.get(Site, res["site_id"])
        assert site.site_code == "GJ-2025-001"
        assert db.query(SamplingPoint).filter_by(site_id=site.id).count() == 134
        assert db.query(Measurement).filter_by(site_id=site.id).count() == 134 * 14
    finally:
        db.close()


@needs_db
def test_api_sites_and_measurements():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.main import app
    from app.services.pipeline import run_import
    bootstrap()
    load_kb()
    db = SessionLocal()
    try:
        run_import(db, GEJIU, "yunnan_gejiu")
    finally:
        db.close()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.get("/api/v1/sites", headers=h)
    assert r.status_code == 200 and r.json()["total"] >= 1
    sid = r.json()["items"][0]["id"]
    assert c.get(f"/api/v1/sites/{sid}", headers=h).json()["n_measurements"] == 134 * 14
    assert len(c.get(f"/api/v1/sites/{sid}/points", headers=h).json()) == 134
    mr = c.get(f"/api/v1/sites/{sid}/measurements", params={"factor": "砷"}, headers=h)
    assert mr.json()["total"] == 134
    # 未带令牌应被拒
    assert c.get("/api/v1/sites").status_code == 401


@needs_db
@needs_data
def test_api_batch_import_and_overview_badges():
    """批量导入 + 场地概览徽章(n_factors/n_exceed/data_quality)。"""
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.main import app
    bootstrap()
    load_kb()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 批量导入: 同一个文件传两次(两次导入会建两个场地实例, 验证多文件串行不竞态)
    with open(GEJIU, "rb") as f1, open(GEJIU, "rb") as f2:
        r = c.post("/api/v1/import/batch", headers=h,
                   data={"mapping_id": "yunnan_gejiu"},
                   files=[("files", ("a.xlsx", f1, "application/vnd.ms-excel")),
                          ("files", ("b.xlsx", f2, "application/vnd.ms-excel"))])
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2 and body["succeeded"] == 2 and body["failed"] == 0
    assert len(body["results"]) == 2
    # 场地列表概览徽章: n_factors/n_exceed/data_quality 字段存在且合理
    sites = c.get("/api/v1/sites", params={"size": 5}, headers=h).json()
    item = sites["items"][0]
    assert "n_factors" in item and item["n_factors"] > 0
    assert "n_exceed" in item and item["n_exceed"] >= 0
    assert "data_quality" in item
    # 个旧重金属场地应有超标记录
    assert any(it["n_exceed"] > 0 for it in sites["items"])


@needs_db
@needs_data
def test_import_skip_duplicate_and_new_version():
    """裴总 P1-3: 同文件二次导入默认 skip(不造新场地); new_version 建新 site_code。"""
    from app.db.bootstrap import main as bootstrap
    from app.db.session import SessionLocal
    from app.models import Site
    from app.services.pipeline import run_import
    bootstrap()
    db = SessionLocal()
    try:
        r1 = run_import(db, GEJIU, "yunnan_gejiu")
        assert r1.get("action", "created") == "created"
        n1 = db.query(Site).count()
        # 二次默认 skip → 不增场地, 复用同 site_id
        r2 = run_import(db, GEJIU, "yunnan_gejiu", on_conflict="skip")
        assert r2["action"] == "skipped", f"应 skip, 实际 {r2.get('action')}"
        assert r2["site_id"] == r1["site_id"]
        assert db.query(Site).count() == n1, "skip 不应新增场地"
        # new_version → 建新场地
        r3 = run_import(db, GEJIU, "yunnan_gejiu", on_conflict="new_version")
        assert r3["action"] == "new_version"
        assert r3["site_id"] != r1["site_id"]
        assert db.query(Site).count() == n1 + 1, "new_version 应新增 1 个场地"
    finally:
        db.close()
