"""阶段C: 三块分别训练 RF + 数据湖合并训练。

裴总: 重金属/OP/复合三块分别训练 + 合并数据湖完整再训练(autoresearch)。
产物: ml/artifacts/rf_barrier_factor_v0.1_<date>_<name>.joblib (4 model: hm/op/composite/lake)。
load_latest 加载最新(lake 最后, 含重金属+有机, diagnosis 用它)。

运行: cd backend && .venv/bin/python ../ml/models/train_three.py
"""
import os, sys, json
import pandas as pd
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))
from data_prep import prepare  # noqa
ARTIFACTS = os.path.join(ROOT, "ml", "artifacts")
TRAIN_BASE = os.path.join(ROOT, "data", "training")
DROP_COLS = ["Latitude", "Longitude", "Province", "City", "Pollution_Type", "DOI",
             "Source", "id_DOI", "id_Source", "ID", "Year", "LandUse", "SamplingDepth",
             "split_source", "is_synthetic"]


def _prep_csv(name):
    """读 imputed train, drop 非特征(经纬度等防泄漏), 写 tmp csv。"""
    src = os.path.join(TRAIN_BASE, name, "imputed", "train.csv")
    df = pd.read_csv(src)
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    # 标签须保留
    assert "标签" in df.columns, f"{name} 缺标签列"
    tmp = os.path.join(TRAIN_BASE, name, "imputed", "_train_prepared.csv")
    df.to_csv(tmp, index=False)
    return tmp


def _train(name, csv_path):
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from datetime import datetime, timezone

    X, y, meta = prepare(csv_path)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    model = RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                   random_state=42, n_jobs=-1)
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)[:, 1]
    metrics = {
        "accuracy": round(float(accuracy_score(y_te, model.predict(X_te))), 4),
        "f1": round(float(f1_score(y_te, model.predict(X_te))), 4),
        "auc": round(float(roc_auc_score(y_te, proba)), 4),
        "test_size": int(len(y_te))}
    version = "v0.1_" + datetime.now(timezone.utc).strftime("%Y%m%d") + "_" + name
    # lake(数据湖)用 z 前缀使字典序最后(>op) → load_latest 优先用它(裴总: 数据湖完整训练)
    if name == "lake":
        version = "v0.1_" + datetime.now(timezone.utc).strftime("%Y%m%d") + "_zlake_final"
    bundle = {"model": model, "model_name": "rf_barrier_factor", "version": version,
              "algorithm": "RandomForestClassifier",
              "params": {"n_estimators": 300, "class_weight": "balanced"},
              "feature_list": meta["feature_list"], "medians": meta["medians"],
              "data_version": meta["data_version"] + "_" + name,
              "is_real_data": meta["is_real_data"], "data_source": meta["data_source"],
              "label_source": meta["label_source"], "metrics": metrics,
              "trained_at": datetime.now(timezone.utc).isoformat(),
              "n_features": int(X.shape[1]), "block": name}
    path = os.path.join(ARTIFACTS, f"rf_barrier_factor_{version}.joblib")
    joblib.dump(bundle, path)
    with open(os.path.join(ARTIFACTS, f"rf_barrier_factor_{version}.meta.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in bundle.items() if k != "model"}, f, ensure_ascii=False, indent=2)
    # 特征含有机?
    has_org = any(k in str(meta["feature_list"]) for k in ["PAH", "OCP", "PCB", "PAE", "DDT", "HCH", "PBDE", "PFAS", "TPH"])
    print(f"[{name}] n={len(X)} feat={X.shape[1]} 含有机={has_org} metrics={metrics} → {version}")
    return path


def build_lake():
    """三块 concat → 数据湖(特征并集) → train csv。"""
    lake_rows = []
    for name in ["hm", "op", "composite"]:
        df = pd.read_csv(os.path.join(TRAIN_BASE, name, "imputed", "train.csv"))
        df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
        df["__block"] = name
        lake_rows.append(df)
    lake = pd.concat(lake_rows, ignore_index=True, sort=False)
    # 特征并集的缺失(块间无的列)用中位数 + missing 标记(已在各块; 新缺失补 0/median)
    lake_dir = os.path.join(TRAIN_BASE, "lake", "imputed")
    os.makedirs(lake_dir, exist_ok=True)
    lake.to_csv(os.path.join(lake_dir, "train.csv"), index=False)
    print(f"[lake] 合并: {lake.shape} (三块concat, 特征并集)")


if __name__ == "__main__":
    for name in ["hm", "op", "composite"]:
        csv = _prep_csv(name)
        _train(name, csv)
    build_lake()
    # 数据湖训练(最后, load_latest 加载它 → diagnosis 用含有机 model)
    _train("lake", os.path.join(TRAIN_BASE, "lake", "imputed", "train.csv"))
    print("\n完成。4 model(hm/op/composite/lake) → ml/artifacts/")
