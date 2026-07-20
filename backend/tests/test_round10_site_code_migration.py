from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]


def _run_alembic(database_url: str, *args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(BACKEND / "alembic.ini"), *args],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_0006_migrates_existing_numeric_site_codes(tmp_path: Path):
    """模拟已处于 0005 的旧库，0006 必须自动迁移已有展示编号。"""
    database = tmp_path / "legacy_0005.db"
    with sqlite3.connect(database) as conn:
        conn.executescript(
            """
            CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
            INSERT INTO alembic_version(version_num) VALUES ('0005_round9');
            CREATE TABLE sites (
                id INTEGER PRIMARY KEY,
                site_code VARCHAR(50) NOT NULL UNIQUE,
                name VARCHAR(200) NOT NULL
            );
            INSERT INTO sites(id, site_code, name) VALUES
                (1, 'AUTO-20260720-1234', '旧自动编号'),
                (2, 'GJ-2025-001', '旧业务编号'),
                (3, 'SRS-SAFE', '已有纯字母编号');
            """
        )

    database_url = f"sqlite:///{database.as_posix()}"
    _run_alembic(database_url, "upgrade", "head")

    with sqlite3.connect(database) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sites)")}
        rows = conn.execute(
            "SELECT id, site_code, original_site_code FROM sites ORDER BY id"
        ).fetchall()
    assert "original_site_code" in columns
    assert rows == [
        (1, "SRS-A", "AUTO-20260720-1234"),
        (2, "SRS-B", "GJ-2025-001"),
        (3, "SRS-SAFE", None),
    ]
    assert all(not any(char.isdigit() for char in row[1]) for row in rows)

    _run_alembic(database_url, "downgrade", "0005_round9")
    with sqlite3.connect(database) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sites)")}
    assert "original_site_code" not in columns
