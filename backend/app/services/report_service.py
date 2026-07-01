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
    RemediationCase, Site, StandardThreshold, TechnologyLibrary, ThresholdRule,
    WorkflowAttachment, WorkflowRecord,
)
from app.services.file_service import save_bytes
from app.services.workflow_service import STAGE_NAME, get_stages

from app.core.config import resource_root

ROOT = resource_root()
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


def docx_emu_width(doc) -> int:
    """返回 DOCX 正文可用宽度(EMU 单位), 用于图片自适应页宽。"""
    try:
        section = doc.sections[0]
        # 页宽 - 左右边距
        usable = section.page_width - section.left_margin - section.right_margin
        return int(usable) if usable and usable > 0 else 5500000  # 兜底约 15cm
    except Exception:  # noqa: BLE001
        return 5500000


def _embed_docx_image(doc, data_url: str | None, caption: str) -> None:
    """把 base64 PNG 嵌入 DOCX; data_url 为空/损坏时静默跳过( P1-1 DOCX 同步 PDF 图件)。"""
    if not data_url or not data_url.startswith("data:image/png;base64,"):
        return
    import base64 as _b64
    from io import BytesIO as _BIO
    try:
        img_bytes = _b64.b64decode(data_url.split(",", 1)[1])
        doc.add_picture(_BIO(img_bytes), width=docx_emu_width(doc))
        p = doc.add_paragraph(caption)
        p.italic = True
    except Exception:  # noqa: BLE001
        doc.add_paragraph(f"[{caption} 渲染失败]")


