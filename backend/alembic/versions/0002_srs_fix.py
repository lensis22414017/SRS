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


def upgrade() -> None:
    # --- import_batches: 数据版本与幂等(brief 4.2) ---
    op.add_column("import_batches",
                  sa.Column("source_sha256", sa.String(64), nullable=True))
    op.create_index("ix_import_batches_source_sha256", "import_batches", ["source_sha256"])
    op.add_column("import_batches",
                  sa.Column("mapping_hash", sa.String(64), nullable=True))
    op.add_column("import_batches",
                  sa.Column("data_version", sa.String(80), nullable=True))

    # --- recommendations: 结构化推荐理由(brief 4.6) ---
    op.add_column("recommendations",
                  sa.Column("reason_struct", sa.JSON(), nullable=True))
    op.add_column("recommendations",
                  sa.Column("matched_factors", sa.JSON(), nullable=True))
    op.add_column("recommendations",
                  sa.Column("source", sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column("recommendations", "source")
    op.drop_column("recommendations", "matched_factors")
    op.drop_column("recommendations", "reason_struct")
    op.drop_index("ix_import_batches_source_sha256", table_name="import_batches")
    op.drop_column("import_batches", "data_version")
    op.drop_column("import_batches", "mapping_hash")
    op.drop_column("import_batches", "source_sha256")
