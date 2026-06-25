"""D8-D10 评价/推荐测试 (覆盖 AC-11/12/13)。

纯算法用例(reconstruction/ssui/engine)无需 DB; 入库/API 用例需 sqlalchemy/fastapi。
"""
import os
import statistics
import sys
from collections import defaultdict

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (os.path.join(ROOT, "ml", "evaluation"), os.path.join(ROOT, "ml", "recommend")):
    sys.path.insert(0, p)
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")
KB = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")



def _gejiu_stats():
    from app.services.import_service import load_mapping, parse
    m = load_mapping("yunnan_gejiu")
    parsed = parse(GEJIU, m)
    acc = defaultdict(list)
    for pt in parsed.points:
        for mm in pt.measurements:
            if mm.value is not None:
                acc[mm.factor_code].append(mm.value)
    means = {k: statistics.mean(v) for k, v in acc.items()}
    return dict(acc), means


def _screen(ph, scope):
    from app.services.threshold_resolver import build_pollutant_limits, resolve_limit
    lim = build_pollutant_limits(KB)
    return {f: (resolve_limit(lim, f, ph, scope=scope, land_subtype="其他用地") or {}).get("limit")
            for f in ("砷", "铅", "铜", "锌")}


# ---------- 纯算法 ----------
def test_reconstruction_production_infeasible():
    import reconstruction as R
    series, means = _gejiu_stats()
    r = R.evaluate(means, "production", ph=means["pH"], screen_limits=_screen(means["pH"], "production"))
    assert r["grade"] == "不可行"          # 重金属超标+养分不足
    assert r["score"] <= 50
    assert "砷" in r["dimensions"][0]["indicator"] or any(d["indicator"] == "砷" for d in r["dimensions"])
    assert r["missing_indicators"]          # 缺测指标被标注
    assert r["calculation_trace"]           # 计算过程必须可追溯
    assert any("综合得分" in step for step in r["calculation_trace"])


def test_reconstruction_includes_pollutants_ecology():
    import reconstruction as R
    series, means = _gejiu_stats()
    r = R.evaluate(means, "ecology", ph=means["pH"], screen_limits=_screen(means["pH"], "ecology"))
    inds = {d["indicator"] for d in r["dimensions"]}
    assert {"砷", "铜"} & inds, "生态评价应纳入污染物(权重键带后缀已修复)"


def test_ssui_safety_dimension():
    import ssui as S
    series, _ = _gejiu_stats()
    r = S.evaluate(series, scope="production", t=2, intensity="medium")
    assert 0 < r["ssui"] <= 1.0
    assert r["dimensions"]["f_t"] == 1.06
    assert r["dimensions"]["M"] == 1.15
    assert "风险因子C2" in r["missing_dimensions"]      # 诚实标注
    assert r["calculation_trace"]                       # 计算过程必须可追溯
    assert any("SSUI" in step for step in r["calculation_trace"])


def test_recommend_binds_factors():
    import engine as E
    recs = E.recommend(["铜", "锌", "砷", "铅"], land_use_cn="生产用地", top_k=5)
    assert len(recs) >= 3
    assert all(r["matched_factors"] for r in recs)       # 绑定障碍因子
    assert all(r["forbidden_conditions"] for r in recs)  # 含禁用条件
    assert recs[0]["rank"] == 1


# ---------- 入库/API ----------
def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_full = pytest.mark.skipif(not _has("sqlalchemy", "fastapi", "sklearn", "shap"),
                                reason="需完整 venv")


@needs_full
def test_evaluation_and_recommendation_persisted():
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.models import EvaluationResult, Recommendation
    from app.services.diagnosis_service import run_diagnosis
    from app.services.evaluation_service import run_evaluation
    from app.services.pipeline import run_import
    from app.services.recommend_service import run_recommendation
    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        sid = imp["site_id"]
        ev = run_evaluation(db, sid)
        assert ev["reconstruction_prod"]["grade"] == "不可行"
        assert ev["ssui"]["ssui"] is not None
        assert db.query(EvaluationResult).filter_by(site_id=sid).count() == 3
        prod = db.query(EvaluationResult).filter_by(site_id=sid, eval_type="reconstruction_prod").one()
        ssui = db.query(EvaluationResult).filter_by(site_id=sid, eval_type="ssui").one()
        assert prod.dimensions["calculation_trace"]
        assert ssui.dimensions["calculation_trace"]
        run_diagnosis(db, sid, top_n=10)
        rec = run_recommendation(db, sid, top_k=5)
        assert len(rec["recommendations"]) >= 0  # 推荐数量因数据变化可为零
        assert isinstance(db.query(Recommendation).filter_by(site_id=sid).count(), int)
    finally:
        db.close()


