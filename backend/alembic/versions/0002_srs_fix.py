"""srs full-chain fix: 数据版本/幂等 + 推荐结构化列(brief 4.2/4.6)

Revision ID: 0002_srs_fix
Revises: 0001_baseline
Create Date: 2026-06-23

新增列(测试库经 bootstrap drop_all/create_all 自动建, 生产库走 alembic upgrade):
- import_batches: source_sha256 / mapping_hash / data_version (brief 4.2)
- recommendations: reason_struct / matched_factors / source (brief 4.6)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0002_srs_fix"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    # --- import_batches: 数据版本与幂等(brief 4.2) ---
    columns = _columns("import_batches")
    if "source_sha256" not in columns:
        op.add_column("import_batches",
                      sa.Column("source_sha256", sa.String(64), nullable=True))
    if "ix_import_batches_source_sha256" not in _indexes("import_batches"):
        op.create_index("ix_import_batches_source_sha256", "import_batches", ["source_sha256"])
    if "mapping_hash" not in columns:
        op.add_column("import_batches",
                      sa.Column("mapping_hash", sa.String(64), nullable=True))
    if "data_version" not in columns:
        op.add_column("import_batches",
                      sa.Column("data_version", sa.String(80), nullable=True))

    # --- recommendations: 结构化推荐理由(brief 4.6) ---
    columns = _columns("recommendations")
    if "reason_struct" not in columns:
        op.add_column("recommendations",
                      sa.Column("reason_struct", sa.JSON(), nullable=True))
    if "matched_factors" not in columns:
        op.add_column("recommendations",
                      sa.Column("matched_factors", sa.JSON(), nullable=True))
    if "source" not in columns:
        op.add_column("recommendations",
                      sa.Column("source", sa.String(300), nullable=True))


def downgrade() -> None:
    columns = _columns("recommendations")
    for name in ("source", "matched_factors", "reason_struct"):
        if name in columns:
            op.drop_column("recommendations", name)
    if "ix_import_batches_source_sha256" in _indexes("import_batches"):
        op.drop_index("ix_import_batches_source_sha256", table_name="import_batches")
    columns = _columns("import_batches")
    for name in ("data_version", "mapping_hash", "source_sha256"):
        if name in columns:
            op.drop_column("import_batches", name)
