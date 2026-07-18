"""评价与推荐 API。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import assert_site_access, get_current_user
from app.db.session import get_db
from app.models import EvaluationResult, Recommendation, Site, TechnologyLibrary, User
from app.services.evaluation_service import run_evaluation
from app.services.recommend_service import run_recommendation

router = APIRouter(prefix=get_settings().api_v1_prefix, tags=["evaluation"])


def _require_site(db: Session, user: User, site_id: int) -> Site:
    """企业数据隔离校验: 企业用户只能访问本企业场地。"""
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    return s


@router.post("/sites/{site_id}/evaluation")
def trigger_evaluation(site_id: int,
                       payload: dict | None = Body(default=None),
                       t: float = Query(2.0),
                       intensity: str = Query("medium"),
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """v1.0.1 final-audit: t/intensity 从 body JSON 或 Query 参数接收(前端可调)。"""
    _require_site(db, user, site_id)
    # 优先从 body JSON 读(前端用 body 传参)
    if payload:
        t = float(payload.get("t", t))
        intensity = payload.get("intensity", intensity)
    # v1.0.1 final-audit: 统一强度枚举映射 weak→low, strong→high
    _INTENSITY_MAP = {"weak": "low", "medium": "medium", "strong": "high",
                      "low": "low", "high": "high"}
    intensity = _INTENSITY_MAP.get(intensity, "medium")
    try:
        return run_evaluation(db, site_id, t=t, intensity=intensity)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/sites/{site_id}/evaluation")
def get_evaluation(site_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    from app.services.versioning import current_site_data_version
    current_dv = current_site_data_version(db, site_id)
    rows = (db.query(EvaluationResult).filter_by(site_id=site_id)
            .order_by(EvaluationResult.id.desc()).all())
    if not rows:
        # brief 4.5: 无历史也返回当前数据版本, 供前端历史区提示"暂无历史, 请运行"
        return {"site_id": site_id, "current_data_version": current_dv, "results": {}}
    latest = {}
    for r in rows:
        if r.eval_type in latest:
            continue
        latest[r.eval_type] = {
            "score": r.score, "grade": r.grade, "data_version": r.data_version,
            "is_stale": r.data_version != current_dv,  # brief 4.5: 数据变更后旧评价 stale
            "param_version": r.param_version, "dimensions": r.dimensions,
            "weights": r.weights, "limiting_factors": r.limiting_factors,
            "risk_factors": r.risk_factors, "explanation": r.explanation,
            "created_at": str(r.created_at),
        }
    return {"site_id": site_id, "current_data_version": current_dv, "results": latest}


@router.post("/sites/{site_id}/recommendation")
def trigger_recommendation(site_id: int, top_k: int = Query(5, ge=1, le=10),
                           user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    try:
        return run_recommendation(db, site_id, top_k=top_k)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/sites/{site_id}/recommendation")
def get_recommendation(site_id: int, user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    rows = (db.query(Recommendation).filter_by(site_id=site_id)
            .order_by(Recommendation.rank).all())
    if not rows:
        # 无推荐不返回 404(OP 场地前端会触发 organic_fallback 生成候选);
        # 给 200 + 空列表 + 引导, 避免前端报错或裸 404
        site = db.get(Site, site_id)
        hint = ("该场地为有机污染且尚未生成推荐; 点击「生成推荐」将基于有机因子匹配 OP 修复候选"
                if site and site.pollution_type == "organic"
                else "暂无推荐方案, 请先运行障碍因子诊断后生成推荐")
        return {"site_id": site_id, "items": [], "empty_reason": hint}
    tech = {t.id: t for t in db.query(TechnologyLibrary).all()}
    # brief 4.6: 透传 reason_struct/matched_factors/source/cost/duration,
    # 前端 RecommendationPage 已消费 reason_struct, 旧 GET 只返回 reason → 卡片字段空
    return {"site_id": site_id, "items": [{
        "rank": r.rank,
        "technology": tech[r.technology_id].tech_name if r.technology_id in tech else None,
        "match_score": r.match_score, "rule_version": r.rule_version,
        "reason": r.reason,
        "reason_struct": r.reason_struct,
        "matched_factors": r.matched_factors,
        "source": r.source,
        "cost_level": tech[r.technology_id].cost_level if r.technology_id in tech else None,
        "duration_level": tech[r.technology_id].duration_level if r.technology_id in tech else None,
    } for r in rows]}
