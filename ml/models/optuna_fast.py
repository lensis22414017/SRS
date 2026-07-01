"""zzv0.3 R5 快速版: Optuna贝叶斯调参, 目标=valid AUC(单次拟合, 比5折CV快10倍)。
best参数最终用GroupKFold确认0泄漏CV。"""
import os, sys, json, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.metrics import roc_auc_score
import optuna

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")
HM = ["Cd_mgkg","Pb_mgkg","As_mgkg","Cr_mgkg","Hg_mgkg","Cu_mgkg","Zn_mgkg","Ni_mgkg"]
PHYS = ["SoilpH","OC_pct","CEC_cmolkg","Sand_pct","Silt_pct","Clay_pct","SoilBD_gcm3","Elevation_m","MAP_mm","EC_mScm","TN_gkg"]
GEE = ["gee_ndvi","gee_precip_annual_mm","gee_temp_mean_c","gee_elevation_m","gee_slope_deg","gee_aspect_deg","gee_soil_pH","gee_soc_g_kg","gee_cec_cmol_kg","gee_clay_pct","gee_sand_pct","gee_silt_pct","gee_bulk_density_g_cm3","gee_nitrogen_g_kg"]
BG = {"Cd_mgkg":0.6,"Pb_mgkg":500,"As_mgkg":25,"Cr_mgkg":250,"Hg_mgkg":1.0,"Cu_mgkg":100,"Zn_mgkg":300,"Ni_mgkg":100}

def engineer(X):
    df = X.copy()
    for c in HM:
        if c in df.columns: df[f"log_{c}"] = np.log1p(df[c].clip(lower=0))
    if "SoilpH" in df.columns:
        for c in HM:
            if c in df.columns: df[f"pH_x_{c}"] = df["SoilpH"]*df[c]
    pi_cols=[]
    for c in HM:
        if c in df.columns:
            df[f"PI_{c}"] = df[c]/BG[c]; pi_cols.append(f"PI_{c}")
    if pi_cols:
        pi_df=df[pi_cols]; df["PI_nemerow"]=np.sqrt((pi_df.max(axis=1)**2+pi_df.mean(axis=1)**2)/2)
    return df

base_cols = HM+PHYS+GEE
X_tr = engineer(pd.read_csv(os.path.join(SPLIT_DIR,"train_X_barrier.csv"))[base_cols])
X_va = engineer(pd.read_csv(os.path.join(SPLIT_DIR,"valid_X_barrier.csv"))[base_cols])
X_te = engineer(pd.read_csv(os.path.join(SPLIT_DIR,"test_X_barrier.csv"))[base_cols])
cols = list(X_tr.columns)
ye_tr = pd.read_csv(os.path.join(SPLIT_DIR,"train_y_eco.csv")).iloc[:,0]
ye_va = pd.read_csv(os.path.join(SPLIT_DIR,"valid_y_eco.csv")).iloc[:,0]
ye_te = pd.read_csv(os.path.join(SPLIT_DIR,"test_y_eco.csv")).iloc[:,0]
g_tr = pd.read_csv(os.path.join(SPLIT_DIR,"train_groups.csv"))["id_DOI"].fillna("").astype(str)
print(f"特征: {len(cols)}列")

def objective(trial):
    p = {"learning_rate":trial.suggest_float("lr",0.01,0.2,log=True),
         "max_iter":trial.suggest_int("max_iter",200,800,step=100),
         "max_leaf_nodes":trial.suggest_int("max_leaf_nodes",15,95),
         "min_samples_leaf":trial.suggest_int("min_samples_leaf",10,80),
         "l2_regularization":trial.suggest_float("l2",0.0,5.0),
         "early_stopping":True,"validation_fraction":0.15,"n_iter_no_change":20,"random_state":42}
    m=HistGradientBoostingClassifier(**p); m.fit(X_tr,ye_tr)
    return roc_auc_score(ye_va,m.predict_proba(X_va)[:,1])

print("Optuna 20 trials (valid AUC快速搜索)...")
study=optuna.create_study(direction="maximize",sampler=optuna.samplers.TPESampler(seed=42))
study.optimize(objective,n_trials=20)
print(f"best valid AUC={study.best_value:.4f} params={study.best_params}")

# best参数最终GroupKFold确认
bp=study.best_params
best_full=dict(learning_rate=bp["lr"],max_iter=bp["max_iter"],max_leaf_nodes=bp["max_leaf_nodes"],
               min_samples_leaf=bp["min_samples_leaf"],l2_regularization=bp["l2"],
               early_stopping=True,validation_fraction=0.15,n_iter_no_change=20,random_state=42)
cv=cross_val_score(HistGradientBoostingClassifier(**best_full),X_tr,ye_tr,groups=g_tr,cv=GroupKFold(5),scoring="roc_auc")
m=HistGradientBoostingClassifier(**best_full); m.fit(X_tr,ye_tr)
va=roc_auc_score(ye_va,m.predict_proba(X_va)[:,1]); te=roc_auc_score(ye_te,m.predict_proba(X_te)[:,1])
print(f"\n✅ eco轨 Optuna best三集:")
print(f"  CV(0泄漏)={cv.mean():.4f}±{cv.std():.4f} valid={va:.4f} test={te:.4f}")
json.dump({"params":best_full,"feature_cols":cols,"cv_auc":round(float(cv.mean()),4),
           "valid_auc":round(float(va),4),"test_auc":round(float(te),4)},
          open(os.path.join(ROOT,"ml","autoresearch_dual_track","best_eco_optuna.json"),"w"),ensure_ascii=False,indent=2)
print("已保存 best_eco_optuna.json")
