"""修复 import_batches schema 漂移(ORM 加去重列但 SQLite 表未 migration)。

裴总打通诊断: run_diagnosis → current_site_data_version 查 ImportBatch 崩
(no such column: source_sha256)。ORM 加了 source_sha256/mapping_hash 等
(plan feedback_dedup_provenance 去重溯源), 但 Alembic migration 未跑。
本脚本 ALTER TABLE ADD COLUMN 补缺失列(schema演进, 不改已有数据)。
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.models import ImportBatch  # noqa: E402
from app.db.session import engine  # noqa: E402
import sqlite3  # noqa: E402

db_path = engine.url.database
print(f"DB: {db_path}")
conn = sqlite3.connect(db_path)
actual = {r[1]: r[2] for r in conn.execute("PRAGMA table_info(import_batches)").fetchall()}
orm_cols = {c.name: c for c in ImportBatch.__table__.columns}
missing = {n: c for n, c in orm_cols.items() if n not in actual}
print(f"实际列({len(actual)}): {sorted(actual.keys())}")
print(f"ORM列({len(orm_cols)}): {sorted(orm_cols.keys())}")
print(f"缺失列({len(missing)}): {sorted(missing.keys())}\n")

type_map = {"String": "TEXT", "Integer": "INTEGER", "Text": "TEXT",
            "DateTime": "TEXT", "Boolean": "INTEGER", "JSON": "TEXT", "Float": "REAL"}
for name, col in missing.items():
    tname = type(col.type).__name__
    sql_type = type_map.get(tname, "TEXT")
    # SQLite ALTER ADD COLUMN 不能 NOT NULL 无 default(若有数据), 用 NULL 允许 + default
    default = ""
    if col.default is not None:
        try:
            dv = col.default.arg
            default = f" DEFAULT {dv!r}" if not callable(dv) else ""
        except Exception:
            default = ""
    sql = f"ALTER TABLE import_batches ADD COLUMN {name} {sql_type}{default}"
    try:
        conn.execute(sql)
        print(f"  ✓ {sql}")
    except sqlite3.OperationalError as e:
        print(f"  ✗ {name}: {e}")
conn.commit()

# 验证
actual2 = {r[1] for r in conn.execute("PRAGMA table_info(import_batches)").fetchall()}
still_missing = [n for n in orm_cols if n not in actual2]
print(f"\n修复后缺失: {still_missing if still_missing else '无 ✓'}")
conn.close()
