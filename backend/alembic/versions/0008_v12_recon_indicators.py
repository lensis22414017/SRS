"""v1.2: 课题二 28 项重构可行性指标(数值+类别)独立批次与观测表。

Revision ID: 0008_v12_recon_indicators
Revises: 0007_v11_stage_provenance
Create Date: 2026-10-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_v12_recon_indicators"
down_revision = "0007_v11_stage_provenance"
branch_labels = None
depends_on = None


def _ts():
    return [sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True)]


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "recon_import_batches" not in tables:
        op.create_table(
            "recon_import_batches",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("site_id", sa.Integer, sa.ForeignKey("sites.id"), index=True),
            sa.Column("source_file", sa.String(300)),
            sa.Column("source_sha256", sa.String(64), index=True),
            sa.Column("template_version", sa.String(30)),
            sa.Column("stage", sa.String(30), server_default="pre_remediation"),
            sa.Column("subproject", sa.String(10), server_default="S2"),
            sa.Column("data_origin", sa.String(30), server_default="client_real"),
            sa.Column("provenance_status", sa.String(20), server_default="unverified"),
            sa.Column("land_subtype", sa.String(10), nullable=True),
            sa.Column("farmland", sa.String(10), nullable=True),
            sa.Column("eco_land_class", sa.String(20), nullable=True),
            sa.Column("status", sa.String(20), server_default="previewed"),
            sa.Column("point_count", sa.Integer, server_default="0"),
            sa.Column("cell_count", sa.Integer, server_default="0"),
            sa.Column("error_count", sa.Integer, server_default="0"),
            sa.Column("warning_count", sa.Integer, server_default="0"),
            sa.Column("validation_report", sa.JSON, nullable=True),
            sa.Column("mapping_snapshot", sa.JSON, nullable=True),
            sa.Column("cleaning_log", sa.JSON, nullable=True),
            sa.Column("method_version", sa.String(60), nullable=True),
            sa.Column("imported_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
            sa.Column("confirmed_at", sa.DateTime, nullable=True),
            *_ts(),
        )
    if "recon_observations" not in tables:
        op.create_table(
            "recon_observations",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("batch_id", sa.Integer, sa.ForeignKey("recon_import_batches.id"), index=True),
            sa.Column("site_id", sa.Integer, sa.ForeignKey("sites.id"), index=True),
            sa.Column("point_label", sa.String(60)),
            sa.Column("feature_id", sa.String(40), index=True),
            sa.Column("feature_cn", sa.String(60), nullable=True),
            sa.Column("value_num", sa.Float, nullable=True),
            sa.Column("value_cat", sa.String(200), nullable=True),
            sa.Column("original_text", sa.Text, nullable=True),
            sa.Column("transform", sa.String(120), nullable=True),
            sa.Column("qualifier", sa.String(10), nullable=True),
            sa.Column("unit", sa.String(30), nullable=True),
            sa.Column("source_sheet", sa.String(60), nullable=True),
            sa.Column("source_row", sa.Integer, nullable=True),
            sa.Column("source_col", sa.String(10), nullable=True),
            sa.Column("stage", sa.String(30), server_default="pre_remediation"),
            sa.Column("data_origin", sa.String(30), server_default="client_real"),
            *_ts(),
            sa.UniqueConstraint("batch_id", "point_label", "feature_id", name="uq_recon_obs"),
        )


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "recon_observations" in tables:
        op.drop_table("recon_observations")
    if "recon_import_batches" in tables:
        op.drop_table("recon_import_batches")
