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


def _columns(table_name: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade():
    # Round8 审计二类 2.2: evaluation_results.input_fingerprint
    if "input_fingerprint" not in _columns("evaluation_results"):
        with op.batch_alter_table("evaluation_results") as batch:
            batch.add_column(sa.Column("input_fingerprint", sa.String(64), nullable=True))
    if "ix_evaluation_results_input_fingerprint" not in _indexes("evaluation_results"):
        with op.batch_alter_table("evaluation_results") as batch:
            batch.create_index("ix_evaluation_results_input_fingerprint",
                               ["input_fingerprint"], unique=False)

    # Round8 审计四类 4.4: diagnosis_results 新增 KOS 持久化字段
    columns = _columns("diagnosis_results")
    additions = [
        ("diagnosis_method", sa.String(30)),
        ("track", sa.String(10)),
        ("subset", sa.String(20)),
        ("model_version", sa.String(40)),
        ("result_payload", sa.JSON),
    ]
    missing = [(name, type_) for name, type_ in additions if name not in columns]
    if missing:
        with op.batch_alter_table("diagnosis_results") as batch:
            for name, type_ in missing:
                batch.add_column(sa.Column(name, type_, nullable=True))


def downgrade():
    if "ix_evaluation_results_input_fingerprint" in _indexes("evaluation_results"):
        with op.batch_alter_table("evaluation_results") as batch:
            batch.drop_index("ix_evaluation_results_input_fingerprint")
    if "input_fingerprint" in _columns("evaluation_results"):
        with op.batch_alter_table("evaluation_results") as batch:
            batch.drop_column("input_fingerprint")
    columns = _columns("diagnosis_results")
    present = [name for name in (
        "diagnosis_method", "track", "subset", "model_version", "result_payload"
    ) if name in columns]
    if present:
        with op.batch_alter_table("diagnosis_results") as batch:
            for name in present:
                batch.drop_column(name)
