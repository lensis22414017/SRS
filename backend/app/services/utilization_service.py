"""v1.1 (C3): 利用方向决策服务 — 组装门禁输入 + 功能评分, 调用 ml/evaluation/utilization.py 并持久化。

修复前(pre_remediation): 点位 = 修复前检测值; 功能评分 = 课题二重构可行性(reconstruction_prod/eco)。
修复后(post_remediation): 点位 = 课题三批次中的修复后污染物检测; 功能评分 = 课题三 SSUI(ssui_post_*)。
"""
from __future__ import annotations

import os
import sys

from sqlalchemy.orm import Session

from app.core.config import resource_root
from app.models import (POST_REMEDIATION, PRE_REMEDIATION, EvaluationResult, FactorDictionary, ImportBatch,
                        Measurement, SamplingPoint, Site, SSUIImportBatch, UtilizationDecision)
from app.services import audit_service

ROOT = resource_root()
_ML = os.path.join(ROOT, "ml", "evaluation")
if _ML not in sys.path:
    sys.path.insert(0, _ML)
import utilization as U  # noqa: E402

_UNIT = {"mg/kg": 1.0, "mgkg": 1.0, "mg·kg-1": 1.0, "μg/kg": 1e-3, "ug/kg": 1e-3, "µg/kg": 1e-3,
         "ng/g": 1e-3, "ng/kg": 1e-6, "g/kg": 1e3, "": 1.0, None: 1.0}
_PH_NAMES = {"pH", "ph", "PH", "pH值"}
_GATE_KEYS = {U._key(x) for x in U.GB15618_REQUIRED + U.GB36600_BASIC}


def _norm_unit(u):
    return None if u is None else str(u).strip().lower().replace(" ", "")


def _pre_points(db: Session, site_id: int) -> tuple[list[dict], list[str], str]:
    rows = (db.query(SamplingPoint.point_code, FactorDictionary.factor_name, FactorDictionary.factor_code,
                     Measurement.value, Measurement.unit, Measurement.data_origin)
            .join(Measurement, Measurement.sampling_point_id == SamplingPoint.id)
            .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id, Measurement.stage == PRE_REMEDIATION,
                    Measurement.value.isnot(None), Measurement.qa_status != "rejected").all())
    pts: dict = {}
    skipped: set = set()
    origins: set = set()
    for pc, fname, fcode, val, unit, origin in rows:
        origins.add(origin or "field")
        p = pts.setdefault(pc, {"point": pc, "pH": None})
        name = fname or fcode
        if name in _PH_NAMES or fcode in _PH_NAMES:
            p["pH"] = float(val); continue
        canon = U.canonical_factor(name)
        u = _norm_unit(unit)
        if u not in _UNIT:
            if U._key(canon) in _GATE_KEYS:
                skipped.add(f"{name}({unit})")
            continue
        v = float(val) * _UNIT[u]
        p[canon] = max(p.get(canon, float("-inf")), v)
    notes = [f"单位无法识别, 未参与门禁: {', '.join(sorted(skipped))}"] if skipped else []
    # v1.2: 课题二 28 项指标批次中的污染物与 pH 同属修复前点位数据, 一并参与法规门禁
    from app.services import recon_import_service as RI
    b = RI.latest_confirmed(db, site_id)
    if b is not None:
        _s2 = {"cd": "Cd", "hg": "Hg", "as": "As", "pb": "Pb", "cr": "Cr", "cu": "Cu", "ni": "Ni", "zn": "Zn",
               "bap": "苯并[a]芘"}
        merged, separate, conflicts = 0, 0, []
        for p2 in RI.batch_points(db, b):
            q = {"point": f"S2:{p2['point']}", "pH": p2.get("ph")}
            for fid, canon in _s2.items():
                if isinstance(p2.get(fid), (int, float)):
                    q[canon] = float(p2[fid])
            # v1.2.1(R03): 点位编号与修复前检测点相同且共有因子数值一致 → 同一样品, 合并而不重复计数
            base = pts.get(str(p2["point"]))
            if base is not None:
                diff = [k for k, v in q.items() if k not in ("point", "pH") and k in base
                        and abs(float(base[k]) - v) > 1e-6 * max(1.0, abs(v))]
                if not diff:
                    for k, v in q.items():
                        if k == "point":
                            continue
                        if k == "pH":
                            if base.get("pH") is None and v is not None:
                                base["pH"] = float(v)
                        elif k not in base:
                            base[k] = v
                    merged += 1
                    continue
                conflicts.append(f"{p2['point']}({'、'.join(diff)})")
            pts[q["point"]] = q
            separate += 1
        origins.add(b.data_origin or "client_real")
        notes.append(f"已纳入课题二指标批次 #{b.id} 的 {b.point_count} 个点位污染物/pH 数据"
                     f"(与修复前检测点同一样品合并 {merged} 个, 单独计入 {separate} 个)")
        if conflicts:
            notes.append("课题二批次与修复前检测同编号点位数值不一致, 已分别计入并需复核: " + "、".join(conflicts[:10]))
    origin = "monte_carlo_demo" if "monte_carlo_demo" in origins else (
        "test_fixture" if "test_fixture" in origins else ("client_real" if origins else "field"))
    return list(pts.values()), notes, origin


