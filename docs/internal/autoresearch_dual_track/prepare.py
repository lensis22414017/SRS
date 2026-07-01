"""L1 基础设施(锁定): zzv0.3 重训 — GroupKFold(0泄漏) + train/valid/test 三集评估。

agent 只能动 L2 train.py, L1 锁定保证跨实验评估可比(karpathy 铁律)。
zzv0.3 变更(2026-07-01 项目组重定):
  - 0泄漏 = group split(DOI/Source 连通分量跨集零重叠) + GroupKFold CV(防同文献跨折)
  - 保留非派生浓度列(剔除20个标签派生列), 原生NaN(树模型处理, 不填充)
  - evaluate 输出 train/valid/test 三集 AUC + GroupKFold CV AUC
"""
import os
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.metrics import roc_auc_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")

METRICS = ["mean_cv_auc", "prod_cv_auc", "eco_cv_auc",
           "prod_valid_auc", "eco_valid_auc", "prod_test_auc", "eco_test_auc"]
BUDGET_SECONDS = 240

_DATA = None


def load_data():
    global _DATA
    if _DATA is None:
        X_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_X_barrier.csv"))
        X_va = pd.read_csv(os.path.join(SPLIT_DIR, "valid_X_barrier.csv"))
        X_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_X_barrier.csv"))
        yp_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_y_prod.csv")).iloc[:, 0]
        yp_va = pd.read_csv(os.path.join(SPLIT_DIR, "valid_y_prod.csv")).iloc[:, 0]
        yp_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_y_prod.csv")).iloc[:, 0]
        ye_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_y_eco.csv")).iloc[:, 0]
        ye_va = pd.read_csv(os.path.join(SPLIT_DIR, "valid_y_eco.csv")).iloc[:, 0]
        ye_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_y_eco.csv")).iloc[:, 0]
        g_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_groups.csv"))["id_DOI"].fillna("").astype(str)
        _DATA = (X_tr, X_va, X_te, yp_tr, yp_va, yp_te, ye_tr, ye_va, ye_te, g_tr)
    return _DATA


def evaluate(train_module):
    """跑 GroupKFold 5折CV(0泄漏) + valid + test 三集 AUC。"""
    (X_tr, X_va, X_te, yp_tr, yp_va, yp_te,
     ye_tr, ye_va, ye_te, g_tr) = load_data()
    cv = GroupKFold(n_splits=5)
    r = {}
    for track, y_tr, y_va, y_te in [("prod", yp_tr, yp_va, yp_te),
                                     ("eco", ye_tr, ye_va, ye_te)]:
        cv_aucs = cross_val_score(train_module.build_model(track), X_tr, y_tr,
                                  groups=g_tr, cv=cv, scoring="roc_auc")
        r[f"{track}_cv_auc"] = round(float(cv_aucs.mean()), 4)
        r[f"{track}_cv_std"] = round(float(cv_aucs.std()), 4)
        m = train_module.build_model(track)
        m.fit(X_tr, y_tr)
        proba_va = m.predict_proba(X_va)[:, 1]
        proba_te = m.predict_proba(X_te)[:, 1]
        r[f"{track}_valid_auc"] = round(float(roc_auc_score(y_va, proba_va)), 4)
        r[f"{track}_test_auc"] = round(float(roc_auc_score(y_te, proba_te)), 4)
    r["mean_cv_auc"] = round((r["prod_cv_auc"] + r["eco_cv_auc"]) / 2, 4)
    r["mean_valid_auc"] = round((r["prod_valid_auc"] + r["eco_valid_auc"]) / 2, 4)
    r["mean_test_auc"] = round((r["prod_test_auc"] + r["eco_test_auc"]) / 2, 4)
    return r


if __name__ == "__main__":
    import train
    r = evaluate(train)
    print(json.dumps(r, indent=2, ensure_ascii=False))
