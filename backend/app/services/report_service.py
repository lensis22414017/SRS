"""全流程追溯报告生成: 聚合 15 项 -> Jinja2 HTML -> PDF(weasyprint 优先, xhtml2pdf 降级)。

PDF 三级降级策略:
  1. weasyprint (高质量 CSS 渲染, 需系统库 pango/cairo)
  2. xhtml2pdf + reportlab CID 字体 (无需系统库, 纯 Python)
  3. 纯 HTML (以上均不可用时, 保留完整内容)
报告入 report_records + file_objects, 带版本与数据快照。
"""
from __future__ import annotations

import os
import statistics
from io import BytesIO
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    AuditLog, DiagnosisResult, EvaluationResult, FactorDictionary, FileObject,
    ImportBatch, Measurement, MLModel, Recommendation, ReportRecord, SamplingPoint,
    RemediationCase, Site, StandardThreshold, TechnologyLibrary, WorkflowAttachment,
    WorkflowRecord,
)
from app.services.file_service import save_bytes
from app.services.workflow_service import STAGE_NAME, get_stages

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TEMPLATE_DIR = os.path.join(ROOT, "reporting", "templates")
TEMPLATE_VERSION = "tpl_v0.1"


def _factor_summary(db: Session, site_id: int) -> list[dict]:
    rows = (db.query(FactorDictionary.factor_code, FactorDictionary.level1_category,
                     Measurement.value, Measurement.unit)
            .join(Measurement, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id).all())
    agg: dict[str, dict] = {}
    for code, cat, val, unit in rows:
        if val is None:
            continue
        d = agg.setdefault(code, {"factor": code, "category": cat, "vals": [], "unit": unit})
        d["vals"].append(val)
    out = []
    for d in agg.values():
        vs = d["vals"]
        out.append({"factor": d["factor"], "category": d["category"], "count": len(vs),
                    "min": round(min(vs), 3), "mean": round(statistics.mean(vs), 3),
                    "max": round(max(vs), 3), "unit": d["unit"]})
    out.sort(key=lambda x: x["factor"])
    return out


def _coverage_summary(db: Session, site_id: int, n_points: int) -> dict:
    factor_count = (db.query(FactorDictionary.factor_code)
                    .join(Measurement, Measurement.factor_id == FactorDictionary.id)
                    .filter(Measurement.site_id == site_id)
                    .distinct().count())
    n_meas = db.query(Measurement).filter_by(site_id=site_id).count()
    denominator = n_points * factor_count if n_points and factor_count else 0
    coverage = round(n_meas / denominator * 100, 2) if denominator else 0
    return {
        "factor_count": factor_count,
        "observed_cells": n_meas,
        "expected_cells": denominator,
        "coverage_pct": coverage,
        "missing_pct": round(100 - coverage, 2) if denominator else 0,
        "note": "measurements 长表只保存实测项; 未检测字段不会伪造为 0。",
    }


def _standard_versions(db: Session) -> list[dict]:
    rows = (db.query(StandardThreshold.standard_code, StandardThreshold.standard_name,
                     StandardThreshold.version, StandardThreshold.source_reference)
            .distinct().all())
    return [{"standard_code": c, "standard_name": n, "version": v,
             "source_reference": r} for c, n, v, r in rows]


def _remediation_cases(db: Session, site: Site, limit: int = 8) -> list[dict]:
    q = db.query(RemediationCase)
    if site.pollution_type:
        token = {"heavy_metal": "HM", "organic": "OP", "composite": "HM+OP"}.get(
            site.pollution_type, site.pollution_type)
        q = q.filter(RemediationCase.pollution_type.contains(token))
    rows = q.limit(limit).all()
    if not rows:
        rows = db.query(RemediationCase).limit(limit).all()
    return [{
        "case_id": r.case_id,
        "site_type": r.site_type,
        "region": r.region,
        "land_use": r.land_use,
        "pollution_type": r.pollution_type,
        "pollutants": r.pollutants,
        "remediation_technology": r.remediation_technology,
        "technology_category": r.technology_category,
        "cost_level": r.cost_level,
        "effectiveness": r.effectiveness,
        "limitation": r.limitation,
        "secondary_risk": r.secondary_risk,
        "evidence_source": r.evidence_source,
        "doi": r.doi,
    } for r in rows]


