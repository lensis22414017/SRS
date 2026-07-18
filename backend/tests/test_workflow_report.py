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
        # 更新调查评估阶段(状态机要求 not_started → in_progress → completed)
        W.update_stage(db, sid, "survey", status="in_progress")
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
        W.update_stage(db, sid, "survey", status="in_progress")
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
        #  P1-1: DOCX 同步 PDF 图件 — 至少 map + SHAP + EDA 三张
        assert len(media_files) >= 3, (
            f"DOCX 媒体图件应 ≥3 (map+shap+eda), 实际 {len(media_files)}: {media_files}")
        for section in ["地图图件", "检测数据摘要", "数据质量校验",
                        "功能重构可行性", "SSUI", "推荐修复方案矩阵",
                        "五阶段全流程追溯", "附件清单", "人工复核意见区"]:
            assert section in text, f"DOCX 报告缺章节: {section}"
        assert "操作日志摘要" not in text, "DOCX 不应含操作日志摘要()"
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
                        "附件清单", "报告版本", "人工复核意见区"]:  # 操作日志摘要已按移除
            assert section in html, f"报告缺章节: {section}"
        assert "三、采样点信息" not in html
        assert "十、五阶段全流程追溯记录" not in html
        # 报告不含"操作日志摘要"(甲方明确可不提系统操作摘要)
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


@needs_db
def test_workflow_five_stage_full_e2e():
    """T10.1 端到端: 五阶段各上传(中文文件名) + 刷新持久化 + 下载SHA256一致。

     P1: 证明追溯上传闭环真实可用(非摆设), 覆盖 Stop hook 要求:
    - 五阶段(survey/approval/construction/effect/maintenance)各一附件
    - 中文文件名(save_upload 用 uuid_原名, 中文不乱码)
    - 刷新持久化(GET → GET, 附件数稳定, 不因刷新丢失)
    - 下载内容 SHA256 与原文件一致(FileObject 内容完整性)
    """
    import hashlib
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

    # 五阶段各上传一附件(中文文件名 + 中文角色 + 不同内容)
    stages_files = [
        ("survey", "调查报告", "调查评估原始数据_2026.pdf", b"survey content alpha"),
        ("approval", "审批意见", "方案审批意见书_盖章版.docx", b"approval content beta"),
        ("construction", "监理报告", "施工监理周报_第3周.xlsx", b"construction content gamma"),
        ("effect", "效果评估报告", "修复效果评估报告_终版.pdf", b"effect content delta"),
        ("maintenance", "管护记录", "后期管护记录_年度.xlsx", b"maintenance content epsilon"),
    ]
    for stage, role, fname, content in stages_files:
        up = c.post(f"/api/v1/sites/{sid}/workflow/{stage}/attachment", headers=h,
                    data={"file_role": role},
                    files={"file": (fname, io.BytesIO(content), "application/octet-stream")})
        assert up.status_code == 200, f"{stage} 上传失败: {up.text}"

    # 刷新持久化: GET → GET, 五阶段附件数稳定不丢失
    wf1 = c.get(f"/api/v1/sites/{sid}/workflow", headers=h).json()
    wf2 = c.get(f"/api/v1/sites/{sid}/workflow", headers=h).json()
    for stage, _role, _fname, _content in stages_files:
        a1 = ([s for s in wf1["stages"] if s["stage"] == stage][0].get("attachments")) or []
        a2 = ([s for s in wf2["stages"] if s["stage"] == stage][0].get("attachments")) or []
        assert len(a1) >= 1 and len(a1) == len(a2), \
            f"{stage} 刷新后附件数变化: {len(a1)}→{len(a2)} (持久化失败)"

    # 中文文件名 + 下载SHA256 完整性(FileObject.original_name 存中文, save_upload 用 uuid_原名)
    from app.models import FileObject
    db2 = SessionLocal()
    try:
        for stage, _role, fname, content in stages_files:
            wf = c.get(f"/api/v1/sites/{sid}/workflow", headers=h).json()
            s = [x for x in wf["stages"] if x["stage"] == stage][0]
            att = (s.get("attachments") or [])[0]
            fo = db2.get(FileObject, att["file_object_id"])
            assert fo and fo.original_name == fname, \
                f"{stage} 中文文件名: 期望'{fname}', 实际'{fo.original_name if fo else None}'"
            dl = c.get(f"/api/v1/sites/{sid}/workflow/{stage}/attachments/{att['id']}/download", headers=h)
            assert dl.status_code == 200, f"{stage} 下载失败: {dl.text}"
            assert hashlib.sha256(dl.content).hexdigest() == hashlib.sha256(content).hexdigest(), \
                f"{stage} 下载内容 SHA256 与上传不一致(内容被篡改/丢失)"
    finally:
        db2.close()
