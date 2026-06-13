"""RF 行级随机 vs DOI/Source group split 对照训练。

用途是暴露行级随机切分的虚高风险, 不是把阈值派生标签当作独立科学结论。
真实性能报告必须优先使用 DOI/Source 分组指标。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_MODEL_READY = os.path.join(ROOT, "data", "model_ready", "model_ready_hm.csv")
ARTIFACT_DIR = os.path.join(ROOT, "ml", "artifacts")
REPORT_PATH = os.path.join(ROOT, "docs", "model", "rf_group_split_report.md")


def _standard_screening_min() -> dict[str, float]:
    """从标准阈值种子读取最保守筛选值, 避免在训练逻辑中另写阈值常量。"""
    import sys
    backend = os.path.join(ROOT, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from app.db.load_standard_thresholds import seed_rows

    out: dict[str, float] = {}
    for row in seed_rows():
        if row["standard_code"] != "GB 15618-2018" or row["screening_value"] is None:
            continue
        factor = row["factor_name"]
        out[factor] = min(out.get(factor, float("inf")), float(row["screening_value"]))
    return out


def derive_threshold_label(df: pd.DataFrame, thresholds: dict[str, float] | None = None) -> pd.Series:
    thresholds = thresholds or _standard_screening_min()
    flags = []
    for factor, limit in thresholds.items():
        col = f"measured_{factor}_mgkg"
        if col in df.columns:
            flags.append(pd.to_numeric(df[col], errors="coerce") > limit)
    if not flags:
        raise ValueError("无法从 model_ready 表派生风险标签: 缺少 measured_*_mgkg 列")
    return pd.concat(flags, axis=1).any(axis=1).astype(int)


def _feature_frame(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    cols = [c for c in df.columns if c.startswith("measured_") or c.startswith("missing_")]
    cols = [c for c in cols if c != target_col]
    if not cols:
        raise ValueError("缺少 measured_/missing_ 特征列")
    return df[cols].apply(pd.to_numeric, errors="coerce")


def _metrics(y_true, proba, pred) -> dict:
    from sklearn.metrics import balanced_accuracy_score, f1_score, roc_auc_score
    out = {
        "n_test": int(len(y_true)),
        "positive_rate": round(float(np.mean(y_true)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(y_true, pred)), 4),
        "macro_f1": round(float(f1_score(y_true, pred, average="macro", zero_division=0)), 4),
    }
    try:
        out["roc_auc"] = round(float(roc_auc_score(y_true, proba)), 4)
    except ValueError:
        out["roc_auc"] = None
    return out


def _fit_eval(X: pd.DataFrame, y: pd.Series, train_idx, test_idx,
              n_estimators: int, random_state: int) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline

    model = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("rf", RandomForestClassifier(
            n_estimators=n_estimators,
            class_weight="balanced",
            min_samples_leaf=2,
            random_state=random_state,
            n_jobs=-1,
        )),
    ])
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    return {"model": model, **_metrics(y_test, proba, pred)}


def _row_random_split(X, y, random_state: int):
    from sklearn.model_selection import train_test_split
    idx = np.arange(len(X))
    stratify = y if y.nunique() == 2 and y.value_counts().min() >= 2 else None
    train_idx, test_idx = train_test_split(
        idx, test_size=0.2, random_state=random_state, stratify=stratify)
    return train_idx, test_idx


def _group_split(df: pd.DataFrame, group_col: str, random_state: int):
    from sklearn.model_selection import GroupShuffleSplit
    groups = df[group_col].fillna("__missing_group__").astype(str)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=random_state)
    train_idx, test_idx = next(splitter.split(df, groups=groups))
    return train_idx, test_idx, groups


def _leakage_check(groups: pd.Series, train_idx, test_idx) -> dict:
    train_groups = set(groups.iloc[train_idx])
    test_groups = set(groups.iloc[test_idx])
    overlap = sorted(train_groups & test_groups)
    return {"passed": len(overlap) == 0, "overlap_count": len(overlap), "overlap_examples": overlap[:5]}


def compare_row_random_and_group_split(df: pd.DataFrame, target_col: str = "label_risk",
                                       group_cols=("id_DOI", "id_Source"),
                                       n_estimators: int = 160,
                                       random_state: int = 42) -> dict:
    work = df.copy()
    if target_col not in work.columns:
        work[target_col] = derive_threshold_label(work)
    work = work[work[target_col].notna()].reset_index(drop=True)
    y = work[target_col].astype(int)
    X = _feature_frame(work, target_col)

    row_train, row_test = _row_random_split(X, y, random_state)
    row_res = _fit_eval(X, y, row_train, row_test, n_estimators, random_state)
    row_res.pop("model", None)
    row_res["split_strategy"] = "row_random"

    group_results = {}
    leakage = {}
    for col in group_cols:
        if col not in work.columns:
            continue
        train_idx, test_idx, groups = _group_split(work, col, random_state)
        res = _fit_eval(X, y, train_idx, test_idx, n_estimators, random_state)
        res.pop("model", None)
        res["split_strategy"] = f"group_split:{col}"
        res["n_train"] = int(len(train_idx))
        group_results[col] = res
        leakage[col] = _leakage_check(groups, train_idx, test_idx)

    group_aucs = [v["roc_auc"] for v in group_results.values() if v.get("roc_auc") is not None]
    if row_res.get("roc_auc") is not None and group_aucs:
        gap = round(float(row_res["roc_auc"] - np.mean(group_aucs)), 4)
    else:
        gap = None
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": target_col,
        "n_rows": int(len(work)),
        "n_features": int(X.shape[1]),
        "row_random": row_res,
        "group_splits": group_results,
        "auc_gap_row_minus_group": gap,
        "leakage_checks": leakage,
        "warning": ("行级随机切分可能共享 DOI/Source 结构, 仅作虚高风险对照; 主真实性能看 group_splits。"
                    "若 row/group 指标都接近 1, 优先解释为阈值派生标签与污染物特征强绑定, "
                    "不能当作独立真实性能证据。"),
    }


def train_from_csv(csv_path: str = DEFAULT_MODEL_READY, random_state: int = 42) -> dict:
    df = pd.read_csv(csv_path, low_memory=False)
    result = compare_row_random_and_group_split(df, random_state=random_state)
    result["source_csv"] = os.path.relpath(csv_path, ROOT)
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    out_json = os.path.join(ARTIFACT_DIR, "rf_group_split_metrics.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    _write_report(result, REPORT_PATH)
    return result


def _write_report(result: dict, path: str):
    lines = [
        "# RF 分组切分重训报告",
        "",
        "> 本报告用于暴露行级随机切分虚高风险。真实泛化能力以 DOI/Source group split 为准。",
        "",
        f"- 数据源: `{result.get('source_csv', 'in-memory')}`",
        f"- 样本数: {result['n_rows']}",
        f"- 特征数: {result['n_features']}",
        f"- 行级随机 ROC-AUC: {result['row_random'].get('roc_auc')}",
        f"- AUC 差值(row - group mean): {result['auc_gap_row_minus_group']}",
        "",
        "## 分组切分指标",
        "",
        "| 分组键 | ROC-AUC | Balanced Acc | Macro-F1 | 测试样本 | 泄漏检查 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for col, metrics in result["group_splits"].items():
        leak = result["leakage_checks"].get(col, {})
        lines.append(
            f"| {col} | {metrics.get('roc_auc')} | {metrics.get('balanced_accuracy')} | "
            f"{metrics.get('macro_f1')} | {metrics.get('n_test')} | "
            f"{'PASS' if leak.get('passed') else 'FAIL'} |"
        )
    lines += [
        "",
        "## 解释口径",
        "",
        "阈值派生标签只用于训练切分和泄漏诊断, 不能替代人工复核或独立实测验证。",
        "若行级随机指标显著高于 group split, 应按虚高风险处理, 不作为主性能证据。",
        "若 row-random 与 group split 均接近 1, 也不能视作模型已可靠; 这通常说明标签由同一批污染物阈值派生, 与特征存在规则绑定。",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    res = train_from_csv()
    print(json.dumps(res, ensure_ascii=False, indent=2))