def _score_from_eval(ev: EvaluationResult | None, label: str) -> dict | None:
    if ev is None:
        return {"value": None, "feasible": None, "reason": f"{label}未计算", "source": label}
    g = ev.grade or ""
    feasible = True if g == "可行" else (False if g == "不可行" else None)
    status = None
    if ev.eval_type.startswith("ssui_post_"):
        dims = ev.dimensions or {}
        from app.services.ssui_post_service import effective_status
        status = effective_status(ev)  # v1.2.1 旧记录无 status: 按原值推导
        # v1.2.2(T01): 只有域内(ok)结果可作功能评分依据; out_of_domain / invalid / insufficient 一律不支持
        feasible = dims.get("feasible") if status == "ok" else None
        if status == "out_of_domain":
            return {"value": ev.score, "label": None, "feasible": None, "source": label, "evaluation_id": ev.id,
                    "status": status, "legacy_record": not dims.get("status"), "stored_grade": g or None,
                    "reason": f"{label}原值 {ev.score} 超出等级有效域 [0, 1.0]: 不分级、不作功能支持判断(原值保留)"}
    return {"value": ev.score, "label": g, "feasible": feasible, "source": label, "evaluation_id": ev.id,
            "status": status,
            "reason": None if feasible is not None else f"{label}结果为'{g or '无'}'(证据不足/受阻)"}


def _latest(db: Session, site_id: int, eval_type: str, stage: str | None = None):
    q = db.query(EvaluationResult).filter(EvaluationResult.site_id == site_id, EvaluationResult.eval_type == eval_type)
    if stage:
        q = q.filter(EvaluationResult.stage == stage)
    return q.order_by(EvaluationResult.id.desc()).first()


def run(db: Session, site_id: int, stage: str = PRE_REMEDIATION, *, farmland_type: str | None = None,
        eco_land_class: str | None = None, user_id: int | None = None) -> dict:
    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"场地不存在: {site_id}")
    notes: list[str] = []
    batch_ref = {}
    if stage == PRE_REMEDIATION:
        points, notes, origin = _pre_points(db, site_id)
        ps = _score_from_eval(_latest(db, site_id, "reconstruction_prod"), "课题二生产重构可行性")
        es = _score_from_eval(_latest(db, site_id, "reconstruction_eco"), "课题二生态重构可行性")
    elif stage == POST_REMEDIATION:
        bp = (db.query(SSUIImportBatch).filter_by(site_id=site_id, track="production", status="confirmed")
              .order_by(SSUIImportBatch.id.desc()).first())
        be = (db.query(SSUIImportBatch).filter_by(site_id=site_id, track="ecology", status="confirmed")
              .order_by(SSUIImportBatch.id.desc()).first())
        latest = max([b for b in (bp, be) if b], key=lambda b: b.id, default=None)
        points = (latest.validation_report or {}).get("points", []) if latest else []
        origin = latest.data_origin if latest else "field"
        if not latest:
            notes.append("尚无已确认的修复后(课题三)导入批次")
        batch_ref = {"production_batch": bp.id if bp else None, "ecology_batch": be.id if be else None,
                     "points_batch": latest.id if latest else None}
        ps = _score_from_eval(_latest(db, site_id, "ssui_post_production", POST_REMEDIATION), "课题三生产 SSUI")
        es = _score_from_eval(_latest(db, site_id, "ssui_post_ecology", POST_REMEDIATION), "课题三生态 SSUI")
    else:
        raise ValueError("stage 必须为 pre_remediation / post_remediation")
    res = U.decide(stage, points, pollution_type=site.pollution_type, farmland_type=farmland_type,
                   eco_land_class=eco_land_class, production_score=ps, ecology_score=es, data_origin=origin)
    res["assumptions"] = res["assumptions"] + notes
    res["evidence_refs"] = batch_ref
    rec = UtilizationDecision(site_id=site_id, stage=stage, decision_state=res["decision_state"],
                              conclusion_text=res["conclusion_text"],
                              production_gate=res["production"]["gate"], ecology_gate=res["ecology"]["gate"],
                              production_score=(ps or {}).get("value"), ecology_score=(es or {}).get("value"),
                              evidence={"production": res["production"], "ecology": res["ecology"],
                                        "use_state": res.get("use_state"), "hypothetical_screen": res.get("hypothetical_screen"),
                                        "use_scope_note": res.get("use_scope_note"),
                                        "farmland_type": farmland_type, "eco_land_class": eco_land_class,
                                        "remediation_targets": res["remediation_targets"], "refs": batch_ref,
                                        "standards_sha256": res["standards_sha256"]},
                              assumptions=res["assumptions"], missing_evidence=res["missing_evidence"],
                              method_version=res["method_version"], method_status=res["method_status"],
                              input_fingerprint=res["input_fingerprint"], data_origin=origin, created_by=user_id)
    db.add(rec); db.flush()
    audit_service.log(db, "utilization_decide", user_id, "utilization_decision", rec.id,
                      detail={"stage": stage, "state": res["decision_state"]}, commit=False)
    db.commit()
    res["decision_id"] = rec.id
    res.pop("points", None)
    return res


