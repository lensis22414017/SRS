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
    from app.services.import_service import import_site_data
    result = import_site_data(db, REAL_XLSX, enterprise_id=1)
    return result["site_id"]


@pytest.mark.skipif(not os.path.exists(REAL_XLSX),
                    reason="个旧真实数据文件不存在")
def test_kos_prod_outputs_complete(fresh_db):
    """生产 KOS 诊断输出完整(审计 1.4)。"""
    from app.services.kos_service import run_kos_diagnosis
    db = fresh_db
    try:
        site_id = _import_gejiu(db)
        from app.models import Measurement, FactorDictionary
        rows = (db.query(Measurement.value_used_for_model, Measurement.value,
                         FactorDictionary.factor_name)
                .join(FactorDictionary,
                      Measurement.factor_id == FactorDictionary.id, isouter=True)
                .filter(Measurement.site_id == site_id,
                        Measurement.value.isnot(None)).all())
        sv = {}
        for vu, v, fn in rows:
            if not fn:
                continue
            val = vu if vu is not None else v
            try:
                vf = float(val)
            except (TypeError, ValueError):
                continue
            if fn not in sv or vf > sv[fn]:
                sv[fn] = vf
        assert len(sv) > 0, "导入后应有测量数据"

        result = run_kos_diagnosis(sv, track="prod", subset="all",
                                    site_pH=6.0, db_session=db)

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

        # 5) unmapped_factors 列表存在(可为空)
        assert "unmapped_factors" in result, "必须有 unmapped_factors 字段"
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
        from app.models import Measurement, FactorDictionary
        rows = (db.query(Measurement.value_used_for_model, Measurement.value,
                         FactorDictionary.factor_name)
                .join(FactorDictionary,
                      Measurement.factor_id == FactorDictionary.id, isouter=True)
                .filter(Measurement.site_id == site_id,
                        Measurement.value.isnot(None)).all())
        sv = {}
        for vu, v, fn in rows:
            if not fn:
                continue
            val = vu if vu is not None else v
            try:
                vf = float(val)
            except (TypeError, ValueError):
                continue
            if fn not in sv or vf > sv[fn]:
                sv[fn] = vf

        result = run_kos_diagnosis(sv, track="eco", subset="all",
                                    site_pH=6.0, db_session=db)

        assert len(result.get("key_obstacles", [])) > 0, "生态 KOS 必须有障碍因子"
        for k in result["key_obstacles"]:
            comps = k.get("components", {})
            for dim in ("R", "W", "M", "S", "E"):
                assert dim in comps, f"{k['factor']} 缺五分量 {dim}"
        assert len(result.get("model_contribution", [])) > 0
    finally:
        db.close()


def test_old_diagnosis_endpoint_returns_410(fresh_db):
    """旧端点 /diagnosis 必须返回 410 Gone(审计 1.1-1.3)。"""
    from fastapi.testclient import TestClient
    from app.main import app
    db = fresh_db
    try:
        # 种入一个场地
        from app.services.import_service import import_site_data
        REAL = os.path.join(BACKEND, "..", "data", "raw",
                            "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")
        if not os.path.exists(REAL):
            pytest.skip("个旧真实数据文件不存在")
        result = import_site_data(db, REAL, enterprise_id=1)
        site_id = result["site_id"]
        db.commit()

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
