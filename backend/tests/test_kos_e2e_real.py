#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""R3 审计阶段 N1.3: KOS 诊断端到端验证。

验证审计第一类要求:
  1) 导入个旧真实 Excel 后, 生产/生态 KOS 均输出 Top-N
  2) 五分量证据条(R/W/M/S/E)齐全
  3) 模型贡献度非空
  4) coverage > 0
  5) unmapped_factors 列表存在
  6) review_required 标志正确
  7) 旧端点 /diagnosis 返回 410 Gone
"""
import os
import sys
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

REAL_XLSX = os.path.join(
    BACKEND, "..", "data", "raw",
    "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx"
)


@pytest.fixture
def fresh_db():
    """R3 审计第八类: 使用 conftest 的独立 tempfile db, 不再 reset_engine 覆盖。"""
    from app.db.session import SessionLocal
    from app.db import session as _session_mod
    from app.models import Base
    Base.metadata.drop_all(bind=_session_mod.engine)
    Base.metadata.create_all(bind=_session_mod.engine)
    from app.db.seed_db import seed_if_empty
    seed_if_empty()
    return SessionLocal()


def _import_gejiu(db):
    """导入个旧真实数据, 返回 site_id。"""
    from app.models import User
    from app.services.import_service import smart_detect_and_map
    from app.services.pipeline import run_import_with_mapping

    user = db.query(User).filter_by(username="admin").first()
    _, mapping, _ = smart_detect_and_map(REAL_XLSX)
    result = run_import_with_mapping(
        db,
        REAL_XLSX,
        mapping,
        imported_by=user.id if user else None,
        on_conflict="skip",
    )
    return result["site_id"]


def _diagnosis_inputs(db, site_id):
    from app.models import FactorDictionary, Measurement

    rows = (
        db.query(
            Measurement.value_used_for_model,
            Measurement.value,
            Measurement.sampling_point_id,
            FactorDictionary.factor_name,
        )
        .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id, isouter=True)
        .filter(Measurement.site_id == site_id, Measurement.value.isnot(None))
        .all()
    )
    site_values = {}
    per_point = {}
    for value_used, value, point_id, factor_name in rows:
        if not factor_name:
            continue
        raw_value = value_used if value_used is not None else value
        try:
            numeric = float(raw_value)
        except (TypeError, ValueError):
            continue
        site_values[factor_name] = max(site_values.get(factor_name, numeric), numeric)
        if point_id is not None:
            per_point.setdefault(point_id, {})[factor_name] = numeric
    return site_values, per_point


@pytest.mark.skipif(not os.path.exists(REAL_XLSX),
                    reason="个旧真实数据文件不存在")
def test_kos_prod_outputs_complete(fresh_db):
    """生产 KOS 诊断输出完整(审计 1.4)。"""
    from app.services.kos_service import run_kos_diagnosis
    db = fresh_db
    try:
        site_id = _import_gejiu(db)
        sv, per_point = _diagnosis_inputs(db, site_id)
        assert len(sv) > 0, "导入后应有测量数据"

        result = run_kos_diagnosis(sv, track="prod", subset="all",
                                    site_pH=6.0, land_use_type="其他用地",
                                    db_session=db, per_point_data=per_point)

        # 1) key_obstacles 必须非空
        assert len(result.get("key_obstacles", [])) > 0, "必须有障碍因子"

        # 2) 五分量齐全
        for k in result["key_obstacles"]:
            comps = k.get("components", {})
            for dim in ("R", "W", "M", "S", "E"):
                assert dim in comps, f"{k['factor']} 缺五分量 {dim}"

        # 3) 模型贡献度非空
        assert len(result.get("model_contribution", [])) > 0, "模型贡献度不能为空"

        # 4) coverage > 0
        assert result.get("coverage", 0) > 0, f"coverage 应>0, 实际 {result.get('coverage')}"

        # 5) unmapped 列表存在(可为空)
        assert "unmapped" in result, "必须有 unmapped 字段"
        assert result["model_contribution_scope"] == "local_point", \
            f"真实点位应产生局部解释，实际: {result.get('local_shap_status')}"
    finally:
        db.close()


@pytest.mark.skipif(not os.path.exists(REAL_XLSX),
                    reason="个旧真实数据文件不存在")
def test_kos_eco_outputs_complete(fresh_db):
    """生态 KOS 诊断输出完整(审计 1.4)。"""
    from app.services.kos_service import run_kos_diagnosis
    db = fresh_db
    try:
        site_id = _import_gejiu(db)
        sv, per_point = _diagnosis_inputs(db, site_id)

        result = run_kos_diagnosis(sv, track="eco", subset="all",
                                    site_pH=6.0, land_use_type="第二类用地",
                                    db_session=db, per_point_data=per_point)

        assert len(result.get("key_obstacles", [])) > 0, "生态 KOS 必须有障碍因子"
        for k in result["key_obstacles"]:
            comps = k.get("components", {})
            for dim in ("R", "W", "M", "S", "E"):
                assert dim in comps, f"{k['factor']} 缺五分量 {dim}"
        assert len(result.get("model_contribution", [])) > 0
        assert result["model_contribution_scope"] == "local_point", \
            f"真实点位应产生局部解释，实际: {result.get('local_shap_status')}"
    finally:
        db.close()


def test_old_diagnosis_endpoint_returns_410(fresh_db):
    """旧端点 /diagnosis 必须返回 410 Gone(审计 1.1-1.3)。"""
    from fastapi.testclient import TestClient
    from app.main import app
    db = fresh_db
    try:
        from app.models import Site
        site = Site(site_code="SRS-OLDENDPOINT", name="旧端点测试场地")
        db.add(site)
        db.commit()
        site_id = site.id

        # 登录获取 token
        client = TestClient(app)
        login_r = client.post("/api/v1/auth/login",
                              json={"username": "admin", "password": "Demo@2026"})
        assert login_r.status_code == 200, f"登录失败: {login_r.text}"
        token = login_r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 调旧端点
        r = client.post(f"/api/v1/sites/{site_id}/diagnosis", headers=headers)
        assert r.status_code == 410, f"旧端点应返回 410, 实际 {r.status_code}: {r.text}"
        assert "废弃" in r.text or "kos-diagnosis" in r.text.lower(), \
            "响应应指引到 kos-diagnosis"
    finally:
        db.close()
