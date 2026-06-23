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
