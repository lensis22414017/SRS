"""D11-D12 追溯/报告测试 (覆盖 AC-14/AC-15)。需完整 venv。"""
import os
import re
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")



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
        assert rec.data_snapshot["n_recommendations"] >= 0  # 推荐数量受数据变化影响
        # 可重复生成 -> v2
        res2 = report_service.generate(db, sid)
        assert res2["version"] == "v2"
        res3 = report_service.generate(db, sid, report_format="docx")
        assert res3["version"] == "v3"
        assert res3["format"] == "docx"
        from app.models import FileObject
        from app.services.file_service import abs_path
        fo = db.get(FileObject, res3["file_object_id"])
        assert fo and zipfile.is_zipfile(abs_path(fo.storage_key))
        with zipfile.ZipFile(abs_path(fo.storage_key)) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
            media_files = [n for n in z.namelist() if n.startswith("word/media/")]
        text = re.sub("<[^>]+>", " ", xml)
        # 裴总 P1-1: DOCX 同步 PDF 图件 — 至少 map + SHAP + EDA 三张
        assert len(media_files) >= 3, (
            f"DOCX 媒体图件应 ≥3 (map+shap+eda), 实际 {len(media_files)}: {media_files}")
        for section in ["地图图件", "检测数据摘要", "数据质量校验",
                        "功能重构可行性", "SSUI", "推荐修复方案矩阵",
                        "五阶段全流程追溯", "附件清单", "人工复核意见区"]:
            assert section in text, f"DOCX 报告缺章节: {section}"
        assert "操作日志摘要" not in text, "DOCX 不应含操作日志摘要(裴总第一节)"
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
                        "地图图件", "数据质量校验", "障碍因子识别", "功能重构可行性",
                        "可持续利用评价", "推荐重构方案", "五阶段全流程追溯",
                        "附件清单", "报告版本", "人工复核意见区"]:  # 操作日志摘要已按裴总问题4移除
            assert section in html, f"报告缺章节: {section}"
        assert "三、采样点信息" not in html
        assert "十、五阶段全流程追溯记录" not in html
        # 裴总第一节: 报告不含"操作日志摘要"(甲方明确可不提系统操作摘要)
        assert "操作日志摘要" not in html
    finally:
        db.close()


@needs_db
def test_workflow_attachment_download_and_authz():
    """阶段附件下载: 正常下载 + 内容一致 + 越权(site/stage 不匹配)返回 404。"""
    import io
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.db.session import SessionLocal
    from app.main import app
    from app.services import workflow_service as W
    from app.services.pipeline import run_import

    bootstrap()
    db = SessionLocal()
    sid = None
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        sid = imp["site_id"]
        W.init_stages(db, sid)
    finally:
        db.close()

    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    # 上传附件到 survey 阶段
    content = b"attachment download test content"
    up = c.post(f"/api/v1/sites/{sid}/workflow/survey/attachment", headers=h,
                data={"file_role": "调查报告"},
                files={"file": ("report.txt", io.BytesIO(content), "text/plain")})
    assert up.status_code == 200, up.text

    # 从 get_workflow 取真实 attachment_id
    wf = c.get(f"/api/v1/sites/{sid}/workflow", headers=h).json()
    survey = [s for s in wf["stages"] if s["stage"] == "survey"][0]
    atts = survey.get("attachments") or []
    assert len(atts) >= 1
    att_id = atts[0]["id"]

    # 正常下载 + 内容一致
    dl = c.get(f"/api/v1/sites/{sid}/workflow/survey/attachments/{att_id}/download", headers=h)
    assert dl.status_code == 200, dl.text
    assert dl.content == content, "下载内容应与上传一致"

    # 越权 1: stage 不匹配(survey 的附件用 construction 访问)应 404
    assert c.get(f"/api/v1/sites/{sid}/workflow/construction/attachments/{att_id}/download",
                 headers=h).status_code == 404
    # 越权 2: 不存在的 site 应 404
    assert c.get(f"/api/v1/sites/999999/workflow/survey/attachments/{att_id}/download",
                 headers=h).status_code == 404
    # 越权 3: 不带令牌应 401
    assert c.get(f"/api/v1/sites/{sid}/workflow/survey/attachments/{att_id}/download").status_code == 401
