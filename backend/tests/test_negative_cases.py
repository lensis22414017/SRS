#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 审计第 10.7 节: 负向测试(缺测/缺阈值/缺模型/低置信度)。

验证系统在数据缺失场景下的正确降级行为, 不产生虚假结论。
"""
import os
import sys
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)


@pytest.fixture
def fresh_db():
    from app.db.session import SessionLocal, reset_engine_for_tests
    from app.models import Base
    from app.db import session as _session_mod
    reset_engine_for_tests("sqlite:///./srs_test_session.db")
    Base.metadata.drop_all(bind=_session_mod.engine)
    Base.metadata.create_all(bind=_session_mod.engine)
    from app.db.seed_db import seed_if_empty
    os.environ["SRS_DEMO_SEED"] = "1"
    seed_if_empty()
    return SessionLocal()


def test_missing_threshold_does_not_score_100(fresh_db):
    """缺阈值 → 污染物退出打分(不给100, GPT 5.4)。"""
    sys.path.insert(0, os.path.join(BACKEND, "..", "ml", "evaluation"))
    from reconstruction import score_pollutant
    assert score_pollutant(80.0, None) is None, "缺阈值应退出打分"


def test_low_coverage_insufficient(fresh_db):
    """覆盖率低 → 证据不足(GPT 5.5)。"""
    sys.path.insert(0, os.path.join(BACKEND, "..", "ml", "evaluation"))
    from reconstruction import evaluate
    result = evaluate({"pH": 6.5}, scope="production")
    assert result["grade"] == "证据不足/无法评价"
    assert result.get("is_insufficient") is True


def test_ssui_na_without_economic(fresh_db):
    """SSUI 缺经济数据 → N/A(GPT 6.4)。"""
    sys.path.insert(0, os.path.join(BACKEND, "..", "ml", "evaluation"))
    from ssui import evaluate as ssui_evaluate
    result = ssui_evaluate({"pH": [6.5], "有机质": [30]}, scope="production")
    assert result.get("is_na") is True
    assert result["grade"] == "N/A(数据不足)"


def test_kos_ph_missing_still_identifies_obstacles(fresh_db):
    """KOS pH 缺失 → 用兜底阈值仍识别障碍(GPT 4.10)。"""
    from app.services.kos_service import run_kos_diagnosis
    db = fresh_db
    result = run_kos_diagnosis(
        {"砷_As(mg/kg)": 80.0, "铅_Pb(mg/kg)": 300.0},
        track="prod", subset="all", site_pH=None, db_session=db)
    assert len(result["key_obstacles"]) > 0, "pH 缺失用兜底后必须有障碍"
    db.close()


def test_first_run_empty_business_tables(fresh_db):
    """首启空库: 业务表全 0(GPT 1.1)。"""
    from app.models import Site, Measurement, DiagnosisResult, EvaluationResult
    db = fresh_db
    try:
        assert db.query(Site).count() == 0, "首启 sites 应=0"
        assert db.query(Measurement).count() == 0, "首启 measurements 应=0"
        assert db.query(DiagnosisResult).count() == 0, "首启 diagnosis 应=0"
        assert db.query(EvaluationResult).count() == 0, "首启 evaluation 应=0"
    finally:
        db.close()


def test_first_run_has_reference_tables(fresh_db):
    """首启有参考数据: 角色/权限/因子字典/标准阈值(GPT 1.2)。"""
    from app.models import Role, Permission, FactorDictionary, StandardThreshold
    db = fresh_db
    try:
        assert db.query(Role).count() == 4, f"首启 roles 应=4, 实际{db.query(Role).count()}"
        assert db.query(Permission).count() >= 14, "首启 permissions 应>=14"
        assert db.query(FactorDictionary).count() > 0, "首启 factor_dict 应>0"
        assert db.query(StandardThreshold).count() > 0, "首启 std_thresholds 应>0"
    finally:
        db.close()
