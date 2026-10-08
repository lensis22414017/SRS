"""v1.1 G7: 重启后结果一致 + 备份/恢复后课题三结果与利用结论可完整复原。"""
import io
import os

from test_v11_utilization_ssui import _fill_template, _login, _make_site


def test_restart_and_backup_restore_preserve_s3_results_and_decisions():
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from app.db.session import SessionLocal, reset_engine_for_tests
    from app.main import app
    from app.models import EvaluationResult, SSUIRecord, UtilizationDecision
    from app.services import backup_service
    db = SessionLocal()
    try:
        sid, code = _make_site(db, "PERSISTTEST")
    finally:
        db.close()
    c = TestClient(app); h = _login(c)
    t = c.get("/api/v1/templates/ssui-post?track=production", headers=h).content
    pj = c.post(f"/api/v1/sites/{sid}/ssui-post/preview", headers=h,
                files={"file": ("p.xlsx", _fill_template(t, code), "application/octet-stream")}).json()
    cj = c.post(f"/api/v1/ssui-post/batches/{pj['batch_id']}/confirm", headers=h).json()
    d1 = c.post(f"/api/v1/sites/{sid}/utilization?stage=post_remediation&farmland_type=其他", headers=h).json()
    before = c.get(f"/api/v1/sites/{sid}/utilization?stage=post_remediation", headers=h).json()["decision"]

    # 1) 重启(重建 engine + 新客户端)后一致
    reset_engine_for_tests(os.environ["DATABASE_URL"])
    c2 = TestClient(app); h2 = _login(c2)
    after_restart = c2.get(f"/api/v1/sites/{sid}/utilization?stage=post_remediation", headers=h2).json()["decision"]
    assert after_restart == before
    b = c2.get(f"/api/v1/sites/{sid}/ssui-post/batches", headers=h2).json()["batches"][0]
    assert b["ssui"] == cj["calc"]["ssui"] and b["status"] == "confirmed"

    # 2) 备份 → 破坏 → 恢复
    bk = backup_service.create_backup("g7")
    assert os.path.exists(bk["path"])
    v = backup_service.verify_backup(bk["path"])
    assert v.get("ok", v.get("valid", True)), v
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM utilization_decisions")); db.execute(text("DELETE FROM ssui_records"))
        db.commit()
        assert db.query(UtilizationDecision).count() == 0
    finally:
        db.close()
    from app.db import session as _s
    _s.engine.dispose()
    backup_service.restore_backup(bk["path"], confirm=True)
    reset_engine_for_tests(os.environ["DATABASE_URL"])
    c3 = TestClient(app); h3 = _login(c3)
    restored = c3.get(f"/api/v1/sites/{sid}/utilization?stage=post_remediation", headers=h3).json()["decision"]
    assert restored == before
    db = SessionLocal()
    try:
        assert db.query(SSUIRecord).filter_by(batch_id=pj["batch_id"]).count() == 25
        ev = db.get(EvaluationResult, cj["evaluation_id"])
        assert ev.score == cj["calc"]["ssui"]
    finally:
        db.close()
    # 3) 重新运行决策: 输入指纹确定性
    d2 = c3.post(f"/api/v1/sites/{sid}/utilization?stage=post_remediation&farmland_type=其他", headers=h3).json()
    assert d2["input_fingerprint"] == d1["input_fingerprint"] and d2["decision_state"] == d1["decision_state"]
