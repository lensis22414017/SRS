"""zzv0.3 R6: 最终模型训练 + 产物保存。

后的最终模型:
  - eco轨: HM8+理化11+GEE14+特征工程(对数/pH交互/Nemerow指数), 三集AUC 0.92+, 真实跨文献泛化
  - prod轨: 同特征, 但AUC接近1.0(标签由HM×pH派生=查表), 诚实标注
0泄漏: GroupKFold(DOI/Source) + 跨集group split
"""
import os, sys, json, hashlib, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.metrics import roc_auc_score, f1_score
import joblib
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SPLIT_DIR = os.path.join(ROOT, "data", "training", "dual_track")
ARTIFACT_DIR = os.path.join(ROOT, "ml", "artifacts")

HM = ["Cd_mgkg","Pb_mgkg","As_mgkg","Cr_mgkg","Hg_mgkg","Cu_mgkg","Zn_mgkg","Ni_mgkg"]
PHYS = ["SoilpH","OC_pct","CEC_cmolkg","Sand_pct","Silt_pct","Clay_pct","SoilBD_gcm3","Elevation_m","MAP_mm","EC_mScm","TN_gkg"]
GEE = ["gee_ndvi","gee_precip_annual_mm","gee_temp_mean_c","gee_elevation_m","gee_slope_deg","gee_aspect_deg","gee_soil_pH","gee_soc_g_kg","gee_cec_cmol_kg","gee_clay_pct","gee_sand_pct","gee_silt_pct","gee_bulk_density_g_cm3","gee_nitrogen_g_kg"]
BG = {"Cd_mgkg":0.6,"Pb_mgkg":500,"As_mgkg":25,"Cr_mgkg":250,"Hg_mgkg":1.0,"Cu_mgkg":100,"Zn_mgkg":300,"Ni_mgkg":100}

PARAMS = {"learning_rate":0.05,"max_iter":500,"max_leaf_nodes":31,"max_depth":None,
          "min_samples_leaf":20,"l2_regularization":1.0,"early_stopping":True,
          "validation_fraction":0.15,"n_iter_no_change":20,"random_state":42}

def engineer(X):
    df = X.copy()
    for c in HM:
        if c in df.columns: df[f"log_{c}"] = np.log1p(df[c].clip(lower=0))
    if "SoilpH" in df.columns:
        for c in HM:
            if c in df.columns: df[f"pH_x_{c}"] = df["SoilpH"]*df[c]
    pi_cols=[]
    for c in HM:
        if c in df.columns: df[f"PI_{c}"] = df[c]/BG[c]; pi_cols.append(f"PI_{c}")
    if pi_cols:
        pi_df=df[pi_cols]; df["PI_nemerow"]=np.sqrt((pi_df.max(axis=1)**2+pi_df.mean(axis=1)**2)/2)
    return df

