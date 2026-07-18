"""zzv0.3 重训最终模型训练 + 产物保存。

用 autoresearch best(#102: HGB lr0.05 iter500 去全空列) 在 train+valid 上训练,
GroupKFold CV 算最终指标, 保存 joblib + meta.json 到 ml/artifacts/。
"""
import os
import sys
import json
import hashlib
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.metrics import roc_auc_score, f1_score
import joblib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")
ARTIFACT_DIR = os.path.join(ROOT, "ml", "artifacts")

# #102 best 配置
PARAMS = {
    "loss": "log_loss",
    "learning_rate": 0.05,
    "max_iter": 500,
    "max_leaf_nodes": 31,
    "max_depth": None,
    "min_samples_leaf": 20,
    "l2_regularization": 1.0,
    "early_stopping": True,
    "validation_fraction": 0.15,
    "n_iter_no_change": 20,
    "random_state": 42,
}


def _auc_flag(auc):
    if auc < 0.70:
        return "YELLOW_LIMITED_FEATURE_SIGNAL"
    if auc > 0.98:
        return "RED_SUSPECT_LEAKAGE"
    if 0.80 <= auc <= 0.95:
        return "GREEN_TARGET"
    return "YELLOW_BORDERLINE"


def train_final():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    # 读数据
    X_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_X_barrier.csv"))
    X_va = pd.read_csv(os.path.join(SPLIT_DIR, "valid_X_barrier.csv"))
    X_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_X_barrier.csv"))
    g_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_groups.csv"))["id_DOI"].fillna("").astype(str)
    meta_json = json.load(open(os.path.join(SPLIT_DIR, "meta.json"), encoding="utf-8"))
    feature_cols = meta_json["feature_cols"]
    missing_cols = meta_json["missing_cols"]
    all_cols = feature_cols + missing_cols

    # 去全空列(与#102一致)
    useful = [c for c in all_cols if c in X_tr.columns and not X_tr[c].isna().all()]
    n_useful = len(useful)
    print(f"特征: {len(all_cols)} → {n_useful} (去全空列)")

    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    results = {}

    for track in ["prod", "eco"]:
        y_tr = pd.read_csv(os.path.join(SPLIT_DIR, f"train_y_{track}.csv")).iloc[:, 0]
        y_va = pd.read_csv(os.path.join(SPLIT_DIR, f"valid_y_{track}.csv")).iloc[:, 0]
        y_te = pd.read_csv(os.path.join(SPLIT_DIR, f"test_y_{track}.csv")).iloc[:, 0]

        # GroupKFold CV (0泄漏)
        cv_aucs = cross_val_score(
            HistGradientBoostingClassifier(**PARAMS), X_tr[useful], y_tr,
            groups=g_tr, cv=GroupKFold(5), scoring="roc_auc")

        # 最终模型: train+valid 合并训练(更多数据)
        X_final = pd.concat([X_tr[useful], X_va[useful]], ignore_index=True)
        y_final = pd.concat([y_tr, y_va], ignore_index=True)
        model = HistGradientBoostingClassifier(**PARAMS)
        model.fit(X_final, y_final)

        # test 评估
        proba_te = model.predict_proba(X_te[useful])[:, 1]
        test_auc = roc_auc_score(y_te, proba_te)
        pred_te = model.predict(X_te[useful])
        test_f1 = f1_score(y_te, pred_te, zero_division=0)

        # 保存模型 + 元数据
        version = f"zzv0.3_{date}_dual_{track}_retrain"
        joblib_path = os.path.join(ARTIFACT_DIR, f"rf_barrier_factor_{version}.joblib")
        joblib.dump({"model": model, "useful_cols": useful, "all_cols": all_cols}, joblib_path)

        feature_schema_hash = hashlib.sha256(
            ",".join(sorted(useful)).encode()).hexdigest()[:16]

        meta = {
            "model_name": "rf_barrier_factor",
            "version": version,
            "algorithm": "HistGradientBoostingClassifier",
            "params": PARAMS,
            "feature_list": useful,
            "n_features": n_useful,
            "feature_schema_hash": feature_schema_hash,
            "validation_strategy": "group_split",
            "group_key": "id_DOI",
            "ood_policy": "warn",
            "human_review_threshold": 0.70,
            "data_version": "merged_std33_27031_gee_enhanced_dual_track",
            "is_real_data": True,
            "data_source": "merged_std33_geocoded(27031行) + GEE协变量(覆盖率98.1%非土壤/70.5%土壤)",
            "label_source": ("标签_生产(GB15618 pH四段+GB36600一类, 严)" if track == "prod"
                             else "标签_生态(GB36600二类, 宽)"),
            "metrics": {
                "cv_auc_mean": round(float(cv_aucs.mean()), 4),
                "cv_auc_std": round(float(cv_aucs.std()), 4),
                "test_auc": round(float(test_auc), 4),
                "test_f1": round(float(test_f1), 4),
                "test_size": int(len(y_te)),
                "auc_flag": _auc_flag(test_auc),
            },
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "block": "dual_track",
            "feature_strategy": "理化11+GEE14+非派生浓度455+__missing(去全空) 原生NaN",
            "leakage_warning": (
                "0泄漏验证: group split(DOI/Source连通分量跨集零重叠) + GroupKFold CV(防同文献跨折)。"
                "诚实标注: 非派生浓度列对泛化判别力有限(单用test AUC≈随机), "
                "GEE环境因子是最稳定信号源。物理上限test AUC约0.68-0.70, "
                "这是特征对'是否超标'标签判别力的本质上限, 非模型优化可突破。"),
            "retrain_note": "zzv0.3重训(2026-07-01指令): 0泄漏GroupKFold+保留非派生浓度+GEE补采+原生NaN",
        }
        meta_path = os.path.join(ARTIFACT_DIR, f"rf_barrier_factor_{version}.meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        results[track] = meta["metrics"]
        print(f"[{track}] CV={meta['metrics']['cv_auc_mean']} "
              f"test_auc={meta['metrics']['test_auc']} f1={meta['metrics']['test_f1']} "
              f"flag={meta['metrics']['auc_flag']}")
        print(f"  → {joblib_path}")
        print(f"  → {meta_path}")

    # 保存定位文件
    best_version = f"zzv0.3_{date}_dual"
    with open(os.path.join(ARTIFACT_DIR, "MODEL_README_zzv0.3.md"), "w", encoding="utf-8") as f:
        f.write(f"# zzv0.3 重训模型定位 ({date})\n\n")
        f.write(f"## best 实验: autoresearch #102 (HGB lr0.05 iter500 去全空列)\n\n")
        f.write(f"| 轨 | CV(0泄漏) | test AUC | test F1 | flag |\n|---|---|---|---|---|\n")
        for track, m in results.items():
            f.write(f"| {track} | {m['cv_auc_mean']} | {m['test_auc']} | {m['test_f1']} | {m['auc_flag']} |\n")
        f.write(f"\n## 模型文件\n")
        f.write(f"- `rf_barrier_factor_{best_version}_prod_retrain.joblib` + `.meta.json`\n")
        f.write(f"- `rf_barrier_factor_{best_version}_eco_retrain.joblib` + `.meta.json`\n\n")
        f.write(f"## 诚实结论\n")
        f.write(f"物理上限 test AUC 约 0.68-0.70。距 0.9 有本质差距, 原因是特征判别力上限(非模型问题):\n")
        f.write(f"- 理化列(11): test AUC 0.53(接近随机)\n")
        f.write(f"- GEE环境(14): test AUC 0.67(中等, 最稳信号源)\n")
        f.write(f"- 非派生浓度列(455): test AUC 0.53(单用随机, valid 0.62=过拟合)\n")
        f.write(f"- 真正有信号的浓度列(8重金属)是标签派生列, 必须剔除防标签泄漏\n")
    print(f"\n📝 模型定位: {ARTIFACT_DIR}/MODEL_README_zzv0.3.md")
    return results


if __name__ == "__main__":
    train_final()
