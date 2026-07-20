"""数据管理 API: 导入、场地列表/详情、采样点、检测值长表查询、校验报告。"""
from __future__ import annotations

import os
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import (
    assert_site_access, get_current_user, require_permission, scope_sites_query,
)
from app.db.session import get_db
from app.models import (
    AuditLog, DiagnosisFactorDetail, DiagnosisResult, EconomicIndicator, EconomicRawInput,
    EvaluationResult, FactorDictionary, ImportBatch, Measurement, ReportRecord, SamplingPoint,
    Site, StandardThreshold, ThresholdRule, User, WorkflowRecord,
)
from app.services.audit_service import log
from app.services.import_service import load_mapping, read_table, resolve_mapping_for_file
from app.services.pipeline import run_import_with_mapping

def _to_base26(n: int) -> str:
    """整数→纯字母 Base26 编码(0→A, 25→Z, 26→BA, ...)。"""
    if n < 0:
        n = 0
    chars = []
    n += 1  # 1→A 而非 0→A
    while n > 0:
        n, rem = divmod(n - 1, 26)
        chars.append(chr(ord('A') + rem))
    return ''.join(reversed(chars))


def _format_site_code(db: Session, site_id: int):
    """v1.0.1 final-audit: 场地编号纯字母(零数字), 格式 SRS-XXXX-YYYY。

    site_id 转 Base26 字母, 保证全库唯一且不含数字。
    采样点数量只放"采样点"独立列, 不拼入 site_code。
    """
    import re as _re
    site = db.get(Site, site_id)
    if not site:
        return
    # 纯字母编码: SRS-{site_id的Base26}-{随机4字母}(确保唯一性+可读性)
    code = f"SRS-{_to_base26(site_id)}"
    # 如有原业务编号且含数字, 另存 original_site_code
    if site.site_code and _re.search(r'[0-9]', str(site.site_code)):
        if not getattr(site, 'original_site_code', None):
            try:
                site.original_site_code = site.site_code
            except Exception:
                pass  # 字段可能不存在
    site.site_code = code
    db.commit()

router = APIRouter(prefix=get_settings().api_v1_prefix, tags=["data"])


@router.post("/import")
async def import_data(mapping_id: str = Form(...), file: UploadFile = File(...),
                      on_conflict: str = Form("skip"),
                      user: User = Depends(require_permission("data:input")),
                      db: Session = Depends(get_db)):
    import datetime as _dt
    import json as _json

    settings = get_settings()
    os.makedirs(settings.file_storage_dir, exist_ok=True)
    # 自动重命名: 时间戳_区域_污染类型.ext (便于管理)
    ext = os.path.splitext(file.filename or "data.xlsx")[1] or ".xlsx"
    region = pollution = ""
    try:
        mp = os.path.join(os.path.dirname(__file__), "..", "services", "mappings", f"{mapping_id}.json")
        if os.path.exists(mp):
            meta = _json.load(open(mp, encoding="utf-8")).get("site", {})
            region = (meta.get("city") or meta.get("province") or "").replace("市", "").replace("省", "")
            pollution = {"heavy_metal": "重金属", "organic": "有机", "composite": "复合"}.get(meta.get("pollution_type", ""), "")
    except Exception:  # noqa: BLE001
        pass
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    canonical = f"{ts}_{region or '场地'}_{pollution or '污染'}{ext}"
    dest = os.path.join(settings.file_storage_dir, canonical)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # ── 解析映射: auto=按文件 sheet/列签名自动识别; 否则按 mapping_id 加载 ──
    used_id, mapping, det_report = _resolve_mapping(mapping_id, dest)
    _apply_auto_site_code(mapping, mapping_id, file.filename)
    try:
        result = run_import_with_mapping(db, dest, mapping, imported_by=user.id,
                                         on_conflict=on_conflict)
        if result.get("site_id"):
            _format_site_code(db, result["site_id"])
        
        result["stored_filename"] = canonical
        result["original_filename"] = file.filename
        result["mapping_id"] = used_id
        result["mapping_label"] = (mapping.get("site") or {}).get("name")
        result["detection_report"] = det_report
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"导入失败 [{type(e).__name__}]: {e}")
    log(db, action="import", user_id=user.id, resource_type="sites",
        resource_id=result.get("site_id"), detail={"mapping_id": used_id, "requested": mapping_id})
    return result


def _resolve_mapping(mapping_id: str, dest: str) -> tuple[str, dict, dict]:
    """auto/空 → 统一自动识别(预设→smart); 否则按 mapping_id 加载。

    单文件/批量共用 resolve_mapping_for_file(brief 4.1), 保证同文件两路径同决策。
    低置信/缺必需字段 → 转为 review_required(400), 引导 Wizard, 不硬导入正式链路。
    返回 (used_id, mapping, detection_report)。
    """
    used_id, mapping, report = resolve_mapping_for_file(mapping_id, dest)
    if report.get("confidence", 1.0) < 0.5:
        warnings = report.get("warnings") or ["未识别到关键列"]
        raise HTTPException(
            400,
            "字段映射置信度不足，已转为待复核(review_required)。请使用『自定义字段映射 Wizard』手动映射后导入。"
            f" used_id={used_id}; confidence={report.get('confidence')}; "
            f"识别到: 点位列={report.get('point_code_column')}; "
            f"问题: {'; '.join(warnings)}。")
    return used_id, mapping, report


def _apply_auto_site_code(mapping: dict, mapping_id: str, original_filename: str | None) -> None:
    """auto+smart 识别时用原文件名重设 site_code(避免 canonical 时间戳冲突 + 可读)。

    smart_detect 默认 site_code='AUTO-'+canonical stem(含时间戳), 同分钟多文件会冲突到
    同一 site_code → 多场地被合并; 改用上传的原文件名 stem, 保证多场地唯一且可读。
    """
    if mapping_id not in ("auto", "", "detect", None):
        return
    if not (mapping or {}).get("_smart_generated"):
        return
    stem = os.path.splitext(original_filename or "AUTO场地")[0]
    safe = "".join(c for c in stem if c.isalnum() or c in ("-_",))[:40] or "AUTO场地"
    mapping.setdefault("site", {})["site_code"] = f"AUTO-{safe}"
    mapping["site"]["name"] = stem


