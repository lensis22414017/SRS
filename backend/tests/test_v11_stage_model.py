"""v1.1 G5: 修复前/后数据分离与旧库升级。"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

BACKEND = Path(__file__).resolve().parents[1]


def _alembic(url: str, *args: str):
    env = os.environ.copy(); env["DATABASE_URL"] = url
    r = subprocess.run([sys.executable, "-m", "alembic", "-c", str(BACKEND / "alembic.ini"), *args],
                       cwd=BACKEND, env=env, text=True, capture_output=True, timeout=180)
    assert r.returncode == 0, r.stdout + r.stderr


def test_runtime_upgrade_adds_columns_and_preserves_rows(tmp_path):
    from app.db.init_db import upgrade_v11_columns
    db = tmp_path / "legacy_v102.db"
    with sqlite3.connect(db) as c:
        c.executescript("""
            CREATE TABLE import_batches (id INTEGER PRIMARY KEY, site_id INTEGER, source_file VARCHAR(300),
                row_count INTEGER, status VARCHAR(20));
            INSERT INTO import_batches VALUES (1, 7, 'gejiu.xlsx', 134, 'success');
            CREATE TABLE measurements (id INTEGER PRIMARY KEY, site_id INTEGER, value FLOAT, data_origin VARCHAR(30));
            INSERT INTO measurements VALUES (1, 7, 401.0, 'field'), (2, 7, 9505.0, 'field');
        """)
    eng = create_engine(f"sqlite:///{db}")
    added = upgrade_v11_columns(eng)
    assert "import_batches.stage" in added and "measurements.stage" in added
    assert upgrade_v11_columns(eng) == []  # 幂等
    with sqlite3.connect(db) as c:
        assert c.execute("SELECT id, source_file, row_count, stage, data_origin FROM import_batches").fetchall() == \
            [(1, "gejiu.xlsx", 134, "pre_remediation", "field")]
        assert c.execute("SELECT value, stage FROM measurements ORDER BY id").fetchall() == \
            [(401.0, "pre_remediation"), (9505.0, "pre_remediation")]


def test_alembic_chain_to_0007_and_back(tmp_path):
    url = f"sqlite:///{tmp_path / 'fresh.db'}"
    _alembic(url, "upgrade", "head")
    insp = inspect(create_engine(url))
    tables = set(insp.get_table_names())
    assert {"ssui_import_batches", "ssui_records", "utilization_decisions"} <= tables
    assert "stage" in {c["name"] for c in insp.get_columns("measurements")}
    assert {"stage", "subproject", "data_origin", "method_version"} <= {c["name"] for c in insp.get_columns("import_batches")}
    _alembic(url, "downgrade", "0006_site_original_code")
    insp = inspect(create_engine(url))
    assert "ssui_records" not in set(insp.get_table_names())
    assert "stage" not in {c["name"] for c in insp.get_columns("measurements")}
    _alembic(url, "upgrade", "head")


def test_post_remediation_measurements_never_enter_pre_stage_calculations():
    """课题一/二计算只读修复前测值: 写入一条修复后测值, 重构评价输入不变。"""
    from app.db.session import SessionLocal
    from app.db.init_db import create_all
    from app.models import FactorDictionary, Measurement, SamplingPoint, Site, POST_REMEDIATION
    from app.services import evaluation_service as ES
    create_all()
    db = SessionLocal()
    try:
        site = Site(site_code="STAGE-TEST-A", name="阶段隔离测试", pollution_type="heavy_metal", land_use_type="耕地")
        db.add(site); db.flush()
        pt = SamplingPoint(site_id=site.id, point_code="P1"); db.add(pt); db.flush()
        f = db.query(FactorDictionary).filter_by(factor_name="镉").first()
        if f is None:
            f = FactorDictionary(factor_code="Cd_stage_test", factor_name="镉"); db.add(f); db.flush()
        db.add(Measurement(site_id=site.id, sampling_point_id=pt.id, factor_id=f.id, value=0.2))
        db.flush()
        before = ES._load_point_matrix(db, site.id) if hasattr(ES, "_load_point_matrix") else None
        db.add(Measurement(site_id=site.id, sampling_point_id=pt.id, factor_id=f.id, value=99.0,
                           stage=POST_REMEDIATION))
        db.flush()
        vals = [m.value for m in db.query(Measurement).filter(Measurement.site_id == site.id).all()]
        assert sorted(vals) == [0.2, 99.0]
        from app.models import PRE_REMEDIATION
        pre = [m.value for m in db.query(Measurement).filter(
            Measurement.site_id == site.id, Measurement.stage == PRE_REMEDIATION).all()]
        assert pre == [0.2]
        if before is not None:
            assert ES._load_point_matrix(db, site.id) == before
    finally:
        db.rollback(); db.close()


def test_compute_services_filter_pre_remediation_stage():
    """静态门禁: 所有课题一/二计算路径的测值查询都带阶段过滤。"""
    import re
    for rel in ["app/services/diagnosis_service.py", "app/services/evaluation_service.py",
                "app/services/recommend_service.py", "app/api/diagnosis.py"]:
        src = (BACKEND / rel).read_text(encoding="utf-8")
        for m in re.finditer(r"Measurement\.site_id == site_id", src):
            tail = src[m.end(): m.end() + 60]
            assert "Measurement.stage == PRE_REMEDIATION" in tail, f"{rel}: 缺少阶段过滤 @ {m.start()}"
