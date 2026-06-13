"""标准阈值库入库测试。"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_standard_thresholds.db")


def test_standard_thresholds_table_and_loader():
    from app.db.init_db import create_all
    from app.db.load_standard_thresholds import load
    from app.db.session import SessionLocal
    from app.models import StandardThreshold

    create_all()
    db = SessionLocal()
    try:
        db.query(StandardThreshold).delete()
        db.commit()
        count = load(db)
        assert count >= 20
        codes = {r.standard_code for r in db.query(StandardThreshold).all()}
        assert {"GB 15618-2018", "GB 36600-2018", "HJ 25.5-2018"} <= codes

        as_agri = (db.query(StandardThreshold)
                   .filter_by(standard_code="GB 15618-2018", factor_name="As",
                              land_use_type="农用地", pH_condition="pH>7.5")
                   .first())
        assert as_agri and as_agri.screening_value == 25
        assert as_agri.source_reference.startswith("https://www.mee.gov.cn/")

        hj = db.query(StandardThreshold).filter_by(standard_code="HJ 25.5-2018").first()
        assert hj and hj.screening_value is None
        assert "效果评估" in (hj.notes or "")
    finally:
        db.close()
