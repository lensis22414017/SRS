"""统一初始化: 建表 + 种子数据。可重复运行。

每次调用先清空全部表再重建, 保证测试隔离(生产部署用 Alembic 迁移, 不走此路径)。
"""
from app.db.base import Base
from app.db.init_db import create_all
from app.db.seed_db import seed
from app.db.session import engine


def main():
    Base.metadata.drop_all(bind=engine)
    create_all()
    seed()
    print("bootstrap 完成: 表 + 种子数据就绪")


if __name__ == "__main__":
    main()
