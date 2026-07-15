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


@router.get("/sites/{site_id}/diagnoses")
def list_diagnoses(site_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """列出场地所有历史诊断记录（摘要），按时间倒序。"""
    _require_site(db, user, site_id)
    rows = (db.query(DiagnosisResult).filter_by(site_id=site_id)
            .order_by(DiagnosisResult.id.desc()).all())
    if not rows:
        return []
    result = []
    for i, d in enumerate(rows):
        details = (db.query(DiagnosisFactorDetail, FactorDictionary)
                   .join(FactorDictionary,
                         DiagnosisFactorDetail.factor_id == FactorDictionary.id)
                   .filter(DiagnosisFactorDetail.diagnosis_id == d.id,
                           DiagnosisFactorDetail.sampling_point_id.is_(None))
                   .order_by(DiagnosisFactorDetail.rank).limit(5).all())
        top_summary = [fd.factor_name for _, fd in details]
        result.append({
            "id": d.id, "site_id": site_id,
            "data_version": d.data_version,
            "top_factors_summary": top_summary,
            "status": d.status,
            "created_at": str(d.created_at),
            "is_latest": (i == 0),
        })
    return result


@router.get("/diagnoses/{diagnosis_id}")
def get_diagnosis_detail(diagnosis_id: int, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """查看特定历史诊断的完整结果。"""
    diag = db.get(DiagnosisResult, diagnosis_id)
    if not diag:
        raise HTTPException(404, "诊断记录不存在")
    _require_site(db, user, diag.site_id)
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
        "diagnosis_id": diag.id, "site_id": diag.site_id,
        "model": ({"name": model.model_name, "version": model.version,
                   "metrics": model.metrics, "feature_list": model.feature_list,
                   "training_data_version": model.training_data_version}
                  if model else None),
        "data_version": diag.data_version,
        "summary": diag.summary_polished or diag.summary,
        "summary_raw": diag.summary,
        "polish_model": diag.polish_model,
        "top_factors": global_items,
        "local_explanation": local_items,
        "shap_global": diag.shap_global,
        "created_at": str(diag.created_at),
    }


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
        "summary": diag.summary_polished or diag.summary,
        "summary_raw": diag.summary,
        "polish_model": diag.polish_model,
        "top_factors": global_items,
        "local_explanation": local_items,
        "shap_global": diag.shap_global,
        "created_at": str(diag.created_at),
    }


# ──────────────────────────────────────────────────────────────
# P4 KOS 诊断端点(基于 P3-Alpha 模型 + KOS 引擎)
# ──────────────────────────────────────────────────────────────
@router.post("/sites/{site_id}/kos-diagnosis")
def trigger_kos_diagnosis(site_id: int, track: str = Query("prod", pattern="^(prod|eco)$"),
                          subset: str = Query("all", pattern="^(all|hm|op|hm_op)$"),
                          top_n: int = Query(10, ge=3, le=30),
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """运行 KOS 诊断(三层输出:明确障碍 + 关键障碍 KOS + 补测建议)。"""
    from app.models import Measurement
    site = _require_site(db, user, site_id)
    from app.services.kos_service import run_kos_diagnosis
    # 直接查 Measurement 长表 + join FactorDictionary 取因子名,取每因子最大值(最不利点)
    rows = (db.query(Measurement.value, FactorDictionary.factor_name, FactorDictionary.factor_code)
            .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id, isouter=True)
            .filter(Measurement.site_id == site_id, Measurement.value.isnot(None))
            .all())
    site_values = {}
    for value, fname, fcode in rows:
        fn = fname or fcode
        if fn and value is not None:
            try:
                v = float(value)
                if fn not in site_values or v > site_values[fn]:
                    site_values[fn] = v
            except (TypeError, ValueError):
                continue
    if not site_values:
        raise HTTPException(400, "场地无检测数据,无法诊断")
    result = run_kos_diagnosis(site_values, track=track, subset=subset, top_n=top_n)
    result["site_id"] = site_id
    result["site_name"] = site.name
    return result


@router.get("/models/registry")
def get_model_registry(user: User = Depends(get_current_user)):
    """获取模型注册表(前端用于显示模型版本/状态)。"""
    import json, os
    _f = os.path.abspath(__file__)  # backend/app/api/diagnosis.py
    _root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(_f))))
    candidates = [
        os.path.join(_root, "ml", "artifacts", "p3_alpha", "model_registry_v0.8.json"),
        os.path.join(os.getcwd(), "ml", "artifacts", "p3_alpha", "model_registry_v0.8.json"),
        os.path.join(os.getcwd(), "..", "ml", "artifacts", "p3_alpha", "model_registry_v0.8.json"),
    ]
    reg_path = next((p for p in candidates if os.path.exists(p)), None)
    if not reg_path:
        raise HTTPException(404, f"模型注册表未生成 (searched: {candidates})")
    with open(reg_path, encoding="utf-8") as f:
        return json.load(f)
