"""SHAP 解释服务: 全局重要性 + 单样本局部解释。

需 shap (本机 venv)。输入为已对齐的特征 DataFrame。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def explain(model, X: pd.DataFrame, max_local: int = 200) -> dict:
    """返回 {global: [{feature, mean_abs_shap, direction}], local: {row_index: [...]}}"""
    import shap

    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(X.iloc[:max_local])
    # 二分类: shap_values 可能为 list[2] 或 3D array, 取正类
    if isinstance(sv, list):
        sv = sv[1]
    elif getattr(sv, "ndim", 2) == 3:
        sv = sv[:, :, 1]
    sv = np.asarray(sv)

    mean_abs = np.abs(sv).mean(axis=0)
    mean_signed = sv.mean(axis=0)
    global_imp = [{
        "feature": f,
        "mean_abs_shap": round(float(a), 6),
        "direction": "positive" if s >= 0 else "negative",
    } for f, a, s in zip(X.columns, mean_abs, mean_signed)]
    global_imp.sort(key=lambda d: d["mean_abs_shap"], reverse=True)

    local = {}
    for i in range(min(len(X), max_local)):
        row = [{
            "feature": f,
            "shap_value": round(float(v), 6),
            "feature_value": round(float(X.iloc[i][f]), 6),
        } for f, v in zip(X.columns, sv[i])]
        row.sort(key=lambda d: abs(d["shap_value"]), reverse=True)
        local[int(i)] = row[:15]
    return {"global": global_imp, "local": local}
