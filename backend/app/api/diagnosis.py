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


@router.post("/sites/{site_id}/diagnosis", status_code=410)
def trigger_diagnosis(site_id: int,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """[已废弃 v1.0.1] 旧 RF+SHAP 端点会触发现场重训(读虚拟数据), 已被 KOS 路径取代。

    返回 410 Gone, 指引到 POST /sites/{site_id}/kos-diagnosis。
    """
    _require_site(db, user, site_id)
    raise HTTPException(
        status_code=410,
        detail="此端点已废弃(会触发现场训练, 违反生产规范)。请改用 POST /api/v1/sites/{site_id}/kos-diagnosis。".format(site_id=site_id)
    )


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


def _build_kos_response(diag: DiagnosisResult, db: Session, site_id: int | None = None) -> dict:
    """Round8 审计 4.6 + Round9 P0-3.4: 统一构建 KOS 历史详情响应, 带 kos_result 字段。

    兼容 KOS(用 result_payload)和旧 RF+SHAP(用 shap_global)两种记录。
    Round9 P0-3.4: 优先从 result_payload.key_obstacles 读 Top-N(不再依赖 DiagnosisFactorDetail)。
    """
    model = db.get(MLModel, diag.model_id) if diag.model_id else None
    details = (db.query(DiagnosisFactorDetail, FactorDictionary)
               .join(FactorDictionary,
                     DiagnosisFactorDetail.factor_id == FactorDictionary.id)
               .filter(DiagnosisFactorDetail.diagnosis_id == diag.id).all())
    global_items, local_items = [], []
    for d, fd in details:
        item = {"factor": fd.factor_name, "category": fd.level1_category,
                "importance": d.importance, "shap_value": d.shap_value,
                "kos_score": getattr(d, "kos_score", None),
                "direction": d.direction, "rank": d.rank}
        if d.sampling_point_id is None:
            global_items.append(item)
        else:
            sp = db.get(SamplingPoint, d.sampling_point_id)
            item["point_code"] = sp.point_code if sp else None
            local_items.append(item)
    global_items.sort(key=lambda x: (x["rank"] or 999))

    # Round9 P0-3.4: KOS 记录优先从 result_payload 读 Top-N
    kos_result = diag.result_payload if diag.diagnosis_method == "kos" else None
    # 若 KOS 但 DiagnosisFactorDetail 为空, 从 result_payload.key_obstacles 兜底
    if diag.diagnosis_method == "kos" and kos_result and not global_items:
        for ko in (kos_result.get("key_obstacles") or [])[:10]:
            global_items.append({
                "factor": ko.get("factor"), "category": None,
                "importance": None,  # Round9 P0-3.3: KOS 不冒充 SHAP importance
                "shap_value": None,
                "kos_score": ko.get("KOS"),
                "direction": None,
                "rank": ko.get("rank"),
            })
        global_items.sort(key=lambda x: (x["rank"] or 999))

    return {
        "diagnosis_id": diag.id,
        "site_id": site_id if site_id is not None else diag.site_id,
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
        "diagnosis_method": diag.diagnosis_method,
        "track": diag.track,
        "subset": diag.subset,
        "model_version": diag.model_version,
        "kos_result": kos_result,
        "created_at": str(diag.created_at),
    }


# Round9 P0-3.1: KOS canonical payload 序列化器
# 审计 P0-3.5"不要继续手工遗漏字段" — 自动遍历 result dict 保留所有审计字段,
# 剔除私有下划线字段、非 JSON 序列化对象(numpy/joblib 类型)
_KOS_PAYLOAD_REQUIRED_KEYS = [
    "track", "subset", "model_id", "model_version", "model_status",
    "data_version", "threshold_version",
    "mapping_details", "mapping_conflicts", "unmapped",
    "unit_conversion_details", "explicit_obstacles",
    "key_obstacles", "model_attention_factors",
    "family_warnings", "unknown_alerts", "recommended_tests",
    "model_contribution", "model_feature_names", "factor_statistics",
    "model_contribution_scope", "local_shap_status",
    "decision_point_id", "decision_point_code", "decision_point_selection",
    "per_point_stats", "n_sampling_points",
    "open_set", "open_set_summary",
    "data_quality_flags", "ambiguous_threshold_factors", "coverage",
    "limitations", "organic_guardrails", "kos_weights",
    "interpretation_note", "review_required",
]


def _json_safe(obj):
    """递归把 numpy 类型转成 JSON 安全类型; 失败返回 None(不丢整个 payload)。"""
    import math
    try:
        if obj is None or isinstance(obj, (bool, int, str)):
            return obj
        if isinstance(obj, float):
            return obj if math.isfinite(obj) else None
        # numpy scalar
        if hasattr(obj, "item") and not isinstance(obj, (list, dict, tuple)):
            try:
                return _json_safe(obj.item())
            except Exception:
                return None
        if isinstance(obj, dict):
            return {str(k): _json_safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_json_safe(x) for x in obj]
        # 其他类型(str 模型对象等)→ str 兜底
        return str(obj)
    except Exception:
        return None


def _kos_canonical_payload(result: dict, track: str = "prod",
                            subset: str = "all", top_n: int = 10) -> dict:
    """Round9 P0-3.1: KOS canonical payload — 自动收集所有审计要求字段。

    替代 Round8 手工挑字段(漏 mapping_details/unit_conversion_details 等)。
    修正 Round8 字段名错误: unmapped_factors→unmapped, per_point_data→per_point_stats。
    """
    payload = {
        key: _json_safe(value)
        for key, value in result.items()
        if not key.startswith("_") and key not in {"kos_result", "diagnosis_id"}
    }
    for key in _KOS_PAYLOAD_REQUIRED_KEYS:
        payload.setdefault(key, None)
    # API 层补充(非 kos_service 返回)
    payload["subset"] = payload.get("subset") or subset
    payload["top_n"] = top_n
    payload["track"] = payload.get("track") or track
    return payload


@router.get("/diagnoses/{diagnosis_id}")
def get_diagnosis_detail(diagnosis_id: int, user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """查看特定历史诊断的完整结果。"""
    diag = db.get(DiagnosisResult, diagnosis_id)
    if not diag:
        raise HTTPException(404, "诊断记录不存在")
    _require_site(db, user, diag.site_id)
    return _build_kos_response(diag, db)


@router.get("/sites/{site_id}/diagnosis")
def latest_diagnosis(site_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _require_site(db, user, site_id)
    diag = (db.query(DiagnosisResult).filter_by(site_id=site_id)
            .order_by(DiagnosisResult.id.desc()).first())
    if not diag:
        raise HTTPException(404, "该场地暂无诊断结果")
    return _build_kos_response(diag, db, site_id=site_id)


# ──────────────────────────────────────────────────────────────
# P4 KOS 诊断端点(基于 P3-Alpha 模型 + KOS 引擎)
# ──────────────────────────────────────────────────────────────
@router.post("/sites/{site_id}/kos-diagnosis")
def trigger_kos_diagnosis(site_id: int, track: str = Query("prod", pattern="^(prod|eco)$"),
                          subset: str = Query("all", pattern="^(all|hm|op|hm_op)$"),
                          top_n: int = Query(10, ge=3, le=30),
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """运行 KOS 诊断(三层输出:明确障碍 + 关键障碍 KOS + 补测建议)。"""
    # v1.0.1 final-audit: 模型完整性阻断(缺失模型不允许诊断)
    from fastapi import Request
    from starlette.requests import Request as StarletteRequest
    # 检查 app.state.model_health(启动时已设置)
    from app.main import app as _app
    model_health = getattr(_app.state, "model_health", {})
    if not model_health.get("ok"):
        raise HTTPException(503, f"模型工件不完整, KOS诊断不可用: {model_health.get('reason', '未知原因')}")
    from app.models import Measurement
    site = _require_site(db, user, site_id)
    from app.services.kos_service import run_kos_diagnosis
    # P0-3 数据质量防线:
    # 1) 优先用 Measurement.value_used_for_model, 为空才用 value
    # 2) qa_status=='rejected' 的数据跳过, 标记到 data_quality_flags
    # 3) 对每个因子返回统计量 (点位数/有效测量数/最大值/中位数/P95/超标点数/超标比例)
    # 4) aggregation_method="maximum_valid_measurement" (取每因子最大值, 最不利点)
    #    v1.0.2(GPT 4.7): 同时按采样点分组, 支持按点位计算超标率/P95
    # 5) As/Cd/Pb/Hg 浓度 >10000 mg/kg 触发 extreme_value_warning (不改值, 只标记)
    rows = (db.query(Measurement.value_used_for_model, Measurement.value,
                     Measurement.qa_status, Measurement.sampling_point_id,
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
    # v1.0.2: 按采样点分组 {point_id: {factor_name: value}}
    per_point_data = {}
    n_rejected = 0
    extreme_warnings = []

    for value_used, value, qa_status, point_id, fname, fcode in rows:
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
        # 取最大值 (最不利点, 兼容旧逻辑)
        if fn not in site_values or vf > site_values[fn]:
            site_values[fn] = vf
        # v1.0.2: 按采样点分组
        if point_id is not None:
            per_point_data.setdefault(point_id, {})[fn] = vf
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
                                site_pH=site_pH, land_use_type=land_use_type, db_session=db,
                                per_point_data=per_point_data)
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
        k["aggregation_method"] = result.get(
            "rule_aggregation_method",
            "site_factor_worst_case_with_per_point_evidence",
        )
    # 极端值警告 + rejected 跳过 数量 加入 data_quality_flags
    if data_quality_flags_pre:
        result["data_quality_flags"] = data_quality_flags_pre + result.get("data_quality_flags", [])
    result["aggregation_method"] = result.get(
        "rule_aggregation_method",
        "site_factor_worst_case_with_per_point_evidence",
    )
    result["factor_statistics"] = factor_stats

    # P0-OPEN-4: 开放集分层识别 — 对所有实测因子做四层分类(formal/candidate/family/unknown)
    # 不丢弃任何因子, 未收录因子进入 candidate/family_alert/unknown_measured
    # M0-3: 开放集分层识别 — 删除 except pass, 失败时返回 open_set_status="failed"
    try:
        from app.services.open_set_classifier import classify_open_set
        from app.services.factor_normalizer import _ALIAS_TO_CANONICAL
        known_canonical = set(_ALIAS_TO_CANONICAL.values())
        # 模型已见特征来自完整 measured SHAP 清单，不能拿局部贡献 Top-10
        # 代替模型适用域，否则未进入局部 Top-10 的已见因子会被误判为未知。
        model_features = set(result.get("model_feature_names") or [])
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
    decision_point_id = result.get("decision_point_id")
    if decision_point_id is not None:
        decision_point = db.get(SamplingPoint, decision_point_id)
        result["decision_point_code"] = (
            decision_point.point_code if decision_point else None
        )

    # Round9 P0-3: KOS 诊断结果持久化(canonical payload 自动收集所有审计字段)
    # P0-3.1: 用 _kos_canonical_payload 替代手工挑字段(不再漏字段, 不再写错字段名)
    # P0-3.3: DiagnosisFactorDetail.kos_score 存 KOS 排序分; importance 留空(不冒充 SHAP)
    # P0-3.4: 不再用 result.get("_canonical_to_raw")(字段不存在), 改用 mapping_details
    from fastapi import HTTPException as _HTTPException
    try:
        from app.services.versioning import current_site_data_version
        import hashlib
        import json
        kos_data_version = current_site_data_version(db, site_id)
        # Round9 P0-3.1: canonical payload 自动收集所有审计要求字段
        kos_payload = _kos_canonical_payload(result, track=track, subset=subset, top_n=top_n)
        # 模型版本(从 model_registry_v0.8.json 读, 没有则用 p3_alpha_v0.8)
        model_version = result.get("model_version") or "p3_alpha_v0.8"
        feature_names = result.get("model_feature_names") or []
        feature_hash = hashlib.sha256(
            json.dumps(feature_names, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        model_record = (db.query(MLModel).filter_by(
            model_name=result.get("model_id"), version=model_version).first())
        if model_record is None:
            model_record = MLModel(
                model_name=result.get("model_id") or "unknown_kos_model",
                version=model_version,
                algorithm=result.get("model_algorithm"),
                feature_list={"measured_factor_groups": feature_names,
                              "n_features": result.get("model_n_features")},
                training_data_version=result.get("data_version"),
                metrics=result.get("model_metrics") or {},
                artifact_path=result.get("model_artifact_path"),
                validation_strategy=result.get("model_validation_strategy") or "group_split",
                group_key=result.get("model_group_key") or "id_DOI/source",
                feature_schema_hash=feature_hash,
                ood_policy="warn",
            )
            db.add(model_record)
            db.flush()
        diag = DiagnosisResult(
            site_id=site_id,
            model_id=model_record.id,
            data_version=kos_data_version,
            top_n=top_n,
            summary=f"KOS诊断({track}/{subset}): {len(result.get('key_obstacles', []))} 个关键障碍",
            shap_global={"kos_result": True},  # 仅作旧端兼容标记
            diagnosis_method="kos",
            track=track,
            subset=subset,
            model_version=model_version,
            validation_strategy=model_record.validation_strategy,
            group_key=model_record.group_key,
            feature_schema_hash=model_record.feature_schema_hash,
            threshold_library_version=result.get("threshold_version"),
            result_payload=kos_payload,
            status="kos_done",
            human_review_triggered=result.get("review_required", False),
            review_reason="KOS启发式阈值需复核" if result.get("review_required") else None,
        )
        db.add(diag)
        db.flush()
        # Round9 P0-3.4: 用 mapping_details 建立 canonical→raw 映射(不再用 _canonical_to_raw)
        canonical_to_raw = {}
        for md in result.get("mapping_details", []):
            c = md.get("canonical")
            if c:
                canonical_to_raw.setdefault(c, []).append(md.get("original_name", c))
        # Round9 P0-3.3: DiagnosisFactorDetail.kos_score 存 KOS 分; importance 不冒充 SHAP
        for rank, ko in enumerate(result.get("key_obstacles", [])[:top_n], 1):
            canon = ko.get("factor", "")
            raw_names = canonical_to_raw.get(canon, [])
            raw_name = raw_names[0] if raw_names else canon
            fd = db.query(FactorDictionary).filter(
                (FactorDictionary.factor_code == canon) |
                (FactorDictionary.factor_name == raw_name) |
                (FactorDictionary.factor_name == canon)).first()
            if fd:
                db.add(DiagnosisFactorDetail(
                    diagnosis_id=diag.id,
                    factor_id=fd.id,
                    importance=None,  # Round9 P0-3.3: KOS 不冒充 SHAP importance
                    shap_value=None,
                    kos_score=ko.get("KOS"),  # 专用 KOS 排序分
                    direction=ko.get("direction", ""),
                    rank=rank,
                ))
        # Round8 审计 4.2: 追加式历史(最多保留最近 10 条 kos_done)
        stale_kos = (db.query(DiagnosisResult)
                     .filter_by(site_id=site_id, status="kos_done")
                     .order_by(DiagnosisResult.id.desc()).offset(10).all())
        for old_diag in stale_kos:
            db.query(DiagnosisFactorDetail).filter_by(
                diagnosis_id=old_diag.id).delete(synchronize_session=False)
            db.delete(old_diag)
        db.commit()
        result["diagnosis_id"] = diag.id
        # Round9 P0-3.1: 直接返回的 kos_result 与 GET 历史详情完全一致(深度相等)
        result["kos_result"] = kos_payload
        result["diagnosis_method"] = "kos"
    except _HTTPException:
        db.rollback()
        raise
    except Exception as e:
        # Round8 审计 4.3: 持久化失败必须 rollback 并返回 5xx(禁止返回 200)
        db.rollback()
        import traceback
        traceback.print_exc()
        raise _HTTPException(
            status_code=503,
            detail=(f"KOS 诊断结果持久化失败: {type(e).__name__}: {str(e)[:200]}。"
                    f"诊断未保存到历史记录, 请检查数据库或磁盘空间后重试。"))

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
