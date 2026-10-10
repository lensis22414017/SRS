"""v1.2.1(R01): 修复旧版导入把形态标记(如 Cr(VI) 中的 "VI")误存为 Measurement.unit 的数据。

Revision ID: 0009_v121_unit_artifacts
Revises: 0008_v12_recon_indicators
Create Date: 2026-10-10
"""
from alembic import op

revision = "0009_v121_unit_artifacts"
down_revision = "0008_v12_recon_indicators"
branch_labels = None
depends_on = None


def upgrade():
    from app.db.init_db import repair_v121_unit_artifacts
    repair_v121_unit_artifacts(op.get_bind().engine)


def downgrade():
    # 数据修复不可逆(原错误值为形态标记, 非单位), 不回滚
    pass
