"""建表助手: 供测试与本地起步使用 (生产用 alembic 迁移)。"""
from app.db import session as _session
from app.db.base import Base
import app.models  # noqa: F401  触发模型注册


def create_all():
    # 经模块属性访问 engine, 使 reset_engine_for_tests 重赋值后立即生效(brief 4.9)。
    Base.metadata.create_all(bind=_session.engine)


if __name__ == "__main__":
    create_all()
    print("已建表:", len(Base.metadata.tables), "张")
    for t in sorted(Base.metadata.tables):
        print("  -", t)
