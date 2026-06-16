"""EDA 科研级可视化测试 (覆盖箱线/分布/QQ/相关/分组)。

- profile.py 纯算法用例仅需 pandas/numpy/scipy, 沙箱可跑。
- API 用例需 backend 依赖 (sqlalchemy/fastapi), 在 venv/docker 环境:
    cd backend && DATABASE_URL=sqlite:///./test.db pytest -q tests/test_eda.py
"""
import os

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")
# profile.py 在 ml/eda 下, 加入 sys.path
import sys
_ML_EDA = os.path.join(ROOT, "ml", "eda")
if _ML_EDA not in sys.path:
    sys.path.insert(0, _ML_EDA)

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_eda.db")


# ---------- profile.py 纯算法 ----------
def test_boxplot_five_numbers_monotonic():
    from profile import boxplot_summary
    rng = np.random.default_rng(42)
    s = pd.Series(rng.normal(50, 10, 500).tolist() + [500, -300])  # 含离群点
    b = boxplot_summary(s)
    # 五数单调: lower <= q1 <= median <= q3 <= upper
    assert b["lower"] <= b["q1"] <= b["median"] <= b["q3"] <= b["upper"], b
    assert b["n_outliers"] >= 2  # 注入了 2 个极端值
    assert len(b["outliers"]) <= 200  # 离群点采样上限
    # 须线基于 1.5*IQR
    assert b["whisker_low"] == round(b["q1"] - 1.5 * (b["q3"] - b["q1"]), 4)


def test_boxplot_insufficient_samples():
    from profile import boxplot_summary
    b = boxplot_summary(pd.Series([1.0, 2.0]))
    assert b["lower"] is None and b["outliers"] == []


def test_distribution_sample_cap():
    from profile import distribution_sample
    rng = np.random.default_rng(1)
    s = pd.Series(rng.uniform(0, 100, 50000).tolist())
    d = distribution_sample(s, max_points=2000)
    assert len(d["values"]) == 2000           # 触发抽样上限
    assert d["n_total"] == 50000              # 原始数量保留(可追溯)
    assert d["values"] == sorted(d["values"])  # 排序后等距抽样, 保持有序


def test_distribution_small_returns_all():
    from profile import distribution_sample
    s = pd.Series([3.0, 1.0, 2.0])
    d = distribution_sample(s, max_points=2000)
    assert d["values"] == [1.0, 2.0, 3.0] and d["n_total"] == 3


def test_correlation_symmetric_and_diagonal():
    from profile import correlation_matrix
    rng = np.random.default_rng(7)
    n = 100
    df = pd.DataFrame({"a": rng.normal(0, 1, n),
                       "b": rng.normal(0, 1, n)})
    df["c"] = df["a"] * 2 + rng.normal(0, 0.1, n)  # c 与 a 强相关
    corr = correlation_matrix(df)
    assert corr["labels"] == ["a", "b", "c"]
    m = corr["matrix"]
    # 对角线自相关 = 1
    for i in range(3):
        assert abs(m[i][i] - 1.0) < 1e-6
    # 矩阵对称
    for i in range(3):
        for j in range(3):
            assert abs(m[i][j] - m[j][i]) < 1e-6
    # a-c 强正相关
    ai = corr["labels"].index("a"); ci = corr["labels"].index("c")
    assert m[ai][ci] > 0.9


def test_correlation_drops_constant_columns():
    from profile import correlation_matrix
    df = pd.DataFrame({"const": [5.0] * 100, "vary": list(range(100)),
                       "vary2": [x * 0.5 for x in range(100)]})
    corr = correlation_matrix(df)
    # 常数列无方差应被剔除, 仅剩两个有方差列
    assert "const" not in corr["labels"]
    assert set(corr["labels"]) == {"vary", "vary2"}


