"""zzv0.4 P4-1: confident learning 标签审计。

文献依据: [#6 Northcutt et al. 2021] Confident Learning
第31行: 每轮训练前排查疑似错标, 输出候选复核清单
实现: 用交叉验证的预测概率 + 标签, 找出"模型认为大概率是A但标为B"的疑似错标样本。
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def confident_learning_audit(X, y, model_cls, cv_groups=None, n_splits: int = 5, seed: int = 42) -> dict:
    """confident learning 标签审计(文献[#6])。
    返回 {n_suspected, suspected_indices, confidence_stats}。"""
    from sklearn.model_selection import GroupKFold, cross_val_predict
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return {"n_suspected": 0, "note": "单类, 无法审计"}
    cv = GroupKFold(n_splits=n_splits)
    groups = cv_groups if cv_groups is not None else None
    try:
        if groups is not None:
            proba = cross_val_predict(model_cls(), X, y, groups=groups, cv=cv,
                                      method="predict_proba")[:, 1]
        else:
            proba = cross_val_predict(model_cls(), X, y, cv=n_splits,
                                      method="predict_proba")[:, 1]
    except Exception as e:
        return {"n_suspected": 0, "note": f"CV失败: {e}"}
    # 疑似错标: 模型预测概率与标签严重不一致
    # 正样本但预测概率<0.3 / 负样本但预测概率>0.7
    suspected_pos = (y == 1) & (proba < 0.3)  # 标为障碍但模型认为不像
    suspected_neg = (y == 0) & (proba > 0.7)  # 标为正常但模型认为像障碍
    suspected_idx = np.where(suspected_pos | suspected_neg)[0]
    return {
        "n_total": len(y),
        "n_suspected": int(len(suspected_idx)),
        "suspected_rate": round(len(suspected_idx) / len(y), 4),
        "suspected_indices": suspected_idx[:50].tolist(),  # 前50个供人工复核
        "suspected_pos_mislabeled": int(suspected_pos.sum()),
        "suspected_neg_mislabeled": int(suspected_neg.sum()),
        "note": "疑似错标样本(模型概率与标签严重不一致), 建议人工复核。文献[#6 Northcutt]",
    }


def run_label_audit(track: str = "prod") -> dict:
    """运行标签审计(对训练集)。"""
    import os, sys
    ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")
    from sklearn.ensemble import HistGradientBoostingClassifier
    X = pd.read_csv(os.path.join(SPLIT_DIR, "train_X_barrier.csv"))
    y = pd.read_csv(os.path.join(SPLIT_DIR, f"train_y_{track}.csv")).iloc[:, 0]
    g_path = os.path.join(SPLIT_DIR, "train_groups.csv")
    groups = pd.read_csv(g_path)["id_DOI"].fillna("").astype(str) if os.path.exists(g_path) else None
    return confident_learning_audit(X, y, HistGradientBoostingClassifier,
                                    cv_groups=groups)


if __name__ == "__main__":
    for track in ["prod", "eco"]:
        print(f"\n=== {track} 轨标签审计 ===")
        r = run_label_audit(track)
        for k, v in r.items():
            if k != "suspected_indices":
                print(f"  {k}: {v}")