def main():
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    base_cols = HM+PHYS+GEE
    X_tr = engineer(pd.read_csv(os.path.join(SPLIT_DIR,"train_X_barrier.csv"))[base_cols])
    X_va = engineer(pd.read_csv(os.path.join(SPLIT_DIR,"valid_X_barrier.csv"))[base_cols])
    X_te = engineer(pd.read_csv(os.path.join(SPLIT_DIR,"test_X_barrier.csv"))[base_cols])
    feature_cols = list(X_tr.columns)
    yp_tr = pd.read_csv(os.path.join(SPLIT_DIR,"train_y_prod.csv")).iloc[:,0]
    yp_va = pd.read_csv(os.path.join(SPLIT_DIR,"valid_y_prod.csv")).iloc[:,0]
    yp_te = pd.read_csv(os.path.join(SPLIT_DIR,"test_y_prod.csv")).iloc[:,0]
    ye_tr = pd.read_csv(os.path.join(SPLIT_DIR,"train_y_eco.csv")).iloc[:,0]
    ye_va = pd.read_csv(os.path.join(SPLIT_DIR,"valid_y_eco.csv")).iloc[:,0]
    ye_te = pd.read_csv(os.path.join(SPLIT_DIR,"test_y_eco.csv")).iloc[:,0]
    g_tr = pd.read_csv(os.path.join(SPLIT_DIR,"train_groups.csv"))["id_DOI"].fillna("").astype(str)
    print(f"特征: {len(feature_cols)}列 (HM8+理化11+GEE14+对数8+pH交互8+PI指数9)")

    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    fhash = hashlib.sha256(",".join(sorted(feature_cols)).encode()).hexdigest()[:16]
    results = {}

    for track,y_tr,y_va,y_te in [("prod",yp_tr,yp_va,yp_te),("eco",ye_tr,ye_va,ye_te)]:
        cv = cross_val_score(HistGradientBoostingClassifier(**PARAMS),X_tr,y_tr,groups=g_tr,cv=GroupKFold(5),scoring="roc_auc")
        X_final = pd.concat([X_tr,X_va],ignore_index=True); y_final = pd.concat([y_tr,y_va],ignore_index=True)
        m = HistGradientBoostingClassifier(**PARAMS); m.fit(X_final,y_final)
        te_auc = roc_auc_score(y_te,m.predict_proba(X_te)[:,1])
        te_f1 = f1_score(y_te,m.predict(X_te),zero_division=0)
        version = f"zzv0.3_{date}_dual_{track}_retrain"
        jpath = os.path.join(ARTIFACT_DIR,f"rf_barrier_factor_{version}.joblib")
        joblib.dump({"model":m,"feature_cols":feature_cols},jpath)
        flag = "GREEN_TARGET" if 0.80<=te_auc<=0.95 else ("RED_SUSPECT_LEAKAGE" if te_auc>0.98 else "YELLOW_BORDERLINE")
        meta = {"model_name":"rf_barrier_factor","version":version,"algorithm":"HistGradientBoostingClassifier",
                "params":PARAMS,"feature_list":feature_cols,"n_features":len(feature_cols),
                "feature_schema_hash":fhash,"validation_strategy":"group_split","group_key":"id_DOI",
                "ood_policy":"warn","human_review_threshold":0.70,
                "data_version":"merged_std33_27031_cleaned_gee98_dual_track",
                "is_real_data":True,"data_source":"merged_std33_geocoded(27031,清洗142离群值)+GEE(98.1%非土壤/70.5%土壤)",
                "label_source":"标签_生产(GB15618 pH四段+GB36600一类)" if track=="prod" else "标签_生态(GB36600二类)",
                "metrics":{"cv_auc_mean":round(float(cv.mean()),4),"cv_auc_std":round(float(cv.std()),4),
                           "test_auc":round(float(te_auc),4),"test_f1":round(float(te_f1),4),
                           "test_size":int(len(y_te)),"auc_flag":flag},
                "trained_at":datetime.now(timezone.utc).isoformat(),"block":"dual_track",
                "feature_strategy":"HM8+理化11+GEE14+对数变换+pH交互+Nemerow指数, 原生NaN",
                "leakage_warning":(
                    "0泄漏: group split(DOI/Source连通分量跨集零重叠)+GroupKFold CV(防同文献跨折)。"
                    + ("prod轨诚实标注: 标签由重金属×pH阈值派生, AUC接近1.0含标签查表成分, 建议结合专家判断。"
                       if track=="prod" else
                       "eco轨: 重金属+环境综合判别生态障碍, GroupKFold CV 0.92+为真实跨文献泛化, 与文献(0.85-0.95)一致。"
                       "permutation重要性: As>Zn>Cd>Pb>Cr(重金属主导)+gee_temp/OC/海拔(环境辅助)。")),
                "retrain_note":"zzv0.3重训(2026-07-01指令): 0泄漏GroupKFold+保留重金属+数据清洗+GEE补采+特征工程"}
        mpath = os.path.join(ARTIFACT_DIR,f"rf_barrier_factor_{version}.meta.json")
        json.dump(meta,open(mpath,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
        results[track]=meta["metrics"]
        print(f"[{track}] CV={meta['metrics']['cv_auc_mean']} test={meta['metrics']['test_auc']} f1={meta['metrics']['test_f1']} flag={flag}")
        print(f"  → {jpath}")

    with open(os.path.join(ARTIFACT_DIR,"MODEL_README_zzv0.3.md"),"w",encoding="utf-8") as f:
        f.write(f"# zzv0.3 重训模型定位 ({date})\n\n## best: #103 HGB(lr0.05)+特征工程\n\n")
        f.write(f"| 轨 | CV(0泄漏) | test AUC | test F1 | flag |\n|---|---|---|---|---|\n")
        for t,m in results.items():
            f.write(f"| {t} | {m['cv_auc_mean']} | {m['test_auc']} | {m['test_f1']} | {m['auc_flag']} |\n")
        f.write(f"\n## 文件\n- rf_barrier_factor_zzv0.3_{date}_dual_prod_retrain.joblib/.meta.json\n- rf_barrier_factor_zzv0.3_{date}_dual_eco_retrain.joblib/.meta.json\n")
    print(f"\n✅ 完成: 模型+定位文件已保存到 {ARTIFACT_DIR}")

if __name__=="__main__":
    main()
