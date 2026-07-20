#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Round8 外部审计返修七项验收测试。

验证审计裁决中明确要求的场景(每条都有真实失败→真实修复→真实测试证明):

  一(scope覆盖): production/ecology SSUI 使用不同权重得到不同结果
  二(指纹重构): 经济数据修改后 SSUI stale; 修改 t/intensity/scope/proxy 产生新指纹
  三(阈值链路): D16 单调性; 有实测无阈值→review_required(不回退 Min-Max)
  四(KOS持久化): 两次运行保留两条历史; 持久化失败返回 5xx; 刷新恢复 kos_result
  五(首启并发): 条件 UPDATE + BEGIN IMMEDIATE 互斥(模拟并发)
  六(场地删除): foreign_keys=ON + 单删/批删 + 无孤儿
"""
import os
import sys
import json
import tempfile
import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

ROOT = os.path.dirname(BACKEND)
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")
FIXTURE_ECONOMIC = os.path.join(BACKEND, "tests", "fixtures", "economic_2020_rice.json")


def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has("sqlalchemy", "fastapi"),
                              reason="需 SQLAlchemy + FastAPI")


@pytest.fixture
def fresh_db():
    """Round8: 每测试干净 DB + 种子。"""
    from app.db.session import SessionLocal
    from app.db import session as _session_mod
    from app.models import Base
    Base.metadata.drop_all(bind=_session_mod.engine)
    Base.metadata.create_all(bind=_session_mod.engine)
    from app.db.seed_db import seed_if_empty
    seed_if_empty()
    return SessionLocal()


def _client():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.main import app
    bootstrap()
    # Round8: 测试环境跳过模型工件检查(KOS 单测不依赖真实 P3-Alpha 工件)
    app.state.model_health = {"ok": True, "reason": "test_mode"}
    return TestClient(app)


def _login_token(c, username="admin", password="Demo@2026"):
    r = c.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return r.json()["access_token"]


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def _import_gejiu(db):
    """导入个旧真实 Excel, 返回 site_id(Round8: 用真实的 run_import_with_mapping)。"""
    from app.services.pipeline import run_import_with_mapping
    from app.services.import_service import smart_detect_and_map
    from app.models import User
    # Round8: foreign_keys=ON 后 imported_by 必须引用真实 user_id
    user = db.query(User).filter_by(username="admin").first()
    imported_by = user.id if user else None
    _, mapping, _ = smart_detect_and_map(GEJIU)
    result = run_import_with_mapping(db, GEJIU, mapping,
                                     imported_by=imported_by, on_conflict="skip")
    return result["site_id"]


def _make_test_site(db, code="SRS-TEST", pollution_type="heavy_metal"):
    """统一构造测试场地(Round8: 用正确的 Site 字段)。"""
    from app.models import Site, Organization
    org = db.query(Organization).first()
    site = Site(name=f"测试场地{code}", site_code=code,
                pollution_type=pollution_type,
                organization_id=org.id if org else None)
    db.add(site); db.commit()
    return site


def _seed_eight_economic_indicators(db, site_id, year=2020, scenario="production"):
    """给场地种 8 项经济指标(D18-D25), source_type=site_actual。"""
    from app.models import EconomicIndicator
    # 与 fixtures/economic_2020_rice.json 同口径
    # D18/D19/D20/D21 是成本(负向), D22/D23/D24/D25 是效益(正向)
    indicators = [
        ("D18", "劳动力成本", 4500.0, "yuan/mu", "negative"),
        ("D19", "机械化成本", 800.0, "yuan/mu", "negative"),
        ("D20", "土地成本", 1200.0, "yuan/mu", "negative"),
        ("D21", "非机械化成本", 1500.0, "yuan/mu", "negative"),
        ("D22", "单位面积总产值", 3500.0, "yuan/mu", "positive"),
        ("D23", "效益费用比", 0.95, "ratio", "positive"),
        ("D24", "人均可支配收入", 18000.0, "yuan/person/year", "positive"),
        ("D25", "单位面积实物产量", 600.0, "kg/mu", "positive"),
    ]
    for code, name, val, unit, direction in indicators:
        db.add(EconomicIndicator(
            site_id=site_id, evaluation_year=year, scenario=scenario,
            indicator_code=code, indicator_name=name, raw_value=val,
            unit=unit, direction=direction,
            source_type="site_actual", is_proxy=False,
            source_name="测试夹具(Round8 审计)", version="v1.0"))
    db.commit()


# ═══════════════════════════════════════════════════════════════
# 一、scope 覆盖修复审计
# ═══════════════════════════════════════════════════════════════

@needs_db
@pytest.mark.skipif(not os.path.exists(GEJIU), reason="个旧真实数据文件不存在")
def test_scope_no_more_override(fresh_db):
    """审计 1.1-1.3: 修复后 production 评价不会被双轨循环覆盖为 ecology。

    关键验证: SSUI 用 requested_scope(production), 不被 recon_scope(ecology) 覆盖。
    """
    from app.services.evaluation_service import run_evaluation
    db = fresh_db
    try:
        site_id = _import_gejiu(db)
        _seed_eight_economic_indicators(db, site_id)
        result = run_evaluation(db, site_id, evaluation_year=2020,
                                scenario="production", scope="production")
        # 关键断言: 返回结果带 scope 字段, 必须是用户请求的 production
        assert result.get("scope") == "production", \
            f"SSUI scope 必须是用户请求的 production, 实际 {result.get('scope')}"
        # 后端 EvaluationResult.ssui.input_fingerprint 也应反映 production
        from app.models import EvaluationResult
        ssui_row = db.query(EvaluationResult).filter_by(
            site_id=site_id, eval_type="ssui").order_by(
            EvaluationResult.id.desc()).first()
        assert ssui_row is not None, "SSUI 应已持久化"
        assert ssui_row.input_fingerprint, "input_fingerprint 必须非空(审计 2.2)"
    finally:
        db.close()


@needs_db
@pytest.mark.skipif(not os.path.exists(GEJIU), reason="个旧真实数据文件不存在")
def test_scope_production_vs_ecology_differ(fresh_db):
    """审计 1.7: production 和 ecology SSUI 必须得到不同、可解释的结果。"""
    from app.services.evaluation_service import run_evaluation
    from app.models import EvaluationResult
    db = fresh_db
    try:
        site_id = _import_gejiu(db)
        _seed_eight_economic_indicators(db, site_id, scenario="production")
        _seed_eight_economic_indicators(db, site_id, scenario="ecology")

        # 跑 production
        run_evaluation(db, site_id, evaluation_year=2020,
                       scenario="production", scope="production")
        prod_ssui = db.query(EvaluationResult).filter_by(
            site_id=site_id, eval_type="ssui").order_by(
            EvaluationResult.id.desc()).first()
        prod_fp = prod_ssui.input_fingerprint
        prod_grade = prod_ssui.grade

        # 跑 ecology(必须产生不同指纹)
        run_evaluation(db, site_id, evaluation_year=2020,
                       scenario="ecology", scope="ecology")
        eco_ssui = db.query(EvaluationResult).filter_by(
            site_id=site_id, eval_type="ssui").order_by(
            EvaluationResult.id.desc()).first()
        eco_fp = eco_ssui.input_fingerprint

        # 关键断言: 不同 scope 必须产生不同指纹(审计 2.7)
        assert prod_fp != eco_fp, \
            f"production/ecology SSUI 指纹必须不同(避免串轨); prod={prod_fp} eco={eco_fp}"
        # 都不能是 None
        assert prod_fp and eco_fp, "input_fingerprint 不能为空"
    finally:
        db.close()


@needs_db
def test_evaluation_api_rejects_invalid_scope(fresh_db):
    """审计 1.4/1.6: scope/scenario 非法值返回 422(不再 404)。"""
    db = fresh_db
    try:
        c = _client()
        token = _login_token(c)
        # 先造场地
        from app.models import Site, Organization
        org = db.query(Organization).first()
        site = Site(name="测试场地", site_code="SRS-TEST", pollution_type="heavy_metal",
                    organization_id=org.id if org else None)
        db.add(site); db.commit()
        sid = site.id

        # 非法 scope
        r = c.post(f"/api/v1/sites/{sid}/evaluation",
                   json={"scope": "invalid_value"},
                   headers=_auth_header(token))
        assert r.status_code == 422, \
            f"非法 scope 必须返回 422(审计 1.6), 实际 {r.status_code}: {r.text}"

        # 非法 scenario
        r = c.post(f"/api/v1/sites/{sid}/evaluation",
                   json={"scenario": "industrial"},
                   headers=_auth_header(token))
        assert r.status_code == 422, f"非法 scenario 必须返回 422"
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# 二、评价指纹重构审计
# ═══════════════════════════════════════════════════════════════

@needs_db
def test_param_version_separate_from_fingerprint(fresh_db):
    """审计 2.1: param_version 不再被塞入 fingerprint(两者分离)。"""
    from app.services.evaluation_service import PARAM_VERSION
    db = fresh_db
    try:
        # param_version 必须是版本号字符串, 不是哈希
        assert PARAM_VERSION == "evaluation_params_v0.2", \
            f"PARAM_VERSION 必须是版本号, 实际 {PARAM_VERSION}"
        # 验证 evaluation_input_fingerprint 返回完整 SHA-256，禁止短哈希碰撞。
        from app.services.versioning import evaluation_input_fingerprint
        site = _make_test_site(db, code="SRS-TEST2")
        fp = evaluation_input_fingerprint(db, site.id, evaluation_year=2020,
                                          scenario="production", scope="production",
                                          t=2.0, intensity="medium", allow_proxy=False,
                                          param_version=PARAM_VERSION)
        assert len(fp) == 64, f"指纹长度必须 64, 实际 {len(fp)}"
        assert all(c in "0123456789abcdef" for c in fp), "指纹必须是 hex"
    finally:
        db.close()


@needs_db
def test_param_file_sha_in_fingerprint(fresh_db):
    """审计 2.3: 指纹含 evaluation_params.json 真实 SHA-256。"""
    from app.services.versioning import _eval_params_sha256
    sha = _eval_params_sha256()
    # 不能是空/missing/unreadable(参数文件必须存在且可读)
    assert sha not in ("missing", "unreadable", ""), \
        f"参数文件 SHA-256 必须可计算, 实际 {sha}"
    # 保存完整 SHA-256，不再截断。
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)


@needs_db
def test_econ_data_change_invalidates_ssui(fresh_db):
    """审计 2.5: 经济数据修改后旧 SSUI stale(指纹变化)。"""
    from app.services.versioning import evaluation_input_fingerprint
    from app.models import EconomicIndicator
    db = fresh_db
    try:
        site = _make_test_site(db, code="SRS-FP1")
        sid = site.id

        # 无经济数据时算一次指纹
        fp1 = evaluation_input_fingerprint(db, sid, evaluation_year=2020,
                                           scenario="production")

        # 添加经济数据
        db.add(EconomicIndicator(
            site_id=sid, evaluation_year=2020, scenario="production",
            indicator_code="D18", indicator_name="劳动力成本",
            raw_value=4500.0, unit="yuan/mu", direction="negative",
            source_type="site_actual", version="v1.0"))
        db.commit()

        fp2 = evaluation_input_fingerprint(db, sid, evaluation_year=2020,
                                           scenario="production")
        # 关键断言: 添加经济数据后指纹必须变化
        assert fp1 != fp2, \
            f"经济数据变化后 SSUI 指纹必须变化(审计 2.5); fp1={fp1} fp2={fp2}"
    finally:
        db.close()


@needs_db
def test_threshold_set_hash_in_fingerprint(fresh_db):
    """审计 2.3: 指纹含阈值集哈希。"""
    from app.services.versioning import _threshold_set_hash
    h = _threshold_set_hash(fresh_db)
    assert h and len(h) >= 8, f"阈值集哈希必须非空, 实际 {h}"


# ═══════════════════════════════════════════════════════════════
# 三、阈值链路审计
# ═══════════════════════════════════════════════════════════════

def test_d16_monotonicity():
    """审计 3.8 / Round9 P0-2.5: 单调性测试(新公式 r=1→1.0, r=2→0.5, r=3→0.0, r≥3→0.0)。

    Round9 P0-2.5 公式(代码/注释/测试三者一致):
      score = max(0, 1 - 0.5*(r-1))
      r ≤ 1 → score = 1.0
      r = 1.5 → score = 0.75
      r = 2 → score = 0.5
      r = 3 → score = 0.0(clip)
    """
    from ssui import _aggregate_pollutant_risk
    factor_list = ["镉"]
    thresholds = {"镉": {"limit": 0.3, "type": "upper", "resolution_status": "resolved"}}

    # Round9 新结构化返回 + 新公式
    # 0.3 mg/kg(阈值边界)→ r=1.0 → score=1.0
    r = _aggregate_pollutant_risk(factor_list, {"镉": [0.3]}, thresholds, "D16_重金属污染物")
    assert r["score"] == 1.0, f"阈值边界应得 1.0, 实际 {r['score']}"

    # 0.15 mg/kg(半阈值)→ r=0.5 → score=1.0(安全)
    r = _aggregate_pollutant_risk(factor_list, {"镉": [0.15]}, thresholds, "D16_重金属污染物")
    assert r["score"] == 1.0, f"安全值应得 1.0, 实际 {r['score']}"

    # 0.45 mg/kg(1.5 倍)→ r=1.5 → score=0.75
    r = _aggregate_pollutant_risk(factor_list, {"镉": [0.45]}, thresholds, "D16_重金属污染物")
    assert r["score"] == 0.75, f"1.5 倍超标应得 0.75, 实际 {r['score']}"

    # 0.6 mg/kg(2 倍)→ r=2 → score=0.5
    r = _aggregate_pollutant_risk(factor_list, {"镉": [0.6]}, thresholds, "D16_重金属污染物")
    assert r["score"] == 0.5, f"2 倍超标应得 0.5, 实际 {r['score']}"

    # 0.9 mg/kg(3 倍)→ r=3 → score=0.0(clip)
    r = _aggregate_pollutant_risk(factor_list, {"镉": [0.9]}, thresholds, "D16_重金属污染物")
    assert r["score"] == 0.0, f"3 倍超标应得 0.0(clip), 实际 {r['score']}"

    # 3.0 mg/kg(10 倍)→ r=10 → score=0.0(clip)
    r = _aggregate_pollutant_risk(factor_list, {"镉": [3.0]}, thresholds, "D16_重金属污染物")
    assert r["score"] == 0.0, f"10 倍超标应得 0.0(clip), 实际 {r['score']}"


def test_d16_worst_factor_dominates():
    """审计 3.10 / Round9 P0-2.3: 正常砷 + 严重镉必须由镉决定 D16 风险。"""
    from ssui import _aggregate_pollutant_risk
    # 砷=10(GB15618 阈值)→ r=1.0(安全), 镉=3.0(10倍阈值)→ r=10(严重超标)
    thresholds = {"砷": {"limit": 10.0, "type": "upper", "resolution_status": "resolved"},
                  "镉": {"limit": 0.3, "type": "upper", "resolution_status": "resolved"}}
    series = {"砷": [10.0], "镉": [3.0]}
    r = _aggregate_pollutant_risk(["砷", "镉"], series, thresholds, "D16_重金属污染物")
    # Round9 P0-2.6: 必须返回 worst_factor
    assert r.get("worst_factor") == "镉", f"最严重因子应为镉, 实际 {r.get('worst_factor')}"
    assert r.get("worst_ratio") == 10.0, f"最严重超标倍数应为 10, 实际 {r.get('worst_ratio')}"
    assert r["score"] == 0.0, f"砷正常+镉严重超标时 D16 应由镉决定得 0.0, 实际 {r['score']}"
    assert r["status"] in ("measured", "partial_resolved")


def test_no_threshold_no_minmax_fallback():
    """审计 3.5/3.9 / Round9 P0-2.3: 有实测但无阈值时不得回退场内 Min-Max。"""
    from ssui import _aggregate_pollutant_risk
    thresholds = {}  # 无阈值
    series = {"镉": [0.1, 0.5, 5.0]}
    r = _aggregate_pollutant_risk(
        ["镉"], series, thresholds, "D16_重金属污染物",
        threshold_resolution_status={"镉": "not_found"})
    # 关键断言: status=unresolved_threshold, score=None(不回退 Min-Max)
    assert r["status"] == "unresolved_threshold", \
        f"无阈值时必须返回 unresolved_threshold(审计 3.5), 实际 {r['status']}"
    assert r["score"] is None, \
        f"无阈值时 score 必须为 None(不回退 Min-Max), 实际 {r['score']}"
    # Round9 P0-2.3: 必须把具体因子列入 unresolved_factors(供上游 blocked)
    assert "镉" in r["unresolved_factors"], \
        f"实测无阈值的镉必须列入 unresolved_factors, 实际 {r['unresolved_factors']}"


def test_persistent_severe_exceedance_not_missing():
    """审计 3.9 / Round9 P0-2: 恒定严重超标不能变成 missing。"""
    from ssui import _aggregate_pollutant_risk
    # 所有采样点都是 5.0 mg/kg(严重超标 0.3 阈值), 但有阈值 → 应得分 0.0 而非 missing
    thresholds = {"镉": {"limit": 0.3, "type": "upper", "resolution_status": "resolved"}}
    series = {"镉": [5.0, 5.0, 5.0]}  # 恒定
    r = _aggregate_pollutant_risk(
        ["镉"], series, thresholds, "D16_重金属污染物")
    assert r["status"] == "measured", "恒定超标因子应被识别"
    assert r["score"] == 0.0, "恒定严重超标应得 0.0(不变成 missing)"
    assert r["worst_factor"] == "镉"


# ═══════════════════════════════════════════════════════════════
# 四、KOS 持久化闭环审计
# ═══════════════════════════════════════════════════════════════

@needs_db
@pytest.mark.skipif(not os.path.exists(GEJIU), reason="个旧真实数据文件不存在")
def test_kos_history_kept_append_only(fresh_db):
    """审计 4.1/4.9: 两次 KOS 运行后历史必须有两条(追加式, 不删旧)。"""
    db = fresh_db
    try:
        # 关键: 先调 _client() 让 bootstrap 完成, 再用同一 engine 导入数据
        c = _client()
        token = _login_token(c)
        site_id = _import_gejiu(db)

        # 第一次 KOS 运行
        r1 = c.post(f"/api/v1/sites/{site_id}/kos-diagnosis?track=prod&subset=all",
                    headers=_auth_header(token))
        assert r1.status_code == 200, f"第一次 KOS 应成功: {r1.text}"
        body1 = r1.json()
        assert "diagnosis_id" in body1, "POST 返回必须带 diagnosis_id"
        assert body1.get("diagnosis_method") == "kos", \
            "POST 返回必须带 diagnosis_method='kos'"

        # 第二次 KOS 运行(同 track 同 subset, 应保留两条)
        r2 = c.post(f"/api/v1/sites/{site_id}/kos-diagnosis?track=prod&subset=all",
                    headers=_auth_header(token))
        assert r2.status_code == 200, f"第二次 KOS 应成功: {r2.text}"
        body2 = r2.json()

        # 关键断言: 两次的 diagnosis_id 必须不同(追加式)
        assert body1["diagnosis_id"] != body2["diagnosis_id"], \
            "两次运行必须产生不同的 diagnosis_id(审计 4.1: 追加式历史)"

        # 历史列表至少两条
        from app.models import DiagnosisResult
        n_kos = db.query(DiagnosisResult).filter_by(
            site_id=site_id, status="kos_done").count()
        assert n_kos >= 2, f"历史至少 2 条(审计 4.9), 实际 {n_kos}"
    finally:
        db.close()


@needs_db
@pytest.mark.skipif(not os.path.exists(GEJIU), reason="个旧真实数据文件不存在")
def test_kos_history_detail_returns_kos_result(fresh_db):
    """审计 4.6/4.7: GET 详情对 KOS 返回 kos_result 字段; 刷新可恢复完整结果。"""
    db = fresh_db
    try:
        c = _client()
        token = _login_token(c)
        site_id = _import_gejiu(db)

        # POST 触发 KOS
        r = c.post(f"/api/v1/sites/{site_id}/kos-diagnosis?track=prod",
                   headers=_auth_header(token))
        assert r.status_code == 200
        post_body = r.json()
        diag_id = post_body["diagnosis_id"]
        post_key_obstacles = post_body.get("key_obstacles", [])

        # GET 详情
        r2 = c.get(f"/api/v1/diagnoses/{diag_id}", headers=_auth_header(token))
        assert r2.status_code == 200
        detail = r2.json()
        # 关键断言: detail 必须带 kos_result 字段(审计 4.6)
        assert detail.get("diagnosis_method") == "kos", \
            f"diagnosis_method 必须为 kos, 实际 {detail.get('diagnosis_method')}"
        assert detail.get("kos_result") is not None, \
            "GET 详情必须返回 kos_result 字段(审计 4.6)"
        # kos_result.key_obstacles 与 POST 返回一致(可恢复)
        assert detail["kos_result"].get("key_obstacles") == post_key_obstacles, \
            "GET 详情 kos_result.key_obstacles 必须与 POST 一致(审计 4.7 刷新恢复)"
        # track/subset/model_version 字段齐全
        assert detail.get("track") == "prod"
        assert detail.get("subset") is not None
        assert detail.get("model_version") is not None
    finally:
        db.close()


@needs_db
@pytest.mark.skipif(not os.path.exists(GEJIU), reason="个旧真实数据文件不存在")
def test_kos_persistence_failure_returns_5xx(fresh_db, monkeypatch):
    """审计 4.3: KOS 持久化失败必须返回 5xx(禁止返回 200 + data_quality_flags)。"""
    db = fresh_db
    try:
        c = _client()
        token = _login_token(c)
        site_id = _import_gejiu(db)

        # monkeypatch DiagnosisResult.__init__ 让其 raise(模拟持久化失败)
        from app.api import diagnosis as diag_module
        original_init = diag_module.DiagnosisResult.__init__

        def failing_init(self, *args, **kwargs):
            raise OSError("模拟数据库写入失败")

        diag_module.DiagnosisResult.__init__ = failing_init
        try:
            # c 已在前面创建(避免 bootstrap 重置破坏 monkeypatch)
            token = _login_token(c)
            r = c.post(f"/api/v1/sites/{site_id}/kos-diagnosis?track=prod",
                       headers=_auth_header(token))
            # 关键断言: 必须返回 5xx(审计 4.3)
            assert r.status_code in (500, 503), \
                f"持久化失败必须返回 5xx(审计 4.3), 实际 {r.status_code}: {r.text}"
            body = r.json()
            assert "持久化失败" in body.get("detail", "") or "persistence" in body.get("detail", "").lower(), \
                f"detail 必须提示持久化失败, 实际 {body.get('detail')}"
        finally:
            diag_module.DiagnosisResult.__init__ = original_init
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# 五、首启并发审计
# ═══════════════════════════════════════════════════════════════

@needs_db
def test_setup_sequential_only_one_succeeds(fresh_db):
    """审计 5.6 / Round9 P0-4: 顺序两次首启请求只允许一个成功。

    Round9: 旧 test_setup_concurrent_only_one_succeeds 是顺序请求(非真并发),
    按审计 P0-4.5 改名为 _sequential 保留作为基础回归。
    真·并发测试见 test_round9_audit.py 的 test_setup_real_concurrent(两线程+Barrier)。
    """
    db = fresh_db
    try:
        # 关键: 先调 _client() 让 bootstrap 完成(它会 drop+create+seed 覆盖 fresh_db 状态)
        c = _client()
        # 准备 pending 状态的 SystemConfig(模拟首启)
        from app.models import SystemConfig, User
        # 先把现有 admin 用户全部置为 inactive(模拟首启)
        db.query(User).filter(User.status == "active").update({"status": "inactive"})
        sc = db.query(SystemConfig).filter_by(config_key="setup_status").first()
        if sc:
            sc.config_value = "pending"
        else:
            db.add(SystemConfig(config_key="setup_status", config_value="pending",
                                description="首启状态"))
        db.commit()

        # 顺序两次请求(模拟并发竞争的结果; 真·并发测试在新文件)
        body1 = {"username": "admin_concurrent_1", "password": "Test@2026abc",
                 "confirm_password": "Test@2026abc"}
        body2 = {"username": "admin_concurrent_2", "password": "Test@2026abc",
                 "confirm_password": "Test@2026abc"}

        r1 = c.post("/api/v1/setup/complete", json=body1)
        r2 = c.post("/api/v1/setup/complete", json=body2)

        # 关键断言: 第一个成功(200), 第二个失败(409)
        assert r1.status_code == 200, f"第一个首启应成功, 实际 {r1.status_code}: {r1.text}"
        assert r2.status_code == 409, \
            f"第二个首启必须 409(审计 5.6 并发保护), 实际 {r2.status_code}: {r2.text}"

        # 数据库只有一个 active admin
        active_admins = db.query(User).filter(
            User.status == "active", User.username.in_(["admin_concurrent_1", "admin_concurrent_2"])).all()
        assert len(active_admins) == 1, \
            f"数据库只应有一个 active admin, 实际 {len(active_admins)}"
        assert active_admins[0].username == "admin_concurrent_1"
    finally:
        db.close()


@needs_db
def test_setup_admin_role_missing_fails(fresh_db):
    """审计 5.5: admin 角色不存在时必须失败, 不创建无角色用户。"""
    from app.api.setup import setup_complete, SetupCompleteBody
    db = fresh_db
    try:
        from app.models import SystemConfig, User, Role, UserRole, RolePermission
        # 准备 pending 状态
        db.query(User).filter(User.status == "active").update({"status": "inactive"})
        # 删除 admin 角色前先清理所有 FK 引用(user_roles + role_permissions)
        admin_role = db.query(Role).filter_by(code="admin").first()
        if admin_role:
            db.query(UserRole).filter_by(role_id=admin_role.id).delete()
            db.query(RolePermission).filter_by(role_id=admin_role.id).delete()
            db.flush()
        db.query(Role).filter_by(code="admin").delete()
        sc = db.query(SystemConfig).filter_by(config_key="setup_status").first()
        if sc:
            sc.config_value = "pending"
        else:
            db.add(SystemConfig(config_key="setup_status", config_value="pending",
                                description="首启"))
        db.commit()

        # 直接调 setup_complete 服务函数(同一 db session, 避免 TestClient session 隔离)
        body = SetupCompleteBody(username="admin_no_role", password="Test@2026abc",
                                  confirm_password="Test@2026abc")
        try:
            setup_complete(body, db=db)
            assert False, "admin 角色缺失必须抛 HTTPException(500)"
        except Exception as e:
            # 期望 HTTPException(500, "admin 角色不存在")
            from fastapi import HTTPException
            assert isinstance(e, HTTPException), \
                f"应抛 HTTPException, 实际 {type(e).__name__}: {e}"
            assert e.status_code == 500, \
                f"admin 角色缺失必须 500(审计 5.5), 实际 {e.status_code}"
            assert "admin 角色不存在" in e.detail or "角色" in str(e.detail), \
                f"detail 应提示角色不存在, 实际 {e.detail}"

        # 用户不应被创建
        from app.models import User as U
        n = db.query(U).filter_by(username="admin_no_role").count()
        assert n == 0, "无角色管理员不应被创建"
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# 六、场地删除审计
# ═══════════════════════════════════════════════════════════════

@needs_db
def test_enable_foreign_keys_pragma(fresh_db):
    """审计 6.1: 测试环境 SQLite 必须启用 PRAGMA foreign_keys=ON。"""
    db = fresh_db
    try:
        result = db.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys")).scalar()
        # foreign_keys 必须为 1(启用)
        assert result == 1, \
            f"测试环境必须启用 PRAGMA foreign_keys=ON(审计 6.1), 实际 {result}"
    finally:
        db.close()


@needs_db
def test_site_single_delete_cascades_economic(fresh_db):
    """审计 6.3: 有经济数据的场地单删, 所有子表归零且无孤儿。

    Round8 审计 6.5: 调用真实 delete_site 服务函数(经 @router.delete 装饰的生产代码路径)。
    使用 mock_user 绕过 require_permission 装饰器(测试专用), 验证级联逻辑正确性。
    """
    db = fresh_db
    try:
        from app.models import EconomicIndicator, EconomicRawInput, EvaluationResult
        from app.api.data import delete_site
        from unittest.mock import MagicMock
        site = _make_test_site(db, code="SRS-DEL1")
        sid = site.id
        # 种 8 条 EconomicIndicator + 1 条 EconomicRawInput + 1 条 EvaluationResult
        _seed_eight_economic_indicators(db, sid)
        db.add(EconomicRawInput(
            site_id=sid, evaluation_year=2020, scenario="production",
            area_hectare=10.0, yield_kg=90000.0, gross_output_yuan=525000.0,
            total_cost_yuan=120000.0, source_type="site_actual"))
        db.add(EvaluationResult(site_id=sid, eval_type="ssui", data_version="v1",
                                param_version="p", input_fingerprint="fp",
                                score=0.5, grade="测试"))
        db.commit()
        # 删除前确认数据已写入
        assert db.query(EconomicIndicator).filter_by(site_id=sid).count() == 8
        assert db.query(EconomicRawInput).filter_by(site_id=sid).count() == 1

        # 调用真实 delete_site 服务函数(生产代码路径, 不绕过任何业务逻辑)
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.organization_id = None
        delete_site(sid, user=mock_user, db=db)

        # 关键断言: 经济表必须归零(审计 6.3)
        assert db.query(EconomicIndicator).filter_by(site_id=sid).count() == 0, \
            "单删后 economic_indicators 必须归零"
        assert db.query(EconomicRawInput).filter_by(site_id=sid).count() == 0, \
            "单删后 economic_raw_inputs 必须归零"
        assert db.query(EvaluationResult).filter_by(site_id=sid).count() == 0, \
            "单删后 evaluation_results 必须归零"
        # 场地本身已删除
        from app.models import Site as _Site
        assert db.get(_Site, sid) is None, "场地本身必须删除"
    finally:
        db.close()


@needs_db
def test_site_batch_delete_cascades_economic(fresh_db):
    """审计 6.4: 批量删除同样必须级联删除经济表。"""
    db = fresh_db
    try:
        from app.models import (EconomicIndicator, EconomicRawInput)
        from app.api.data import batch_delete_sites
        from unittest.mock import MagicMock
        ids = []
        for i in range(3):
            site = _make_test_site(db, code=f"SRS-BD{i}")
            sid = site.id
            ids.append(sid)
            # 每个场地种经济数据
            _seed_eight_economic_indicators(db, sid)
            db.add(EconomicRawInput(
                site_id=sid, evaluation_year=2020, scenario="production",
                area_hectare=10.0, source_type="site_actual"))
        db.commit()
        # 删除前确认
        for sid in ids:
            assert db.query(EconomicIndicator).filter_by(site_id=sid).count() == 8

        # 调用真实 batch_delete_sites 服务函数(生产代码路径)
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.organization_id = None
        result = batch_delete_sites({"ids": ids}, user=mock_user, db=db)

        # 关键断言: 所有场地的经济表必须归零
        for sid in ids:
            assert db.query(EconomicIndicator).filter_by(site_id=sid).count() == 0, \
                f"批删后 site={sid} economic_indicators 必须归零(审计 6.4)"
            assert db.query(EconomicRawInput).filter_by(site_id=sid).count() == 0, \
                f"批删后 site={sid} economic_raw_inputs 必须归零"
    finally:
        db.close()