def collect(db: Session, site_id: int, version: str) -> dict:
    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"场地不存在: {site_id}")

    batch = (db.query(ImportBatch).filter_by(site_id=site_id)
             .order_by(ImportBatch.id.desc()).first())
    points = db.query(SamplingPoint).filter_by(site_id=site_id).all()
    n_meas = db.query(Measurement).filter_by(site_id=site_id).count()
    vr = (batch.validation_report or {}) if batch else {}

    diag = (db.query(DiagnosisResult).filter_by(site_id=site_id)
            .order_by(DiagnosisResult.id.desc()).first())
    diag_ctx = None
    if diag:
        from app.models import DiagnosisFactorDetail
        model = db.get(MLModel, diag.model_id) if diag.model_id else None
        details = (db.query(DiagnosisFactorDetail, FactorDictionary)
                   .join(FactorDictionary, DiagnosisFactorDetail.factor_id == FactorDictionary.id)
                   .filter(DiagnosisFactorDetail.diagnosis_id == diag.id,
                           DiagnosisFactorDetail.sampling_point_id.is_(None))
                   .order_by(DiagnosisFactorDetail.rank).all())
        diag_ctx = {
            "model_name": model.model_name if model else "RF",
            "model_version": model.version if model else "—",
            "metrics": (model.metrics if model else {}) or {},
            "data_version": diag.data_version, "summary": diag.summary,
            "top_factors": [{"rank": d.rank, "factor": fd.factor_name,
                             "category": fd.level1_category,
                             "importance": d.importance, "direction": d.direction}
                            for d, fd in details],
        }

    evals = {e.eval_type: e for e in
             db.query(EvaluationResult).filter_by(site_id=site_id)
             .order_by(EvaluationResult.id.desc()).all()[::-1]}
    recon = []
    for et, title in (("reconstruction_prod", "生产功能重构"),
                      ("reconstruction_eco", "生态功能重构")):
        e = evals.get(et)
        if e:
            recon.append({"title": title, "score": e.score, "grade": e.grade,
                          "limiting_factors": e.limiting_factors or [],
                          "explanation": e.explanation})
    ssui_e = evals.get("ssui")
    ssui_ctx = ({"score": ssui_e.score, "grade": ssui_e.grade,
                 "explanation": ssui_e.explanation} if ssui_e else None)

    recs = (db.query(Recommendation).filter_by(site_id=site_id)
            .order_by(Recommendation.rank).all())
    tech = {t.id: t for t in db.query(TechnologyLibrary).all()}
    rec_ctx = []
    for r in recs:
        t = tech.get(r.technology_id)
        rec_ctx.append({
            "rank": r.rank,
            "technology": t.tech_name if t else "—",
            "match_score": r.match_score,
            "reason": r.reason or "",
            "cost_level": t.cost_level if t else None,
            "duration_level": t.duration_level if t else None,
            "limitations": t.limitations if t else None,
            "forbidden_conditions": t.forbidden_conditions if t else None,
            "secondary_risk": t.secondary_risk if t else None,
        })

    workflow = get_stages(db, site_id)
    attachments = []
    for w in db.query(WorkflowRecord).filter_by(site_id=site_id).all():
        for a in db.query(WorkflowAttachment).filter_by(workflow_record_id=w.id).all():
            fo = db.get(FileObject, a.file_object_id)
            attachments.append({"stage_name": STAGE_NAME.get(w.stage), "file_role": a.file_role,
                                "original_name": fo.original_name if fo else "—"})

    logs = (db.query(AuditLog).order_by(AuditLog.id.desc()).limit(10).all())
    audit_ctx = [{"created_at": str(a.created_at), "action": a.action,
                  "resource_type": a.resource_type, "resource_id": a.resource_id,
                  "result": a.result} for a in logs]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return {
        "site": {"site_code": site.site_code, "name": site.name,
                 "pollution_type": site.pollution_type, "land_use_type": site.land_use_type,
                 "province": site.province, "city": site.city,
                 "longitude": float(site.longitude) if site.longitude is not None else None,
                 "latitude": float(site.latitude) if site.latitude is not None else None},
        "data_source": {"source_file": batch.source_file if batch else None,
                        "batch_id": batch.id if batch else None,
                        "status": batch.status if batch else None,
                        "script_version": batch.script_version if batch else None,
                        "n_points": len(points), "n_measurements": n_meas},
        "sampling_points": [{"point_code": p.point_code, "region": p.region,
                             "longitude": float(p.longitude) if p.longitude is not None else None,
                             "latitude": float(p.latitude) if p.latitude is not None else None,
                             "depth_top_cm": p.depth_top_cm, "depth_bottom_cm": p.depth_bottom_cm,
                             "soil_type": p.soil_type} for p in points],
        "factor_summary": _factor_summary(db, site_id),
        "coverage": _coverage_summary(db, site_id, len(points)),
        "validation": {"passed": vr.get("passed", True), "n_errors": vr.get("n_errors", 0),
                       "n_warnings": vr.get("n_warnings", 0), "n_exceed": vr.get("n_exceed", 0),
                       "exceed_factors": (vr.get("summary", {}) or {}).get("exceed_factors", [])},
        "diagnosis": diag_ctx, "reconstruction": recon, "ssui": ssui_ctx,
        "recommendations": rec_ctx,
        "remediation_cases": _remediation_cases(db, site),
        "standard_versions": _standard_versions(db),
        "workflow": workflow,
        "attachments": attachments, "audit_logs": audit_ctx,
        "report": {"version": version, "template_version": TEMPLATE_VERSION,
                   "data_version": diag.data_version if diag else f"site{site_id}",
                   "standard_version": "GB15618/GB36600/HJ25.5-2018",
                   "generated_at": now},
    }


