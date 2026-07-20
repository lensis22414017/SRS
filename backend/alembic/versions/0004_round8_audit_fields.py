"""Round8 audit: input_fingerprint + KOS persistence fields

Revision ID: 0004_round8
Revises: 0003_economic
Create Date: 2026-07-20

Round8 外部审计修复(七项):
- evaluation_results 新增 input_fingerprint(SSUI 输入指纹, 替代塞入 param_version)
- diagnosis_results 新增 KOS 持久化专用字段: diagnosis_method/track/subset/model_version/result_payload
  (审计 4.4: 不得用 shap_value/shap_global 伪装 KOS)
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_round8"
down_revision = "0003_economic"
branch_labels = None
depends_on = None


def upgrade():
    # Round8 审计二类 2.2: evaluation_results.input_fingerprint
    with op.batch_alter_table("evaluation_results") as batch:
        batch.add_column(sa.Column("input_fingerprint", sa.String(64), nullable=True))
        batch.create_index("ix_evaluation_results_input_fingerprint",
                           ["input_fingerprint"], unique=False)

    # Round8 审计四类 4.4: diagnosis_results 新增 KOS 持久化字段
    with op.batch_alter_table("diagnosis_results") as batch:
        batch.add_column(sa.Column("diagnosis_method", sa.String(30), nullable=True))
        batch.add_column(sa.Column("track", sa.String(10), nullable=True))
        batch.add_column(sa.Column("subset", sa.String(20), nullable=True))
        batch.add_column(sa.Column("model_version", sa.String(40), nullable=True))
        batch.add_column(sa.Column("result_payload", sa.JSON, nullable=True))


def downgrade():
    with op.batch_alter_table("evaluation_results") as batch:
        batch.drop_index("ix_evaluation_results_input_fingerprint")
        batch.drop_column("input_fingerprint")
    with op.batch_alter_table("diagnosis_results") as batch:
        batch.drop_column("diagnosis_method")
        batch.drop_column("track")
        batch.drop_column("subset")
        batch.drop_column("model_version")
        batch.drop_column("result_payload")
