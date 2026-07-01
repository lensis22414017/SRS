"""v1.0 P0-1: 检测限导入端到端测试 — <0.001 / ND / 未检出 的完整管线持久化。

不直接构造 Measurement — 模拟真实 Excel/CSV 导入流程, 验证:
1. 解析层: _parse_detection_limit 正确识别三模式
2. 传输层: ParsedMeasurement 携带 original_value_text/qualifier/detection_limit
3. 入库层: Measurement 正确写入所有监管字段
"""
import pytest
from app.db.session import SessionLocal
from app.models import Measurement, Site, SamplingPoint, FactorDictionary, ImportBatch
from app.services.import_service import (
    _parse_detection_limit, ParsedMeasurement, ParsedPoint, ParsedSite,
)
from app.services.ingest_service import ingest


class TestDetectionLimitParsing:
    """解析层: _parse_detection_limit 单元测试"""

    def test_less_than(self):
        dl = _parse_detection_limit("<0.001")
        assert dl["value"] == pytest.approx(0.0005)
        assert dl["detection_limit"] == pytest.approx(0.001)
        assert dl["qualifier"] == "<"
        assert dl["original_value_text"] == "<0.001"

    def test_less_than_with_space(self):
        dl = _parse_detection_limit("< 0.5")
        assert dl["detection_limit"] == pytest.approx(0.5)
        assert dl["qualifier"] == "<"

    def test_less_than_equal(self):
        dl = _parse_detection_limit("<=0.01")
        assert dl["detection_limit"] == pytest.approx(0.01)
        assert dl["qualifier"] in ("<", "<=")

    def test_nd_uppercase(self):
        dl = _parse_detection_limit("ND")
        assert dl["value"] is None
        assert dl["original_value_text"] == "ND"
        assert dl["qualifier"] == "ND"
        assert dl["is_below_detection"]

    def test_nd_lowercase(self):
        dl = _parse_detection_limit("nd")
        assert dl["original_value_text"] == "nd"
        assert dl["is_below_detection"]

    def test_nd_with_dots(self):
        dl = _parse_detection_limit("N.D.")
        assert dl["is_below_detection"]

    def test_chinese_weijianchu(self):
        dl = _parse_detection_limit("未检出")
        assert dl["value"] is None
        assert dl["qualifier"] == "ND"
        assert dl["is_below_detection"]
        assert dl["original_value_text"] == "未检出"

    def test_chinese_diyujianchuxian(self):
        dl = _parse_detection_limit("低于检出限")
        assert dl["qualifier"] == "ND"

    def test_chinese_jianchuxianyixia(self):
        dl = _parse_detection_limit("检出限以下")
        assert dl["is_below_detection"]

    def test_chinese_diyujiancexian(self):
        dl = _parse_detection_limit("低于检测限")
        assert dl["qualifier"] == "ND"

    def test_normal_number(self):
        dl = _parse_detection_limit("3.14")
        assert dl["value"] == pytest.approx(3.14)
        assert dl["detection_limit"] is None
        assert not dl["is_below_detection"]

    def test_slash_missing(self):
        dl = _parse_detection_limit("/")
        assert dl["value"] is None
        assert dl["original_value_text"] == "/"

    def test_dash_missing(self):
        dl = _parse_detection_limit("--")
        assert dl["value"] is None


class TestParsedMeasurementFields:
    """传输层: ParsedMeasurement 携带所有监管字段"""

    def test_parsed_measurement_has_new_fields(self):
        pm = ParsedMeasurement(
            factor_code="Cd", factor_name="镉", value=0.5, unit="mg/kg",
            original_value_text="<1.0", qualifier="<", detection_limit=1.0,
            method="ICP-MS", is_below_detection=False, replicate_group_id="REP-01",
        )
        assert pm.original_value_text == "<1.0"
        assert pm.qualifier == "<"
        assert pm.detection_limit == 1.0
        assert pm.replicate_group_id == "REP-01"


class TestIngestPersistence:
    """入库层: Measurement 持久化包含全部监管字段 (端到端)"""

    def test_ingest_persists_detection_limit_fields(self):
        """通过真实 ingest() 导入模拟数据, 验证 original_value_text/qualifier/detection_limit 入库"""
        db = SessionLocal()
        try:
            site_code = "__test_dl_site__"
            existing = db.query(Site).filter_by(site_code=site_code).first()
            if existing:
                db.query(Measurement).filter_by(site_id=existing.id).delete()
                db.query(SamplingPoint).filter_by(site_id=existing.id).delete()
                db.query(ImportBatch).filter_by(site_id=existing.id).delete()
                db.delete(existing)
                db.commit()
            fac_cd = db.query(FactorDictionary).filter_by(factor_code="Cd").first()
            if not fac_cd:
                fac_cd = FactorDictionary(factor_code="Cd", factor_name="镉")
                db.add(fac_cd)
                db.commit()
            fac_pb = db.query(FactorDictionary).filter_by(factor_code="Pb").first()
            if not fac_pb:
                fac_pb = FactorDictionary(factor_code="Pb", factor_name="铅")
                db.add(fac_pb)
                db.commit()

            parsed = ParsedSite(
                site={"site_code": site_code, "province": "测试省"},
                source_file="test_dl.xlsx",
                factor_defs=[
                    {"factor_code": "Cd", "factor_name": "镉", "unit": "mg/kg"},
                    {"factor_code": "Pb", "factor_name": "铅", "unit": "mg/kg"},
                ],
                points=[
                    ParsedPoint(
                        point_code="DL-001", longitude=120.0, latitude=30.0,
                        measurements=[
                            ParsedMeasurement(factor_code="Cd", factor_name="镉",
                                value=0.0005, unit="mg/kg",
                                original_value_text="<0.001", qualifier="<",
                                detection_limit=0.001, method="ICP-MS"),
                            ParsedMeasurement(factor_code="Pb", factor_name="铅",
                                value=None, unit="mg/kg",
                                original_value_text="ND", qualifier="ND",
                                method="ICP-MS", is_below_detection=True),
                        ]
                    ),
                    ParsedPoint(
                        point_code="DL-002", longitude=120.1, latitude=30.1,
                        measurements=[
                            ParsedMeasurement(factor_code="Cd", factor_name="镉",
                                value=None, unit="mg/kg",
                                original_value_text="未检出", qualifier="ND",
                                method="AAS", is_below_detection=True),
                        ]
                    ),
                ],
            )

            result = ingest(db, parsed, on_conflict="overwrite")
            assert result["n_measurements"] == 3

            meas = db.query(Measurement).filter_by(site_id=result["site_id"]).all()
            assert len(meas) == 3

            m_cd = [m for m in meas if m.value is not None and m.value > 0][0]
            assert m_cd.original_value_text == "<0.001"
            assert m_cd.qualifier == "<"
            assert m_cd.detection_limit == 0.001
            assert not m_cd.is_below_detection
            assert m_cd.value == pytest.approx(0.0005)

            m_nd = [m for m in meas if m.original_value_text == "ND"][0]
            assert m_nd.value is None
            assert m_nd.qualifier == "ND"
            assert m_nd.is_below_detection

            m_wjc = [m for m in meas if m.original_value_text == "未检出"][0]
            assert m_wjc.value is None
            assert m_wjc.qualifier == "ND"
            assert m_wjc.is_below_detection

            for m in meas:
                assert m.qa_status == "raw"
                assert m.evidence_level == "A"
                assert m.data_origin == "field"

        finally:
            db.rollback()
            db.close()
