"""数据库会话。"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine_for_tests(database_url: str | None = None) -> None:
    """测试专用: 清 settings 缓存, 重建 engine 并重绑 SessionLocal。

    解决 brief 4.9 的串库三重锁定:
      1) 各 test 模块 os.environ.setdefault(DATABASE_URL) 互相冲突(conftest 先占);
      2) get_settings 的 @lru_cache 首次缓存后不随 env 变化;
      3) 模块级 engine 在首次 import 时一次性绑定, 之后不随 env 重建。
    - SessionLocal 用 configure 重绑(保持对象同一性, 已 import 它的模块自动生效);
    - engine 用 global 重新赋值, 消费者须通过 app.db.session.engine 属性访问
      (bootstrap.py / init_db.py 已改为模块属性引用, 避免持有旧 engine)。
    """
    global engine
    get_settings.cache_clear()
    if database_url:
        os.environ["DATABASE_URL"] = database_url
    new_settings = get_settings()
    new_connect_args = ({"check_same_thread": False}
                        if new_settings.database_url.startswith("sqlite") else {})
    engine = create_engine(new_settings.database_url,
                           connect_args=new_connect_args, future=True)
    SessionLocal.configure(bind=engine)