def test_grouped_stats_sorted_by_mean():
    from profile import grouped_stats
    df = pd.DataFrame({"g": ["A"] * 10 + ["B"] * 10,
                       "v": [1.0] * 10 + [10.0] * 10})
    g = grouped_stats(df, "v", "g")
    assert g["group_col"] == "g"
    assert len(g["groups"]) == 2
    # 按均值降序
    assert g["groups"][0]["mean"] == 10.0 and g["groups"][0]["group"] == "B"
    assert g["groups"][1]["mean"] == 1.0 and g["groups"][1]["group"] == "A"


# ---------- API (需 backend 依赖) ----------
def _has_backend_deps():
    try:
        import sqlalchemy  # noqa: F401
        import fastapi  # noqa: F401
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has_backend_deps(),
                              reason="需 sqlalchemy/fastapi (venv/docker 环境)")
needs_data = pytest.mark.skipif(not os.path.exists(GEJIU),
                                reason="缺少个旧原始数据文件")


def _setup_and_login():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.main import app
    from app.services.pipeline import run_import
    bootstrap()
    load_kb()
    db = SessionLocal()
    try:
        res = run_import(db, GEJIU, "yunnan_gejiu")
    finally:
        db.close()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    return c, {"Authorization": f"Bearer {tok}"}, res["site_id"]


@needs_db
@needs_data
def test_eda_api_default_returns_all_sections():
    c, h, sid = _setup_and_login()
    r = c.get(f"/api/v1/sites/{sid}/eda", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["n_factors"] > 0
    f0 = body["factors"][0]
    # 默认 include 全返回
    assert "stats" in f0 and "histogram" in f0
    assert "boxplot" in f0 and "distribution" in f0 and "qq" in f0
    # 五数单调
    b = f0["boxplot"]
    assert b["lower"] <= b["q1"] <= b["median"] <= b["q3"] <= b["upper"]
    # 相关矩阵(个旧 14 因子)
    assert "correlation" in body
    assert len(body["correlation"]["labels"]) >= 2


@needs_db
@needs_data
def test_eda_api_include_subset():
    c, h, sid = _setup_and_login()
    # 只取 boxplot, 节省响应
    r = c.get(f"/api/v1/sites/{sid}/eda",
              params={"include": "boxplot"}, headers=h)
    body = r.json()
    f0 = body["factors"][0]
    assert "boxplot" in f0
    assert "distribution" not in f0 and "qq" not in f0
    assert "correlation" not in body


@needs_db
@needs_data
def test_eda_api_distribution_cap():
    c, h, sid = _setup_and_login()
    r = c.get(f"/api/v1/sites/{sid}/eda",
              params={"include": "distribution", "max_points": 500}, headers=h)
    body = r.json()
    for f in body["factors"]:
        assert len(f["distribution"]["values"]) <= 500


@needs_db
@needs_data
def test_eda_api_grouped_by_region():
    c, h, sid = _setup_and_login()
    r = c.get(f"/api/v1/sites/{sid}/eda",
              params={"include": "grouped", "group_by": "region"}, headers=h)
    body = r.json()
    assert "grouped" in body
    assert body["grouped"]["group_by"] == "region"
    assert len(body["grouped"]["overall"]["groups"]) >= 1
    # per_factor 每个因子都有分组
    assert len(body["grouped"]["per_factor"]) == body["n_factors"]


@needs_db
@needs_data
def test_eda_api_single_factor_filter():
    c, h, sid = _setup_and_login()
    r = c.get(f"/api/v1/sites/{sid}/eda",
              params={"factor": "砷", "include": "boxplot"}, headers=h)
    body = r.json()
    assert body["n_factors"] == 1
    assert body["factors"][0]["factor"] == "砷"


@needs_db
@needs_data
def test_eda_api_no_data_404():
    c, h, _ = _setup_and_login()
    # 用一个不存在的场地 id
    r = c.get("/api/v1/sites/999999/eda", headers=h)
    assert r.status_code == 404
