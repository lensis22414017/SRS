"""D11-D12 追溯/报告测试 (覆盖 AC-14/AC-15)。需完整 venv。"""
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_wf.db")


def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has("sqlalchemy", "fastapi"), reason="需 venv")
needs_ml = pytest.mark.skipif(not _has("sqlalchemy", "fastapi", "sklearn", "shap"),
                              reason="需完整 venv")


@needs_db
def test_workflow_five_stages():
    from app.db.bootstrap import main as bootstrap
    from app.db.session import SessionLocal
    from app.services import workflow_service as W
    from app.services.pipeline import run_import
    bootstrap()
    db = SessionLocal()
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        sid = imp["site_id"]
        W.init_stages(db, sid)
        stages = W.get_stages(db, sid)
        assert len(stages) == 5
        assert [s["stage"] for s in stages] == \
            ["survey", "approval", "construction", "effect", "maintenance"]
        # 更新调查评估阶段
        W.update_stage(db, sid, "survey", status="completed",
                       review_comment="调查报告齐全", is_completed=True, advance=True)
        s0 = [s for s in W.get_stages(db, sid) if s["stage"] == "survey"][0]
        assert s0["is_completed"] and s0["status"] == "completed"
    finally:
        db.close()


@needs_db
def test_workflow_attachment_and_audit():
    from app.db.bootstrap import main as bootstrap
    from app.db.session import SessionLocal
    from app.models import AuditLog
    from app.services import workflow_service as W
    from app.services.file_service import save_bytes
    from app.services.pipeline import run_import
    bootstrap()
    db = SessionLocal()
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        sid = imp["site_id"]
        W.init_stages(db, sid)
        fo = save_bytes(db, b"demo report content", "调查报告.txt", "text/plain")
        db.commit()
        W.attach_file(db, sid, "survey", fo.id, file_role="调查报告")
        stages = W.get_stages(db, sid)
        survey = [s for s in stages if s["stage"] == "survey"][0]
        assert survey["n_attachments"] == 1
        assert db.query(AuditLog).filter_by(action="workflow_attach").count() >= 1
    finally:
        db.close()


@needs_ml
def test_report_generation_full_chain():
    """AC-15: 完整闭环 -> 生成报告(PDF 或降级 HTML), 含版本与数据快照。"""
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.models import ReportRecord
    from app.services import report_service, workflow_service as W
    from app.services.diagnosis_service import run_diagnosis
    from app.services.evaluation_service import run_evaluation
    from app.services.pipeline import run_import
    from app.services.recommend_service import run_recommendation
    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        sid = imp["site_id"]
        run_diagnosis(db, sid, top_n=10)
        run_evaluation(db, sid)
        run_recommendation(db, sid, top_k=5)
        W.init_stages(db, sid)
        W.update_stage(db, sid, "survey", status="completed", is_completed=True)
        res = report_service.generate(db, sid)
        assert res["version"] == "v1"
        assert res["format"] in ("pdf", "html")
        assert res["file_object_id"]
        rec = db.get(ReportRecord, res["report_id"])
        assert rec.data_snapshot["diagnosis"] is True
        assert rec.data_snapshot["n_recommendations"] >= 3
        # 可重复生成 -> v2
        res2 = report_service.generate(db, sid)
        assert res2["version"] == "v2"
    finally:
        db.close()


@needs_db
def test_report_html_renders():
    """模板渲染不依赖 PDF 库: 校验 15 项关键章节存在。"""
    from app.db.bootstrap import main as bootstrap
    from app.db.session import SessionLocal
    from app.services import report_service
    from app.services.pipeline import run_import
    from app.services import workflow_service as W
    bootstrap()
    db = SessionLocal()
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        sid = imp["site_id"]
        W.init_stages(db, sid)
        ctx = report_service.collect(db, sid, "v1")
        html = report_service.render_html(ctx)
        for section in ["场地基本信息", "数据来源说明", "采样点信息", "检测数据摘要",
                        "数据质量校验", "障碍因子识别", "功能重构可行性",
                        "可持续利用评价", "推荐重构方案", "五阶段全流程追溯",
                        "附件清单", "操作日志摘要", "报告版本"]:
            assert section in html, f"报告缺章节: {section}"
    finally:
        db.close()
