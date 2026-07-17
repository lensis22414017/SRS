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
    # P0-3 数据质量防线:
    # 1) 优先用 Measurement.value_used_for_model, 为空才用 value
    # 2) qa_status=='rejected' 的数据跳过, 标记到 data_quality_flags
    # 3) 对每个因子返回统计量 (点位数/有效测量数/最大值/中位数/P95/超标点数/超标比例)
    # 4) aggregation_method="maximum_valid_measurement" (取每因子最大值, 最不利点)
    # 5) As/Cd/Pb/Hg 浓度 >10000 mg/kg 触发 extreme_value_warning (不改值, 只标记)
    rows = (db.query(Measurement.value_used_for_model, Measurement.value,
                     Measurement.qa_status,
                     FactorDictionary.factor_name, FactorDictionary.factor_code)
            .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id, isouter=True)
            .filter(Measurement.site_id == site_id)
            .all())

    EXTREME_THRESHOLD_MGKG = 10000.0
    # 极端值检查覆盖的因子 (中英文)
    EXTREME_FACTOR_PATTERNS = ("As_mgkg", "Cd_mgkg", "Pb_mgkg", "Hg_mgkg",
                               "砷", "镉", "铅", "汞")

    site_values = {}
    per_factor_raw = {}    # factor -> [values] 用于统计
    n_rejected = 0
    extreme_warnings = []

    for value_used, value, qa_status, fname, fcode in rows:
        fn = fname or fcode
        if not fn:
            continue
        if qa_status == "rejected":
            n_rejected += 1
            continue
        v = value_used if value_used is not None else value
        if v is None:
            continue
        try:
            vf = float(v)
        except (TypeError, ValueError):
            continue
        per_factor_raw.setdefault(fn, []).append(vf)
        # 取最大值 (最不利点)
        if fn not in site_values or vf > site_values[fn]:
            site_values[fn] = vf
        # 极端值检查 (不改值, 只标记到 data_quality_flags)
        if any(p in fn for p in EXTREME_FACTOR_PATTERNS) and vf > EXTREME_THRESHOLD_MGKG:
            extreme_warnings.append(
                f"extreme_value_warning: {fn}={vf} mg/kg 超过 10000 mg/kg 极端值阈值")

    if not site_values:
        raise HTTPException(400, "场地无检测数据,无法诊断")

    # 每个因子的统计量
    factor_stats = _compute_factor_stats(per_factor_raw)

    # 数据质量标记 (前置)
    data_quality_flags_pre = []
    if n_rejected > 0:
        data_quality_flags_pre.append(
            f"skipped_rejected_measurements: {n_rejected} 条 qa_status=rejected 数据被跳过")
    data_quality_flags_pre.extend(extreme_warnings)

    # M0-2/v1.0.2: 提取场地 pH 和土地用途, 传入动态阈值解析
    # v1.0.2: 用多别名匹配 + FactorDictionary factor_code 兜底(修复根因 1-A)
    site_pH = None
    # 优先从 site_values 按常见 key 取
    for ph_key in ("pH", "pH值", "酸碱度", "SoilpH", "pH_merged", "pH_value"):
        if ph_key in site_values and site_values[ph_key] is not None:
            try:
                site_pH = float(site_values[ph_key])
                break
            except (TypeError, ValueError):
                continue
    # 兜底: 查 FactorDictionary 的 factor_code='pH' 对应的 measurement
    if site_pH is None:
        ph_factor = db.query(FactorDictionary).filter(
            FactorDictionary.factor_code.in_(["pH", "pH_value", "SoilpH"])).first()
        if ph_factor:
            ph_meas = db.query(Measurement).filter(
                Measurement.site_id == site_id,
                Measurement.factor_id == ph_factor.id,
                Measurement.qa_status != "rejected").order_by(Measurement.value.desc()).first()
            if ph_meas:
                try:
                    v = ph_meas.value_used_for_model if ph_meas.value_used_for_model is not None else ph_meas.value
                    site_pH = float(v) if v is not None else None
                except (TypeError, ValueError):
                    site_pH = None
    land_use_type = getattr(site, "land_use_type", None)

    result = run_kos_diagnosis(site_values, track=track, subset=subset, top_n=top_n,
                                site_pH=site_pH, land_use_type=land_use_type, db_session=db)
    # M0-6: 按 canonical key 保存统计量, 用动态阈值计算 exceedance_count/ratio
    # 建立 canonical→原始因子名 映射(从 normalize_factors_v2 的 mapping_details)
    canonical_to_raw = {}
    for md in result.get("mapping_details", []):
        c = md.get("canonical")
        if c:
            canonical_to_raw.setdefault(c, []).append(md["original_name"])

    stats_map = {fn: s for fn, s in factor_stats.items()}
    for k in result.get("key_obstacles", []):
        fac = k.get("factor")  # canonical 名 (如 Cd_mgkg)
        # 通过 mapping 找到原始中文名, 取对应统计
        raw_names = canonical_to_raw.get(fac, [])
        s = {}
        for rn in raw_names:
            if rn in stats_map:
                s = stats_map[rn]
                break
        if not s and fac in stats_map:
            s = stats_map[fac]
        # M0-6: 用本次动态阈值计算 exceedance_count/ratio(不再永远为0)
        thr_val = k.get("threshold_value")
        if thr_val and raw_names:
            all_vals = []
            for rn in raw_names:
                all_vals.extend(per_factor_raw.get(rn, []))
            if all_vals:
                exceed_n = sum(1 for v in all_vals if v > thr_val)
                s = dict(s)  # 复制避免修改原引用
                s["exceedance_count"] = exceed_n
                s["exceedance_ratio"] = round(exceed_n / len(all_vals), 4) if all_vals else 0.0
        k["factor_statistics"] = s
        k["aggregation_method"] = "maximum_valid_measurement"
    # 极端值警告 + rejected 跳过 数量 加入 data_quality_flags
    if data_quality_flags_pre:
        result["data_quality_flags"] = data_quality_flags_pre + result.get("data_quality_flags", [])
    result["aggregation_method"] = "maximum_valid_measurement"
    result["factor_statistics"] = factor_stats

    # P0-OPEN-4: 开放集分层识别 — 对所有实测因子做四层分类(formal/candidate/family/unknown)
    # 不丢弃任何因子, 未收录因子进入 candidate/family_alert/unknown_measured
    # M0-3: 开放集分层识别 — 删除 except pass, 失败时返回 open_set_status="failed"
    try:
        from app.services.open_set_classifier import classify_open_set
        from app.services.factor_normalizer import _ALIAS_TO_CANONICAL
        known_canonical = set(_ALIAS_TO_CANONICAL.values())
        # 模型特征来自 SHAP measured 的 group
        model_features = set()
        for mc in result.get("model_contribution", []):
            model_features.add(mc.get("factor", ""))
        # M0-2: 用本次诊断的动态阈值结果(而非硬编码), 从 key_obstacles 提取已解析阈值
        thr_map = {}
        for k in result.get("key_obstacles", []):
            fac = k.get("factor")
            tv = k.get("threshold_value")
            if fac and tv is not None:
                thr_map[fac] = {"type": "upper", "limit": tv}
        # pH 阈值
        from app.services.kos_service import PH_THRESHOLD
        thr_map["pH"] = PH_THRESHOLD.get(track, {})

        open_set = classify_open_set(site_values, known_canonical, model_features, thr_map)
        result["open_set"] = open_set
        result["open_set_summary"] = open_set["open_set_summary"]
        result["unknown_measured_factors"] = open_set["unknown_measured"]
        result["family_alerts"] = open_set["family_alerts"]
        result["model_candidates"] = open_set["model_candidates"]
        result["open_set_status"] = "ok"
        result["review_required"] = result.get("review_required", False) or open_set["open_set_summary"]["n_unknown"] > 0
    except Exception as e:
        # M0-3: 不静默吞异常, 返回失败状态
        result["open_set_status"] = "failed"
        result["open_set_error_code"] = type(e).__name__
        result["open_set_error_message"] = str(e)[:200]
        result["unknown_measured_factors"] = []
        result["family_alerts"] = []
        result["model_candidates"] = []
        result["open_set_summary"] = {"n_formal": 0, "n_model_candidate": 0,
                                       "n_family_alert": 0, "n_unknown": 0,
                                       "n_unit_conflict": 0, "n_mapping_conflict": 0}
        result.setdefault("data_quality_flags", []).append(
            f"open_set_failed: {type(e).__name__}: {str(e)[:100]}")
        result["review_required"] = True

    result["site_id"] = site_id
    result["site_name"] = site.name
    return result