def render_html(context: dict) -> str:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR),
                      autoescape=select_autoescape(["html"]))
    return env.get_template("traceability_report.html").render(**context)


def html_to_pdf(html: str) -> bytes | None:
    """HTML → PDF: weasyprint 优先 (高质量), xhtml2pdf 降级, 均失败返回 None。"""
    # 第一级: weasyprint (CSS3 完整支持, 中文排版好)
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except (ImportError, OSError):
        pass
    # 第二级: xhtml2pdf + reportlab UnicodeCID 字体 (纯 Python, 无需系统库)
    try:
        from io import BytesIO
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from xhtml2pdf import pisa
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        except Exception:
            pass
        buf = BytesIO()
        result = pisa.CreatePDF(src=html, dest=buf, encoding="utf-8")
        if result.err:
            return None
        return buf.getvalue()
    except ImportError:
        return None


def render_docx(context: dict) -> bytes:
    """生成 DOCX 字节。保持和 HTML/PDF 同一数据上下文。"""
    from docx import Document

    doc = Document()
    doc.add_heading("污染场地全流程监管追溯报告", level=0)
    doc.add_paragraph(f"{context['site']['name']}（{context['site']['site_code']}）")
    doc.add_paragraph(f"报告版本 {context['report']['version']}｜生成时间 {context['report']['generated_at']}")

    def add_kv(title: str, rows: list[tuple[str, object]]):
        doc.add_heading(title, level=1)
        table = doc.add_table(rows=0, cols=2)
        table.style = "Table Grid"
        for k, v in rows:
            cells = table.add_row().cells
            cells[0].text = str(k)
            cells[1].text = "" if v is None else str(v)

    add_kv("场地基本信息", [
        ("场地编号", context["site"]["site_code"]),
        ("场地名称", context["site"]["name"]),
        ("污染类型", context["site"]["pollution_type"]),
        ("用地类型", context["site"]["land_use_type"]),
        ("行政区划", f"{context['site']['province'] or ''} {context['site']['city'] or ''}"),
    ])
    add_kv("数据覆盖率与缺失率摘要", [
        ("采样点数", context["data_source"]["n_points"]),
        ("检测记录数", context["data_source"]["n_measurements"]),
        ("实测因子数", context["coverage"]["factor_count"]),
        ("覆盖率", f"{context['coverage']['coverage_pct']}%"),
        ("缺失率", f"{context['coverage']['missing_pct']}%"),
        ("说明", context["coverage"]["note"]),
    ])

    doc.add_heading("Top-N 障碍因子", level=1)
    if context.get("diagnosis") and context["diagnosis"].get("top_factors"):
        table = doc.add_table(rows=1, cols=5)
        table.style = "Table Grid"
        for i, h in enumerate(["排名", "因子", "类别", "重要性", "方向"]):
            table.rows[0].cells[i].text = h
        for t in context["diagnosis"]["top_factors"]:
            cells = table.add_row().cells
            cells[0].text = str(t["rank"])
            cells[1].text = str(t["factor"])
            cells[2].text = str(t["category"] or "")
            cells[3].text = str(t["importance"])
            cells[4].text = str(t["direction"] or "")
    else:
        doc.add_paragraph("暂无诊断结果。")

    doc.add_heading("推荐修复方案矩阵", level=1)
    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    for i, h in enumerate(["排序", "技术", "匹配度", "成本", "禁用条件", "理由"]):
        table.rows[0].cells[i].text = h
    for r in context.get("recommendations", []):
        cells = table.add_row().cells
        cells[0].text = str(r["rank"])
        cells[1].text = str(r["technology"])
        cells[2].text = str(r["match_score"])
        cells[3].text = str(r.get("cost_level") or "")
        cells[4].text = str(r.get("forbidden_conditions") or "")
        cells[5].text = str(r.get("reason") or "")[:240]
    if not context.get("recommendations"):
        doc.add_paragraph("暂无推荐方案。")

    doc.add_heading("修复案例证据库", level=1)
    for c in context.get("remediation_cases", [])[:6]:
        doc.add_paragraph(
            f"{c['case_id']}｜{c['remediation_technology']}｜{c['pollutants']}｜"
            f"证据: {c.get('evidence_source') or '—'}"
        )

    add_kv("模型版本、数据版本、标准版本、报告版本", [
        ("模型版本", context["diagnosis"]["model_version"] if context.get("diagnosis") else "—"),
        ("数据版本", context["report"]["data_version"]),
        ("标准版本", context["report"]["standard_version"]),
        ("模板版本", context["report"]["template_version"]),
        ("报告版本", context["report"]["version"]),
    ])
    doc.add_paragraph("人工复核意见区：")
    doc.add_paragraph("\n\n")

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate(db: Session, site_id: int, generated_by: int | None = None,
             report_format: str = "pdf") -> dict:
    n_prev = db.query(ReportRecord).filter_by(site_id=site_id).count()
    version = f"v{n_prev + 1}"
    ctx = collect(db, site_id, version)
    requested = (report_format or "pdf").lower()

    if requested == "docx":
        docx_bytes = render_docx(ctx)
        fo = save_bytes(
            db, docx_bytes, f"追溯报告_{ctx['site']['site_code']}_{version}.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        fmt = "docx"
    else:
        html = render_html(ctx)
        pdf = html_to_pdf(html)
        if pdf:
            fo = save_bytes(db, pdf, f"追溯报告_{ctx['site']['site_code']}_{version}.pdf",
                            content_type="application/pdf")
            fmt = "pdf"
        else:
            fo = save_bytes(db, html.encode("utf-8"),
                            f"追溯报告_{ctx['site']['site_code']}_{version}.html",
                            content_type="text/html")
            fmt = "html"

    rec = ReportRecord(
        site_id=site_id, report_type="traceability", version=version,
        data_snapshot={"data_version": ctx["report"]["data_version"],
                       "standard_version": ctx["report"]["standard_version"],
                       "format": fmt,
                       "diagnosis": bool(ctx["diagnosis"]),
                       "n_recommendations": len(ctx["recommendations"]),
                       "n_remediation_cases": len(ctx["remediation_cases"]),
                       "validation_passed": ctx["validation"]["passed"]},
        template_version=TEMPLATE_VERSION, file_object_id=fo.id,
        generated_by=generated_by, generated_at=datetime.now(timezone.utc))
    db.add(rec)
    db.commit()
    return {"report_id": rec.id, "site_id": site_id, "version": version,
            "format": fmt, "file_object_id": fo.id,
            "storage_key": fo.storage_key, "file_name": fo.original_name}
