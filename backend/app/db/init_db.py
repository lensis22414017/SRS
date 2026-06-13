"""建表助手: 供测试与本地起步使用 (生产用 alembic 迁移)。"""
from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401  触发模型注册


def create_all():
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    create_all()
    print("已建表:", len(Base.metadata.tables), "张")
    for t in sorted(Base.metadata.tables):
        print("  -", t)
