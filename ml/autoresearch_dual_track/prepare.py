"""L1 基础设施(锁定): zzv0.3 #103 — GroupKFold(0泄漏) + train/valid/test 三集评估。
特征: HM8+理化11+GEE14=33(不含有机浓度, 防eco标签有机泄漏)。原生NaN。"""
import os
import json
import pandas as pd
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.metrics import roc_auc_score, f1_score

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")
METRICS = ["mean_cv_auc", "prod_cv_auc", "eco_cv_auc",
           "prod_valid_auc", "eco_valid_auc", "prod_test_auc", "eco_test_auc"]

# 特征白名单: HM8+理化11+GEE14(不含有机浓度, 防eco标签泄漏)
HM = ["Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cr_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg"]
PHYS = ["SoilpH", "OC_pct", "CEC_cmolkg", "Sand_pct", "Silt_pct", "Clay_pct",
        "SoilBD_gcm3", "Elevation_m", "MAP_mm", "EC_mScm", "TN_gkg"]
GEE = ["gee_ndvi", "gee_precip_annual_mm", "gee_temp_mean_c", "gee_elevation_m",
       "gee_slope_deg", "gee_aspect_deg", "gee_soil_pH", "gee_soc_g_kg",
       "gee_cec_cmol_kg", "gee_clay_pct", "gee_sand_pct", "gee_silt_pct",
       "gee_bulk_density_g_cm3", "gee_nitrogen_g_kg"]
FEATURE_COLS = HM + PHYS + GEE  # 33

_DATA = None


def load_data():
    global _DATA
    if _DATA is None:
        X_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_X_barrier.csv"))[FEATURE_COLS]
        X_va = pd.read_csv(os.path.join(SPLIT_DIR, "valid_X_barrier.csv"))[FEATURE_COLS]
        X_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_X_barrier.csv"))[FEATURE_COLS]
        yp_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_y_prod.csv")).iloc[:, 0]
        yp_va = pd.read_csv(os.path.join(SPLIT_DIR, "valid_y_prod.csv")).iloc[:, 0]
        yp_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_y_prod.csv")).iloc[:, 0]
        ye_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_y_eco.csv")).iloc[:, 0]
        ye_va = pd.read_csv(os.path.join(SPLIT_DIR, "valid_y_eco.csv")).iloc[:, 0]
        ye_te = pd.read_csv(os.path.join(SPLIT_DIR, "test_y_eco.csv")).iloc[:, 0]
        g_tr = pd.read_csv(os.path.join(SPLIT_DIR, "train_groups.csv"))["id_DOI"].fillna("").astype(str)
        _DATA = (X_tr, X_va, X_te, yp_tr, yp_va, yp_te, ye_tr, ye_va, ye_te, g_tr)
    return _DATA


def evaluate(train_module):
    (X_tr, X_va, X_te, yp_tr, yp_va, yp_te,
     ye_tr, ye_va, ye_te, g_tr) = load_data()
    cv = GroupKFold(n_splits=5)
    r = {}
    for track, y_tr, y_va, y_te in [("prod", yp_tr, yp_va, yp_te),
                                     ("eco", ye_tr, ye_va, ye_te)]:
        cv_aucs = cross_val_score(train_module.build_model(track), X_tr, y_tr,
                                  groups=g_tr, cv=cv, scoring="roc_auc")
        r[f"{track}_cv_auc"] = round(float(cv_aucs.mean()), 4)
        r[f"{track}_cv_std"] = round(float(cv_aucs.std()), 4)
        m = train_module.build_model(track)
        m.fit(X_tr, y_tr)
        r[f"{track}_valid_auc"] = round(float(roc_auc_score(y_va, m.predict_proba(X_va)[:, 1])), 4)
        r[f"{track}_test_auc"] = round(float(roc_auc_score(y_te, m.predict_proba(X_te)[:, 1])), 4)
    r["mean_cv_auc"] = round((r["prod_cv_auc"] + r["eco_cv_auc"]) / 2, 4)
    r["mean_valid_auc"] = round((r["prod_valid_auc"] + r["eco_valid_auc"]) / 2, 4)
    r["mean_test_auc"] = round((r["prod_test_auc"] + r["eco_test_auc"]) / 2, 4)
    return r


if __name__ == "__main__":
    import train
    print(json.dumps(evaluate(train), indent=2, ensure_ascii=False))