@router.post("/import/columns")
async def get_file_columns(file: UploadFile = File(...),
                           _user: User = Depends(require_permission("data:input"))):
    """读取上传文件的列名，供字段映射 wizard 使用。不写库。"""
    import tempfile as _tmp
    suffix = os.path.splitext(file.filename or "data.xlsx")[1] or ".xlsx"
    with _tmp.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        df = read_table(tmp_path, {"sheet": None})
        columns = [str(c).strip() for c in df.columns.tolist()]
        preview = df.head(3).fillna("").astype(str).to_dict(orient="records")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"文件解析失败: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return {"columns": columns, "preview": preview, "n_rows": len(df)}


@router.post("/import/wizard")
async def import_wizard(mapping: str = Form(...), file: UploadFile = File(...),
                        user: User = Depends(require_permission("data:input")),
                        db: Session = Depends(get_db)):
    """字段映射 wizard 导入: 前端传入内联 mapping JSON + 文件, 不依赖预定义 mapping_id。"""
    import datetime as _dt
    import json as _json

    try:
        mapping_dict = _json.loads(mapping)
    except Exception:
        raise HTTPException(400, "mapping 不是合法 JSON")

    settings = get_settings()
    os.makedirs(settings.file_storage_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "data.xlsx")[1] or ".xlsx"
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    canonical = f"{ts}_wizard{ext}"
    dest = os.path.join(settings.file_storage_dir, canonical)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = run_import_with_mapping(db, dest, mapping_dict, imported_by=user.id)
        result["stored_filename"] = canonical
        result["original_filename"] = file.filename
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"导入失败: {e}")
    log(db, action="import", user_id=user.id, resource_type="sites",
        resource_id=result.get("site_id"), detail={"mapping_id": "wizard"})
    return result


@router.post("/import/batch")
async def import_batch(mapping_id: str = Form(...),
                      files: list[UploadFile] = File(...),
                      on_conflict: str = Form("skip"),
                      user: User = Depends(require_permission("data:input")),
                      db: Session = Depends(get_db)):
    """批量导入: 多文件共用同一 mapping_id, 串行跑 pipeline 避免写库竞态。

    每个文件独立校验并返回结果; 单文件失败不阻断其余文件。
    返回 { total, succeeded, failed, results: [{filename, ok, ...}] }。
    """
    import datetime as _dt

    is_auto = mapping_id in ("auto", "", "detect", None)
    # 非 auto: 先校验映射文件(一次, 对所有文件共用); auto: 每个文件单独识别
    if not is_auto:
        try:
            mapping = load_mapping(mapping_id)
        except FileNotFoundError:
            raise HTTPException(404, f"映射配置不存在: {mapping_id}")

    settings = get_settings()
    os.makedirs(settings.file_storage_dir, exist_ok=True)
    results: list[dict] = []
    succeeded = failed = 0
    for idx, file in enumerate(files, 1):
        original_name = os.path.basename(file.filename or "data.xlsx")
        stem, ext = os.path.splitext(original_name)
        ext = ext or ".xlsx"
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        canonical = f"{ts}_{idx:02d}_{stem or 'batch'}{ext}"
        dest = os.path.join(settings.file_storage_dir, canonical)
        try:
            with open(dest, "wb") as f:
                shutil.copyfileobj(file.file, f)
            if is_auto:
                used_id, file_mapping, det_report = resolve_mapping_for_file(mapping_id, dest)
                # 低置信: 计 review_required, 该文件 failed, 不阻断批量其余文件(brief 4.1)
                if det_report.get("confidence", 1.0) < 0.5:
                    raise HTTPException(
                        400, "映射置信度不足(review_required): "
                        + "; ".join(det_report.get("warnings") or []))
            else:
                used_id, file_mapping = mapping_id, mapping
                det_report = {"used_id": mapping_id, "confidence": 1.0, "source": "preset"}
            _apply_auto_site_code(file_mapping, mapping_id, original_name)
            res = run_import_with_mapping(db, dest, file_mapping, imported_by=user.id,
                                          on_conflict=on_conflict)
            
            if res.get("site_id"):
                _format_site_code(db, res["site_id"])

            res["stored_filename"] = canonical
            res["original_filename"] = original_name
            res["mapping_id"] = used_id
            res["mapping_label"] = (file_mapping.get("site") or {}).get("name")
            res["detection_report"] = det_report
            res["ok"] = True
            succeeded += 1
            log(db, action="import", user_id=user.id, resource_type="sites",
                resource_id=res.get("site_id"), detail={"mapping_id": used_id, "batch": True})
        except Exception as e:  # noqa: BLE001
            failed += 1
            results.append({"original_filename": original_name, "ok": False,
                            "error": f"导入失败 [{type(e).__name__}]: {e}"})
            continue
        results.append(res)
    return {"total": len(files), "succeeded": succeeded, "failed": failed, "results": results}


