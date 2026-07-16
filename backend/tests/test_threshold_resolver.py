"""P0-2 动态阈值选择测试。

测试 pH 分级阈值正确选择:
- pH=5.0 → pH<=5.5 档
- pH=6.0 → 5.5<pH<=6.5 档
- pH=7.0 → 6.5<pH<=7.5 档
- pH=8.0 → pH>7.5 档
- 缺失 pH → ambiguous
- eco 轨道第二类用地
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal
from app.models import StandardThreshold
from app.services.threshold_resolver import resolve_threshold_from_db


@pytest.fixture(scope="module")
def db():
    """共享一个 DB 连接。确保 StandardThreshold 种子数据存在。"""
    from app.db.init_db import create_all
    create_all()
    d = SessionLocal()
    # 如果测试库没有阈值数据，从种子加载
    if d.query(StandardThreshold).count() == 0:
        try:
            from app.db.load_standard_thresholds import load
            load(d)
            d.commit()
        except Exception:
            pass
    yield d
    d.close()


class TestP02DynamicThreshold:
    """P0-2: 按 pH 分级选择数据库阈值"""

    def test_cd_low_pH(self, db):
        """Cd, pH=5.0 → pH<=5.5 档 (limit=0.3)"""
        r = resolve_threshold_from_db(db, "Cd_mgkg", track="prod", site_pH=5.0)
        assert r["threshold_resolution_status"] == "resolved"
        assert r["threshold_value"] == 0.3
        assert "5.5" in r["pH_condition"]

    def test_cd_mid_pH(self, db):
        """Cd, pH=6.0 → 5.5<pH<=6.5 档"""
        r = resolve_threshold_from_db(db, "Cd_mgkg", track="prod", site_pH=6.0)
        assert r["threshold_resolution_status"] == "resolved"
        assert r["threshold_value"] == 0.3

    def test_cd_high_pH(self, db):
        """Cd, pH=8.0 → pH>7.5 档 (limit=0.6)"""
        r = resolve_threshold_from_db(db, "Cd_mgkg", track="prod", site_pH=8.0)
        assert r["threshold_resolution_status"] == "resolved"
        assert r["threshold_value"] == 0.6
        assert "7.5" in r["pH_condition"]

    def test_cd_boundary_55(self, db):
        """Cd, pH=5.5 边界 → pH<=5.5 档"""
        r = resolve_threshold_from_db(db, "Cd_mgkg", track="prod", site_pH=5.5)
        assert r["threshold_resolution_status"] == "resolved"
        assert r["threshold_value"] == 0.3

    def test_missing_pH_ambiguous(self, db):
        """Cd, 缺 pH → ambiguous (GB15618 需要 pH 分档)"""
        r = resolve_threshold_from_db(db, "Cd_mgkg", track="prod", site_pH=None)
        assert r["threshold_resolution_status"] == "ambiguous"
        assert r["review_required"] is True

    def test_eco_track_second_class(self, db):
        """eco 轨道 → 第二类用地 (Cd=65 mg/kg)"""
        r = resolve_threshold_from_db(db, "Cd_mgkg", track="eco")
        assert r["threshold_resolution_status"] == "resolved"
        assert r["threshold_value"] == 65.0  # GB36600 第二类用地

    def test_as_pH_grading(self, db):
        """As 的 pH 分级: pH<=5.5→40, 6.5<pH<=7.5→30, pH>7.5→25"""
        r1 = resolve_threshold_from_db(db, "As_mgkg", track="prod", site_pH=5.0)
        assert r1["threshold_value"] == 40.0
        r3 = resolve_threshold_from_db(db, "As_mgkg", track="prod", site_pH=7.0)
        assert r3["threshold_value"] == 30.0
        r4 = resolve_threshold_from_db(db, "As_mgkg", track="prod", site_pH=8.0)
        assert r4["threshold_value"] == 25.0

    def test_not_found_factor(self, db):
        """不存在因子的阈值 → not_found"""
        r = resolve_threshold_from_db(db, "NonExistent_mgkg", track="prod", site_pH=7.0)
        assert r["threshold_resolution_status"] == "not_found"
        assert r["review_required"] is True

    def test_threshold_metadata_completeness(self, db):
        """阈值元数据完整性: standard/version/unit/source_id"""
        r = resolve_threshold_from_db(db, "Cd_mgkg", track="prod", site_pH=7.0)
        assert r["threshold_standard"]
        assert r["threshold_version"]
        assert r["threshold_unit"]
        assert r["threshold_source_id"] is not None
