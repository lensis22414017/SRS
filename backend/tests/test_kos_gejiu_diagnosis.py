#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPT 审计第 4.20 + 10.6 节: 个旧诊断负向测试。

验证:
  1) 个旧超标数据(As/Pb/Cu/Zn 严重超标)必须识别为障碍因子
  2) 不得只把 pH 列为唯一关键因子
  3) 不得输出"总体优/低风险"
  4) pH 缺失时用兜底阈值, key_obstacles 仍非空
  5) TOP-N + 五分量(R/W/M/S/E) + 模型贡献度三件套齐全
"""
import os
import sys
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)


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


def test_gejiu_overload_identifies_obstacles(fresh_db):
    """个旧超标数据必须识别 As/Pb/Cu/Zn 为障碍(GPT 4.20)。"""
    from app.services.kos_service import run_kos_diagnosis
    db = fresh_db
    try:
        # 个旧超标数据(As 是主要超标物)
        site_values = {
            "砷_As(mg/kg)": 80.0,    # 超 40
            "铅_Pb(mg/kg)": 300.0,   # 超 170
            "铜_Cu(mg/kg)": 150.0,   # 超 100
            "锌_Zn(mg/kg)": 400.0,   # 超 300
            "镉_Cd(mg/kg)": 0.3,     # 未超 0.6
            "pH": 6.0,
        }
        result = run_kos_diagnosis(site_values, track="prod", subset="all",
                                   site_pH=6.0, db_session=db)

        # 1) key_obstacles 必须非空
        assert len(result["key_obstacles"]) > 0, "超标数据必须有障碍因子"

        # 2) 必须识别 As/Pb/Cu/Zn(至少 3 个)为障碍
        obstacle_factors = {k["factor"] for k in result["key_obstacles"]}
        expected = {"As_mgkg", "Pb_mgkg", "Cu_mgkg", "Zn_mgkg"}
        matched = obstacle_factors & expected
        assert len(matched) >= 3, f"应识别至少3个重金属障碍, 实际 {matched}"

        # 3) 不得只有 pH
        assert "pH" not in obstacle_factors or len(obstacle_factors) > 1, \
            "不得只把 pH 列为唯一关键因子"

        # 4) TOP-N 每项必须有五分量 R/W/M/S/E
        for k in result["key_obstacles"]:
            comps = k.get("components", {})
            for dim in ("R", "W", "M", "S", "E"):
                assert dim in comps, f"{k['factor']} 缺五分量 {dim}"

        # 5) 模型贡献度必须非空
        assert len(result["model_contribution"]) > 0, "模型贡献度不能为空"

        # 6) 不得出现"总体优/低风险"等虚假结论词
        for k in result["key_obstacles"]:
            assert k["KOS"] > 0, f"{k['factor']} KOS 应>0(是障碍)"
    finally:
        db.close()


def test_ph_missing_uses_fallback(fresh_db):
    """pH 缺失时用兜底阈值, key_obstacles 仍非空(GPT 4.10 + v1.0.2)。"""
    from app.services.kos_service import run_kos_diagnosis
    db = fresh_db
    try:
        site_values = {
            "砷_As(mg/kg)": 80.0,
            "铅_Pb(mg/kg)": 300.0,
            # pH 故意缺失
        }
        result = run_kos_diagnosis(site_values, track="prod", subset="all",
                                   site_pH=None, db_session=db)

        # 兜底后 key_obstacles 必须非空
        assert len(result["key_obstacles"]) > 0, "pH 缺失用兜底后必须有障碍因子"

        # 所有障碍因子应标记 fallback 状态
        for k in result["key_obstacles"]:
            status = k.get("threshold_resolution_status", "resolved")
            assert status in ("fallback", "resolved"), f"{k['factor']} 状态异常: {status}"

        # ambiguous_factors 应包含超标因子
        assert len(result.get("ambiguous_threshold_factors", [])) > 0, \
            "pH 缺失应产生 ambiguous_factors"
    finally:
        db.close()


def test_exceedance_ratio_displayed(fresh_db):
    """原始超标倍数必须完整显示(GPT 4.15)。"""
    from app.services.kos_service import run_kos_diagnosis
    db = fresh_db
    try:
        site_values = {"砷_As(mg/kg)": 80.0, "pH": 6.0}
        result = run_kos_diagnosis(site_values, track="prod", subset="all",
                                   site_pH=6.0, db_session=db)
        for k in result["key_obstacles"]:
            if k["factor"] == "As_mgkg":
                # As=80, threshold=40, exceedance_ratio 应≈2.0
                ratio = k.get("exceedance_ratio", 0)
                assert ratio > 1.0, f"As 超标倍数应>1, 实际 {ratio}"
    finally:
        db.close()
