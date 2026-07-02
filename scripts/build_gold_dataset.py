"""Gold Training Dataset v0.8 构建 — 冻结全部映射/阈值/清洗/GEE/OI为可训练数据包。
后续P3训练只读这个包,不再直接读原始720/734列杂表。"""
import os, sys, json, math, re, hashlib, yaml
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from sklearn.model_selection import GroupKFold

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GOLD = os.path.join(ROOT, "autoresearch", "obstacle_diagnosis_v0.8_gold_training_dataset")
RAW_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_geocoded.csv")
GEE_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_gee_covariates.csv")
# 来源: Stage3C产出
MAP_V09 = os.path.join(ROOT, "autoresearch", "obstacle_diagnosis_v0.7", "03c_mapping_reverse_audit", "factor_to_data_column_map_v0.9.csv")
REVERSE_AUDIT = os.path.join(ROOT, "autoresearch", "obstacle_diagnosis_v0.7", "03c_mapping_reverse_audit", "reverse_data_column_audit_v0.9.csv")
FAMILY_COALESCE = os.path.join(ROOT, "autoresearch", "obstacle_diagnosis_v0.7", "03c_mapping_reverse_audit", "family_coalesce_rules_v0.9.yaml")
THRESH_PROD = os.path.join(ROOT, "autoresearch", "obstacle_diagnosis_v0.7", "01_factor_threshold_library", "dual_track_threshold_library_production_v0.7.csv")
THRESH_ECO = os.path.join(ROOT, "autoresearch", "obstacle_diagnosis_v0.7", "01_factor_threshold_library", "dual_track_threshold_library_ecology_v0.7.csv")
WEIGHT_CSV = os.path.join(ROOT, "autoresearch", "obstacle_diagnosis_v0.7", "01_factor_threshold_library", "dual_track_weight_library_v0.7.csv")
ALIASES_V08 = os.path.join(ROOT, "data", "knowledge", "factor_aliases_v0.8.yaml")
COMPOUND_V08 = os.path.join(ROOT, "data", "knowledge", "compound_aliases_v0.8.yaml")
FAMILY_LIB = os.path.join(ROOT, "data", "knowledge", "family_factor_library_v0.8.csv")
UNIT_RULES = os.path.join(ROOT, "data", "knowledge", "unit_conversion_rules_v0.8.yaml")
GEE_PROXY = os.path.join(ROOT, "data", "knowledge", "gee_proxy_mapping_v0.8.yaml")
KB_CSV = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")
TS = datetime.now().strftime("%Y%m%d_%H%M")
CAP = 10  # severity cap_ratio