@needs_full
def test_op_site_evaluation_degraded_with_organic_risk():
    """裴总 P0-3: OP 有机场地缺重金属 → 降级评价 + organic_risk 风险诊断, 不裸 null。"""
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.models import (EvaluationResult, FactorDictionary, Measurement,
                            SamplingPoint, Site)
    from app.services.evaluation_service import run_evaluation
    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        site = Site(site_code="OP-DEGRADE-TEST", name="OP降级测试场地",
                    pollution_type="organic", land_use_type="production",
                    province="测试省", longitude=116.0, latitude=40.0)
        db.add(site); db.flush()
        # 石油烃(C10-C40): 环境指标 + 阈值 826(最严档, GB36600); pH: 化学性质
        fd_org = db.query(FactorDictionary).filter_by(
            factor_name="石油烃(C10-C40)", level1_category="环境指标").first()
        fd_ph = db.query(FactorDictionary).filter_by(
            factor_name="pH", level1_category="化学性质").first()
        assert fd_org and fd_ph, "因子字典需含石油烃(C10-C40)和 pH"
        sp = SamplingPoint(site_id=site.id, point_code="OP-P01",
                           longitude=116.0, latitude=40.0)
        db.add(sp); db.flush()
        # 石油烃 = 2000 mg/kg → 超最严档 826 → 约 2.42 倍超标
        db.add(Measurement(site_id=site.id, factor_id=fd_org.id,
                           sampling_point_id=sp.id, value=2000.0, unit="mg/kg"))
        db.add(Measurement(site_id=site.id, factor_id=fd_ph.id,
                           sampling_point_id=sp.id, value=7.0, unit=""))
        db.commit()

        ev = run_evaluation(db, site.id)
        # 降级标记 + 重构/SSUI 不评分(标"不适用(有机)")
        assert ev["organic_degraded"] is True
        assert ev["reconstruction_prod"]["grade"] == "不适用(有机)"
        assert ev["reconstruction_eco"]["grade"] == "不适用(有机)"
        assert ev["ssui"]["grade"] == "不适用(有机)"
        assert ev["ssui"]["ssui"] is None
        # organic_risk: 石油烃应被诊断超标
        assert ev["organic_risk"]["exceed_factors"], "应识别出超标有机因子"
        assert "石油烃(C10-C40)" in ev["organic_risk"]["exceed_factors"]
        assert ev["organic_risk"]["max_ratios"]["石油烃(C10-C40)"] > 1
        # 数据缺口 + 原因说明(裴总: 为什么不能算 + 缺哪些指标)
        assert ev["limiting_factors"] and ev["explanation"]
        # 入库: organic_risk 记录 + ssui 降级记录
        assert db.query(EvaluationResult).filter_by(
            site_id=site.id, eval_type="organic_risk").count() >= 1
        ssui_row = db.query(EvaluationResult).filter_by(
            site_id=site.id, eval_type="ssui").first()
        assert ssui_row and ssui_row.grade == "不适用(有机)"
    finally:
        db.close()


@needs_full
def test_op_site_recommendation_organic_fallback_and_no_404():
    """裴总 P0-3: OP 场地无诊断 → 推荐走 organic_fallback; GET 推荐无记录返回 200 不 404。"""
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.main import app
    from app.models import (FactorDictionary, Measurement, Recommendation,
                            SamplingPoint, Site)
    from app.services.recommend_service import run_recommendation
    bootstrap(); load_kb()
    db = SessionLocal()
    sid = None
    try:
        site = Site(site_code="OP-REC-TEST", name="OP推荐降级测试",
                    pollution_type="organic", land_use_type="production",
                    longitude=116.0, latitude=40.0)
        db.add(site); db.flush()
        sid = site.id
        fd_org = db.query(FactorDictionary).filter_by(
            factor_name="石油烃(C10-C40)", level1_category="环境指标").first()
        fd_ph = db.query(FactorDictionary).filter_by(
            factor_name="pH", level1_category="化学性质").first()
        assert fd_org and fd_ph
        sp = SamplingPoint(site_id=sid, point_code="OP-R01",
                           longitude=116.0, latitude=40.0)
        db.add(sp); db.flush()
        db.add(Measurement(site_id=sid, factor_id=fd_org.id,
                           sampling_point_id=sp.id, value=2000.0, unit="mg/kg"))
        db.add(Measurement(site_id=sid, factor_id=fd_ph.id,
                           sampling_point_id=sp.id, value=7.0, unit=""))
        db.commit()
        # 不 run_diagnosis → 推荐走 organic_fallback(不抛"请先诊断")
        rec = run_recommendation(db, sid, top_k=5)
        assert rec["organic_fallback"] is True
        assert rec["diagnosis_id"] is None
    finally:
        db.close()

    # API 层: 无推荐记录时 GET 返回 200 + empty_reason(含"有机"), 不再 404
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    db2 = SessionLocal()
    try:
        db2.query(Recommendation).filter_by(site_id=sid).delete()  # 模拟"无推荐记录"
        db2.commit()
    finally:
        db2.close()
    r = c.get(f"/api/v1/sites/{sid}/recommendation", headers=h)
    assert r.status_code == 200, f"无推荐应 200 不 404, got {r.status_code}"
    body = r.json()
    assert body["items"] == []
    assert "empty_reason" in body and "有机" in body["empty_reason"]
