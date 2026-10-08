"""v1.1: 修复前/后数据分离、子课题与来源字段、SSUI 独立批次、利用决策表。

Revision ID: 0007_v11_stage_provenance
Revises: 0006_site_original_code
Create Date: 2026-10-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_v11_stage_provenance"
down_revision = "0006_site_original_code"
branch_labels = None
depends_on = None

_COLS = {
    "import_batches": [
        sa.Column("stage", sa.String(30), nullable=False, server_default="pre_remediation"),
        sa.Column("subproject", sa.String(10), nullable=True),
        sa.Column("data_origin", sa.String(30), nullable=False, server_default="field"),
        sa.Column("method_version", sa.String(40), nullable=True),
    ],
    "measurements": [
        sa.Column("stage", sa.String(30), nullable=False, server_default="pre_remediation"),
    ],
    "evaluation_results": [
        sa.Column("stage", sa.String(30), nullable=True),
        sa.Column("subproject", sa.String(10), nullable=True),
        sa.Column("method_version", sa.String(40), nullable=True),
        sa.Column("method_status", sa.String(20), nullable=True),
        sa.Column("source_batch_id", sa.Integer, nullable=True),
    ],
}


_INDEXES = [("import_batches", "stage"), ("import_batches", "subproject"), ("measurements", "stage")]


def _ts():
    return [sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True)]


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for table, cols in _COLS.items():
        if table not in tables:  # 部分旧库/测试库不含该表: 由 create_all 建表时自带新列
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        if all(col.name in existing for col in cols):
            continue
        with op.batch_alter_table(table) as batch:
            for col in cols:
                if col.name not in existing:
                    batch.add_column(col.copy())
    insp = sa.inspect(bind)
    for table, col in _INDEXES:
        if table in tables:
            names = {i["name"] for i in insp.get_indexes(table)}
            if f"ix_{table}_{col}" not in names:
                op.create_index(f"ix_{table}_{col}", table, [col])
    if "ssui_import_batches" not in tables:
        op.create_table(
            "ssui_import_batches",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("site_id", sa.Integer, sa.ForeignKey("sites.id"), index=True),
            sa.Column("source_file", sa.String(300)),
            sa.Column("source_sha256", sa.String(64), index=True),
            sa.Column("template_version", sa.String(30)),
            sa.Column("stage", sa.String(30)),
            sa.Column("track", sa.String(20)),
            sa.Column("evaluation_year", sa.Integer),
            sa.Column("years_since_remediation", sa.Float),
            sa.Column("multiplier_m", sa.Float),
            sa.Column("data_origin", sa.String(30)),
            sa.Column("status", sa.String(20)),
            sa.Column("row_count", sa.Integer),
            sa.Column("valid_count", sa.Integer),
            sa.Column("error_count", sa.Integer),
            sa.Column("validation_report", sa.JSON),
            sa.Column("mapping_snapshot", sa.JSON),
            sa.Column("method_version", sa.String(40)),
            sa.Column("imported_by", sa.Integer, sa.ForeignKey("users.id")),
            sa.Column("confirmed_at", sa.DateTime),
            *_ts(),
        )
    if "ssui_records" not in tables:
        op.create_table(
            "ssui_records",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("batch_id", sa.Integer, sa.ForeignKey("ssui_import_batches.id"), index=True),
            sa.Column("site_id", sa.Integer, sa.ForeignKey("sites.id"), index=True),
            sa.Column("indicator_code", sa.String(10)),
            sa.Column("indicator_name", sa.String(80)),
            sa.Column("raw_value", sa.Float),
            sa.Column("unit", sa.String(30)),
            sa.Column("score", sa.Float),
            sa.Column("source_sheet", sa.String(60)),
            sa.Column("source_row", sa.Integer),
            sa.Column("source_col", sa.String(10)),
            sa.Column("note", sa.Text),
            *_ts(),
            sa.UniqueConstraint("batch_id", "indicator_code", name="uq_ssui_record"),
        )
    if "utilization_decisions" not in tables:
        op.create_table(
            "utilization_decisions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("site_id", sa.Integer, sa.ForeignKey("sites.id"), index=True),
            sa.Column("stage", sa.String(30)),
            sa.Column("decision_state", sa.String(40)),
            sa.Column("conclusion_text", sa.Text),
            sa.Column("production_gate", sa.JSON),
            sa.Column("ecology_gate", sa.JSON),
            sa.Column("production_score", sa.Float),
            sa.Column("ecology_score", sa.Float),
            sa.Column("evidence", sa.JSON),
            sa.Column("assumptions", sa.JSON),
            sa.Column("missing_evidence", sa.JSON),
            sa.Column("method_version", sa.String(40)),
            sa.Column("method_status", sa.String(20)),
            sa.Column("input_fingerprint", sa.String(64), index=True),
            sa.Column("data_origin", sa.String(30)),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id")),
            *_ts(),
        )


def downgrade():
    insp = sa.inspect(op.get_bind())
    tables = set(insp.get_table_names())
    for t in ("utilization_decisions", "ssui_records", "ssui_import_batches"):
        if t in tables:
            op.drop_table(t)
    for table, cols in _COLS.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        drop = [c.name for c in cols if c.name in existing]
        for ix in insp.get_indexes(table):
            if set(ix["column_names"]) & set(drop):
                op.drop_index(ix["name"], table_name=table)
        if drop:
            with op.batch_alter_table(table) as batch:
                for name in drop:
                    batch.drop_column(name)
