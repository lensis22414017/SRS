"""评价与推荐 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
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
def trigger_evaluation(site_id: int, t: float = Query(2.0), intensity: str = "medium",
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
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
        raise HTTPException(404, "暂无推荐方案")
    tech = {t.id: t for t in db.query(TechnologyLibrary).all()}
    return {"site_id": site_id, "items": [{
        "rank": r.rank, "technology": tech[r.technology_id].tech_name if r.technology_id in tech else None,
        "match_score": r.match_score, "rule_version": r.rule_version,
        "reason": r.reason,
    } for r in rows]}