def _compute_factor_stats(per_factor_raw: dict) -> dict:
    """为每个因子计算统计量: 点位数/有效测量数/最大值/中位数/P95/超标点数/超标比例。

    per_factor_raw: {factor_name: [value, value, ...]}
    returns: {factor_name: {n_points, valid_measurement_count, max_value,
                            median_value, p95_value, exceedance_count,
                            exceedance_ratio}}
    注: 超标判断需要阈值; 此处无法拿到阈值 (主因子名是中文), 因此 exceedance_*
    默认填 0 / 0.0, 由下游 KOS 引擎补全 (那里有 thresholds)。 这里只算描述统计。
    """
    import math
    stats = {}
    for fn, vals in per_factor_raw.items():
        if not vals:
            continue
        vals_sorted = sorted(vals)
        n = len(vals_sorted)
        median = (vals_sorted[n // 2] if n % 2 == 1
                  else (vals_sorted[n // 2 - 1] + vals_sorted[n // 2]) / 2)
        # 简化 P95: nearest-rank 法
        p95_idx = max(0, min(n - 1, int(round(0.95 * (n - 1)))))
        p95 = vals_sorted[p95_idx]
        stats[fn] = {
            "measurement_count": n,
            "valid_measurement_count": n,
            "max_value": max(vals),
            "median_value": median,
            "p95_value": p95,
            # 超标点数 / 比例 由 KOS 引擎在拿到阈值后补全; API 层无阈值故置 0
            "exceedance_count": 0,
            "exceedance_ratio": 0.0,
        }
    return stats


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
