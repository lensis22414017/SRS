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

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_eval.db")


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
        assert len(rec["recommendations"]) >= 3
        assert db.query(Recommendation).filter_by(site_id=sid).count() >= 3
    finally:
        db.close()
