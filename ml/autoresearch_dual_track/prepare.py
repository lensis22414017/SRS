"""L1 基础设施(锁定): dual_track 数据加载 + evaluate() 跑 5折CV。

agent 只能动 L2 train.py, L1 锁定保证跨实验评估可比(karpathy 铁律)。
防泄漏信任: X_barrier 已由 build_dual_track 剔除 475 污染物列, evaluate 不复核
(L2 红线: 不得引入污染物特征, 仅改 RF 超参/特征选择/集成)。
"""
import os
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import roc_auc_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")

METRICS = ["mean_cv_auc", "prod_cv_auc", "eco_cv_auc", "prod_test_auc", "eco_test_auc"]
BUDGET_SECONDS = 180  # 5折CV×2轨预算(每次迭代等长可比)

_DATA = None


def load_data():
    global _DATA
    if _DATA is None:
        X_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_X_barrier.csv"))
        X_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_X_barrier.csv"))
        yp_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_y_prod.csv")).iloc[:, 0]
        yp_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_y_prod.csv")).iloc[:, 0]
        ye_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_y_eco.csv")).iloc[:, 0]
        ye_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_y_eco.csv")).iloc[:, 0]
        _DATA = (X_tr, X_te, yp_tr, yp_te, ye_tr, ye_te)
    return _DATA


def evaluate(train_module):
    """跑 5折CV + 测试集, 返回指标 dict。train_module.build_model(track) 返回新 RF。"""
    X_tr, X_te, yp_tr, yp_te, ye_tr, ye_te = load_data()
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    r = {}
    for track, y_tr, y_te in [("prod", yp_tr, yp_te), ("eco", ye_tr, ye_te)]:
        m = train_module.build_model(track)
        m.fit(X_tr, y_tr)
        cv_aucs = cross_val_score(train_module.build_model(track), X_tr, y_tr,
                                  cv=cv, scoring="roc_auc")
        r[f"{track}_cv_auc"] = round(float(cv_aucs.mean()), 4)
        r[f"{track}_cv_std"] = round(float(cv_aucs.std()), 4)
        proba = m.predict_proba(X_te)[:, 1]
        r[f"{track}_test_auc"] = round(float(roc_auc_score(y_te, proba)), 4)
    r["mean_cv_auc"] = round((r["prod_cv_auc"] + r["eco_cv_auc"]) / 2, 4)
    return r


if __name__ == "__main__":
    import train
    r = evaluate(train)
    print(json.dumps(r, indent=2, ensure_ascii=False))
