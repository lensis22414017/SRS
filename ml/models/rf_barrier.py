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
        "is_real_data": meta.get("is_real_data", False),  # True=真实文献(GB15618标签)
        "data_source": meta.get("data_source", ""),
        "label_source": meta.get("label_source", ""),  # 标签派生方式(可追溯)
        "dropped_leakage_cols": meta.get("dropped_leakage_cols", []),
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


def load_latest(track=None):
    """加载最新模型 bundle; 无产物时返回 None。

    双轨接入(2026-06-24 Wave): track='prod'/'eco' 按修复后用途选对应轨模型
    (lake_prod_full=生产严 GB15618/GB36600一类; lake_eco_full=生态宽 GB36600二类)。
    track=None 取字典序最后(向后兼容旧调用); 无指定轨产物则回退全部最新。
    diagnosis_service 应按 Site.land_use_type 传 track 实现双轨路由。

    2026-06-26 修复(项目组要求打通双轨诊断): track 过滤兼容 Wave E 命名
    (_{block}_{track}_{group}.joblib, 如 _lake_prod_full) — 旧 endswith('_prod.joblib')
    只匹配单层命名致路由失效(实测选了 op_prod 而非 lake_prod_full)。
    诊断主模型强制 lake(数据湖完整)+full组(过渡含浓度; barrier组AUC≈0.54不可诊断)。
    """
    import joblib
    if not os.path.isdir(ARTIFACTS):
        return None
    cands = sorted(f for f in os.listdir(ARTIFACTS)
                   if f.startswith(MODEL_NAME) and f.endswith(".joblib"))
    if not cands:
        return None
    if track:
        # 1) 按轨过滤: 兼容旧 _prod.joblib + Wave E _lake_prod_full.joblib 两种命名
        filt = [f for f in cands
                if f.endswith(f"_{track}.joblib") or f"_{track}_" in f]
        cands = filt if filt else cands
        # 2) 优先 _barrier_gee (防泄漏+GEE协变量, v0.2, CV AUC 0.83 达项目组目标 0.8-0.95)
        barrier_gee = sorted(f for f in cands if "_barrier_gee" in f)
        if barrier_gee:
            return joblib.load(os.path.join(ARTIFACTS, barrier_gee[-1]))
        # 3) 过渡兼容: _lake_full (含浓度泄漏, 仅新模型不存在时)
        lake_full = sorted(f for f in cands if "_lake_" in f and "_full" in f)
        if lake_full:
            return joblib.load(os.path.join(ARTIFACTS, lake_full[-1]))
    return joblib.load(os.path.join(ARTIFACTS, cands[-1]))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    train(sys.argv[1] if len(sys.argv) > 1 else None)
