"""地图 API 回归测试: GeoJSON 图层、天地图代理配置、企业隔离。"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")



def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has("sqlalchemy", "fastapi"), reason="需 venv")


@needs_db
def test_site_map_layers_geojson_and_exceedance():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.main import app
    from app.services.pipeline import run_import
    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        sid = imp["site_id"]
    finally:
        db.close()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    r = c.get(f"/api/v1/sites/{sid}/map/layers",
              headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    data = r.json()
    assert data["geojson"]["type"] == "FeatureCollection"
    assert len(data["geojson"]["features"]) == 134
    assert len(data["pollutants"]) >= 10
    # 风险分级统一为 8 级(brief 4.8): none/low/med1/med2/high/severe/extreme/unknown
    # 与后端 _risk()、前端 SiteMap.excColor 三者一致。
    assert {x["risk_level"] for x in data["legend"]} == {
        "none", "low", "med1", "med2", "high", "severe", "extreme", "unknown"}
    features = [f for f in data["geojson"]["features"]
                if f["geometry"]["coordinates"][0] is not None]
    assert features
    assert any((f["properties"]["selected"] or {}).get("exceedance") is not None
               for f in features)


@needs_db
def test_site_map_layers_filter_factor():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.main import app
    from app.services.pipeline import run_import
    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        sid = imp["site_id"]
    finally:
        db.close()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    r = c.get(f"/api/v1/sites/{sid}/map/layers", params={"factor": "砷"},
              headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    for feat in r.json()["geojson"]["features"]:
        for m in feat["properties"]["measurements"]:
            assert m["factor_code"] == "砷" or m["factor_name"] == "砷"


def test_gaode_tile_proxy_no_key_returns_response_or_502(monkeypatch):
    """高德瓦片代理: 无 key 时走公共通道; 网络不通时返回 502(不得返回 503/401)。"""
    from fastapi import HTTPException
    from app.api.map import gaode_tile
    from app.core.config import get_settings
    monkeypatch.delenv("GAODE_KEY", raising=False)
    get_settings.cache_clear()
    try:
        resp = gaode_tile(8, 215, 105)  # 云南个旧附近 z8 瓦片
        # 在线时应返回 JPEG
        assert resp.status_code == 200
        assert resp.media_type == "image/jpeg"
    except HTTPException as e:
        # 沙盒/离线环境允许 502; 不应出现 503/401/403
        assert e.status_code == 502, f"期望 502 但得到 {e.status_code}: {e.detail}"
    finally:
        get_settings.cache_clear()


def test_tianditu_tile_requires_backend_key(monkeypatch):
    from fastapi import HTTPException
    from app.api.map import tianditu_tile
    from app.core.config import get_settings
    monkeypatch.delenv("TIANDITU_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as e:
        tianditu_tile("img", 1, 1, 1)
    assert e.value.status_code == 503
    get_settings.cache_clear()


# ============ 离线行政区边界(三级金字塔) ============
GEO_DIR = os.path.join(ROOT, "data", "geo")
needs_geo = pytest.mark.skipif(not os.path.exists(os.path.join(GEO_DIR, "geo_index.json")),
                               reason="离线行政区数据未安装, 运行 scripts/download_admin_boundaries.py")


@needs_db
@needs_geo
def test_geo_index_summary():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.main import app
    bootstrap()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.get("/api/v1/map/geo/index", headers=h)
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["n_provinces"] >= 30   # 全国省级行政区
    assert s["n_prefectures"] >= 400
    assert s["n_counties"] >= 2000


@needs_db
@needs_geo
def test_geo_boundaries_three_levels():
    """三级金字塔: 省(全国) → 地市(云南) → 县(红河州), 个旧市必须找到。"""
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.main import app
    bootstrap()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    # L1 全国省界
    r1 = c.get("/api/v1/map/geo/boundaries", params={"level": "province"}, headers=h)
    assert r1.status_code == 200
    assert len(r1.json()["features"]) >= 30

    # L2 云南省地市
    r2 = c.get("/api/v1/map/geo/boundaries",
               params={"level": "prefecture", "adcode": 530000}, headers=h)
    assert r2.status_code == 200
    p_names = [f["properties"]["name"] for f in r2.json()["features"]]
    assert "红河哈尼族彝族自治州" in p_names

    # L3 红河州县级, 含个旧市
    r3 = c.get("/api/v1/map/geo/boundaries",
               params={"level": "county", "adcode": 532500}, headers=h)
    assert r3.status_code == 200
    c_names = [f["properties"]["name"] for f in r3.json()["features"]]
    assert "个旧市" in c_names

    # 缺 adcode 应 400
    assert c.get("/api/v1/map/geo/boundaries", params={"level": "prefecture"},
                 headers=h).status_code == 400
    # 不存在的 adcode 应 404
    assert c.get("/api/v1/map/geo/boundaries",
                 params={"level": "prefecture", "adcode": 999999}, headers=h).status_code == 404
