"""修复案例库与 DOCX 报告测试。"""
import os



def test_remediation_case_loader_and_docx_report():
    from app.db.bootstrap import main as bootstrap
    from app.db.load_remediation_cases import load
    from app.db.session import SessionLocal
    from app.models import FileObject, RemediationCase, Site
    from app.services import report_service, workflow_service

    bootstrap()
    db = SessionLocal()
    try:
        db.query(RemediationCase).delete()
        db.query(Site).filter_by(site_code="TEST-DOCX").delete()
        db.commit()
        assert load(db) >= 8
        assert db.query(RemediationCase).filter(RemediationCase.pollutants.contains("As")).count() >= 1

        site = Site(site_code="TEST-DOCX", name="DOCX 报告测试场地",
                    pollution_type="heavy_metal", land_use_type="农用地",
                    province="云南", city="个旧")
        db.add(site)
        db.commit()
        workflow_service.init_stages(db, site.id)

        res = report_service.generate(db, site.id, report_format="docx")
        assert res["format"] == "docx"
        assert res["file_name"].endswith(".docx")
        fo = db.get(FileObject, res["file_object_id"])
        assert fo and fo.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

        ctx = report_service.collect(db, site.id, "v-check")
        html = report_service.render_html(ctx)
        for section in ["数据覆盖率", "缺失率摘要", "推荐修复方案矩阵", "模型版本、数据版本、标准版本"]:
            assert section in html
    finally:
        db.close()
