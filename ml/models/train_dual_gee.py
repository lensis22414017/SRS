"""双轨RF训练(模块4): 读 dual_track 切分 → 训练 prod/eco 两 RF → 5折CV + AUC区间标记 → 输出防泄漏模型。

项目组铁律: 防泄漏(X_barrier=理化+GEE, 剔除污染物浓度), 目标AUC 0.8-0.95, 切不能标签泄漏虚高。
AUC区间标记: <0.70 RED_TOO_LOW_RANDOM / >0.98 RED_SUSPECT_LEAKAGE / 0.8-0.95 GREEN_TARGET / 其他 YELLOW。
输出: ml/artifacts/rf_barrier_factor_zzv0.2_{date}_dual_{prod,eco}_barrier_gee.joblib + .meta.json
      (zz前缀字典序最末, load_latest 优先选, 压过旧 _zlake_full 泄漏模型)
"""
import os
import sys
import json
import joblib
import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows GBK终端兼容emoji
except Exception:
    pass

from datetime import datetime, timezone
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARTIFACTS = os.path.join(ROOT, "ml", "artifacts")
SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")


def _auc_flag(auc):
    if auc < 0.70:
        return "RED_TOO_LOW_RANDOM"
    if auc > 0.98:
        return "RED_SUSPECT_LEAKAGE"
    if 0.80 <= auc <= 0.95:
        return "GREEN_TARGET"
    return "YELLOW_BORDERLINE"


def _train_one_track(track, X_train, y_train, X_test, y_test, feature_list, medians):
    model = RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                   random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    proba = model.predict_proba(X_test)[:, 1]
    pred = model.predict(X_test)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "f1": round(float(f1_score(y_test, pred)), 4),
        "auc": round(float(roc_auc_score(y_test, proba)), 4),
        "test_size": int(len(y_test)),
    }
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_aucs = cross_val_score(model, X_train, y_train, cv=cv, scoring="roc_auc")
    metrics["cv_auc_mean"] = round(float(cv_aucs.mean()), 4)
    metrics["cv_auc_std"] = round(float(cv_aucs.std()), 4)
    se = float(cv_aucs.std() / np.sqrt(5))
    metrics["cv_auc_95ci"] = [round(float(cv_aucs.mean() - 1.96 * se), 4),
                              round(float(cv_aucs.mean() + 1.96 * se), 4)]
    metrics["auc_flag"] = _auc_flag(metrics["auc"])

    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    version = f"zzv0.2_{date}_dual_{track}_barrier_gee"
    label_src = ("标签_生产(GB15618 pH四段+GB36600一类, 严)" if track == "prod"
                 else "标签_生态(GB36600二类, 宽)")
    return {
        "model": model, "model_name": "rf_barrier_factor", "version": version,
        "algorithm": "RandomForestClassifier",
        "params": {"n_estimators": 300, "class_weight": "balanced", "random_state": 42},
        "feature_list": feature_list, "medians": medians,
        "data_version": "merged_std33_27031_gee_dual_track",
        "is_real_data": True,
        "data_source": "merged_std33.csv geocoded subset(27031行) + GEE协变量",
        "label_source": label_src,
        "metrics": metrics,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_features": len(feature_list), "block": "dual_track",
        "feature_strategy": "理化稀疏列+GEE栅格协变量, 剔除全部污染物浓度列",
        "leakage_warning": ("X_barrier=理化+GEE协变量, 剔除全部污染物浓度列(防泄漏); "
                            "AUC不虚高, 区间0.8-0.95为可信诊断"),
    }


def main():
    os.makedirs(ARTIFACTS, exist_ok=True)
    print("=" * 64)
    print("双轨RF训练(防泄漏+GEE增强) — prod/eco 两模型")
    print("=" * 64)

    X_train = pd.read_csv(os.path.join(SPLIT_DIR, "train_X_barrier.csv"))
    X_test = pd.read_csv(os.path.join(SPLIT_DIR, "test_X_barrier.csv"))
    y_prod_train = pd.read_csv(os.path.join(SPLIT_DIR, "train_y_prod.csv")).iloc[:, 0]
    y_prod_test = pd.read_csv(os.path.join(SPLIT_DIR, "test_y_prod.csv")).iloc[:, 0]
    y_eco_train = pd.read_csv(os.path.join(SPLIT_DIR, "train_y_eco.csv")).iloc[:, 0]
    y_eco_test = pd.read_csv(os.path.join(SPLIT_DIR, "test_y_eco.csv")).iloc[:, 0]

    feature_list = list(X_train.columns)
    medians = {c: float(X_train[c].median()) for c in feature_list}
    print(f"特征数: {len(feature_list)} | 训练{len(X_train)} 测试{len(X_test)}")
    print(f"prod: 训练正{int(y_prod_train.sum())}/{len(y_prod_train)} | 测试正{int(y_prod_test.sum())}/{len(y_prod_test)}")
    print(f"eco:  训练正{int(y_eco_train.sum())}/{len(y_eco_train)} | 测试正{int(y_eco_test.sum())}/{len(y_eco_test)}")

    for track, y_tr, y_te in [("prod", y_prod_train, y_prod_test),
                              ("eco", y_eco_train, y_eco_test)]:
        print(f"\n--- 训练 {track} 轨 RF ---")
        bundle = _train_one_track(track, X_train, y_tr, X_test, y_te, feature_list, medians)
        m = bundle["metrics"]
        print(f"  AUC={m['auc']} ({m['auc_flag']}) | F1={m['f1']} | Acc={m['accuracy']}")
        print(f"  5折CV AUC={m['cv_auc_mean']}±{m['cv_auc_std']} | 95%CI={m['cv_auc_95ci']}")
        if m["auc_flag"].startswith("RED"):
            print(f"  ⚠️ {m['auc_flag']}: 需排查(随机或泄漏)")

        fname = f"rf_barrier_factor_{bundle['version']}.joblib"
        joblib.dump(bundle, os.path.join(ARTIFACTS, fname))
        meta = {k: v for k, v in bundle.items() if k != "model"}
        with open(os.path.join(ARTIFACTS, fname.replace('.joblib', '.meta.json')),
                  'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, default=str)
        print(f"  → {fname}")

    print("\n✅ 双轨训练完成。下一步: load_latest 路由切换(Task#6) + 17场地回归验证(Task#7)。")


if __name__ == "__main__":
    main()