def _render_points_map_png(coord_points: list, exceed_by_point: dict[int, float],
                           exceed_factor: dict[int, str] | None = None) -> str | None:
    """v0.2: 8级色阶采样点风险散点图(与前端/API一致), 返回 base64 PNG。"""
    if not coord_points:
        return None
    try:
        # 优先用 static_map_renderer
        from app.services.static_map_renderer import (
            _exc_color, COLOR_8_LEVELS, _exc_label, _get_cjk_font,
        )
    except ImportError:
        # fallback: 内联渲染
        _exc_color = None

    try:
        import base64 as _b64
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    font = _get_cjk_font() if _get_cjk_font else None
    if font:
        plt.rcParams["font.family"] = font

    lons = [float(p.longitude) for p in coord_points]
    lats = [float(p.latitude) for p in coord_points]
    vals = [exceed_by_point.get(p.id, 0.0) for p in coord_points]
    factors = (exceed_factor or {})

    # v0.2: 8级色阶
    if _exc_color:
        colors = [_exc_color(v) for v in vals]
    else:
        def _fallback_color(v):
            if v < 1: return "#16a34a"
            if v < 3: return "#facc15"
            if v < 10: return "#f59e0b"
            if v < 30: return "#ea580c"
            if v < 80: return "#dc2626"
            if v < 200: return "#9f1239"
            return "#6b0f1a"
        colors = [_fallback_color(v) for v in vals]
    sizes = [24 if v >= 1 else 14 for v in vals]
    fig, ax = plt.subplots(figsize=(7.5, 5), dpi=120)
    ax.scatter(lons, lats, c=colors, s=sizes, alpha=0.85, edgecolors="white", linewidths=0.5, zorder=5)

    # 图例 8级
    from matplotlib.patches import Patch as _Patch
    _leg = []
    if _exc_label:
        for th, clr in COLOR_8_LEVELS:
            _leg.append(_Patch(facecolor=clr, edgecolor="white", label=_exc_label(float(th))))
    else:
        _leg = [
            _Patch(facecolor="#16a34a", edgecolor="white", label="未超标"),
            _Patch(facecolor="#facc15", edgecolor="white", label="轻度 1-3x"),
            _Patch(facecolor="#f59e0b", edgecolor="white", label="中度 3-10x"),
            _Patch(facecolor="#ea580c", edgecolor="white", label="偏重 10-30x"),
            _Patch(facecolor="#dc2626", edgecolor="white", label="重度 30-80x"),
            _Patch(facecolor="#9f1239", edgecolor="white", label="极重 80-200x"),
            _Patch(facecolor="#6b0f1a", edgecolor="white", label="超极重 >200x"),
            _Patch(facecolor="#64748b", edgecolor="white", label="无数据"),
        ]
    ax.legend(handles=_leg, loc="lower right", fontsize=6, ncol=2, framealpha=0.9)

    if len(set(lons)) > 1:
        ax.set_xlim(min(lons) - (max(lons)-min(lons))*0.08, max(lons) + (max(lons)-min(lons))*0.08)
    if len(set(lats)) > 1:
        ax.set_ylim(min(lats) - (max(lats)-min(lats))*0.08, max(lats) + (max(lats)-min(lats))*0.08)
    ax.set_xlabel("经度" if font else "Longitude", fontsize=8)
    ax.set_ylabel("纬度" if font else "Latitude", fontsize=8)
    ax.set_title(f"采样点超标风险分布（{len(coord_points)} 点位, 8级色阶）" if font
                 else f"Exceedance risk ({len(coord_points)} pts, 8-level)", fontsize=10, fontweight="bold")
    ax.tick_params(labelsize=7)
    ax.grid(True, linestyle="--", alpha=0.3)
    from datetime import datetime as _dt, timezone as _tz
    wm = f"8级色阶 | 渲染: {_dt.now(_tz.utc).strftime('%Y-%m-%d %H:%M UTC')} | 底图: 无(离线坐标散点)"
    fig.text(0.5, 0.01, wm, ha="center", fontsize=5.5, color="#888", family="monospace")
    fig.tight_layout(rect=[0, 0.03, 1, 0.97])
    from io import BytesIO
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return f"data:image/png;base64,{_b64.b64encode(buf.read()).decode('ascii')}"
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _render_shap_figure_png(top_factors: list, site_name: str) -> str | None:
    """用 matplotlib 画 Top-N 障碍因子 SHAP 排名横向条形图(nature-figure 顶刊风格)。
    报告增加顶刊级 SHAP 排名图(matplotlib 科研配图, 非 dashboard)。
    正向(加重)=npg红 #E64B35, 负向(缓解)=npg蓝 #4DBBD5; 去顶右边框, 数值标注。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    if not top_factors:
        return None
    import io, base64
    facts = top_factors[:8][::-1]  # 横向 bar 倒序(最重要在顶部)
    names = [str(f.get("factor", "?")) for f in facts]
    vals = [float(f.get("importance", 0) or 0) for f in facts]
    dirs = [str(f.get("direction", "")) for f in facts]
    colors = ["#E64B35" if d == "positive" else "#4DBBD5" for d in dirs]
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=150)
    ax.barh(range(len(names)), vals, color=colors, height=0.62, edgecolor="white", linewidth=0.6)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel("|SHAP| 相对重要性", fontsize=9)
    ax.set_title(f"关键障碍因子 SHAP 排名 — {site_name}", fontsize=10.5, pad=8, color="#222")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(length=0)
    for i, v in enumerate(vals):
        ax.text(v, i, f" {v:.3f}", va="center", fontsize=7.5, color="#555")
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _render_eda_figure_png(factor_summary: list) -> str | None:
    """各因子浓度均值与最大值对比柱状图(matplotlib), 嵌 DOCX 检测数据摘要章节。"""
    if not factor_summary:
        return None
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    from matplotlib import font_manager as _fm
    _cn_fonts = ["PingFang SC", "Heiti SC", "STHeiti", "Arial Unicode MS",
                 "Noto Sans CJK SC", "WenQuanYi Zen Hei", "SimHei", "Microsoft YaHei"]
    _avail = {_f.name for _f in _fm.fontManager.ttflist}
    _has_cn = any(_f in _avail for _f in _cn_fonts)
    if _has_cn:
        plt.rcParams["font.sans-serif"] = _cn_fonts
        plt.rcParams["axes.unicode_minus"] = False
    facts = factor_summary[:12]
    names = [f["factor"] for f in facts]
    means = [float(f.get("mean") or 0) for f in facts]
    maxs = [float(f.get("max") or 0) for f in facts]
    x = list(range(len(names)))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7, 3.4), dpi=120)
    ax.bar([i - w / 2 for i in x], means, w, label="均值", color="#3680ae")
    ax.bar([i + w / 2 for i in x], maxs, w, label="最大值", color="#e98184")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("浓度", fontsize=9)
    ax.set_title("各因子浓度均值与最大值对比(EDA)", fontsize=10, color="#222")
    ax.legend(fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    import io as _io, base64 as _b64
    buf = _io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return "data:image/png;base64," + _b64.b64encode(buf.getvalue()).decode("ascii")


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

    coord_points = [p for p in points if p.longitude is not None and p.latitude is not None]
    if coord_points:
        lons = [float(p.longitude) for p in coord_points]
        lats = [float(p.latitude) for p in coord_points]
        bounds = {"min_lon": round(min(lons), 6), "max_lon": round(max(lons), 6),
                  "min_lat": round(min(lats), 6), "max_lat": round(max(lats), 6)}
    else:
        bounds = None

    # v0.2: 每个采样点的最大超标倍数 + 最严重因子
    exceed_by_point: dict[int, float] = {}
    exceed_factor: dict[int, str] = {}  # pid → factor_code
    if coord_points:
        th_rows = (db.query(Measurement.sampling_point_id, Measurement.value,
                            ThresholdRule.threshold_max, FactorDictionary.factor_code)
                   .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
                   .join(ThresholdRule, ThresholdRule.factor_id == FactorDictionary.id)
                   .filter(Measurement.site_id == site_id,
                           ThresholdRule.threshold_max != None,
                           ThresholdRule.threshold_max > 0,
                           Measurement.sampling_point_id != None).all())
        for pid, val, tmax, fcode in th_rows:
            if val is None:
                continue
            ratio = float(val) / float(tmax)
            if ratio > exceed_by_point.get(pid, 0.0):
                exceed_by_point[pid] = ratio
                exceed_factor[pid] = fcode  # v0.2: 保留最严重因子
                exceed_by_point[pid] = ratio
    map_image = _render_points_map_png(coord_points, exceed_by_point, exceed_factor)
    shap_image = _render_shap_figure_png((diag_ctx or {}).get("top_factors", []), site.name)

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
        "map_summary": {"n_points": len(points), "n_coord_points": len(coord_points),
                        "coverage_pct": round(len(coord_points) / max(len(points), 1) * 100, 2),
                        "bounds": bounds,
                        "map_image": map_image,
                        "shap_image": shap_image,
                        "note": "交互式地图由系统图层接口生成, 按污染物筛选并以超标倍数分级。上方静态图件由 matplotlib 离线渲染(无瓦片底图)。"},
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

    add_kv("地图图件与采样点空间分布", [
        ("图件说明", "采样点空间分布（离线渲染，基于场地实测坐标，无瓦片底图）；交互式地图请登录系统查看"),
        ("坐标覆盖", f"{context['map_summary']['n_coord_points']} / "
                 f"{context['map_summary']['n_points']} "
                 f"({context['map_summary']['coverage_pct']}%)"),
        ("空间范围", context["map_summary"]["bounds"] or "无可用坐标范围"),
        ("说明", context["map_summary"]["note"]),
    ])
    # 嵌入 matplotlib 静态采样点图件(若有)
    map_img = context["map_summary"].get("map_image")
    if map_img and map_img.startswith("data:image/png;base64,"):
        import base64
        try:
            img_bytes = base64.b64decode(map_img.split(",", 1)[1])
            from io import BytesIO as _BIO
            doc.add_picture(_BIO(img_bytes), width=docx_emu_width(doc))
            doc.add_paragraph("(采样点空间分布与超标风险分级静态图件，离线渲染)").italic = True
        except Exception:  # noqa: BLE001
            doc.add_paragraph("[地图图件渲染失败，请参考上方坐标覆盖与空间范围说明]")

    doc.add_heading("检测数据摘要", level=1)
    if context.get("factor_summary"):
        table = doc.add_table(rows=1, cols=6)
        table.style = "Table Grid"
        for i, h in enumerate(["因子", "类别", "样本数", "最小值", "均值", "最大值"]):
            table.rows[0].cells[i].text = h
        for f in context["factor_summary"][:20]:
            cells = table.add_row().cells
            cells[0].text = str(f["factor"])
            cells[1].text = str(f.get("category") or "")
            cells[2].text = str(f["count"])
            cells[3].text = str(f["min"])
            cells[4].text = str(f["mean"])
            cells[5].text = str(f["max"])
    else:
        doc.add_paragraph("暂无检测数据摘要。")

    # DOCX 同步嵌入 EDA 分析图(均值 vs 最大值, 与 PDF 章节口径一致)
    _embed_docx_image(doc, _render_eda_figure_png(context.get("factor_summary") or []),
                      "(各因子浓度均值与最大值对比 EDA 图件)")

    add_kv("数据质量校验结果", [
        ("校验结论", "通过" if context["validation"]["passed"] else "存在阻断性错误"),
        ("错误 / 警告", f"{context['validation']['n_errors']} / "
                 f"{context['validation']['n_warnings']}"),
        ("超标提示", f"{context['validation']['n_exceed']} 项, 涉及因子: "
                 f"{'、'.join(context['validation']['exceed_factors']) or '无'}"),
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

    # DOCX 同步嵌入 SHAP 障碍因子排名图(与 PDF 口径一致)
    _embed_docx_image(doc, context["map_summary"].get("shap_image"),
                      "(关键障碍因子 SHAP 排名图件)")

    doc.add_heading("功能重构可行性评价", level=1)
    if context.get("reconstruction"):
        for ev in context["reconstruction"]:
            doc.add_paragraph(
                f"{ev['title']}: 综合得分 {ev['score']} ({ev['grade']}), "
                f"关键限制因子: {'、'.join(ev.get('limiting_factors') or []) or '无'}"
            )
            if ev.get("explanation"):
                doc.add_paragraph(str(ev["explanation"]))
    else:
        doc.add_paragraph("暂无功能重构评价结果。")

    doc.add_heading("可持续利用评价（SSUI）", level=1)
    if context.get("ssui"):
        add_kv("SSUI 摘要", [
            ("SSUI 指数", context["ssui"]["score"]),
            ("可持续性等级", context["ssui"]["grade"]),
            ("说明", context["ssui"].get("explanation") or "—"),
        ])
    else:
        doc.add_paragraph("暂无 SSUI 结果。")

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

    doc.add_heading("五阶段全流程追溯记录", level=1)
    table = doc.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    for i, h in enumerate(["阶段", "状态", "版本", "审批意见", "附件数"]):
        table.rows[0].cells[i].text = h
    for w in context.get("workflow", []):
        cells = table.add_row().cells
        cells[0].text = str(w["stage_name"])
        cells[1].text = str(w["status"])
        cells[2].text = str(w.get("version") or "")
        cells[3].text = str(w.get("review_comment") or "")
        cells[4].text = str(w.get("n_attachments") or 0)

    doc.add_heading("附件清单", level=1)
    if context.get("attachments"):
        for a in context["attachments"]:
            doc.add_paragraph(
                f"{a['stage_name']}｜{a.get('file_role') or '—'}｜{a['original_name']}"
            )
    else:
        doc.add_paragraph("暂无附件。")

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
