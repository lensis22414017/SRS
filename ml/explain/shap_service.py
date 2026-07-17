"""SHAP 解释服务: 全局重要性 + 单样本局部解释。

需 shap (本机 venv)。输入为已对齐的特征 DataFrame。
"""
from __future__ import annotations

from typing import Optional

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


# ═══════════════════════════════════════════════════════════════
# P3-Alpha 回归专用解释(规范:AC-10 / training_protocol §5)
# 新增:因子组聚合 + sample_id 绑定 + positive_only + base_value
# ═══════════════════════════════════════════════════════════════
def _feature_to_group(feature_name: str) -> str:
    """把 x_ 前缀特征映射到因子组(用于聚合)"""
    if feature_name.startswith("x_measured_"):
        return feature_name.replace("x_measured_", "")          # 单因子
    if feature_name.startswith("x_family_"):
        return feature_name.replace("x_family_", "") + "(族群)"
    if feature_name.startswith("x_proxy_gee_"):
        base = feature_name.replace("x_proxy_gee_", "")
        return f"GEE_{base}"
    if feature_name.startswith("x_missing_"):
        return f"缺失指示_{feature_name.replace('x_missing_', '')}"
    if feature_name.startswith("x_covariate_"):
        return f"协变量_{feature_name.replace('x_covariate_', '')}"
    return feature_name


def explain_regression(model, X: pd.DataFrame, sample_ids: Optional[None] = None,
                       max_local: int = 500, positive_only: bool = False) -> dict:
    """P3-Alpha 回归模型 SHAP 解释(模型贡献度 M 的来源)。

    规范约束:
    - 称"模型贡献度",不是障碍高度/不是因果(training_protocol §5)
    - 因子组聚合(metrics_config: aggregation=factor_group)
    - local 绑定 sample_id(AC-10 要求,非行号)
    - 不删污染物浓度特征

    返回:
    {
      "global": [{factor_group, mean_abs_shap, direction, contribution_share}],  # 按 mean_abs 降序
      "local": {sample_id: [{factor_group, shap_value, feature_value}]},         # 每样本 top15
      "base_value": float,        # 模型期望输出
      "n_explained": int,
      "n_features": int,
    }
    """
    import shap

    explainer = shap.TreeExplainer(model)
    X_exp = X.iloc[:max_local].copy()
    sv = explainer.shap_values(X_exp)
    # 回归模型 sv 是 2D array(n_samples, n_features),不走二分类分支
    if isinstance(sv, list):
        sv = sv[0]
    sv = np.asarray(sv)
    if sv.ndim == 3:
        sv = sv[:, :, 0]  # 退化情况取首列

    base_value = float(explainer.expected_value) if not hasattr(explainer.expected_value, "__len__") \
        else float(np.ravel(explainer.expected_value)[0])

    # ── global: 因子组聚合 ──
    feat_names = list(X_exp.columns)
    groups = [_feature_to_group(f) for f in feat_names]
    df_g = pd.DataFrame({"feature": feat_names, "group": groups})
    df_g["mean_abs"] = np.abs(sv).mean(axis=0)
    df_g["mean_signed"] = sv.mean(axis=0)

    agg = df_g.groupby("group").agg(
        mean_abs_shap=("mean_abs", "sum"),       # 组内求和(同因子的多列合并)
        mean_signed=("mean_signed", "sum"),
        n_features=("feature", "count"),
        members=("feature", lambda x: list(x)[:3]),
    ).reset_index()
    agg["direction"] = np.where(agg["mean_signed"] >= 0, "positive", "negative")
    total = agg["mean_abs_shap"].sum()
    agg["contribution_share"] = (agg["mean_abs_shap"] / total).round(6) if total > 0 else 0.0
    if positive_only:
        agg = agg[agg["direction"] == "positive"]
    agg = agg.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    agg["mean_abs_shap"] = agg["mean_abs_shap"].round(6)

    global_imp = agg.to_dict(orient="records")

    # ── local: 绑定 sample_id ──
    local = {}
    sids = list(sample_ids) if sample_ids is not None else list(range(len(X_exp)))
    for i in range(len(X_exp)):
        sid = sids[i] if i < len(sids) else i
        row_df = pd.DataFrame({"group": groups, "shap_value": sv[i]})
        row_agg = row_df.groupby("group")["shap_value"].sum().reset_index()
        row_agg = row_agg.reindex(row_agg["shap_value"].abs().sort_values(ascending=False).index)
        rows = [
            {
                "factor_group": r["group"],
                "shap_value": round(float(r["shap_value"]), 6),
            }
            for _, r in row_agg.head(15).iterrows()
        ]
        local[sid] = rows

    return {
        "global": global_imp,
        "local": local,
        "base_value": round(base_value, 6),
        "n_explained": len(X_exp),
        "n_features": len(feat_names),
        "interpretation_note": "模型贡献度, 非因果, 非障碍高度",
    }


def compute_local_shap_for_point(model, feature_cols: list,
                                  point_values: dict) -> dict | None:
    """v1.0.2(GPT P0-2): 对单条采样点记录计算局部 SHAP。

    把单点测量值(point_values={factor_code: value})展平成 110 列 DataFrame:
    - x_measured_{factor}: 有实测值则填, 否则 0
    - x_missing_{factor}: 1 if 缺失 else 0
    - 其他前缀(family/proxy_gee/covariate): 填 0(单点无 GEE/族群数据)

    返回 {factor_group: local_shap_value} 或 None(失败时)。
    """
    try:
        import shap
    except ImportError:
        return None

    try:
        # 构造单行 DataFrame(110列, 缺失列填0)
        row = {}
        for col in feature_cols:
            if col.startswith("x_measured_"):
                factor = col.replace("x_measured_", "")
                row[col] = float(point_values.get(factor, 0))
            elif col.startswith("x_missing_"):
                factor = col.replace("x_missing_", "")
                row[col] = 0.0 if factor in point_values else 1.0
            else:
                row[col] = 0.0  # GEE/族群/协变量: 单点无数据

        X_point = pd.DataFrame([row], columns=feature_cols)
        explainer = shap.TreeExplainer(model)
        sv = explainer.shap_values(X_point)
        if isinstance(sv, list):
            sv = sv[0]
        sv = np.asarray(sv).flatten()

        # 聚合到因子组
        groups = [_feature_to_group(c) for c in feature_cols]
        result = {}
        for i, g in enumerate(groups):
            val = float(sv[i])
            result[g] = round(result.get(g, 0.0) + val, 6)
        return result
    except Exception:
        return None
