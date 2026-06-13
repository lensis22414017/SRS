"""baseline schema (当前 SQLAlchemy 模型全量)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-12

基线迁移: 以当前 app.models 的 metadata 建全部表。
- 适用于从干净数据库(含 PostgreSQL 空卷)初始化;
- 与 app.db.bootstrap 的 create_all 等价, 但纳入 Alembic 版本管理;
- 后续 schema 变更请用 `alembic revision --autogenerate` 生成增量迁移。
"""
from alembic import op  # noqa: F401

# revision identifiers
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 复用模型 metadata, 保证与 ORM 定义单一真相源一致
    from app.db.base import Base
    import app.models  # noqa: F401  触发模型注册
    Base.metadata.create_all(bind=op.get_bind())


def downgrade():
    from app.db.base import Base
    import app.models  # noqa: F401
    Base.metadata.drop_all(bind=op.get_bind())
