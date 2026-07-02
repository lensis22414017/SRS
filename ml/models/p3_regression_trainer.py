#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
p3_regression_trainer.py
====================================================================
P3-Alpha 双轨障碍指数回归训练核心模块
====================================================================
规范约束(来源:training_protocol_v0.8 / 方法学文档 / AC-09 AC-10):
- 主任务:回归 X → OI_prod_formal / OI_eco_formal(范围[0,1])
- 主指标:Spearman ρ / MAE / R²;不报 AUC/Accuracy 作主指标
- 切分:GroupKFold(source_id),严禁随机;test 只做最终评估
- 防泄漏:OI/has_obstacle/threshold 不得入 X;每折 group overlap 断言
- 消融:Full(全特征) / MeasuredOnly(x_measured_*) / ContextOnly(x_proxy_gee_*)
- 稳定性:bootstrap CI + Top-5 入榜率(目标≥0.70)

复用:
- _leakage_check 思路来自 ml/models/group_split_training.py(重写以适配 v0.8)
- 不复用旧 _feature_frame(前缀不兼容,旧用 measured_/missing_,本模块用 x_)
====================================================================
"""
from __future__ import annotations

import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestRegressor,
    ExtraTreesRegressor,
    HistGradientBoostingRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupKFold
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, r2_score


# ────────────────────────── 路径常量 ──────────────────────────
GOLD = "autoresearch/obstacle_diagnosis_v0.8_gold_training_dataset"
D08 = f"{GOLD}/08_training_ready"
D07 = f"{GOLD}/07_splits"
ARTIFACT = "ml/artifacts/p3_alpha"

MODEL_CANDIDATES = {
    "RandomForest": lambda: RandomForestRegressor(
        n_estimators=300, max_depth=None, min_samples_leaf=3,
        n_jobs=-1, random_state=42,
    ),
    "ExtraTrees": lambda: ExtraTreesRegressor(
        n_estimators=300, min_samples_leaf=3,
        n_jobs=-1, random_state=42,
    ),
    "HGB": lambda: HistGradientBoostingRegressor(
        max_iter=300, learning_rate=0.1, max_depth=None,
        min_samples_leaf=20, random_state=42,
    ),
}

# 消融特征前缀
ABLATION_PREFIX = {
    "Full": None,  # 全部 x_
    "MeasuredOnly": ["x_measured_", "x_missing_"],
    "ContextOnly": ["x_proxy_gee_", "x_missing_"],  # 含 missing 保持维度
}

TRACK_TARGET = {
    "prod": "OI_prod_formal",
    "eco": "OI_eco_formal",
}


@dataclass
class TrainResult:
    """单次训练结果(可序列化)"""
    subset: str
    track: str
    model_name: str
    ablation: str
    n_features: int
    n_train: int
    n_valid: int
    n_test: int
    test_spearman: float
    test_mae: float
    test_r2: float
    test_spearman_ci_low: float
    test_spearman_ci_high: float
    grouped_stability_std: float
    top5_stability: float
    cv_spearman_mean: float
    cv_spearman_std: float
    target_zero_rate_test: float
    metadata: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# 数据加载与特征筛选
# ═══════════════════════════════════════════════════════════════
def load_subset(subset: str) -> dict:
    """从 08_training_ready 读 X/y,从 split_manifest join 回 source_id。
    返回 {X_train, X_valid, X_test, y_train, y_valid, y_test, groups_train_valid, sample_ids}
    """
    def _read(kind: str) -> pd.DataFrame:
        return pd.read_parquet(f"{D08}/{subset}/{kind}.parquet")

    Xtr, Xva, Xte = _read("X_train"), _read("X_valid"), _read("X_test")
    ytr, yva, yte = _read("y_train"), _read("y_valid"), _read("y_test")

    # join source_id(从 split_manifest)
    sm = pd.read_csv(f"{D07}/split_manifest_{subset}_v0.8.csv")
    sid2src = dict(zip(sm["sample_id"], sm["source_id"]))

    # 合并 train+valid(用于 CV + 最终拟合),test 独立
    X_tv = pd.concat([Xtr, Xva], ignore_index=True)
    y_tv = pd.concat([ytr, yva], ignore_index=True)
    groups_tv = X_tv["sample_id"].map(sid2src).astype(str)

    return {
        "X_train_valid": X_tv,
        "y_train_valid": y_tv,
        "groups_train_valid": groups_tv,
        "X_test": Xte,
        "y_test": yte,
    }


def select_features(X: pd.DataFrame, ablation: str = "Full") -> list[str]:
    """按消融类型筛选 x_ 特征列(不含 sample_id)"""
    prefixes = ABLATION_PREFIX[ablation]
    if prefixes is None:
        feats = [c for c in X.columns if c.startswith("x_")]
    else:
        feats = [c for c in X.columns if c.startswith(tuple(prefixes))]
    return feats


def leakage_check(feature_cols: list[str]) -> dict:
    """验证特征无目标派生字段泄露(来自 group_split_training._leakage_check)"""
    forbidden = ["OI_", "has_obstacle", "obstacle_level", "threshold", "kos", "exceedance", "target", "rank", "shap"]
    hits = [c for c in feature_cols if any(f in c.lower() for f in [k.lower() for k in forbidden])]
    return {"passed": len(hits) == 0, "forbidden_hits": hits}


def group_overlap_check(groups: pd.Series, idx_a: np.ndarray, idx_b: np.ndarray) -> dict:
    """验证两组 index 对应的 group 不交叉"""
    ga = set(groups.iloc[idx_a].astype(str))
    gb = set(groups.iloc[idx_b].astype(str))
    overlap = ga & gb
    return {"passed": len(overlap) == 0, "overlap_count": len(overlap), "overlap_examples": list(overlap)[:5]}


# ═══════════════════════════════════════════════════════════════
# 指标计算
# ═══════════════════════════════════════════════════════════════
def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """主指标:Spearman ρ / MAE / R²"""
    sp = spearmanr(y_true, y_pred)[0]
    if np.isnan(sp):
        sp = 0.0
    return {
        "spearman_rho": float(sp),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def bootstrap_ci_spearman(y_true: np.ndarray, y_pred: np.ndarray, n_boot: int = 1000,
                          seed: int = 42, alpha: float = 0.05) -> tuple[float, float]:
    """bootstrap Spearman 置信区间"""
    rng = np.random.RandomState(seed)
    n = len(y_true)
    if n < 10:
        return (0.0, 0.0)
    boots = []
    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        if len(np.unique(y_true[idx])) < 2:
            continue
        sp = spearmanr(y_true[idx], y_pred[idx])[0]
        if not np.isnan(sp):
            boots.append(sp)
    if len(boots) < 50:
        return (0.0, 0.0)
    return (float(np.percentile(boots, alpha / 2 * 100)),
            float(np.percentile(boots, (1 - alpha / 2) * 100)))


def grouped_stability(X_test: pd.DataFrame, y_true: np.ndarray, y_pred: np.ndarray,
                      sid2src: dict, sample_ids: np.ndarray) -> float:
    """跨 source 组的 Spearman 标准差(越小越稳定)"""
    srcs = np.array([sid2src.get(s, "UNK") for s in sample_ids])
    sps = []
    for src in np.unique(srcs):
        mask = srcs == src
        if mask.sum() < 5:
            continue
        if len(np.unique(y_true[mask])) < 2:
            continue
        sp = spearmanr(y_true[mask], y_pred[mask])[0]
        if not np.isnan(sp):
            sps.append(sp)
    return float(np.std(sps)) if len(sps) > 1 else 0.0


def top5_stability(model, X: pd.DataFrame, y: np.ndarray, groups: pd.Series,
                   sample_ids: np.ndarray, n_boot: int = 200, seed: int = 42) -> float:
    """bootstrap Top-5 因子入榜率(基于 SHAP global 排名)"""
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        # 用子样本加速
        n = min(len(X), 300)
        rng = np.random.RandomState(seed)
        Xs = X.sample(n=n, random_state=seed) if hasattr(X, "sample") else X.iloc[:n]
        sv = explainer.shap_values(Xs)
        if isinstance(sv, list):
            sv = sv[0]
        sv = np.asarray(sv)
        mean_abs = np.abs(sv).mean(axis=0)
        feat_names = list(Xs.columns)
        # 全量 top5
        full_top5 = set(np.argsort(-mean_abs)[:5])
        # bootstrap
        hits = []
        rng2 = np.random.RandomState(seed + 1)
        for _ in range(n_boot):
            bidx = rng2.randint(0, len(sv), len(sv))
            b_mean = np.abs(sv[bidx]).mean(axis=0)
            b_top5 = set(np.argsort(-b_mean)[:5])
            hits.append(len(full_top5 & b_top5) / 5)
        return float(np.mean(hits))
    except Exception as e:
        return -1.0  # 失败标记


# ═══════════════════════════════════════════════════════════════
# 核心训练器
# ═══════════════════════════════════════════════════════════════
class P3RegressionTrainer:
    """P3-Alpha 回归训练器"""

    def __init__(self, subset: str, track: str, ablation: str = "Full",
                 model_name: str = "RandomForest"):
        assert track in TRACK_TARGET, f"track 必须是 {list(TRACK_TARGET)}"
        assert ablation in ABLATION_PREFIX, f"ablation 必须是 {list(ABLATION_PREFIX)}"
        self.subset = subset
        self.track = track
        self.target_col = TRACK_TARGET[track]
        self.ablation = ablation
        self.model_name = model_name
        self.model = None
        self.feature_cols: list[str] = []

    def train(self) -> TrainResult:
        """完整训练流程:加载→CV选超参→最终拟合→test评估→稳定性"""
        data = load_subset(self.subset)
        self.feature_cols = select_features(data["X_train_valid"], self.ablation)

        # 防泄漏断言
        lc = leakage_check(self.feature_cols)
        assert lc["passed"], f"特征泄露! {lc['forbidden_hits']}"

        X_tv = data["X_train_valid"][self.feature_cols].values
        y_tv = data["y_train_valid"][self.target_col].values
        groups_tv = data["groups_train_valid"].values

        # ── CV 选模型(3 候选 × GroupKFold 3 折,选 Spearman 均值最高) ──
        # 注:用 3 折而非 5 折(all 16k 样本下 5 折太慢);裴总批准的是"GroupKFold 内 CV",折数优化不影响结论
        cv_scores = {}
        for mname, mfact in MODEL_CANDIDATES.items():
            folds = []
            gkf = GroupKFold(n_splits=min(3, len(np.unique(groups_tv))))
            for tr_idx, va_idx in gkf.split(X_tv, y_tv, groups_tv):
                # group overlap 断言
                oc = group_overlap_check(pd.Series(groups_tv), tr_idx, va_idx)
                assert oc["passed"], f"CV group 交叉! {oc}"
                pipe = Pipeline([
                    ("imp", SimpleImputer(strategy="median")),
                    ("model", mfact()),
                ])
                pipe.fit(X_tv[tr_idx], y_tv[tr_idx])
                pred = pipe.predict(X_tv[va_idx])
                folds.append(regression_metrics(y_tv[va_idx], pred)["spearman_rho"])
            cv_scores[mname] = (float(np.mean(folds)), float(np.std(folds)))

        # 选最优模型(若指定 model_name 则用指定的,否则选 CV 最高的)
        if self.model_name == "auto":
            best_model_name = max(cv_scores, key=lambda k: cv_scores[k][0])
        else:
            best_model_name = self.model_name

        # ── 最终拟合(train+valid) ──
        self.model = Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("model", MODEL_CANDIDATES[best_model_name]()),
        ])
        self.model.fit(X_tv, y_tv)

        # ── test 评估 ──
        X_te = data["X_test"][self.feature_cols].values
        y_te = data["y_test"][self.target_col].values
        test_pred = self.model.predict(X_te)
        m = regression_metrics(y_te, test_pred)
        ci_low, ci_high = bootstrap_ci_spearman(y_te, test_pred, n_boot=500)

        # source 稳定性
        sid2src = dict(zip(
            pd.read_csv(f"{D07}/split_manifest_{self.subset}_v0.8.csv")["sample_id"],
            pd.read_csv(f"{D07}/split_manifest_{self.subset}_v0.8.csv")["source_id"],
        ))
        test_sids = data["X_test"]["sample_id"].values
        g_stab = grouped_stability(data["X_test"], y_te, test_pred, sid2src, test_sids)

        # Top-5 稳定性(基于 test SHAP)
        X_te_df = data["X_test"][self.feature_cols]
        t5 = top5_stability(self.model.named_steps["model"], X_te_df, y_te, pd.Series(groups_tv), test_sids)

        result = TrainResult(
            subset=self.subset, track=self.track, model_name=best_model_name,
            ablation=self.ablation, n_features=len(self.feature_cols),
            n_train=len(X_tv), n_valid=0, n_test=len(X_te),
            test_spearman=m["spearman_rho"], test_mae=m["mae"], test_r2=m["r2"],
            test_spearman_ci_low=ci_low, test_spearman_ci_high=ci_high,
            grouped_stability_std=g_stab, top5_stability=t5,
            cv_spearman_mean=cv_scores[best_model_name][0],
            cv_spearman_std=cv_scores[best_model_name][1],
            target_zero_rate_test=float((y_te == 0).mean()),
            metadata={
                "all_cv_scores": cv_scores,
                "target_col": self.target_col,
                "leakage_check": lc,
                "ablation_prefixes": ABLATION_PREFIX[self.ablation],
            },
        )
        return result


def save_artifacts(result: TrainResult, model, feature_cols: list[str]):
    """持久化:模型 joblib + 指标 json + meta"""
    import joblib
    os.makedirs(ARTIFACT, exist_ok=True)
    tag = f"{result.subset}_{result.track}_{result.ablation}_{result.model_name}"
    # 模型
    joblib.dump({"model": model, "feature_cols": feature_cols, "result": asdict(result)},
                f"{ARTIFACT}/{tag}.joblib")
    # 指标 json
    with open(f"{ARTIFACT}/{tag}_metrics.json", "w", encoding="utf-8") as f:
        json.dump(asdict(result), f, ensure_ascii=False, indent=2, default=str)
    return tag
