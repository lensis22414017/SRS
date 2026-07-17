"""pytest 引导: sys.path + 统一测试 DATABASE_URL + session 级 engine 重置。"""
import os
import sys

BACKEND = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BACKEND)
for p in (BACKEND,
          os.path.join(ROOT, "ml", "models"),
          os.path.join(ROOT, "ml", "explain"),
          os.path.join(ROOT, "ml", "evaluation"),
          os.path.join(ROOT, "ml", "recommend")):
    if p not in sys.path:
        sys.path.insert(0, p)
# packaging 加在末尾, 避免其 __init__.py 遮蔽 pip packaging 库 (shap 依赖)
_pkg = os.path.join(ROOT, "packaging")
if _pkg not in sys.path:
    sys.path.append(_pkg)

# 统一测试库: 强制赋值(覆盖各 test 模块冲突的 setdefault), 根除串库(brief 4.9)。
# 各 test 文件里残留的 os.environ.setdefault("DATABASE_URL", ...) 因 conftest 先执行
# 而 setdefault 不覆盖, 已全部失效; 后续将逐步删除。
os.environ["DATABASE_URL"] = "sqlite:///./srs_test_session.db"
os.environ.setdefault("SECRET_KEY", "test_secret")
os.environ.setdefault("DEMO_PASSWORD", "Demo@2026")

import pytest


@pytest.fixture(scope="session", autouse=True)
def _srs_reset_engine():
    """session 级: 清 get_settings 的 @lru_cache + 重建 engine 绑定统一测试库。

    brief 4.9: 修复 get_settings lru_cache + 模块级 engine 一次性绑定导致的串库。
    无 sqlalchemy 时(纯算法测试环境)静默跳过。
    """
    try:
        from app.db.session import reset_engine_for_tests
        reset_engine_for_tests(os.environ["DATABASE_URL"])
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _srs_isolate_db_per_test():
    """M0-8: 每个测试函数独立 DB 隔离。

    问题: 所有测试共用 srs_test_session.db, 测试间数据残留 + SQLite WAL 锁竞争
    导致全量混跑 71 个失败(单独跑全过)。

    方案: 每个测试前 drop+create+seed, 确保干净状态。
    只对需要 DB 的测试生效(纯算法测试无副作用)。
    """
    # 测试前: 重置 DB 到干净种子状态
    try:
        from app.db.session import reset_engine_for_tests, SessionLocal
        from app.db.init_db import create_all
        from app.db.seed_db import seed_if_empty
        from sqlalchemy import inspect as sa_inspect

        # drop all + recreate + seed
        from app.db import session as _session_mod
        from app.models import Base
        Base.metadata.drop_all(bind=_session_mod.engine)
        Base.metadata.create_all(bind=_session_mod.engine)
        # v1.0.2: 测试环境启用演示数据(SRS_DEMO_SEED=1)
        # 生产首启不种演示数据, 但旧测试(如 test_auth)依赖 admin/Demo@2026 演示账号
        os.environ["SRS_DEMO_SEED"] = "1"
        seed_if_empty()
    except Exception as e:
        # 无 SQLAlchemy 环境跳过(纯算法测试), 但打印异常避免静默吞错误
        import sys as _sys
        print(f"[conftest] seed 跳过: {e}", file=_sys.stderr)
    yield
    # 测试后: 清理 session 连接(释放 SQLite WAL 锁)
    try:
        from app.db.session import SessionLocal
        SessionLocal.remove() if hasattr(SessionLocal, 'remove') else None
    except Exception:
        pass
