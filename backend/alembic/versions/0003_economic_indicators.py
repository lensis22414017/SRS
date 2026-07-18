"""SSUI D18-D25 economic indicators tables (R3 audit section 5)

Revision ID: 0003_economic
Revises: 0002_srs_fix
Create Date: 2026-07-16

新增表(R3 审计第五类 SSUI 经济指标):
- economic_indicators: D18-D25 经济指标数据(site_id + 来源元数据)
- economic_raw_inputs: 原始汇总值(area/yield/gross_output/total_cost + D21 分项)

数据分层(source_type):
  site_actual / regional_official_proxy / test_fixture
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_economic"
down_revision = "0002_srs_fix"
branch_labels = None
depends_on = None


def upgrade():
    # economic_indicators: D18-D25 经济指标(每指标一行)
    op.create_table(
        "economic_indicators",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("site_id", sa.Integer, sa.ForeignKey("sites.id"), nullable=False, index=True),
        sa.Column("evaluation_year", sa.Integer, nullable=False),
        sa.Column("scenario", sa.String(50), nullable=False, server_default="production"),
        sa.Column("crop_or_land_use", sa.String(100), nullable=True),
        sa.Column("indicator_code", sa.String(10), nullable=False),
        sa.Column("indicator_name", sa.String(60), nullable=False),
        sa.Column("raw_value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False, server_default="positive"),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="site_actual"),
        sa.Column("source_name", sa.String(200), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("source_geography", sa.String(100), nullable=True),
        sa.Column("source_year", sa.Integer, nullable=True),
        sa.Column("is_proxy", sa.Boolean, server_default=sa.text("0")),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("version", sa.String(20), nullable=False, server_default="v1.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("site_id", "evaluation_year", "scenario", "indicator_code",
                            name="uq_economic_indicator"),
    )

    # economic_raw_inputs: 原始汇总值(用于 D21/D22/D23/D25 交叉校验)
    op.create_table(
        "economic_raw_inputs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("site_id", sa.Integer, sa.ForeignKey("sites.id"), nullable=False, index=True),
        sa.Column("evaluation_year", sa.Integer, nullable=False),
        sa.Column("scenario", sa.String(50), nullable=False, server_default="production"),
        sa.Column("crop_or_land_use", sa.String(100), nullable=True),
        sa.Column("area_hectare", sa.Float, nullable=True),
        sa.Column("yield_kg", sa.Float, nullable=True),
        sa.Column("gross_output_yuan", sa.Float, nullable=True),
        sa.Column("total_cost_yuan", sa.Float, nullable=True),
        sa.Column("d21_seed_cost", sa.Float, nullable=True),
        sa.Column("d21_fertilizer_cost", sa.Float, nullable=True),
        sa.Column("d21_manure_cost", sa.Float, nullable=True),
        sa.Column("d21_pesticide_cost", sa.Float, nullable=True),
        sa.Column("d21_film_cost", sa.Float, nullable=True),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="site_actual"),
        sa.Column("source_name", sa.String(200), nullable=True),
        sa.Column("source_year", sa.Integer, nullable=True),
        sa.Column("is_proxy", sa.Boolean, server_default=sa.text("0")),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("site_id", "evaluation_year", "scenario",
                            name="uq_economic_raw_input"),
    )


def downgrade():
    op.drop_table("economic_raw_inputs")
    op.drop_table("economic_indicators")
