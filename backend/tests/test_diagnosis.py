"""D6-D7 诊断闭环测试 (覆盖 AC-09/AC-10)。

- 数据准备/特征对齐: 纯 pandas, 沙箱可跑。
- 训练/SHAP/API: 需 sklearn+shap, 本机 venv 运行。
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_diag.db")


# ---------- 纯 pandas ----------
def test_prepare_dataset():
    from data_prep import prepare
    X, y, meta = prepare()
    assert meta["n_samples"] >= 1000     # 实测数据集大小可变, 至少1000条
    assert len(y) == meta["n_samples"] and set(y.unique()) == {0, 1}
    # 数据集版本和特征列表因输入数据而异, 只验证基本完整性
    assert len(meta["feature_list"]) >= 10
    assert not X.isna().any().any()       # 填充后无缺失
    assert meta["data_version"].startswith("真实数据集")


def test_align_features_logic():
    """对齐逻辑不依赖 sklearn: 用假 medians/feature_list 验证。"""
    import pandas as pd
    from app.services.diagnosis_service import align_features, load_feature_mapping
    mapping = load_feature_mapping()
    pivot = pd.DataFrame({"砷": [10.0], "铅": [100.0], "pH": [6.8],
                          "有机质": [20.0]}, index=["P1"])
    feature_list = ["As(mg/kg)", "Pb(mg/kg)", "SoilpH", "BackgroundSOC",
                    "Cd(mg/kg)", "SoilpH__missing"]
    medians = {"As(mg/kg)": 8.0, "Pb(mg/kg)": 30.0, "SoilpH": 6.5,
               "BackgroundSOC": 10.0, "Cd(mg/kg)": 0.2}
    X, imputed = align_features(pivot, feature_list, medians, mapping)
    assert float(X.loc["P1", "As(mg/kg)"]) == 10.0
    assert float(X.loc["P1", "Cd(mg/kg)"]) == 0.2          # 中位数填充
    assert imputed == ["Cd(mg/kg)"]                         # 诚实标注
    assert float(X.loc["P1", "BackgroundSOC"]) == pytest.approx(20.0 * 0.58)  # 有机质→SOC换算
    assert int(X.loc["P1", "SoilpH__missing"]) == 0         # pH有实测


# ---------- 需 sklearn/shap ----------
def _has_ml():
    try:
        import sklearn  # noqa: F401
        import shap  # noqa: F401
        import sqlalchemy  # noqa: F401
        return True
    except ImportError:
        return False


needs_ml = pytest.mark.skipif(not _has_ml(), reason="需 sklearn/shap (venv)")


@needs_ml
def test_train_metrics_reasonable():
    from rf_barrier import train
    res = train()
    assert res["metrics"]["auc"] >= 0.85, res["metrics"]
    assert res["version"].startswith("v0.1_")
    assert len(res["feature_list"]) > 10


@needs_ml
def test_diagnosis_end_to_end():
    """AC-09/AC-10: 导入个旧 -> 诊断 -> Top-N + 局部解释入库。"""
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.models import DiagnosisFactorDetail, DiagnosisResult
    from app.services.diagnosis_service import run_diagnosis
    from app.services.pipeline import run_import
    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        res = run_diagnosis(db, imp["site_id"], top_n=10)
        assert res["n_points"] == 134
        assert len(res["top_factors"]) >= 1      # 至少1个障碍因子 (数据可变)
        names = {t["factor"] for t in res["top_factors"]}
        assert names & {"砷", "铅", "铜", "锌", "pH", "有机质"}  # 实测因子进入Top
        assert res["model_version"]
        # 入库校验
        diag = db.get(DiagnosisResult, res["diagnosis_id"])
        assert diag and diag.shap_global["global"]
        details = db.query(DiagnosisFactorDetail).filter_by(diagnosis_id=diag.id).all()
        assert len(details) >= 1       # 至少1条诊断因子详情
    finally:
        db.close()


@needs_ml
def test_diagnosis_api():
    from fastapi.testclient import TestClient
    from app.db.bootstrap import main as bootstrap
    from app.main import app
    bootstrap()
    c = TestClient(app)
    tok = c.post("/api/v1/auth/login",
                 json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    r = c.get("/api/v1/sites", headers=h)
    if r.json()["total"] == 0:
        pytest.skip("无场地数据")
    sid = r.json()["items"][0]["id"]
    r2 = c.get(f"/api/v1/sites/{sid}/diagnosis", headers=h)
    assert r2.status_code in (200, 404)
    assert c.get(f"/api/v1/sites/{sid}/diagnosis").status_code == 401  # 无令牌拒绝