def latest(db: Session, site_id: int, stage: str | None = None) -> UtilizationDecision | None:
    q = db.query(UtilizationDecision).filter_by(site_id=site_id)
    if stage:
        q = q.filter_by(stage=stage)
    return q.order_by(UtilizationDecision.id.desc()).first()


def to_dict(d: UtilizationDecision) -> dict:
    return {"decision_id": d.id, "site_id": d.site_id, "stage": d.stage, "decision_state": d.decision_state,
            "conclusion_text": d.conclusion_text, "production_gate": d.production_gate,
            "ecology_gate": d.ecology_gate, "production_score": d.production_score,
            "ecology_score": d.ecology_score, "evidence": d.evidence, "assumptions": d.assumptions,
            "missing_evidence": d.missing_evidence, "method_version": d.method_version,
            "method_status": d.method_status, "input_fingerprint": d.input_fingerprint,
            "data_origin": d.data_origin, "created_at": d.created_at.isoformat() if d.created_at else None,
            "is_post_remediation_conclusion": d.stage == POST_REMEDIATION,
            "use_state": (d.evidence or {}).get("use_state"),
            "hypothetical_screen": (d.evidence or {}).get("hypothetical_screen"),
            "use_scope_note": (d.evidence or {}).get("use_scope_note")}


def point_screening_ratios(db: Session, site_id: int, *, farmland_type: str | None = None) -> dict:
    """v1.2.1(R03): 地图图层与报告图件共用的逐点超标倍数(修复前, GB 15618-2018 筛选值, 按点位 pH 选档)。

    与法规门禁同一数据(_pre_points: 单位换算、课题二同样品合并)与同一阈值表(utilization.load_standards)。
    农用地类型未指定时取水田/其他较严者; pH 未知时取各档最严值(保守, 与门禁一致)。
    返回 {point_code: {"ratio", "factor", "value", "threshold", "ph", "basis"}}; 无可判定因子的点位不出现。
    """
    points, _notes, _origin = _pre_points(db, site_id)
    std = U.load_standards()
    ft = farmland_type if farmland_type in ("水田", "其他") else None
    out: dict = {}
    for p in points:
        ph = p.get("pH")
        try:
            ph = float(ph) if ph is not None else None
        except (TypeError, ValueError):
            ph = None
        best = None
        for f in U.GB15618_REQUIRED:
            v = p.get(f)
            if not isinstance(v, (int, float)):
                continue
            scr = U._gb15618_limits(std, f, ph, ft)[0]
            if not scr:
                continue
            r = float(v) / scr
            if best is None or r > best["ratio"]:
                best = {"ratio": round(r, 4), "factor": f, "value": float(v), "threshold": scr, "ph": ph,
                        "basis": f"GB 15618-2018 筛选值({ft or '水田/其他较严者'}; 按点位 pH 选档)"}
        if best is not None:
            out[str(p["point"])] = best
    return out
