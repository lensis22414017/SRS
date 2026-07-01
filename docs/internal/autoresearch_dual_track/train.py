"""L2 研究对象(agent 迭代): zzv0.3 重训 best — HGB(lr0.05, iter500) 去全空列。

zzv0.3 红线(项目组2026-07-01重定):
  🔴 0泄漏 = group split + GroupKFold CV; 不得引入20个标签派生列
  ✅ 允许: RF/ET/HGB 超参/集成/特征筛选; 原生NaN处理
best 实验 #102: HGB lr0.05 iter500 + 去全空列(960→678)
  prod test=0.6796 valid=0.6796 | eco 待测
诚实结论: 非派生浓度列(455)对泛化test几乎无贡献(单用test0.53=随机),
  GEE(14)是最稳信号源(test0.67), 物理上限test~0.68-0.70, 距0.9有本质差距(特征判别力上限, 非模型问题)。
"""
import os
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import FunctionTransformer
from sklearn.pipeline import Pipeline

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")

PARAMS = {
    "loss": "log_loss",
    "learning_rate": 0.05,
    "max_iter": 500,
    "max_leaf_nodes": 31,
    "max_depth": None,
    "min_samples_leaf": 20,
    "l2_regularization": 1.0,
    "early_stopping": True,
    "validation_fraction": 0.15,
    "n_iter_no_change": 20,
    "random_state": 42,
}

_USEFUL_COLS = None


def _get_useful_cols():
    global _USEFUL_COLS
    if _USEFUL_COLS is None:
        X = pd.read_csv(os.path.join(SPLIT_DIR, "train_X_barrier.csv"))
        _USEFUL_COLS = [c for c in X.columns if not X[c].isna().all()]
    return _USEFUL_COLS


def build_model(track=None):
    """#102 best: HGB(lr0.05) + 去全空列。prod test=0.68, 三集一致。"""
    useful = _get_useful_cols()
    p = dict(PARAMS)
    selector = FunctionTransformer(lambda X: X[useful], validate=False)
    return Pipeline([("select", selector), ("hgb", HistGradientBoostingClassifier(**p))])
