"""障碍因子诊断 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import assert_site_access, get_current_user
from app.db.session import get_db
from app.models import (
    DiagnosisFactorDetail, DiagnosisResult, FactorDictionary, MLModel, SamplingPoint, Site, User,
)
from app.services.diagnosis_service import run_diagnosis

router = APIRouter(prefix=get_settings().api_v1_prefix, tags=["diagnosis"])


def _require_site(db: Session, user: User, site_id: int) -> Site:
    """加载场地并执行企业数据隔离校验(企业用户只能访问本企业场地)。"""
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    return s


@router.post("/sites/{site_id}/diagnosis")
def trigger_diagnosis(site_id: int, top_n: int = Query(10, ge=3, le=30),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    try:
        return run_diagnosis(db, site_id, top_n=top_n)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except ImportError as e:
        raise HTTPException(503, f"算法依赖缺失(需 scikit-learn/shap): {e}")


@router.get("/sites/{site_id}/diagnosis")
def latest_diagnosis(site_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    diag = (db.query(DiagnosisResult).filter_by(site_id=site_id)
            .order_by(DiagnosisResult.id.desc()).first())
    if not diag:
        raise HTTPException(404, "该场地暂无诊断结果")
    model = db.get(MLModel, diag.model_id) if diag.model_id else None
    details = (db.query(DiagnosisFactorDetail, FactorDictionary)
               .join(FactorDictionary,
                     DiagnosisFactorDetail.factor_id == FactorDictionary.id)
               .filter(DiagnosisFactorDetail.diagnosis_id == diag.id).all())
    global_items, local_items = [], []
    for d, fd in details:
        item = {"factor": fd.factor_name, "category": fd.level1_category,
                "importance": d.importance, "shap_value": d.shap_value,
                "direction": d.direction, "rank": d.rank}
        if d.sampling_point_id is None:
            global_items.append(item)
        else:
            sp = db.get(SamplingPoint, d.sampling_point_id)
            item["point_code"] = sp.point_code if sp else None
            local_items.append(item)
    global_items.sort(key=lambda x: (x["rank"] or 999))
    return {
        "diagnosis_id": diag.id, "site_id": site_id,
        "model": ({"name": model.model_name, "version": model.version,
                   "metrics": model.metrics, "feature_list": model.feature_list,
                   "training_data_version": model.training_data_version}
                  if model else None),
        "data_version": diag.data_version,
        "summary": diag.summary,
        "top_factors": global_items,
        "local_explanation": local_items,
        "shap_global": diag.shap_global,
        "created_at": str(diag.created_at),
    }
