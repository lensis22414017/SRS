"""zzv0.3 R7: 15组测试场地泛化验证。

对齐桥: 中文列名→英文 + GEE补采(按场地坐标) + 特征工程 + eco模型预测
输出: 每个场地的预测障碍概率/Top因子 + 整体泛化报告
"""
import os, sys, glob, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))

# 中文→英文列名映射(复用_generate_splits.py的HM_COLS/ORG_COLS_MAP逻辑)
COL_MAP = {
    "pH": "SoilpH", "有机质(g/kg)": "OC_pct",
    "镉(mg/kg)": "Cd_mgkg", "铅(mg/kg)": "Pb_mgkg", "砷(mg/kg)": "As_mgkg",
    "铬(mg/kg)": "Cr_mgkg", "铜(mg/kg)": "Cu_mgkg", "锌(mg/kg)": "Zn_mgkg",
    "汞(mg/kg)": "Hg_mgkg", "镍(mg/kg)": "Ni_mgkg",
    "多环芳烃总量(ng/g)": "Sum_PAH_ngg", "苯并芘(ng/g)": "BaP_ngg",
    "DDT类(ng/g)": "SumDDTs_ngg", "多氯联苯(ng/g)": "SumPCB_ngg",
    "有机氯农药(ng/g)": "SumOCP_ngg", "经度": "Longitude", "纬度": "Latitude",
}

HM = ["Cd_mgkg","Pb_mgkg","As_mgkg","Cr_mgkg","Hg_mgkg","Cu_mgkg","Zn_mgkg","Ni_mgkg"]
PHYS = ["SoilpH","OC_pct"]
GEE = ["gee_ndvi","gee_precip_annual_mm","gee_temp_mean_c","gee_elevation_m","gee_slope_deg",
       "gee_aspect_deg","gee_soil_pH","gee_soc_g_kg","gee_cec_cmol_kg","gee_clay_pct",
       "gee_sand_pct","gee_silt_pct","gee_bulk_density_g_cm3","gee_nitrogen_g_kg"]
BG = {"Cd_mgkg":0.6,"Pb_mgkg":500,"As_mgkg":25,"Cr_mgkg":250,"Hg_mgkg":1.0,
      "Cu_mgkg":100,"Zn_mgkg":300,"Ni_mgkg":100}


def load_test_site(path):
    """读测试场地, 中文列名→英文。"""
    df = pd.read_excel(path)
    df = df.rename(columns=COL_MAP)
    return df


def enrich_gee(df):
    """按场地坐标补采GEE(每场地的平均坐标)。"""
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        return df
    lat = pd.to_numeric(df["Latitude"], errors="coerce").mean()
    lon = pd.to_numeric(df["Longitude"], errors="coerce").mean()
    if pd.isna(lat) or pd.isna(lon):
        return df
    try:
        import ee
        _gee_pid = os.environ.get("GEE_PROJECT_ID")
        try:
            if _gee_pid:
                ee.Initialize(project=_gee_pid)
        except Exception:
            pass
        sys.path.insert(0, os.path.join(ROOT, "ml", "covariates"))
        from gee_fetch import build_covariate_image
        pt = ee.Feature(ee.Geometry.Point([float(lon), float(lat)]))
        res = build_covariate_image().sampleRegions(
            collection=ee.FeatureCollection([pt]), scale=250).getInfo()
        if res and res.get("features"):
            props = res["features"][0]["properties"]
            for c in GEE:
                if c in props:
                    df[c] = props[c]
    except Exception as e:
        pass  # GEE失败则GEE列保持NaN
    return df


def engineer(X, feature_list):
    """特征工程(对齐训练时的 log/pH交互/Nemerow)。"""
    df = X.copy()
    for c in HM:
        if c in df.columns:
            df[f"log_{c}"] = np.log1p(pd.to_numeric(df[c], errors="coerce").clip(lower=0))
        if "SoilpH" in df.columns and c in df.columns:
            df[f"pH_x_{c}"] = pd.to_numeric(df["SoilpH"], errors="coerce") * pd.to_numeric(df[c], errors="coerce")
    pi_cols = []
    for c, bg in BG.items():
        if c in df.columns:
            df[f"PI_{c}"] = pd.to_numeric(df[c], errors="coerce") / bg
            pi_cols.append(f"PI_{c}")
    if pi_cols:
        pi_df = df[pi_cols]
        df["PI_nemerow"] = np.sqrt((pi_df.max(axis=1)**2 + pi_df.mean(axis=1)**2) / 2)
    # 对齐feature_list顺序, 缺失填NaN
    for c in feature_list:
        if c not in df.columns:
            df[c] = np.nan
    return df[feature_list]


def main():
    from rf_barrier import load_latest
    bundle = load_latest(track="eco")
    model = bundle["model"]
    feature_list = bundle["feature_list"]
    print(f"模型: {bundle['version']} ({len(feature_list)}特征)")
    print(f"eco CV AUC: {bundle['metrics'].get('cv_auc_mean')} test AUC: {bundle['metrics'].get('test_auc')}")
    print("=" * 70)

    files = sorted(glob.glob(os.path.join(ROOT, "data", "test_datasets", "*.xlsx")))
    results = []
    for f in files:
        name = os.path.basename(f).replace(".xlsx", "")
        df = load_test_site(f)
        n = len(df)
        has_hm = any(c in df.columns for c in HM)
        df = enrich_gee(df)
        X = engineer(df, feature_list)
        proba = model.predict_proba(X)[:, 1]
        mean_proba = float(proba.mean())
        n_high = int((proba > 0.5).sum())
        results.append({"场地": name, "采样点": n, "类型": "HM" if has_hm else "OP",
                        "生态障碍概率均值": round(mean_proba, 4),
                        "高障碍点数(>0.5)": n_high,
                        "高障碍占比": f"{n_high/n*100:.1f}%"})

    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))
    print("\n" + "=" * 70)
    print(f"15组场地泛化验证完成:")
    print(f"  障碍概率均值范围: {res_df['生态障碍概率均值'].min():.3f} ~ {res_df['生态障碍概率均值'].max():.3f}")
    hm_sites = res_df[res_df["类型"] == "HM"]
    op_sites = res_df[res_df["类型"] == "OP"]
    print(f"  HM场地({len(hm_sites)}个)障碍概率均值: {hm_sites['生态障碍概率均值'].mean():.3f}")
    print(f"  OP场地({len(op_sites)}个)障碍概率均值: {op_sites['生态障碍概率均值'].mean():.3f}")
    print(f"  (HM场地应高于OP场地, 因eco标签含重金属超标判定)")

    res_df.to_csv(os.path.join(ROOT, "docs", "algorithms", "test_15sites_validation.csv"),
                  index=False, encoding="utf-8-sig")
    print(f"\n保存: docs/algorithms/test_15sites_validation.csv")


if __name__ == "__main__":
    main()