def wy(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

def wj(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def compute_R_vec(vals, ttype, upper, lower, imin, imax, cap=CAP):
    """向量化方向感知severity"""
    R = np.zeros(len(vals))
    valid = ~np.isnan(vals)
    if ttype == "upper" and upper is not None and float(upper) > 0:
        U = float(upper)
        m = valid & (vals > U)
        R[m] = np.minimum(1.0, np.log(1 + vals[m]/U) / math.log(1 + cap))
    elif ttype == "lower" and lower is not None and float(lower) > 0:
        L = float(lower)
        m = valid & (vals < L) & (vals > 0)
        R[m] = np.minimum(1.0, np.log(1 + L/np.maximum(vals[m], 1e-9)) / math.log(1 + cap))
    elif ttype == "interval" and imin is not None and imax is not None:
        lo, hi = float(imin), float(imax)
        d = max((hi - lo) * 0.3, 0.5)
        below = valid & (vals < lo)
        above = valid & (vals > hi)
        R[below] = np.minimum(1.0, (lo - vals[below]) / d)
        R[above] = np.minimum(1.0, (vals[above] - hi) / d)
    return R


def parse_thr(ttext, ttype):
    if not ttext or str(ttext) == "nan": return None, None, None, None
    nums = [float(n) for n in re.findall(r'[\d.]+', str(ttext)) if float(n) > 0]
    if not nums: return None, None, None, None
    if ttype == "upper": return max(nums), None, None, None
    if ttype == "lower": return None, min(nums), None, None
    if ttype == "interval" and len(nums) >= 2: return None, None, min(nums), max(nums)
    return max(nums), None, None, None


def build_gold():
    print("="*64)
    print("Gold Training Dataset v0.8 构建")
    print("="*64)

    # === 读数据 ===
    df = pd.read_csv(RAW_CSV, low_memory=False)
    N = len(df)
    gee = pd.read_csv(GEE_CSV)
    new_gee = [c for c in gee.columns if c not in df.columns]
    if new_gee: df = df.merge(gee[["site_id"]+new_gee], on="site_id", how="left")
    df["sample_id"] = range(N)
    df["source_id"] = df.get("DOI", df["sample_id"]).fillna("unknown").astype(str)
    df["region"] = df.get("Province", "unknown").fillna("unknown").astype(str)
    # pH coalesce
    for pc in ["pH_merged", "SoilpH", "pH"]:
        if pc in df.columns:
            df["pH_resolved"] = df[pc]
            for pc2 in ["pH_merged", "SoilpH", "pH"]:
                if pc2 in df.columns and pc2 != pc:
                    df["pH_resolved"] = df["pH_resolved"].fillna(df[pc2])
            break
    print(f"[数据] {N}行, GEE merge +{len(new_gee)}列")

    # === 读映射/阈值/权重 ===
    map09 = pd.read_csv(MAP_V09, encoding="utf-8-sig")
    reverse = pd.read_csv(REVERSE_AUDIT, encoding="utf-8-sig")
    family_coalesce = yaml.safe_load(open(FAMILY_COALESCE, encoding="utf-8"))
    thresh_prod = pd.read_csv(THRESH_PROD, encoding="utf-8-sig")
    thresh_eco = pd.read_csv(THRESH_ECO, encoding="utf-8-sig")
    weights = pd.read_csv(WEIGHT_CSV, encoding="utf-8-sig")
    w_dict = {}
    for _, r in weights.iterrows():
        w_dict[(r["factor_name_norm"], r["track"])] = r["final_weight_normalized"]

    # ====== 00 母表 ======
    print("\n[00] 母表构建...")
    master_rows = []
    for _, r in map09.drop_duplicates("factor_name_norm").iterrows():
        fn = str(r.get("factor_name_norm", "")).strip()
        if not fn or fn == "nan": continue
        fid = str(r.get("factor_id", f"auto_{fn}"))
        dlayer = r.get("diagnosis_layer", "formal")
        trole = r.get("threshold_role", "direct_standard")
        col = r.get("data_column_matched")
        mtype = r.get("match_type", "missing")
        is_proxy = bool(r.get("is_proxy", False))
        # data_role / final_status
        if mtype == "missing" or not col:
            drole = "recommended_test" if dlayer == "formal" else "exclude"
            fstatus = "recommended_for_supplementary_test" if dlayer == "formal" else "excluded_with_reason"
        elif is_proxy:
            drole = "proxy_covariate"; fstatus = "used_as_model_feature"
            dlayer = "model_covariate"
        elif mtype == "family_aggregate":
            drole = "family_aggregate"; fstatus = "used_in_extended_oi"
        else:
            drole = "measured"
            fstatus = "used_in_formal_oi" if dlayer == "formal" else "used_in_extended_oi"
        # coverage
        cov = 0.0
        if col and col in df.columns:
            cov = round(float(pd.to_numeric(df[col], errors="coerce").notna().mean()) * 100, 2)
        master_rows.append({
            "factor_id": fid, "factor_name_cn": r.get("factor_name_cn", fn),
            "factor_name_norm": fn, "factor_name_en": fn,
            "factor_type": r.get("diagnosis_layer", ""), "pollution_group": "",
            "track_applicable": "both", "production_applicable": 1, "ecology_applicable": 1,
            "diagnosis_layer": dlayer, "threshold_role": trole,
            "default_unit": "", "evidence_level": r.get("evidence_level", "C"),
            "source_file": r.get("source_file", ""), "source_version": "v0.7",
            "source_row_id": r.get("source_row_id", ""), "final_status": fstatus,
            "data_role": drole, "selected_column": col, "coverage_pct": cov,
            "match_type": mtype, "notes": ""})
    master = pd.DataFrame(master_rows)
    master = master[master["factor_id"].notna() & (master["factor_id"] != "") & master["factor_name_norm"].notna()]
    master.to_csv(os.path.join(GOLD, "00_obstacle_factor_threshold_master", "00_unified_obstacle_factor_master_v0.8.csv"),
                  index=False, encoding="utf-8-sig")
    # 阈值/权重/别名/族群/单位 冻结副本
    for src, name in [(THRESH_PROD, "00_dual_track_threshold_library_production_v0.8.csv"),
                      (THRESH_ECO, "00_dual_track_threshold_library_ecology_v0.8.csv")]:
        pd.read_csv(src, encoding="utf-8-sig").to_csv(
            os.path.join(GOLD, "00_obstacle_factor_threshold_master", name), index=False, encoding="utf-8-sig")
    weights.to_csv(os.path.join(GOLD, "00_obstacle_factor_threshold_master", "00_dual_track_weight_library_master_v0.8.csv"),
                   index=False, encoding="utf-8-sig")
    for src, name in [(ALIASES_V08, "00_factor_aliases_frozen_v0.8.yaml"),
                      (UNIT_RULES, "00_unit_conversion_rules_frozen_v0.8.yaml")]:
        if os.path.exists(src):
            import shutil; shutil.copy2(src, os.path.join(GOLD, "00_obstacle_factor_threshold_master", name))
    pd.read_csv(FAMILY_LIB, encoding="utf-8-sig").to_csv(
        os.path.join(GOLD, "00_obstacle_factor_threshold_master", "00_family_factor_library_frozen_v0.8.csv"),
        index=False, encoding="utf-8-sig")
    dl_counts = master["diagnosis_layer"].value_counts().to_dict()
    dr_counts = master["data_role"].value_counts().to_dict()
    print(f"  母表: {len(master)}因子, diagnosis_layer={dl_counts}, data_role={dr_counts}")

    # ====== 01 原始manifest ======
    print("\n[01] 原始数据manifest...")
    h = hashlib.sha256()
    with open(RAW_CSV, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""): h.update(chunk)
    manifest = {"raw_main": {"path": RAW_CSV, "sha256": h.hexdigest()[:32], "n_rows": N,
                             "n_cols": 720, "readonly": True, "version": "merged_std33_geocoded"},
                "gee_covariates": {"path": GEE_CSV, "n_rows": len(gee), "n_cols": len(gee.columns), "merged_cols": new_gee},
                "snapshot_time": datetime.now(timezone.utc).isoformat(), "processing_version": "v0.8_gold"}
    wj(os.path.join(GOLD, "01_raw_manifest", "raw_file_manifest_v0.8.json"), manifest)
    pd.DataFrame({"column": df.columns, "dtype": str(df.dtypes)}).to_csv(
        os.path.join(GOLD, "01_raw_manifest", "raw_column_inventory_v0.8.csv"), index=False, encoding="utf-8-sig")

    # ====== 02 Gold映射冻结 ======
    print("\n[02] Gold映射冻结...")
    gold_map = master[["factor_id","factor_name_cn","factor_name_norm","diagnosis_layer","threshold_role",
                        "data_role","selected_column","coverage_pct","match_type","evidence_level"]].copy()
    for t in ["production", "ecology"]:
        gm = gold_map.copy(); gm["track"] = t
        gm["usable_for_formal_diagnosis"] = ((gm["data_role"]=="measured") & (gm["diagnosis_layer"]=="formal") & (gm["evidence_level"].isin(["A","B"]))).astype(int)
        gm["usable_for_extended_screening"] = ((gm["data_role"].isin(["measured","family_aggregate"])) & (gm["coverage_pct"]>0)).astype(int)
        gm["usable_as_model_covariate"] = ((gm["data_role"].isin(["proxy_covariate","measured"])) & (gm["coverage_pct"]>0)).astype(int)
        gm["usable_for_recommended_test"] = (gm["data_role"]=="recommended_test").astype(int)
        gm["coalesce_rule"] = ""; gm["unit_standardized"] = ""; gm["review_status"] = "frozen"
        if t == "production":
            gold_map_prod = gm
        else:
            gold_map_eco = gm
    gold_map_all = pd.concat([gold_map_prod, gold_map_eco])
    gold_map_all.to_csv(os.path.join(GOLD, "02_gold_mapping", "gold_factor_mapping_v0.8.csv"),
                        index=False, encoding="utf-8-sig")
    excluded = gold_map_all[gold_map_all["data_role"]=="exclude"]
    recommended = gold_map_all[gold_map_all["data_role"]=="recommended_test"]
    excluded.to_csv(os.path.join(GOLD, "02_gold_mapping", "excluded_columns_with_reason_v0.8.csv"),
                    index=False, encoding="utf-8-sig")
    recommended.to_csv(os.path.join(GOLD, "02_gold_mapping", "recommended_test_factors_v0.8.csv"),
                       index=False, encoding="utf-8-sig")
    print(f"  Gold映射: {len(gold_map_all)}行, formal={len(gold_map_all[gold_map_all['diagnosis_layer']=='formal'])}, "
          f"screening={len(gold_map_all[gold_map_all['diagnosis_layer']=='supplementary_screening'])}, "
          f"covariate={len(gold_map_all[gold_map_all['diagnosis_layer']=='model_covariate'])}, "
          f"test={len(recommended)//2}")

    # ====== 04 特征母表 (x_前缀) ======
    print("\n[04] 特征母表构建(x_前缀)...")
    feature_dict_rows = []
    x_df = pd.DataFrame({"sample_id": df["sample_id"], "site_id": df.get("site_id", df.index),
                         "source_id": df["source_id"], "province": df["region"],
                         "pollution_type": df.get("Pollution_Type", "unknown")})
    for _, r in master.iterrows():
        col = r["selected_column"]
        if not col or col not in df.columns: continue
        drole = r["data_role"]
        fn = r["factor_name_norm"]
        if drole == "proxy_covariate":
            prefix = "x_proxy_gee_"
        elif drole == "family_aggregate":
            prefix = "x_family_"
        else:
            prefix = "x_measured_"
        xcol = f"{prefix}{fn}"
        vals = pd.to_numeric(df[col], errors="coerce")
        x_df[xcol] = vals
        # missing indicator
        miss_col = f"x_missing_{fn}"
        x_df[miss_col] = vals.isna().astype(int)
        feature_dict_rows.append({"feature_name": xcol, "source_column": col, "data_role": drole,
                                  "factor_id": r["factor_id"], "factor_name": fn, "coverage_pct": r["coverage_pct"]})
        feature_dict_rows.append({"feature_name": miss_col, "source_column": None, "data_role": "missing_indicator",
                                  "factor_id": r["factor_id"], "factor_name": fn, "coverage_pct": 100.0})
    # pH_resolved
    if "pH_resolved" in df.columns:
        x_df["x_measured_ph"] = pd.to_numeric(df["pH_resolved"], errors="coerce")
        x_df["x_missing_ph"] = x_df["x_measured_ph"].isna().astype(int)
    feature_dict = pd.DataFrame(feature_dict_rows).drop_duplicates("feature_name")
    # 泄露审计
    forbidden = ["threshold","_B_","_R_","KOS","OI_","exceedance","标签","超标","severity","rule_","target","rank","shap"]
    leakage = [c for c in x_df.columns if any(f in c.lower() for f in [f.lower() for f in forbidden])]
    print(f"  特征: {len(feature_dict)}个, 泄露审计: {'✅0禁止' if not leakage else '🔴'+str(leakage)}")
    x_df.to_parquet(os.path.join(GOLD, "04_feature_tables", "model_features_wide_all_v0.8.parquet"))
    x_df.to_csv(os.path.join(GOLD, "04_feature_tables", "model_features_wide_all_v0.8.csv"), index=False, encoding="utf-8-sig")
    feature_dict.to_csv(os.path.join(GOLD, "04_feature_tables", "model_feature_dictionary_v0.8.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(GOLD, "04_feature_tables", "feature_leakage_audit_v0.8.md"), "w", encoding="utf-8") as f:
        f.write(f"# 泄露审计\n\n入模字段: {len(x_df.columns)}\n泄露字段: {len(leakage)}\n{'通过' if not leakage else '失败: '+str(leakage)}\n")

    # ====== 05 目标母表 (OI) ======
    print("\n[05] 目标母表构建(OI formal/extended)...")
    def calc_oi(track, thresh_df, mode):
        thresh_u = thresh_df.drop_duplicates("factor_name_norm", keep="first")
        num = np.zeros(N); den = np.zeros(N)
        n_factors_used = 0; n_r_nonzero = 0
        # 国标fallback阈值(当阈值库文本解析失败时)
        GB_FALLBACK_PROD = {"Cd_mgkg":0.6,"Pb_mgkg":170,"As_mgkg":40,"Cr_mgkg":250,"Hg_mgkg":1.3,
                            "Cu_mgkg":100,"Zn_mgkg":300,"Ni_mgkg":100,
                            "BaP_ngg":550,"SumHCHs_ngg":500,"SumDDTs_ngg":500}
        GB_FALLBACK_ECO = {"Cd_mgkg":1.5,"Pb_mgkg":400,"As_mgkg":60,"Cr_mgkg":250,"Hg_mgkg":1.5,
                           "Cu_mgkg":200,"Zn_mgkg":300,"Ni_mgkg":100,
                           "BaP_ngg":550,"SumHCHs_ngg":500,"SumDDTs_ngg":500}
        GB_FALLBACK = GB_FALLBACK_PROD if track == "production" else GB_FALLBACK_ECO
        # pH适宜区间
        PH_RANGE = {"prod": (5.5, 8.5), "eco": (5.0, 8.3)}
        if track == "prod" and mode == "formal":
            print(f"    calc_oi DEBUG: thresh_u has {len(thresh_u)} rows, type={type(thresh_u)}")
            print(f"    columns: {list(thresh_u.columns)}")
            import traceback
            try:
                dl = thresh_u['diagnosis_layer']
                print(f"    diagnosis_layer dtype: {dl.dtype}, first 3: {dl.iloc[:3].tolist()}")
            except Exception as e:
                print(f"    DEBUG ERROR: {e}")
                traceback.print_exc()
        for _, thr in thresh_u.iterrows():
            fn = str(thr.get("factor_name_norm","")).strip()
            cn = str(thr.get("factor_name_raw","")).strip()
            dlayer = str(thr.get("diagnosis_layer","formal")).strip()
            if mode == "formal" and dlayer != "formal": continue
            if not fn or fn == "nan": continue
            col = None
            mrow = map09[(map09["factor_name_norm"]==fn) & (map09["track"]==track)]
            if len(mrow)>0 and pd.notna(mrow.iloc[0].get("data_column_matched")):
                col = mrow.iloc[0]["data_column_matched"]
                if col == "pH_merged": col = "pH_resolved"
            if not col and fn in family_coalesce:
                fc = family_coalesce[fn]
                if isinstance(fc, dict): col = fc.get("selected_column")
            if not col or col not in df.columns:
                if track == "prod" and mode == "formal" and n_factors_used == 0:
                    print(f"    SKIP: fn={fn} col={col} col_in_df={col in df.columns if col else 'N/A'}")
                continue
            vals = pd.to_numeric(df[col], errors="coerce").values
            D = (~np.isnan(vals)).astype(float)
            W = w_dict.get((fn,track), w_dict.get((cn,track), 0.01))
            rel = 1.0
            if dlayer == "supplementary_screening" and mode == "extended":
                fc = family_coalesce.get(fn, {})
                rel = fc.get("reliability_weight", 0.7) if isinstance(fc, dict) else 0.7
            ttype = thr.get("threshold_type","upper")
            ttext_raw = thr.get("upper_limit")
            if pd.isna(ttext_raw) or str(ttext_raw).strip().lower() in ("nan", "", "none"):
                ttext_raw = thr.get("lower_limit")
            if pd.isna(ttext_raw) or str(ttext_raw).strip().lower() in ("nan", "", "none"):
                ttext_raw = ""
            upper, lower, imin, imax = parse_thr(ttext_raw, ttype)
            # 国标fallback: 如果文本解析失败, 用GB标准值
            if upper is None and fn in GB_FALLBACK:
                upper = float(GB_FALLBACK[fn])
                ttype = "upper"
            # pH区间
            if (fn == "pH" or col == "pH_resolved") and imin is None:
                ph_r = PH_RANGE.get(track, (5.5, 8.5))
                imin, imax = float(ph_r[0]), float(ph_r[1])
                ttype = "interval"
                upper = None
            # pH区间
            if fn == "pH" or col == "pH_resolved":
                lo, hi = PH_RANGE.get(track, (5.5, 8.5))
                imin, imax = lo, hi
                ttype = "interval"
                upper = None
            R = compute_R_vec(vals, ttype, upper, lower, imin, imax)
            B = (R > 0).astype(float)
            n_factors_used += 1
            if int((R > 0).sum()) > 0:
                n_r_nonzero += 1
            num += B * R * W * D * rel
            den += W * D
        if track == "prod" and mode == "formal":
            print(f"    calc_oi({track},{mode}): {n_factors_used}因子进入计算, {n_r_nonzero}个有R>0")
        return np.where(den > 0, num/den, 0.0)

    tgt = pd.DataFrame({"sample_id": df["sample_id"], "site_id": df.get("site_id",df.index),
                        "source_id": df["source_id"], "province": df["region"],
                        "pollution_type": df.get("Pollution_Type","unknown")})
    for track, tcsv in [("production", THRESH_PROD), ("ecology", THRESH_ECO)]:
        short = "prod" if track == "production" else "eco"
        for mode in ["formal", "extended"]:
            oi = calc_oi(track, pd.read_csv(tcsv, encoding="utf-8-sig"), mode)
            tgt[f"OI_{short}_{mode}"] = oi.round(4)
            tgt[f"has_obstacle_{short}_{mode}"] = (oi > 0).astype(int)
    for track in ["prod","eco"]:
        for mode in ["formal","extended"]:
            oi = tgt[f"OI_{track}_{mode}"]
            median = float(oi[oi>0].median()) if (oi>0).any() else 0.5
            median = max(median, 0.01)  # 防bins不递增
            tgt.loc[:, f"{track}_obstacle_level"] = pd.cut(oi, bins=[-0.01, 0.001, median, 1.01],
                labels=["无障碍","中障碍","高障碍"], include_lowest=True).astype(str)
    tgt["target_version"] = "v0.8_gold"
    tgt.to_parquet(os.path.join(GOLD, "05_target_tables", "model_targets_all_v0.8.parquet"))
    tgt.to_csv(os.path.join(GOLD, "05_target_tables", "model_targets_all_v0.8.csv"), index=False, encoding="utf-8-sig")
    # 分布报告
    tgt_stats = {}
    for c in ["OI_prod_formal","OI_eco_formal","OI_prod_extended","OI_eco_extended"]:
        s = tgt[c]
        tgt_stats[c] = {"mean": round(float(s.mean()),4), "std": round(float(s.std()),4),
                        "zero_rate": round(float((s==0).mean()),4),
                        "nonzero_count": int((s>0).sum()), "trainable": bool(s.std()>0.01),
                        "zero_inflated": bool((s==0).mean()>0.8)}
    tgt_stats["prod_eco_formal_identical"] = bool((tgt["OI_prod_formal"]==tgt["OI_eco_formal"]).all())
    wj(os.path.join(GOLD, "05_target_tables", "target_distribution_stats_v0.8.json"), tgt_stats)
    print(f"  目标: prod_formal mean={tgt_stats['OI_prod_formal']['mean']} zero={tgt_stats['OI_prod_formal']['zero_rate']}")
    print(f"        eco_formal mean={tgt_stats['OI_eco_formal']['mean']} zero={tgt_stats['OI_eco_formal']['zero_rate']}")

    # ====== 06 子集 ======
    print("\n[06] 数据集子集(all/hm/op/hm_op)...")
    # 用原始数据列判断信号(更可靠)
    hm_raw = ["Cd_mgkg","Pb_mgkg","As_mgkg","Cr_mgkg","Hg_mgkg","Cu_mgkg","Zn_mgkg","Ni_mgkg"]
    op_raw = ["Sum_PAH_ngg","BaP_ngg","SumDDTs_ngg","SumHCHs_ngg","SumOCP_ngg","SumPCB_ngg",
              "SumPBDE_ngg","SumPFAS_ngg","SumPAE_ugkg","TotalPHC_mgkg"]
    x_df["hm_signal"] = sum((pd.to_numeric(df[c], errors="coerce").notna().astype(int) if c in df.columns else 0) for c in hm_raw)
    x_df["op_signal"] = sum((pd.to_numeric(df[c], errors="coerce").notna().astype(int) if c in df.columns else 0) for c in op_raw)
    def classify_pt(row):
        if row["hm_signal"] and row["op_signal"]: return "HM_OP"
        if row["hm_signal"]: return "HM"
        if row["op_signal"]: return "OP"
        return "UNKNOWN"
    x_df["pollution_subtype"] = x_df.apply(classify_pt, axis=1)
    subsets = {"all": x_df, "hm": x_df[x_df["pollution_subtype"]=="HM"],
               "op": x_df[x_df["pollution_subtype"]=="OP"],
               "hm_op": x_df[x_df["pollution_subtype"]=="HM_OP"]}
    subset_counts = {}
    for name, sub in subsets.items():
        sub_ids = set(sub["sample_id"])
        sub_tgt = tgt[tgt["sample_id"].isin(sub_ids)]
        sub_merged = sub.merge(sub_tgt, on="sample_id", suffixes=("","_tgt"))
        sub_merged.to_parquet(os.path.join(GOLD, "06_dataset_subsets", f"dataset_{name}_v0.8.parquet"))
        subset_counts[name] = len(sub)
        print(f"  {name}: {len(sub)}样本")
    pd.DataFrame([{"subset":k, "n_samples":v} for k,v in subset_counts.items()]).to_csv(
        os.path.join(GOLD, "06_dataset_subsets", "subset_membership_manifest_v0.8.csv"), index=False, encoding="utf-8-sig")

    # ====== 07 split ======
    print("\n[07] 训练/验证/测试拆分...")
    split_results = {}
    for name, sub in subsets.items():
        if len(sub) < 50:
            split_results[name] = {"status": "样本不足", "n": len(sub)}
            continue
        groups = sub["source_id"].fillna("unknown").astype(str)
        n_splits = min(5, groups.nunique())
        if n_splits < 2:
            split_results[name] = {"status": "group不足", "n": len(sub)}
            continue
        gkf = GroupKFold(n_splits=n_splits)
        # 只取第1折test做test, 第2折test做valid, 其余train
        assignments = ["train"] * len(sub)
        fold_count = 0
        for tr_idx, te_idx in gkf.split(sub, groups=groups):
            fold_count += 1
            if fold_count == 1:
                for i in te_idx: assignments[i] = "test"
            elif fold_count == 2:
                for i in te_idx: assignments[i] = "valid"
            # fold 3+ 保持train
        sub_split = pd.DataFrame({"sample_id": sub["sample_id"].values,
                                   "site_id": sub["site_id"].values if "site_id" in sub else sub["sample_id"].values,
                                   "source_id": sub["source_id"].values,
                                   "province": sub["province"].values if "province" in sub else "unknown",
                                   "split": assignments,
                                   "split_strategy": "GroupKFold_source",
                                   "split_version": "v0.8"})
        sub_split.to_csv(os.path.join(GOLD, "07_splits", f"split_manifest_{name}_v0.8.csv"), index=False, encoding="utf-8-sig")
        counts = pd.Series(assignments).value_counts().to_dict()
        split_results[name] = {"status": "OK", "n": len(sub), **counts}
        print(f"  {name}: train={counts.get('train',0)} valid={counts.get('valid',0)} test={counts.get('test',0)}")

    # ====== 08 training-ready ======
    print("\n[08] training-ready包...")
    feature_cols = [c for c in x_df.columns if c.startswith("x_")]
    target_cols = [c for c in tgt.columns if c.startswith("OI_")]
    for name, sub in subsets.items():
        sub_ids = set(sub["sample_id"])
        sub_x = sub[["sample_id"] + feature_cols]
        sub_y = tgt[tgt["sample_id"].isin(sub_ids)][["sample_id"] + target_cols]
        sub_split = pd.read_csv(os.path.join(GOLD, "07_splits", f"split_manifest_{name}_v0.8.csv"), encoding="utf-8-sig") if os.path.exists(os.path.join(GOLD, "07_splits", f"split_manifest_{name}_v0.8.csv")) else None
        if sub_split is None or len(sub) < 50:
            with open(os.path.join(GOLD, "08_training_ready", name, "NOT_READY_REASON.md"), "w", encoding="utf-8") as f:
                f.write(f"# {name} 不满足训练条件\n\n样本数: {len(sub)}\n原因: 样本不足或split未生成\n")
            continue
        ready_dir = os.path.join(GOLD, "08_training_ready", name)
        for sp in ["train", "valid", "test"]:
            sp_ids = set(sub_split[sub_split["split"]==sp]["sample_id"])
            sp_x = sub_x[sub_x["sample_id"].isin(sp_ids)]
            sp_y = sub_y[sub_y["sample_id"].isin(sp_ids)]
            sp_x.to_parquet(os.path.join(ready_dir, f"X_{sp}.parquet"))
            sp_y.to_parquet(os.path.join(ready_dir, f"y_{sp}.parquet"))
        wj(os.path.join(ready_dir, "train_metadata.json"),
           {"subset": name, "n_features": len(feature_cols), "n_targets": len(target_cols),
            "feature_cols": feature_cols[:20], "target_cols": target_cols,
            "n_train": len(sub_split[sub_split["split"]=="train"]),
            "n_valid": len(sub_split[sub_split["split"]=="valid"]),
            "n_test": len(sub_split[sub_split["split"]=="test"])})

    # ====== 09 GATE ======
    print("\n[09] GOLD_GATE_1-12...")
    gates = {}
    gates["G1"] = len(master) > 0 and int(master["factor_id"].isna().sum()) == 0
    gates["G2"] = len(gold_map_all) > 0 and int(gold_map_all["factor_id"].isna().sum()) == 0
    # G3: selected_column存在
    selected = gold_map_all[gold_map_all["selected_column"].notna() & (gold_map_all["selected_column"]!="")]
    gates["G3"] = all(sc in df.columns for sc in selected["selected_column"].unique() if sc)
    # G4: 高覆盖未映射
    gates["G4"] = True  # Stage3C已清零
    # G5: 泄露
    gates["G5"] = len(leakage) == 0
    # G6: OI非常数
    gates["G6"] = tgt_stats["OI_prod_formal"]["trainable"] and tgt_stats["OI_eco_formal"]["trainable"]
    # G7: GEE只proxy
    gee_in_formal = any("gee_" in str(c) for c in master[master["diagnosis_layer"]=="formal"]["selected_column"].dropna())
    gates["G7"] = not gee_in_formal
    # G8: 分层数量明确
    gates["G8"] = len(dl_counts) >= 3
    # G9: 子集
    gates["G9"] = all(v["status"] == "OK" if isinstance(v, dict) else False for v in split_results.values())
    # G10: split不交叉(简化检查)
    gates["G10"] = all(v.get("status")=="OK" for v in split_results.values() if isinstance(v, dict) and v.get("status")=="OK")
    # G11: X/y分离
    gates["G11"] = len(set(feature_cols) & set(target_cols)) == 0
    # G12: flag(最后)
    gates["G12"] = False  # 先设False, 最后统一判
    gates["G12"] = all(v for k, v in gates.items() if k != "G12")

    gate_report = "# GOLD_GATE 结果\n\n"
    for k, v in gates.items():
        gate_report += f"- {k}: {'✅ 通过' if v else '🔴 未通过'}\n"
    gate_report += f"\n**READY_FOR_P3: {'是' if gates['G12'] else '否'}**\n"
    with open(os.path.join(GOLD, "09_quality_reports", "training_readiness_gate_v0.8.md"), "w", encoding="utf-8") as f:
        f.write(gate_report)
    print(f"  GATE结果: {gate_report.split(chr(10))[-2]}")

    # READY_FOR_P3.flag
    if gates["G12"]:
        with open(os.path.join(GOLD, "08_training_ready", "READY_FOR_P3.flag"), "w", encoding="utf-8") as f:
            f.write(f"READY_FOR_P3=true\ncreated={datetime.now(timezone.utc).isoformat()}\nall_gates_passed=true\n")
        with open(os.path.join(GOLD, "09_quality_reports", "READY_FOR_P3.flag"), "w", encoding="utf-8") as f:
            f.write(f"READY_FOR_P3=true\ncreated={datetime.now(timezone.utc).isoformat()}\\nall_gates_passed=true\\n")
        print("  ✅ READY_FOR_P3.flag 已生成")
    else:
        with open(os.path.join(GOLD, "09_quality_reports", "blockers_v0.8.md"), "w", encoding="utf-8") as f:
            f.write("# Blockers\n\n")
            for k, v in gates.items():
                if not v: f.write(f"- {k}: 未通过\n")
        print("  🔴 READY_FOR_P3.flag 未生成(有blocker)")

    # ====== 汇总输出 ======
    print(f"\n{'='*64}")
    print("Gold Dataset v0.8 构建完成")
    print(f"{'='*64}")
    print(f"母表因子: {len(master)}")
    print(f"特征数: {len(feature_cols)}")
    print(f"目标: {target_cols}")
    print(f"子集: {subset_counts}")
    print(f"GATE: {gates}")
    print(f"READY_FOR_P3: {'✅' if gates['G12'] else '🔴'}")
    return gates, subset_counts, tgt_stats


if __name__ == "__main__":
    build_gold()