@router.get("/sites")
def list_sites(q: str | None = None, pollution_type: str | None = None,
               page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=200),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = scope_sites_query(db, user, db.query(Site))
    if q:
        query = query.filter(Site.name.contains(q) | Site.site_code.contains(q))
    if pollution_type:
        query = query.filter(Site.pollution_type == pollution_type)
    total = query.count()
    rows = query.order_by(Site.id).offset((page - 1) * size).limit(size).all()
    # 批量统计: 该页每个场地的样点数/因子数/超标记录数(避免 N+1 查询)
    site_ids = [s.id for s in rows]
    factor_cnt: dict[int, int] = {}
    exceed_cnt: dict[int, int] = {}
    if site_ids:
        fc_rows = (db.query(Measurement.site_id, func.count(func.distinct(Measurement.factor_id)))
                   .filter(Measurement.site_id.in_(site_ids))
                   .group_by(Measurement.site_id).all())
        factor_cnt = {sid: int(c) for sid, c in fc_rows}
        # 超标记录: standard_thresholds(screening_value) ∪ threshold_rules(threshold_max) 并集
        # 修复两套阈值表不统一回归(production用standard_thresholds 47行 / 测试load_kb填threshold_rules 403行)
        # 超标按测量指标计: 每条measurement超过任意对应阈值档算1次(distinct去重, 避免pH档笛卡尔膨胀)
        _std = (db.query(Measurement.id, Measurement.site_id)
                .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
                .join(StandardThreshold, StandardThreshold.factor_id == FactorDictionary.id)
                .filter(Measurement.site_id.in_(site_ids),
                        StandardThreshold.screening_value != None,
                        Measurement.value > StandardThreshold.screening_value)).all()
        _rule = (db.query(Measurement.id, Measurement.site_id)
                 .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
                 .join(ThresholdRule, ThresholdRule.factor_id == FactorDictionary.id)
                 .filter(Measurement.site_id.in_(site_ids),
                         ThresholdRule.threshold_max != None,
                         Measurement.value > ThresholdRule.threshold_max)).all()
        _sid_mids: dict[int, set] = {}
        for _mid, _sid in list(_std) + list(_rule):
            _sid_mids.setdefault(_sid, set()).add(_mid)
        exceed_cnt = {sid: len(mids) for sid, mids in _sid_mids.items()}
    items = [{
        "id": s.id, "site_code": s.site_code, "name": s.name,
        "pollution_type": s.pollution_type, "land_use_type": s.land_use_type,
        "province": s.province, "city": s.city,
        "longitude": float(s.longitude) if s.longitude is not None else None,
        "latitude": float(s.latitude) if s.latitude is not None else None,
        "n_points": db.query(func.count(SamplingPoint.id)).filter_by(site_id=s.id).scalar(),
        "n_factors": factor_cnt.get(s.id, 0),
        "n_exceed": exceed_cnt.get(s.id, 0),
        "data_quality": ("良好" if exceed_cnt.get(s.id, 0) == 0 else
                         "部分超标" if exceed_cnt.get(s.id, 0) < 10 else "大量超标"),
    } for s in rows]
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/sites/statistics")
def site_statistics(user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """场地统计聚合: 按污染类型分类计数 + 覆盖省份 + 检测/超标总量。
    企业用户自动 scope 到本企业场地。
    """
    base_q = scope_sites_query(db, user, db.query(Site))
    sites = base_q.all()
    site_ids = [s.id for s in sites]

    hm = sum(1 for s in sites if s.pollution_type == "heavy_metal")
    op = sum(1 for s in sites if s.pollution_type == "organic")
    composite = sum(1 for s in sites if s.pollution_type == "composite")
    provinces = len({s.province for s in sites if s.province})

    n_points = db.query(func.count(SamplingPoint.id)).filter(
        SamplingPoint.site_id.in_(site_ids)).scalar() if site_ids else 0
    n_meas = db.query(func.count(Measurement.id)).filter(
        Measurement.site_id.in_(site_ids)).scalar() if site_ids else 0

    exceed = 0
    if site_ids:
        _std = (db.query(Measurement.id)
                .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
                .join(StandardThreshold, StandardThreshold.factor_id == FactorDictionary.id)
                .filter(Measurement.site_id.in_(site_ids),
                        StandardThreshold.screening_value != None,
                        Measurement.value > StandardThreshold.screening_value)).all()
        _rule = (db.query(Measurement.id)
                 .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
                 .join(ThresholdRule, ThresholdRule.factor_id == FactorDictionary.id)
                 .filter(Measurement.site_id.in_(site_ids),
                         ThresholdRule.threshold_max != None,
                         Measurement.value > ThresholdRule.threshold_max)).all()
        exceed = len({r[0] for r in list(_std) + list(_rule)})

    # 全局统计（跨所有场地，不受 RBAC scope 限制）
    try:
        total_reports = db.query(func.count(ReportRecord.id)).scalar() or 0
    except Exception:
        total_reports = None

    try:
        active_workflows = db.query(func.count(WorkflowRecord.id)).filter(
            WorkflowRecord.status.notin_(["completed", "archived"])
        ).scalar() or 0
    except Exception:
        active_workflows = None

    return {
        "total_sites": len(sites),
        "total_provinces": provinces,
        "heavy_metal_count": hm,
        "organic_count": op,
        "composite_count": composite,
        "total_sampling_points": n_points,
        "total_measurements": n_meas,
        "exceedance_count": exceed,
        "total_reports": total_reports,
        "active_workflows": active_workflows,
    }


@router.get("/sites/aggregations/top-obstacles")
def top_obstacles_aggregation(
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """跨场地障碍因子 TOP-N 聚合: 扫所有可见场地最新诊断的 Top 因子,
    按"因子"聚合频次 + 平均 importance(不按 rank 拆分同一因子)。
    仅统计 rank <= 5 的因子(每场地贡献其最重要因子)。

    数据来源真实: DiagnosisResult + DiagnosisFactorDetail(全局因子级 SHAP 解释)。
    无诊断结果的场地不参与聚合(不伪造)。
    """
    site_ids = [s.id for s in scope_sites_query(db, user, db.query(Site.id)).all()]
    if not site_ids:
        return {"items": [], "n_sites_with_diagnosis": 0, "note": "无可见场地"}

    # 每场地最新诊断 id(用 DISTINCT ON 取每 site_id 的最大 id)
    latest_diag_ids = (db.query(DiagnosisResult.id)
                       .filter(DiagnosisResult.site_id.in_(site_ids),
                               DiagnosisResult.status == "done")
                       .order_by(DiagnosisResult.site_id, DiagnosisResult.id.desc())
                       .distinct(DiagnosisResult.site_id).all())
    diag_id_list = [r[0] for r in latest_diag_ids]
    if not diag_id_list:
        return {"items": [], "n_sites_with_diagnosis": 0, "note": "无诊断结果"}

    # 按 factor_name 聚合(不按 rank 拆分, 避免同一因子多行)
    rows = (db.query(FactorDictionary.factor_name,
                     FactorDictionary.level1_category,
                     func.avg(DiagnosisFactorDetail.importance).label("avg_importance"),
                     func.count().label("freq"))
            .join(DiagnosisFactorDetail, DiagnosisFactorDetail.factor_id == FactorDictionary.id)
            .filter(DiagnosisFactorDetail.diagnosis_id.in_(diag_id_list),
                    DiagnosisFactorDetail.sampling_point_id.is_(None),
                    DiagnosisFactorDetail.rank != None,
                    DiagnosisFactorDetail.rank <= 5)
            .group_by(FactorDictionary.factor_name, FactorDictionary.level1_category)
            .order_by(func.count().desc(), func.avg(DiagnosisFactorDetail.importance).desc())
            .limit(limit).all())

    items = [{"factor": r.factor_name or "—", "category": r.level1_category or "",
              "freq": int(r.freq), "avg_importance": round(float(r.avg_importance or 0), 4)}
             for r in rows]
    return {"items": items, "n_sites_with_diagnosis": len(diag_id_list),
            "note": "基于各场地最新诊断 Top-5 因子聚合(按因子合并); 无诊断结果的场地不参与"}


@router.get("/sites/aggregations/monthly-trend")
def monthly_trend_aggregation(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按月聚合: 场地累计数 / 检测记录累计数 / 报告生成累计数。
    数据来源: Site.created_at / Measurement.created_at / ReportRecord.generated_at。
    覆盖最近 12 个月。无数据月份为零(不伪造增长)。
    所有查询受 RBAC scope 限制, site_ids 为空时返回空数组(不泄露全局统计)。
    """
    from datetime import datetime
    try:
        from dateutil.relativedelta import relativedelta
    except ImportError:
        # 无 dateutil 时降级为 calendar 精确计算
        import calendar
        def relativedelta(months=0):
            class _R:
                def __init__(self, m): self.m = m
                def __rsub__(self, other):
                    y = other.year - (other.month - m - 1) // 12 if m >= other.month else other.year
                    mm = other.month - m
                    if mm <= 0:
                        mm += 12
                        y = other.year - 1
                    return other.replace(year=y, month=mm, day=1)
            return _R(months)

    now = datetime.now()
    months: list[str] = []
    for i in range(11, -1, -1):
        d = now.replace(day=1) - relativedelta(months=i)
        months.append(d.strftime("%Y-%m"))

    site_ids = [s.id for s in scope_sites_query(db, user, db.query(Site.id)).all()]

    def _cumulative_by_month(model, date_field, is_site_table=False):
        # site_ids 为空时不得返回全库统计(权限隔离)
        if not site_ids:
            return {}, 0
        q = db.query(date_field)
        if not is_site_table and hasattr(model, "site_id"):
            q = q.filter(model.site_id.in_(site_ids))
        elif is_site_table:
            # Site 表用 id 过滤(scope 限定)
            q = q.filter(model.id.in_(site_ids))
        rows = q.all()
        cum = 0
        result = {}
        bucket: dict[str, int] = {}
        for (dt,) in rows:
            if dt is None:
                continue
            key = dt.strftime("%Y-%m") if hasattr(dt, "strftime") else str(dt)[:7]
            bucket[key] = bucket.get(key, 0) + 1
        for m in months:
            cum += bucket.get(m, 0)
            result[m] = cum
        return result, sum(bucket.values())

    site_cum, n_sites = _cumulative_by_month(Site, Site.created_at, is_site_table=True)
    meas_cum, n_meas = _cumulative_by_month(Measurement, Measurement.created_at)
    report_cum, n_reports = _cumulative_by_month(ReportRecord, ReportRecord.generated_at)

    return {
        "months": months,
        "sites_cumulative": [site_cum.get(m, 0) for m in months],
        "measurements_cumulative": [meas_cum.get(m, 0) for m in months],
        "reports_cumulative": [report_cum.get(m, 0) for m in months],
        "totals": {"sites": n_sites, "measurements": n_meas, "reports": n_reports},
        "note": "累计值; 无数据月份维持上一月水平(累计不回退); 受 RBAC scope 限制",
    }


@router.get("/sites/aggregations/workflow-stages")
def workflow_stages_aggregation(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """五阶段监管工作流场地数统计。
    阶段: survey(调查评估)/approval(方案审批)/construction(施工监理)/
          effect(效果评估)/maintenance(后期管护)。
    数据来源真实: WorkflowRecord。无记录的阶段计数为零。
    """
    site_ids = [s.id for s in scope_sites_query(db, user, db.query(Site.id)).all()]
    stages = [
        ("survey", "调查评估"),
        ("approval", "方案审批"),
        ("construction", "施工监理"),
        ("effect", "效果评估"),
        ("maintenance", "后期管护"),
    ]
    items = []
    for code, name in stages:
        q = (db.query(WorkflowRecord.site_id, WorkflowRecord.status)
             .filter(WorkflowRecord.stage == code))
        if site_ids:
            q = q.filter(WorkflowRecord.site_id.in_(site_ids))
        rows = q.all()
        n_total = len({r.site_id for r in rows})
        n_in_progress = len({r.site_id for r in rows if r.status not in ("completed", "archived", "not_started")})
        n_completed = len({r.site_id for r in rows if r.status == "completed"})
        items.append({
            "code": code, "name": name,
            "n_sites": n_total, "n_in_progress": n_in_progress, "n_completed": n_completed,
        })
    return {"items": items, "note": "基于 WorkflowRecord 真实记录; 无记录阶段为零"}


@router.get("/sites/{site_id}")
def site_detail(site_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    n_points = db.query(func.count(SamplingPoint.id)).filter_by(site_id=site_id).scalar()
    n_meas = db.query(func.count(Measurement.id)).filter_by(site_id=site_id).scalar()
    return {
        "id": s.id, "site_code": s.site_code, "name": s.name,
        "pollution_type": s.pollution_type, "land_use_type": s.land_use_type,
        "province": s.province, "city": s.city,
        "longitude": float(s.longitude) if s.longitude is not None else None,
        "latitude": float(s.latitude) if s.latitude is not None else None,
        "n_points": n_points, "n_measurements": n_meas,
    }


class LandUseUpdate(BaseModel):
    """修复后用途(生产用地/生态用地) — 贯穿诊断主轨 + 功能重构评价 + SSUI + 方案推荐。"""
    land_use_type: str


@router.put("/sites/{site_id}/land-use")
def update_site_land_use(site_id: int, body: LandUseUpdate,
                         user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """更新场地修复后用途(项目组决策: 在障碍因子诊断页选择, 影响整条决策链)。

    - 生产用地 → 诊断主轨 prod 模型(GB15618 严阈值) + 生产功能重构评价 + 生产修复技术
    - 生态用地 → 诊断主轨 eco 模型(GB36600 二类宽阈值) + 生态功能重构评价 + 生态修复技术
    """
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    if body.land_use_type not in ("生产用地", "生态用地"):
        raise HTTPException(400, "land_use_type 仅允许: 生产用地 / 生态用地")
    old = s.land_use_type
    s.land_use_type = body.land_use_type
    log(db, action="update_land_use", user_id=user.id,
        resource_type="site", resource_id=s.id,
        detail={"old": old, "new": body.land_use_type})
    db.commit()
    return {"ok": True, "site_id": site_id, "land_use_type": s.land_use_type}


# v1.0.2: 场地删除(GPT 审计第三节) — 级联清理 + 审计墓碑
@router.delete("/sites/{site_id}")
def delete_site(site_id: int,
                user: User = Depends(require_permission("data:delete")),
                db: Session = Depends(get_db)):
    """删除场地 + 事务化级联清理所有关联数据(GPT 3.1-3.3)。

    级联表(按依赖顺序删除):
      WorkflowAttachment → WorkflowRecord → Recommendation → EvaluationResult
      → DiagnosisFactorDetail → DiagnosisResult → ReportRecord → AuditLog
      → ProjectAuthorization → SamplingEvent → DatasetVersion → ImportBatch
      → Measurement → SamplingPoint → Site

    删除后保留审计墓碑(AuditLog, 不含业务内容), 场地不再出现在列表/统计/分析。
    """
    from app.models import (
        DatasetVersion, ProjectAuthorization, Recommendation,
        SamplingEvent, WorkflowAttachment, WorkflowRecord,
    )
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    site_name = s.name
    site_code = s.site_code

    # 收集该场地所有诊断 ID(用于删 DiagnosisFactorDetail)
    diag_ids = [d.id for d in db.query(DiagnosisResult.id).filter_by(site_id=site_id).all()]
    # 收集该场地所有工作流 ID(用于删 WorkflowAttachment)
    wf_ids = [w.id for w in db.query(WorkflowRecord.id).filter_by(site_id=site_id).all()]

    deleted_counts = {}
    try:
        # 1. 子表先删
        if wf_ids:
            n = db.query(WorkflowAttachment).filter(
                WorkflowAttachment.workflow_record_id.in_(wf_ids)).delete(synchronize_session=False)
            deleted_counts["workflow_attachments"] = n
        if diag_ids:
            n = db.query(DiagnosisFactorDetail).filter(
                DiagnosisFactorDetail.diagnosis_id.in_(diag_ids)).delete(synchronize_session=False)
            deleted_counts["diagnosis_factor_details"] = n

        # 2. 按 site_id 删除的表(Round9 P0-7: 调整顺序, measurements 必须在 import_batches 之前删
        #    因为 measurements.import_batch_id FK 引用 import_batches)
        for model_name, model in [
            ("workflow_records", WorkflowRecord),
            ("recommendations", Recommendation),
            ("evaluation_results", EvaluationResult),
            ("diagnosis_results", DiagnosisResult),
            ("report_records", ReportRecord),
            ("project_authorizations", ProjectAuthorization),
            ("sampling_events", SamplingEvent),
            ("dataset_versions", DatasetVersion),
            ("economic_indicators", EconomicIndicator),  # R3-P0-9: 补删经济表
            ("economic_raw_inputs", EconomicRawInput),   # R3-P0-9: 补删经济原始汇总
            ("measurements", Measurement),               # Round9: 先于 import_batches(被 FK 引用)
            ("import_batches", ImportBatch),
            ("sampling_points", SamplingPoint),
        ]:
            n = db.query(model).filter_by(site_id=site_id).delete(synchronize_session=False)
            if n > 0:
                deleted_counts[model_name] = n

        # 3. 删除场地本身
        # 注: RemediationCase 是案例库(无 site_id), 不参与场地删除级联
        db.delete(s)

        # 5. 审计墓碑(不含业务内容, 仅记录删除事件)
        log(db, action="delete_site", user_id=user.id,
            resource_type="site", resource_id=site_id,
            detail={"site_name": site_name, "site_code": site_code,
                    "deleted_counts": deleted_counts})
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"删除失败已回滚: {e}")

    return {"ok": True, "site_id": site_id, "site_name": site_name,
            "deleted_counts": deleted_counts}


# v1.0.1: 场地批量删除() — 复用单条级联逻辑, 事务化批量
@router.post("/sites/batch-delete")
def batch_delete_sites(payload: dict,
                       user: User = Depends(require_permission("data:delete")),
                       db: Session = Depends(get_db)):
    """批量删除场地, 接收 {ids: [int, ...]}, 返回每场地的删除结果。"""
    from app.models import (
        DatasetVersion, ProjectAuthorization, Recommendation,
        SamplingEvent, WorkflowAttachment, WorkflowRecord,
    )
    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        raise HTTPException(400, "ids 必须是非空列表")
    results = []
    for site_id in ids:
        s = db.get(Site, site_id)
        if not s:
            results.append({"site_id": site_id, "ok": False, "error": "场地不存在"})
            continue
        try:
            assert_site_access(db, user, s)
        except Exception:
            results.append({"site_id": site_id, "ok": False, "error": "无权限"})
            continue
        site_name = s.name
        site_code = s.site_code
        diag_ids = [d.id for d in db.query(DiagnosisResult.id).filter_by(site_id=site_id).all()]
        wf_ids = [w.id for w in db.query(WorkflowRecord.id).filter_by(site_id=site_id).all()]
        dc: dict = {}
        if wf_ids:
            n = db.query(WorkflowAttachment).filter(WorkflowAttachment.workflow_record_id.in_(wf_ids)).delete(synchronize_session=False)
            if n: dc["workflow_attachments"] = n
        if diag_ids:
            n = db.query(DiagnosisFactorDetail).filter(DiagnosisFactorDetail.diagnosis_id.in_(diag_ids)).delete(synchronize_session=False)
            if n: dc["diagnosis_factor_details"] = n
        for model_name, model in [
            ("workflow_records", WorkflowRecord), ("recommendations", Recommendation),
            ("evaluation_results", EvaluationResult), ("diagnosis_results", DiagnosisResult),
            ("report_records", ReportRecord), ("project_authorizations", ProjectAuthorization),
            ("sampling_events", SamplingEvent), ("dataset_versions", DatasetVersion),
            # Round8 审计六类 6.3-6.4: 批量删除补经济表(与单删保持一致)
            ("economic_indicators", EconomicIndicator),
            ("economic_raw_inputs", EconomicRawInput),
            # Round9 P0-7: measurements 在 import_batches 之前删(被 FK 引用)
            ("measurements", Measurement), ("import_batches", ImportBatch),
            ("sampling_points", SamplingPoint),
        ]:
            n = db.query(model).filter_by(site_id=site_id).delete(synchronize_session=False)
            if n: dc[model_name] = n
        db.delete(s)
        log(db, action="delete_site", user_id=user.id, resource_type="site", resource_id=site_id,
            detail={"site_name": site_name, "site_code": site_code, "batch": True, "deleted_counts": dc})
        results.append({"site_id": site_id, "ok": True, "site_name": site_name, "deleted_counts": dc})
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"批量删除失败已回滚: {e}")
    return {"ok": True, "results": results, "total": len(results),
            "succeeded": sum(1 for r in results if r.get("ok"))}



@router.get("/sites/{site_id}/points")
def site_points(site_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    pts = db.query(SamplingPoint).filter_by(site_id=site_id).order_by(SamplingPoint.id).all()
    return [{
        "id": p.id, "point_code": p.point_code, "region": p.region,
        "longitude": float(p.longitude) if p.longitude is not None else None,
        "latitude": float(p.latitude) if p.latitude is not None else None,
        "depth_top_cm": p.depth_top_cm, "depth_bottom_cm": p.depth_bottom_cm,
        "soil_type": p.soil_type,
    } for p in pts]


@router.get("/sites/{site_id}/points-wide")
def site_points_wide(site_id: int, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """采样点宽表: 每行=采样点, 列=全部实测因子值 + 元数据。供前端横向滚动表格。"""
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    pts = db.query(SamplingPoint).filter_by(site_id=site_id).order_by(SamplingPoint.id).all()
    rows = (db.query(Measurement, FactorDictionary)
            .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id).all())
    by_point: dict[int, dict] = {}
    factor_order: list[str] = []
    for m, fd in rows:
        by_point.setdefault(m.sampling_point_id, {})[fd.factor_code] = m.value
        if fd.factor_code not in factor_order:
            factor_order.append(fd.factor_code)
    items = []
    for i, p in enumerate(pts, 1):
        row = {"seq": i, "point_code": p.point_code, "region": p.region,
               "longitude": float(p.longitude) if p.longitude is not None else None,
               "latitude": float(p.latitude) if p.latitude is not None else None,
               "depth": f"{p.depth_top_cm or 0}-{p.depth_bottom_cm or 0}",
               "soil_type": p.soil_type}
        row.update(by_point.get(p.id, {}))
        items.append(row)
    # O2: 过滤全空因子列
    empty_factors = [f for f in factor_order if all(
        row.get(f) is None for row in items
    )]
    visible_factors = [f for f in factor_order if f not in empty_factors]
    return {
        "factors": visible_factors,
        "hidden_factors": empty_factors,
        "items": items,
        "total": len(items),
    }


@router.get("/sites/{site_id}/measurements")
def site_measurements(site_id: int, factor: str | None = None,
                      page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=500),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    query = (db.query(Measurement, FactorDictionary, SamplingPoint)
             .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
             .join(SamplingPoint, Measurement.sampling_point_id == SamplingPoint.id)
             .filter(Measurement.site_id == site_id))
    if factor:
        query = query.filter(FactorDictionary.factor_code == factor)
    total = query.count()
    rows = query.order_by(Measurement.id).offset((page - 1) * size).limit(size).all()
    items = [{
        "point_code": sp.point_code, "factor_code": fd.factor_code,
        "factor_name": fd.factor_name, "category": fd.level1_category,
        "value": m.value, "unit": m.unit,
    } for m, fd, sp in rows]
    return {"total": total, "page": page, "size": size, "items": items}


@router.get("/sites/{site_id}/measurements/export")
def export_site_measurements(site_id: int,
                format: str = Query("csv", pattern="^(csv|xlsx)$"),
                user: User = Depends(require_permission("data:export")),
                db: Session = Depends(get_db)):
    """导出场地检测长表(brief 4.3)。16 字段对齐项目验收, 中文不乱码, 写 audit log。"""
    import csv as _csv
    import io
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    rows = (db.query(Measurement, FactorDictionary, SamplingPoint)
            .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
            .join(SamplingPoint, Measurement.sampling_point_id == SamplingPoint.id)
            .filter(Measurement.site_id == site_id)
            .order_by(SamplingPoint.id, Measurement.id).all())
    if not rows:
        raise HTTPException(404, "该场地无检测数据, 无法导出")
    fields = ["site_code", "site_name", "point_code", "longitude", "latitude", "region",
              "depth_top_cm", "depth_bottom_cm", "factor_code", "factor_name", "category",
              "value", "unit", "source_file", "import_batch_id", "detected_at"]
    data = [[s.site_code, s.name, sp.point_code,
             float(sp.longitude) if sp.longitude is not None else None,
             float(sp.latitude) if sp.latitude is not None else None,
             sp.region, sp.depth_top_cm, sp.depth_bottom_cm,
             fd.factor_code, fd.factor_name, fd.level1_category,
             m.value, m.unit, m.source_file, m.import_batch_id,
             str(m.detected_at) if m.detected_at else None]
            for m, fd, sp in rows]
    # brief 4.3 / AC-16: 每次导出写 audit log
    log(db, action="export_measurements", user_id=user.id, resource_type="sites",
        resource_id=site_id, detail={"format": format, "n_rows": len(data)})
    if format == "csv":
        buf = io.StringIO()
        buf.write("﻿")  # utf-8-sig BOM, Excel 打开中文不乱码
        w = _csv.writer(buf)
        w.writerow(fields)
        w.writerows(data)
        return Response(content=buf.getvalue().encode("utf-8-sig"),
                        media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition":
                                 f'attachment; filename="measurements_site{site_id}.csv"'})
    # xlsx
    import pandas as _pd
    df = _pd.DataFrame(data, columns=fields)
    buf2 = io.BytesIO()
    with _pd.ExcelWriter(buf2, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="measurements")
    return Response(content=buf2.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition":
                             f'attachment; filename="measurements_site{site_id}.xlsx"'})


@router.get("/sites/{site_id}/eda")
def site_eda(site_id: int,
             include: str | None = Query(None,
                 description="逗号分隔: distribution,correlation,qq,boxplot,grouped。默认全返回"),
             group_by: str | None = Query(None,
                 description="分组维度: region/depth/factor。需 grouped 才生效"),
             factor: str | None = Query(None,
                 description="仅分析指定因子 code(单因子深挖)"),
             max_points: int = Query(2000, ge=100, le=10000,
                 description="distribution 采样上限, 防响应爆炸"),
             user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """场地进入模型前的 EDA 数据分析: 各因子统计体检 + 直方图 + 科研级图件数据。

    按需返回: boxplot(箱线五数) / distribution(原始分布采样) / qq(正态Q-Q) /
    correlation(跨因子相关矩阵) / grouped(按 region/depth/factor 分层)。
    全部基于真实数据, 不插补。
    """
    import os
    import sys
    import pandas as pd
    s = db.get(Site, site_id)
    if not s:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, s)
    from app.core.config import resource_root
    ml_eda = os.path.join(resource_root(), "ml", "eda")
    if ml_eda not in sys.path:
        sys.path.insert(0, ml_eda)
    from eda_profile import (  # type: ignore
        boxplot_summary, column_stats, correlation_matrix, distribution_sample,
        grouped_stats, histogram, qq_points,
    )

    # 长表查询: factor_code + value + 真实采样点 id/区域/深度(用于 grouped/correlation pivot)
    rows = (db.query(FactorDictionary.factor_code, FactorDictionary.level1_category,
                     Measurement.sampling_point_id,
                     Measurement.value, SamplingPoint.region,
                     SamplingPoint.depth_top_cm, SamplingPoint.depth_bottom_cm)
            .join(Measurement, Measurement.factor_id == FactorDictionary.id)
            .join(SamplingPoint, Measurement.sampling_point_id == SamplingPoint.id)
            .filter(Measurement.site_id == site_id).all())
    if not rows:
        raise HTTPException(404, "该场地无检测数据")
    df = pd.DataFrame(rows, columns=["factor", "category", "point_id", "value", "region",
                                     "depth_top", "depth_bottom"])

    # 解析 include 参数(默认全返回, 兼容前端旧调用)
    inc = {x.strip() for x in include.split(",") if x.strip()} if include else {
        "distribution", "correlation", "qq", "boxplot", "grouped",
        "hypothesis_test", "effect_size", "pca", "outlier_detail"}

    # 非因子列兜底过滤: 误把"深度上限/下限/筛选值/管制值"等映射为因子的情形
    NON_FACTOR_KEYWORDS = ("上限", "下限", "筛选值", "管制值", "标准值", "限值", "阈值")
    factors = []
    for fc, sub in df.groupby("factor"):
        if factor and fc != factor:
            continue
        if any(kw in str(fc) for kw in NON_FACTOR_KEYWORDS):
            continue
        st = column_stats(sub["value"])
        item = {"factor": fc, "category": sub["category"].iloc[0] if len(sub) else None,
                "stats": st, "histogram": histogram(sub["value"], bins=15)}
        if "boxplot" in inc:
            item["boxplot"] = boxplot_summary(sub["value"])
        if "distribution" in inc:
            item["distribution"] = distribution_sample(sub["value"], max_points=max_points)
        if "qq" in inc:
            item["qq"] = qq_points(sub["value"])
        factors.append(item)
    factors.sort(key=lambda x: x["factor"])

    resp: dict = {"site_id": site_id, "n_factors": len(factors), "factors": factors}

    if "correlation" in inc and len(factors) >= 2:
        # pivot 成宽表: 行=真实采样点 id, 列=因子。不能用 region/depth 这种弱键, 否则同区同层样点会被合并。
        pivot = df.pivot_table(index="point_id", columns="factor", values="value", aggfunc="mean")
        resp["correlation"] = correlation_matrix(pivot)

    if "grouped" in inc:
        # 所选分组维度值不足 → 自动降级 region → depth → factor, 不返回空图
        requested_gb = group_by if group_by in ("region", "depth", "factor") else "region"
        effective_gb = requested_gb
        degraded_reason = None
        df["_depth_band"] = df.apply(
            lambda r: f"{int(r['depth_top']) if pd.notna(r['depth_top']) else 0}-"
                      f"{int(r['depth_bottom']) if pd.notna(r['depth_bottom']) else 0}cm", axis=1)

        def _nunique(col: str) -> int:
            s = df[col].dropna().astype(str)
            return s[s.str.strip() != ""].nunique()

        if effective_gb == "region" and _nunique("region") < 2:
            effective_gb = "depth"
            degraded_reason = "场地无区域(region)信息或仅单一区域, 已自动切换为按深度分组"
        if effective_gb == "depth" and _nunique("_depth_band") < 2:
            effective_gb = "factor"
            degraded_reason = (degraded_reason + "; 深度维度亦不足, 已切换为按因子分组"
                               if degraded_reason
                               else "区域与深度维度均不足, 已切换为按因子分组")
        gcol = {"region": "region", "depth": "_depth_band", "factor": "factor"}[effective_gb]
        # 全因子整体分组 + 每个因子单独分组(便于按因子看分层差异)
        per_factor = {}
        for fc, sub in df.groupby("factor"):
            per_factor[fc] = grouped_stats(sub, "value", gcol)
        resp["grouped"] = {"group_by": effective_gb,
                           "requested_group_by": requested_gb,
                           "degraded_reason": degraded_reason,
                           "overall": grouped_stats(df, "value", gcol),
                           "per_factor": per_factor}

    # ── 节五新增: 假设检验 / 效应量 / PCA / 异常值明细 ──
    # 分组依据: 用 region(或 depth_band) 把采样点分两组, 检验"不同区位同一因子浓度是否有显著差异"。
    import numpy as np
    try:
        from scipy import stats as scistats
    except Exception:
        scistats = None

    # 准备分组键(每组 >= 3 样本才参与检验, 防小样本噪声)
    _fallback_grp = df["_depth_band"] if "_depth_band" in df.columns else "未知"
    df["_grp"] = df["region"].fillna(_fallback_grp)
    grp_values = df["_grp"].dropna().astype(str)
    grp_values = grp_values[grp_values.str.strip() != ""]
    valid_groups = [g for g in grp_values.unique() if (df["_grp"].astype(str) == g).sum() >= 3]

    if "hypothesis_test" in inc and scistats and len(valid_groups) >= 2 and len(factors) > 0:
        ht_items = []
        g1_name, g2_name = valid_groups[0], valid_groups[1]
        for fc, sub in df.groupby("factor"):
            v1 = sub.loc[sub["_grp"].astype(str) == g1_name, "value"].dropna().tolist()
            v2 = sub.loc[sub["_grp"].astype(str) == g2_name, "value"].dropna().tolist()
            if len(v1) < 3 or len(v2) < 3:
                continue
            try:
                u_stat, u_p = scistats.mannwhitneyu(v1, v2, alternative="two-sided")
            except Exception:
                u_stat, u_p = None, None
            ht_items.append({"factor": fc, "group_a": g1_name, "group_b": g2_name,
                             "n_a": len(v1), "n_b": len(v2),
                             "mann_whitney_u": round(float(u_stat), 3) if u_stat is not None else None,
                             "mann_whitney_p": round(float(u_p), 5) if u_p is not None else None,
                             "significant": bool(u_p is not None and u_p < 0.05)})
        # Kruskal-Wallis: 多组(若 >=3 组)
        kw_items = []
        if len(valid_groups) >= 3:
            for fc, sub in df.groupby("factor"):
                samples = [sub.loc[sub["_grp"].astype(str) == g, "value"].dropna().tolist()
                           for g in valid_groups]
                samples = [s for s in samples if len(s) >= 3]
                if len(samples) < 3:
                    continue
                try:
                    h_stat, h_p = scistats.kruskal(*samples)
                except Exception:
                    h_stat, h_p = None, None
                kw_items.append({"factor": fc, "n_groups": len(samples),
                                 "kruskal_h": round(float(h_stat), 3) if h_stat is not None else None,
                                 "kruskal_p": round(float(h_p), 5) if h_p is not None else None})
        resp["hypothesis_test"] = {"mann_whitney": ht_items, "kruskal_wallis": kw_items,
                                   "note": f"Mann-Whitney U 检验 {g1_name} vs {g2_name}; p<0.05 表示两组浓度分布有显著差异"}

    if "effect_size" in inc and scistats and len(valid_groups) >= 2 and len(factors) > 0:
        es_items = []
        g1_name, g2_name = valid_groups[0], valid_groups[1]
        for fc, sub in df.groupby("factor"):
            v1 = sub.loc[sub["_grp"].astype(str) == g1_name, "value"].dropna().astype(float).values
            v2 = sub.loc[sub["_grp"].astype(str) == g2_name, "value"].dropna().astype(float).values
            if len(v1) < 2 or len(v2) < 2:
                continue
            # Cohen's d
            m1, m2, s1, s2 = np.mean(v1), np.mean(v2), np.std(v1, ddof=1), np.std(v2, ddof=1)
            pooled_sd = np.sqrt((s1**2 + s2**2) / 2) if (s1 + s2) > 0 else 0
            d = (m1 - m2) / pooled_sd if pooled_sd > 0 else 0
            # Cliff's delta (非参, 更稳健)
            delta = 0.0
            n = 0
            for a in v1:
                for b in v2:
                    n += 1
                    if a > b: delta += 1
                    elif a < b: delta -= 1
            cliff = delta / n if n > 0 else 0
            mag = "可忽略" if abs(d) < 0.2 else "小" if abs(d) < 0.5 else "中" if abs(d) < 0.8 else "大"
            es_items.append({"factor": fc, "group_a": g1_name, "group_b": g2_name,
                             "cohens_d": round(float(d), 3), "cliffs_delta": round(float(cliff), 3),
                             "magnitude": mag})
        resp["effect_size"] = {"items": es_items,
                               "note": "Cohen's d: |d|<0.2可忽略/0.2-0.5小/0.5-0.8中/>0.8大; Cliff's delta 非参更稳健"}

    if "pca" in inc and len(factors) >= 2:
        try:
            from sklearn.decomposition import PCA as SKPCA
            from sklearn.preprocessing import StandardScaler
            pivot = df.pivot_table(index="point_id", columns="factor", values="value", aggfunc="mean").dropna()
            if pivot.shape[0] >= 3 and pivot.shape[1] >= 2:
                X = StandardScaler().fit_transform(pivot.values)
                n_comp = min(3, pivot.shape[1], pivot.shape[0])
                pca = SKPCA(n_components=n_comp)
                scores = pca.fit_transform(X)
                resp["pca"] = {
                    "factors": pivot.columns.tolist(),
                    "n_samples": int(pivot.shape[0]),
                    "n_components": n_comp,
                    "explained_variance_ratio": [round(float(v), 4) for v in pca.explained_variance_ratio_],
                    "cumulative_variance": round(float(np.cumsum(pca.explained_variance_ratio_)[-1]), 4),
                    "loadings": [{"factor": pivot.columns[i],
                                  "pc1": round(float(pca.components_[0][i]), 3),
                                  "pc2": round(float(pca.components_[1][i]), 3) if n_comp >= 2 else None}
                                 for i in range(pivot.shape[1])],
                    "scores_sample": [{"pc1": round(float(scores[j][0]), 3),
                                       "pc2": round(float(scores[j][1]), 3) if n_comp >= 2 else None}
                                      for j in range(min(len(scores), 200))],
                    "note": "PCA 基于标准化后采样点宽表; PC1/PC2 载荷反映各因子对主成分的贡献方向",
                }
        except Exception:
            pass

    if "outlier_detail" in inc and len(factors) > 0:
        od_items = []
        for fc, sub in df.groupby("factor"):
            vals = sub["value"].dropna().astype(float)
            if len(vals) < 4:
                continue
            q1, q3 = vals.quantile(0.25), vals.quantile(0.75)
            iqr = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            mean, std = vals.mean(), vals.std(ddof=0)
            for _, r in sub.iterrows():
                v = r["value"]
                if pd.isna(v):
                    continue
                v = float(v)
                z = (v - mean) / std if std > 0 else 0
                is_iqr = v < lo or v > hi
                is_z = abs(z) > 3
                if is_iqr or is_z:
                    od_items.append({"factor": fc, "point_id": int(r["point_id"]) if pd.notna(r["point_id"]) else None,
                                     "value": round(v, 4), "z_score": round(float(z), 3),
                                     "method": ("IQR" if is_iqr else "") + ("+Z" if is_z else "").lstrip("+"),
                                     "threshold": f"IQR({round(lo,3)}~{round(hi,3)}) / |Z|>3"})
        resp["outlier_detail"] = {"items": od_items[:200], "total": len(od_items),
                                  "note": "IQR 法(Q1-1.5×IQR ~ Q3+1.5×IQR) + Z-score(|Z|>3); 双法命中更可信"}

    return resp


@router.get("/import-batches/{batch_id}/validation-report")
def validation_report(batch_id: int, user: User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    b = db.get(ImportBatch, batch_id)
    if not b:
        raise HTTPException(404, "导入批次不存在")
    # v0.2 P1-6: 校验报告数据隔离 — 企业用户只能看自己的
    if b.site_id:
        site = db.get(Site, b.site_id)
        if site:
            assert_site_access(db, user, site)
    return {
        "batch_id": b.id, "site_id": b.site_id, "source_file": b.source_file,
        "row_count": b.row_count, "valid_count": b.valid_count,
        "invalid_count": b.invalid_count, "status": b.status,
        "report": b.validation_report,
    }


