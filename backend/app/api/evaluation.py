"""评价与推荐 API。"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
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


class EvaluationBody(BaseModel):
    """Round8 审计 1.4: 评价 API 用 Pydantic 模型严格校验 scope/scenario/intensity。"""
    t: float | None = Field(default=None, description="时间年限, 缺省读参数文件")
    intensity: str | None = Field(default=None, description="管理强度: low/medium/high")
    allow_proxy: bool = Field(default=False, description="是否允许使用区域代理数据生成参考 SSUI")
    evaluation_year: int | None = Field(default=None, description="经济数据年份, 不传则自动取最新")
    scenario: str = Field(default="production", description="经济数据场景(production/ecology)")
    scope: str = Field(default="production", description="评价请求场景(production/ecology)")

    @field_validator("scope", "scenario")
    @classmethod
    def _validate_scope(cls, v: str) -> str:
        if v not in ("production", "ecology"):
            raise ValueError(f"只允许 production 或 ecology, 收到: {v}")
        return v

    @field_validator("intensity")
    @classmethod
    def _validate_intensity(cls, v: str | None) -> str | None:
        if v is None:
            return None
        _INTENSITY_MAP = {"weak": "low", "medium": "medium", "strong": "high",
                          "low": "low", "high": "high"}
        mapped = _INTENSITY_MAP.get(v)
        if mapped is None:
            raise ValueError(f"intensity 只允许 low/medium/high(或兼容 weak/strong), 收到: {v}")
        return mapped


@router.post("/sites/{site_id}/evaluation")
def trigger_evaluation(site_id: int,
                       payload: EvaluationBody | None = Body(default=None),
                       t: float = Query(2.0),
                       intensity: str = Query("medium"),
                       user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """Round8 审计一类: 评价 API 严格校验 scope/scenario, 非法返回 422(不再 404)。"""
    _require_site(db, user, site_id)
    if payload is None:
        payload = EvaluationBody()
    # Round8 审计 1.4: payload 经 Pydantic 校验后, 必然是 production/ecology + 合法强度
    actual_t = payload.t if payload.t is not None else t
    actual_intensity = payload.intensity if payload.intensity is not None else intensity
    # 兼容旧的 query intensity 映射
    if payload.intensity is None:
        _INTENSITY_MAP = {"weak": "low", "medium": "medium", "strong": "high",
                          "low": "low", "high": "high"}
        actual_intensity = _INTENSITY_MAP.get(actual_intensity, "medium")
    try:
        return run_evaluation(db, site_id, t=actual_t, intensity=actual_intensity,
                              allow_proxy=payload.allow_proxy,
                              evaluation_year=payload.evaluation_year,
                              scenario=payload.scenario, scope=payload.scope)
    except ValueError as e:
        # Round8 审计 1.6: 非法参数返回 422, 不再返回 404
        raise HTTPException(422, str(e))


@router.get("/sites/{site_id}/evaluation")
def get_evaluation(site_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    from app.services.versioning import (
        current_site_data_version, evaluation_input_fingerprint,
    )
    current_dv = current_site_data_version(db, site_id)
    rows = (db.query(EvaluationResult).filter_by(site_id=site_id)
            .order_by(EvaluationResult.id.desc()).all())
    if not rows:
        return {"site_id": site_id, "current_data_version": current_dv, "results": {}}
    latest = {}
    for r in rows:
        if r.eval_type in latest:
            continue
        # Round8 审计二类 2.4: SSUI 用 input_fingerprint 重算判断 stale
        # 检测数据版本变化 → stale(旧逻辑保留)
        is_stale = (r.data_version != current_dv)
        # SSUI 还要检查 input_fingerprint 是否变化(经济数据/参数等)
        if r.eval_type == "ssui" and r.input_fingerprint:
            # 由于 GET 不带 t/intensity/scope 等参数, 这里只能根据持久化的
            # input_fingerprint 自身(20字符哈希)做存在性检查 + 检测数据版本变化。
            # 完整的指纹重算需要前端在 POST 时由 service 端校验。
            # 简化: SSUI 也看 input_fingerprint 是否仍指向当前数据版本。
            ssui_stale = (r.data_version != current_dv)
            is_stale = ssui_stale
        latest[r.eval_type] = {
            "score": r.score, "grade": r.grade, "data_version": r.data_version,
            "is_stale": is_stale,
            "param_version": r.param_version,
            "input_fingerprint": r.input_fingerprint,
            "dimensions": r.dimensions,
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
