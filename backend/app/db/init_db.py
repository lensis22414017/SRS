"""建表助手: 供测试与本地起步使用 (生产用 alembic 迁移)。"""
from app.db import session as _session
from app.db.base import Base
import app.models  # noqa: F401  触发模型注册


# v1.1: 旧库就地升级(幂等)。只 ADD COLUMN, 不删改任何已有数据。
# 与 alembic 0007_v11_stage_provenance 保持同一列定义。
V11_COLUMNS = {
    "import_batches": [
        ("stage", "VARCHAR(30) NOT NULL DEFAULT 'pre_remediation'"),
        ("subproject", "VARCHAR(10)"),
        ("data_origin", "VARCHAR(30) NOT NULL DEFAULT 'field'"),
        ("method_version", "VARCHAR(40)"),
    ],
    "measurements": [
        ("stage", "VARCHAR(30) NOT NULL DEFAULT 'pre_remediation'"),
    ],
    "evaluation_results": [
        ("stage", "VARCHAR(30)"),
        ("subproject", "VARCHAR(10)"),
        ("method_version", "VARCHAR(40)"),
        ("method_status", "VARCHAR(20)"),
        ("source_batch_id", "INTEGER"),
    ],
}


def upgrade_v11_columns(engine) -> list[str]:
    from sqlalchemy import inspect, text
    added = []
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in V11_COLUMNS.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                    added.append(f"{table}.{name}")
    return added


def create_all():
    # 经模块属性访问 engine, 使 reset_engine_for_tests 重赋值后立即生效(brief 4.9)。
    Base.metadata.create_all(bind=_session.engine)
    upgrade_v11_columns(_session.engine)


if __name__ == "__main__":
    create_all()
    print("已建表:", len(Base.metadata.tables), "张")
    for t in sorted(Base.metadata.tables):
        print("  -", t)
