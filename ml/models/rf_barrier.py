"""RF 障碍因子识别模型: 训练 / 评估 / 持久化 / 加载。

需 scikit-learn + joblib (本机 venv 运行):
    cd backend && source .venv/bin/activate
    python ../ml/models/rf_barrier.py        # 训练并保存
产物: ml/artifacts/rf_barrier_<version>.joblib (含 model + meta)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARTIFACTS = os.path.join(ROOT, "ml", "artifacts")

MODEL_NAME = "rf_barrier_factor"


def train(csv_path: str | None = None, random_state: int = 42) -> dict:
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    from data_prep import DEFAULT_CSV, prepare  # 同目录导入

    X, y, meta = prepare(csv_path or DEFAULT_CSV)
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=random_state)

    model = RandomForestClassifier(
        n_estimators=300, class_weight="balanced",
        random_state=random_state, n_jobs=-1)
    model.fit(X_tr, y_tr)

    proba = model.predict_proba(X_te)[:, 1]
    pred = model.predict(X_te)
    metrics = {
        "accuracy": round(float(accuracy_score(y_te, pred)), 4),
        "f1": round(float(f1_score(y_te, pred)), 4),
        "auc": round(float(roc_auc_score(y_te, proba)), 4),
        "test_size": int(len(y_te)),
    }
    version = "v0.1_" + datetime.now(timezone.utc).strftime("%Y%m%d")

    os.makedirs(ARTIFACTS, exist_ok=True)
    path = os.path.join(ARTIFACTS, f"{MODEL_NAME}_{version}.joblib")
    bundle = {
        "model": model,
        "model_name": MODEL_NAME,
        "version": version,
        "algorithm": "RandomForestClassifier",
        "params": {"n_estimators": 300, "class_weight": "balanced",
                   "random_state": random_state},
        "feature_list": meta["feature_list"],
        "medians": meta["medians"],
        "data_version": meta["data_version"],
        "metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    joblib.dump(bundle, path)
    with open(os.path.join(ARTIFACTS, f"{MODEL_NAME}_{version}.meta.json"),
              "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in bundle.items() if k != "model"},
                  f, ensure_ascii=False, indent=2)
    print(f"训练完成: {path}")
    print("指标:", metrics)
    return {"artifact_path": path, **{k: v for k, v in bundle.items() if k != "model"}}


def load_latest():
    """加载最新模型 bundle; 无产物时返回 None。"""
    import joblib
    if not os.path.isdir(ARTIFACTS):
        return None
    cands = sorted(f for f in os.listdir(ARTIFACTS)
                   if f.startswith(MODEL_NAME) and f.endswith(".joblib"))
    if not cands:
        return None
    return joblib.load(os.path.join(ARTIFACTS, cands[-1]))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    train(sys.argv[1] if len(sys.argv) > 1 else None)
