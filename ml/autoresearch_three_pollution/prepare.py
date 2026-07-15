"""L1固定评估设施：三污染类型×生产/生态双轨，按source_id分组交叉验证。"""
from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold


ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "autoresearch" / "obstacle_diagnosis_v0.8_gold_training_dataset"
SUBSETS = ("hm", "op", "hm_op")
TRACKS = {"prod": "OI_prod_formal", "eco": "OI_eco_formal"}
MIN_FEATURE_COVERAGE = 0.005
BUDGET_FOLDS = 3
METRICS = ("mean_cv_spearman", "worst_cv_spearman", "mean_cv_mae")
_CACHE: dict[str, dict] = {}


def _safe_spearman(y_true, y_pred) -> float:
    score = spearmanr(y_true, y_pred).statistic
    return 0.0 if np.isnan(score) else float(score)


def load_subset(subset: str, include_test: bool = False) -> dict:
    key = f"{subset}:{include_test}"
    if key in _CACHE:
        return _CACHE[key]
    data = pd.read_parquet(GOLD / "06_dataset_subsets" / f"dataset_{subset}_v0.8.parquet")
    manifest_path = GOLD / "07_splits" / f"split_manifest_{subset}_v0.8.csv"
    if manifest_path.exists():
        split = pd.read_csv(manifest_path)
        split_map = split.set_index("sample_id")["split"]
        source_map = split.set_index("sample_id")["source_id"].astype(str)
        row_split = data["sample_id"].map(split_map)
    else:
        test_ids = set(pd.read_parquet(GOLD / "08_training_ready" / subset / "X_test.parquet")["sample_id"])
        row_split = data["sample_id"].map(lambda value: "test" if value in test_ids else "development")
        source_map = data.set_index("sample_id")["source_id"].astype(str)
    selected = row_split.notna() if include_test else (row_split.notna() & row_split.ne("test"))
    frame = data.loc[selected].reset_index(drop=True)
    groups = frame["sample_id"].map(source_map).fillna(frame["source_id"]).astype(str)
    feature_cols = [column for column in frame if column.startswith("x_")]
    coverage = frame[feature_cols].notna().mean()
    unique = frame[feature_cols].nunique(dropna=False)
    feature_cols = [
        column for column in feature_cols
        if coverage[column] >= MIN_FEATURE_COVERAGE and unique[column] > 1
    ]
    result = {
        "X": frame[feature_cols], "y": frame[list(TRACKS.values())],
        "groups": groups, "feature_cols": feature_cols,
        "sample_ids": frame["sample_id"], "split": row_split.loc[selected].reset_index(drop=True),
    }
    _CACHE[key] = result
    return result


def evaluate(train_module, include_test: bool = False) -> dict:
    metrics: dict[str, float] = {}
    spearman_scores, mae_scores = [], []
    for subset in SUBSETS:
        loaded = load_subset(subset, include_test=include_test)
        splits = min(BUDGET_FOLDS, loaded["groups"].nunique())
        cv = GroupKFold(n_splits=splits)
        for track, target in TRACKS.items():
            fold_spearman, fold_mae, fold_r2 = [], [], []
            for train_index, valid_index in cv.split(loaded["X"], loaded["y"][target], loaded["groups"]):
                train_groups = set(loaded["groups"].iloc[train_index])
                valid_groups = set(loaded["groups"].iloc[valid_index])
                assert not train_groups & valid_groups
                model = train_module.build_model(subset, track)
                model.fit(loaded["X"].iloc[train_index], loaded["y"][target].iloc[train_index])
                prediction = np.clip(model.predict(loaded["X"].iloc[valid_index]), 0.0, 1.0)
                truth = loaded["y"][target].iloc[valid_index]
                fold_spearman.append(_safe_spearman(truth, prediction))
                fold_mae.append(float(mean_absolute_error(truth, prediction)))
                fold_r2.append(float(r2_score(truth, prediction)))
            prefix = f"{subset}_{track}"
            metrics[f"{prefix}_cv_spearman"] = round(float(np.mean(fold_spearman)), 4)
            metrics[f"{prefix}_cv_mae"] = round(float(np.mean(fold_mae)), 4)
            metrics[f"{prefix}_cv_r2"] = round(float(np.mean(fold_r2)), 4)
            spearman_scores.append(np.mean(fold_spearman))
            mae_scores.append(np.mean(fold_mae))
    metrics["mean_cv_spearman"] = round(float(np.mean(spearman_scores)), 4)
    metrics["worst_cv_spearman"] = round(float(np.min(spearman_scores)), 4)
    metrics["mean_cv_mae"] = round(float(np.mean(mae_scores)), 4)
    return metrics


if __name__ == "__main__":
    module = importlib.import_module("train")
    print(evaluate(module))
