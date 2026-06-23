"""批量导入 API 回归测试。"""
import os
from types import SimpleNamespace

import pytest



def _has_backend_deps():
    try:
        import fastapi  # noqa: F401
        import sqlalchemy  # noqa: F401
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has_backend_deps(), reason="需 fastapi/sqlalchemy")


@needs_db
def test_import_batch_uses_unique_clean_filenames(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import data as data_api
    from app.db.bootstrap import main as bootstrap
    from app.main import app

    bootstrap()
    seen_paths: list[str] = []

    def fake_run_import(db, path, mapping_id, imported_by=None):
        seen_paths.append(path)
        return {
            "site_id": len(seen_paths),
            "n_points": 1,
            "n_measurements": 1,
            "validation": {"n_errors": 0, "n_exceed": 0, "exceed_factors": []},
        }

    monkeypatch.setattr(data_api, "get_settings",
                        lambda: SimpleNamespace(file_storage_dir=str(tmp_path)))
    monkeypatch.setattr(data_api, "run_import_with_mapping", fake_run_import)

    c = TestClient(app)
    token = c.post("/api/v1/auth/login",
                   json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    files = [
        ("files", ("same.xlsx", b"one", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
        ("files", ("same.xlsx", b"two", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
    ]

    r = c.post("/api/v1/import/batch", data={"mapping_id": "yunnan_gejiu"},
               files=files, headers=headers)

    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2 and body["succeeded"] == 2 and body["failed"] == 0
    stored = [item["stored_filename"] for item in body["results"]]
    assert len(stored) == len(set(stored))
    assert all(name.endswith(".xlsx") and not name.endswith(".xlsx.xlsx") for name in stored)
    assert all(item["original_filename"] == "same.xlsx" for item in body["results"])
    assert len(seen_paths) == 2
    assert all(os.path.exists(path) for path in seen_paths)
