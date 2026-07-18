"""zzv0.4 P2-1/P2-2: permutation importance + ALE(累积局部效应)。

文献依据:
- [#58 permutation importance]: SHAP排序在相关特征下易误导, 需permutation对照
- [#4 Apley&Zhu 2020 ALE]: 相关特征下PDP会外推失真, ALE更稳健
- [#25 ICE]: 个体异质性
第51行: 解释层SHAP+permutation+ALE组合, 不只SHAP
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def permutation_importance(model, X: pd.DataFrame, y, scoring="roc_auc",
                           n_repeats: int = 5, seed: int = 42) -> list[dict]:
    """permutation importance(文献[#58])。
    返回 [{feature, importance_mean, importance_std}], 按重要性降序。"""
    from sklearn.metrics import roc_auc_score
    if len(np.unique(y)) < 2:
        return []
    rng = np.random.RandomState(seed)
    try:
        base_score = roc_auc_score(y, model.predict_proba(X)[:, 1])
    except Exception:
        return []
    results = []
    for col in X.columns:
        imps = []
        for _ in range(n_repeats):
            X_perm = X.copy()
            X_perm[col] = rng.permutation(X_perm[col].values)
            try:
                score = roc_auc_score(y, model.predict_proba(X_perm)[:, 1])
                imps.append(base_score - score)
            except Exception:
                imps.append(0.0)
        results.append({"feature": col,
                        "importance_mean": round(float(np.mean(imps)), 6),
                        "importance_std": round(float(np.std(imps)), 6)})
    results.sort(key=lambda x: -x["importance_mean"])
    return results


def accumulated_local_effects(model, X: pd.DataFrame, feature: str, n_bins: int = 20) -> dict:
    """ALE(累积局部效应, 文献[#4 Apley&Zhu 2020])。
    对相关特征(如pH-金属)比PDP更稳健, 不需离开数据流形外推。
    返回 {feature, bins, ale_values, n_samples_per_bin}。"""
    vals = pd.to_numeric(X[feature], errors="coerce").dropna()
    if len(vals) < n_bins * 2:
        return {"feature": feature, "bins": [], "ale_values": [], "note": "数据不足"}
    # 分位数分箱
    quantiles = np.linspace(0, 1, n_bins + 1)
    bin_edges = np.quantile(vals.values, quantiles)
    bin_edges = np.unique(bin_edges)
    if len(bin_edges) < 3:
        return {"feature": feature, "bins": [], "ale_values": [], "note": "分箱不足"}
    # 每箱内计算局部效应(在箱边界预测差值)
    ale_per_bin = []
    counts = []
    for i in range(len(bin_edges) - 1):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (vals >= lo) & (vals < hi)
        bin_data = X.loc[vals[mask].index].copy()
        if len(bin_data) == 0:
            ale_per_bin.append(0.0)
            counts.append(0)
            continue
        # 在 lo 和 hi 处预测, 取差值(局部效应)
        bin_data_lo = bin_data.copy()
        bin_data_lo[feature] = lo
        bin_data_hi = bin_data.copy()
        bin_data_hi[feature] = hi
        try:
            proba_lo = model.predict_proba(bin_data_lo)[:, 1]
            proba_hi = model.predict_proba(bin_data_hi)[:, 1]
            local_effect = float(np.mean(proba_hi - proba_lo))
        except Exception:
            local_effect = 0.0
        ale_per_bin.append(local_effect)
        counts.append(len(bin_data))
    # 累积 + 居中(ALE 标准做法)
    cumulative = np.cumsum(ale_per_bin)
    centered = cumulative - np.mean(cumulative)
    bin_centers = [(bin_edges[i] + bin_edges[i + 1]) / 2 for i in range(len(bin_edges) - 1)]
    return {"feature": feature, "bin_centers": bin_centers,
            "ale_values": [round(float(v), 6) for v in centered],
            "n_samples": counts}


def explain_comprehensive(model, X: pd.DataFrame, y, top_features: list[str] = None,
                          k: int = 10) -> dict:
    """综合解释: permutation + ALE(对top相关特征)。
    在SHAP之外提供permutation对照 + ALE效应曲线。"""
    perm = permutation_importance(model, X, y)
    top_feats = [p["feature"] for p in perm[:k]] if top_features is None else top_features
    ales = {}
    for f in top_feats[:5]:  # top-5特征算ALE
        if f in X.columns:
            ales[f] = accumulated_local_effects(model, X, f)
    return {"permutation_importance": perm[:k], "ale_effects": ales,
            "note": "permutation对照SHAP防相关特征误导[#58]; ALE对相关特征比PDP稳健[#4]"}
