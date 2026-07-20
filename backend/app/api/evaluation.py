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
    t: float | None = Field(default=None, ge=0, le=100, description="时间年限, 缺省读参数文件")
    intensity: str | None = Field(default=None, description="管理强度: low/medium/high")
    allow_proxy: bool = Field(default=False, description="是否允许使用区域代理数据生成参考 SSUI")
    evaluation_year: int | None = Field(default=None, ge=2000, le=2100,
                                        description="经济数据年份, 不传则自动取最新")
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
        if actual_intensity not in _INTENSITY_MAP:
            raise HTTPException(422, "intensity 只允许 low/medium/high(或兼容 weak/strong)")
        actual_intensity = _INTENSITY_MAP[actual_intensity]
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
    """Round9 P0-1.3: GET 用 run_config 重算指纹判断 stale。

    审计 P0-1.6: 不允许写"GET 没参数所以只能看 data_version"。
    用历史结果保存的 run_config 重新计算当前指纹:
      current_fingerprint != saved.input_fingerprint → is_stale=true。
    """
    _require_site(db, user, site_id)
    from app.services.versioning import (
        current_site_data_version, evaluation_input_fingerprint,
        _eval_params_sha256, _economic_ref_csv_sha256, _threshold_set_hash,
    )
    current_dv = current_site_data_version(db, site_id)
    rows = (db.query(EvaluationResult).filter_by(site_id=site_id)
            .order_by(EvaluationResult.id.desc()).all())
    if not rows:
        return {"site_id": site_id, "current_data_version": current_dv, "results": {}}
    # Round9 P0-1.7: 参数文件/CSV unreadable → 全部 stale(禁止复用)
    params_sha = _eval_params_sha256()
    csv_sha = _economic_ref_csv_sha256()
    threshold_sha = _threshold_set_hash(db)
    params_unreadable = params_sha in {"missing", "unreadable"}
    csv_unreadable = csv_sha in {"missing", "unreadable"}
    threshold_unreadable = threshold_sha in {"no_thr", "thr_err"}

    latest = {}
    for r in rows:
        if r.eval_type in latest:
            continue
        # 默认按 data_version 判断(reconstruction 类)
        is_stale = (r.data_version != current_dv)
        stale_reason = "data_version_changed" if is_stale else None

        # Round9 P0-1.6: SSUI 必须用 run_config 重算指纹
        if r.eval_type == "ssui":
            if not r.run_config or not r.input_fingerprint:
                is_stale = True
                stale_reason = "run_config_missing"
            else:
                try:
                    rc = r.run_config
                    cur_fp = evaluation_input_fingerprint(
                        db, site_id,
                        evaluation_year=rc.get("evaluation_year"),
                        scenario=rc.get("scenario", "production"),
                        scope=rc.get("scope", "production"),
                        t=float(rc.get("t", 2.0)),
                        intensity=rc.get("intensity", "medium"),
                        allow_proxy=bool(rc.get("allow_proxy", False)),
                        param_version=rc.get("param_version", ""),
                    )
                    if cur_fp != r.input_fingerprint:
                        is_stale = True
                        stale_reason = "input_fingerprint_mismatch"
                except Exception:
                    is_stale = True
                    stale_reason = "fingerprint_recalc_failed"

        # Round9 P0-1.7: 参数/CSV 文件 unreadable → 强制 stale
        if params_unreadable:
            is_stale = True
            stale_reason = f"params_file_{params_sha}"
        if csv_unreadable and r.eval_type == "ssui":
            is_stale = True
            stale_reason = f"economic_ref_csv_{csv_sha}"
        if threshold_unreadable:
            is_stale = True
            stale_reason = f"threshold_set_{threshold_sha}"

        item = {
            "score": r.score, "grade": r.grade, "data_version": r.data_version,
            "is_stale": is_stale,
            "stale_reason": stale_reason,
            "param_version": r.param_version,
            "input_fingerprint": r.input_fingerprint,
            "run_config": r.run_config,
            "dimensions": r.dimensions,
            "weights": r.weights, "limiting_factors": r.limiting_factors,
            "risk_factors": r.risk_factors, "explanation": r.explanation,
            "created_at": str(r.created_at),
        }
        if r.eval_type == "ssui" and isinstance(r.dimensions, dict):
            payload = r.dimensions.get("result_payload")
            if isinstance(payload, dict):
                item.update(payload)
                item["score"] = payload.get("ssui")
                item["data_version"] = r.data_version
                item["is_stale"] = is_stale
                item["stale_reason"] = stale_reason
                item["created_at"] = str(r.created_at)
                item["param_version"] = r.param_version
        latest[r.eval_type] = item
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
