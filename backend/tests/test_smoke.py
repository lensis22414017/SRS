"""冒烟测试 (需 backend 依赖: sqlalchemy/fastapi/httpx/passlib)。

运行: cd backend && DATABASE_URL=sqlite:///./test.db pytest -q
"""
import os



def test_models_create_all():
    from app.db.base import Base
    from app.db.session import engine
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    tables = set(Base.metadata.tables.keys())
    # 关键表必须存在
    for t in ["users", "roles", "permissions", "sites", "sampling_points",
              "factor_dictionary", "threshold_rules", "measurements",
              "standard_thresholds", "remediation_case_library",
              "ml_models", "diagnosis_results", "diagnosis_factor_details",
              "evaluation_results", "technology_library", "recommendations",
              "workflow_records", "workflow_attachments", "report_records",
              "file_objects", "audit_logs", "import_batches"]:
        assert t in tables, f"缺表 {t}"
    assert len(tables) >= 20


def test_password_hash_roundtrip():
    from app.core.security import hash_password, verify_password
    h = hash_password("Demo@2026")
    assert h != "Demo@2026"
    assert verify_password("Demo@2026", h)
    assert not verify_password("wrong", h)


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    # R3 审计第七类: status 可以是 "ok"(模型完整) 或 "degraded"(模型不完整)
    # 测试环境模型路径可能解析不到, 关键是端点可用且返回 model_health 字段
    data = r.json()
    assert data["status"] in ("ok", "degraded"), f"status 应为 ok/degraded, 实际={data['status']}"
    assert "model_health" in data, "必须返回 model_health 字段"
