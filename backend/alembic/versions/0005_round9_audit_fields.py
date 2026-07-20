"""Round9 audit: evaluation_results.run_config + diagnosis_factor_details.kos_score

Revision ID: 0005_round9
Revises: 0004_round8
Create Date: 2026-07-20

Round9 外部审计修复:
- evaluation_results 新增 run_config JSON: SSUI 评价运行配置快照(供 GET 重算指纹判断 stale)
- diagnosis_factor_details 新增 kos_score Float: KOS 排序分(不冒充 SHAP importance)
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_round9"
down_revision = "0004_round8"
branch_labels = None
depends_on = None


def upgrade():
    # Round9 P0-1.1: evaluation_results.run_config JSON
    with op.batch_alter_table("evaluation_results") as batch:
        batch.add_column(sa.Column("run_config", sa.JSON, nullable=True))

    # Round9 P0-3.3: diagnosis_factor_details.kos_score Float
    with op.batch_alter_table("diagnosis_factor_details") as batch:
        batch.add_column(sa.Column("kos_score", sa.Float, nullable=True))


def downgrade():
    with op.batch_alter_table("evaluation_results") as batch:
        batch.drop_column("run_config")
    with op.batch_alter_table("diagnosis_factor_details") as batch:
        batch.drop_column("kos_score")
