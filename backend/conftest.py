"""pytest 引导: 确保 backend 根与 ml 子目录在 sys.path, 并设默认测试环境变量。"""
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

os.environ.setdefault("DATABASE_URL", "sqlite:///./srs_test.db")
os.environ.setdefault("SECRET_KEY", "test_secret")
os.environ.setdefault("DEMO_PASSWORD", "Demo@2026")
