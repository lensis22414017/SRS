"""zzv0.3 R4+R5: 特征工程 + Optuna贝叶斯调参(eco轨)。

R4 特征工程:
  - 对数变换: log1p(重金属浓度) — 浓度是右偏分布, 对数后更接近正态, 利于树模型分裂
  - 交互特征: SoilpH × 各重金属 — pH影响重金属生物有效性(GB15618 pH分段就体现这点)
  - 标准化比值的污染指数: max(HM/BG) 综合指数
R5 Optuna调参: 搜HGB超参(learning_rate/max_iter/max_leaf_nodes/l2_reg/min_samples_leaf)
  目标: 最大化 GroupKFold(0泄漏) CV AUC
"""
import os
import sys
import json
import warnings

import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.metrics import roc_auc_score
import optuna

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")

HM = ["Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cr_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg"]
PHYS = ["SoilpH", "OC_pct", "CEC_cmolkg", "Sand_pct", "Silt_pct", "Clay_pct",
        "SoilBD_gcm3", "Elevation_m", "MAP_mm", "EC_mScm", "TN_gkg"]
GEE = ["gee_ndvi", "gee_precip_annual_mm", "gee_temp_mean_c", "gee_elevation_m",
       "gee_slope_deg", "gee_aspect_deg", "gee_soil_pH", "gee_soc_g_kg",
       "gee_cec_cmol_kg", "gee_clay_pct", "gee_sand_pct", "gee_silt_pct",
       "gee_bulk_density_g_cm3", "gee_nitrogen_g_kg"]

# GB15618背景值(算污染指数用)
BG = {"Cd_mgkg": 0.6, "Pb_mgkg": 500, "As_mgkg": 25, "Cr_mgkg": 250,
      "Hg_mgkg": 1.0, "Cu_mgkg": 100, "Zn_mgkg": 300, "Ni_mgkg": 100}


def engineer_features(X):
    """R4 特征工程: 对数变换 + pH交互 + 污染指数。"""
    df = X.copy()
    # 1. 对数变换重金属(右偏→正态)
    for c in HM:
        if c in df.columns:
            df[f"log_{c}"] = np.log1p(df[c].clip(lower=0))
    # 2. pH × 重金属交互(pH影响重金属有效性)
    if "SoilpH" in df.columns:
        for c in HM:
            if c in df.columns:
                df[f"pH_x_{c}"] = df["SoilpH"] * df[c]
    # 3. 综合污染指数(Nemerow式, 用BG背景值)
    pi_cols = []
    for c in HM:
        if c in df.columns:
            pi = df[c] / BG[c]
            df[f"PI_{c}"] = pi
            pi_cols.append(f"PI_{c}")
    if pi_cols:
        pi_df = df[pi_cols]
        df["PI_max"] = pi_df.max(axis=1)
        df["PI_mean"] = pi_df.mean(axis=1)
        df["PI_nemerow"] = np.sqrt((df["PI_max"]**2 + df["PI_mean"]**2) / 2)
    return df


def load_eng_data():
    """加载特征工程后的数据。"""
    X_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_X_barrier.csv"))
    X_va = pd.read_csv(os.path.join(SPLIT_DIR, "valid_X_barrier.csv"))
    X_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_X_barrier.csv"))
    base_cols = HM + PHYS + GEE
    X_tr = engineer_features(X_tr[base_cols])
    X_va = engineer_features(X_va[base_cols])
    X_te = engineer_features(X_te[base_cols])
    # 对齐列
    cols = list(X_tr.columns)
    ye_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_y_eco.csv")).iloc[:, 0]
    ye_va = pd.read_csv(os.path.join(SPLIT_DIR, "valid_y_eco.csv")).iloc[:, 0]
    ye_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_y_eco.csv")).iloc[:, 0]
    g_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_groups.csv"))["id_DOI"].fillna("").astype(str)
    return X_tr[cols], X_va[cols], X_te[cols], ye_tr, ye_va, ye_te, g_tr, cols


def objective(trial, X_tr, y_tr, g_tr):
    """Optuna目标: 最大化GroupKFold CV AUC。"""
    params = {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "max_iter": trial.suggest_int("max_iter", 200, 1000, step=100),
        "max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 15, 127),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 100),
        "l2_regularization": trial.suggest_float("l2_regularization", 0.0, 5.0),
        "early_stopping": True,
        "validation_fraction": 0.15,
        "n_iter_no_change": 20,
        "random_state": 42,
    }
    cv_aucs = cross_val_score(
        HistGradientBoostingClassifier(**params), X_tr, y_tr,
        groups=g_tr, cv=GroupKFold(5), scoring="roc_auc")
    return float(cv_aucs.mean())


def main():
    print("=" * 60)
    print("R4+R5: 特征工程 + Optuna贝叶斯调参 (eco轨)")
    print("=" * 60)
    X_tr, X_va, X_te, y_tr, y_va, y_te, g_tr, cols = load_eng_data()
    print(f"特征工程后: {len(cols)}列 (基础33 + 对数8 + pH交互8 + PI指数11)")

    # R5: Optuna调参(30 trials)
    print("\n[R5] Optuna贝叶斯调参 (30 trials, GroupKFold 0泄漏)...")
    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(lambda t: objective(t, X_tr, y_tr, g_tr), n_trials=10, show_progress_bar=True)
    best = study.best_params
    print(f"  best CV AUC: {study.best_value:.4f}")
    print(f"  best params: {best}")

    # 用best参数训练最终模型, 评估三集
    best_full = dict(best, early_stopping=True, validation_fraction=0.15,
                    n_iter_no_change=20, random_state=42)
    m = HistGradientBoostingClassifier(**best_full)
    m.fit(X_tr, y_tr)
    cv = cross_val_score(HistGradientBoostingClassifier(**best_full), X_tr, y_tr,
                         groups=g_tr, cv=GroupKFold(5), scoring="roc_auc")
    va = roc_auc_score(y_va, m.predict_proba(X_va)[:, 1])
    te = roc_auc_score(y_te, m.predict_proba(X_te)[:, 1])
    print(f"\n✅ eco轨 最终三集AUC(特征工程+Optuna):")
    print(f"  CV(0泄漏)={cv.mean():.4f}±{cv.std():.4f}")
    print(f"  valid={va:.4f} test={te:.4f}")

    # 保存结果
    result = {"best_params": best_full, "feature_cols": cols,
              "cv_auc": round(float(cv.mean()), 4), "valid_auc": round(float(va), 4),
              "test_auc": round(float(te), 4), "n_features": len(cols)}
    with open(os.path.join(ROOT, "ml", "autoresearch_dual_track", "best_eco_optuna.json"), "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n保存: ml/autoresearch_dual_track/best_eco_optuna.json")
    return result


if __name__ == "__main__":
    main()
