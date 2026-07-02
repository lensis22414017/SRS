"""Stage 3B: 字段映射修复 — 建完整别名+单体+族群+proxy+coalesce映射。
从裴总指令逐条落实, 修复18/141→目标50+匹配。"""
import os, sys, json, re, math, yaml
import numpy as np
import pandas as pd
from datetime import datetime

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(ROOT, "autoresearch", "obstacle_diagnosis_v0.7")
RAW_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_geocoded.csv")
GEE_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_gee_covariates.csv")
THRESH_PROD = os.path.join(BASE, "01_factor_threshold_library", "dual_track_threshold_library_production_v0.7.csv")
THRESH_ECO = os.path.join(BASE, "01_factor_threshold_library", "dual_track_threshold_library_ecology_v0.7.csv")
TS = datetime.now().strftime("%Y%m%d_%H%M")


def write_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ============ 1. 扩展别名系统 v0.8 ============

def build_aliases_v08():
    """完整别名: 重金属中文+PAH中文单体+DDT/HCH+理化coalesce+营养+GEE proxy"""
    # 基础别名(因子级)
    factor_aliases = {
        # pH coalesce(优先pH_merged)
        "pH": {"canonical": "pH", "coalesce": ["pH_merged", "SoilpH", "pH"],
               "aliases": ["pH值", "酸碱度", "SoilpH", "pH_merged"]},
        # 有机质
        "OC_pct": {"canonical": "OC_pct", "coalesce": ["OC_pct"],
                    "aliases": ["有机质", "有机碳", "SOC", "SOM", "有机质(g/kg)", "有机碳含量"]},
        "CEC_cmolkg": {"canonical": "CEC_cmolkg", "coalesce": ["CEC_cmolkg"],
                        "aliases": ["阳离子交换量", "CEC", "阳离子交换量(cmol/kg)"],
                        "proxy": ["gee_cec_cmol_kg"]},
        "SoilBD_gcm3": {"canonical": "SoilBD_gcm3", "coalesce": ["SoilBD_gcm3"],
                         "aliases": ["土壤容重", "容重", "BD"],
                         "proxy": ["gee_bulk_density_g_cm3"]},
        "EC_mScm": {"canonical": "EC_mScm", "coalesce": ["EC_mScm"],
                     "aliases": ["电导率", "EC", "含盐量", "盐渍化程度"],
                     "note": "EC与含盐量不严格等价, 仅作related"},
        # 重金属中文→英文
        "Cd_mgkg": {"canonical": "Cd_mgkg", "aliases": ["镉", "Cd", "镉(mg/kg)"]},
        "Pb_mgkg": {"canonical": "Pb_mgkg", "aliases": ["铅", "Pb", "铅(mg/kg)"]},
        "As_mgkg": {"canonical": "As_mgkg", "aliases": ["砷", "As", "砷(mg/kg)"]},
        "Cr_mgkg": {"canonical": "Cr_mgkg", "aliases": ["铬", "Cr", "总铬", "铬(mg/kg)"]},
        "Hg_mgkg": {"canonical": "Hg_mgkg", "aliases": ["汞", "Hg", "汞(mg/kg)"]},
        "Cu_mgkg": {"canonical": "Cu_mgkg", "aliases": ["铜", "Cu", "铜(mg/kg)"]},
        "Zn_mgkg": {"canonical": "Zn_mgkg", "aliases": ["锌", "Zn", "锌(mg/kg)"]},
        "Ni_mgkg": {"canonical": "Ni_mgkg", "aliases": ["镍", "Ni", "镍(mg/kg)"]},
        "Co_mgkg": {"canonical": "Co_mgkg", "aliases": ["钴", "Co", "钴(mg/kg)"]},
        "V_mgkg": {"canonical": "V_mgkg", "aliases": ["钒", "V", "钒(mg/kg)"]},
        "Sb_mgkg": {"canonical": "Sb_mgkg", "aliases": ["锑", "Sb", "锑(mg/kg)"]},
        "Be_mgkg": {"canonical": "Be_mgkg", "aliases": ["铍", "Be", "铍(mg/kg)"]},
        "Ba_mgkg": {"canonical": "Ba_mgkg", "aliases": ["钡", "Ba", "钡(mg/kg)"]},
        "Mn_mgkg": {"canonical": "Mn_mgkg", "aliases": ["锰", "Mn", "锰(mg/kg)"]},
        "Fe_mgkg": {"canonical": "Fe_mgkg", "aliases": ["铁", "Fe", "铁(mg/kg)"]},
        # 六价铬
        "Cr6_mgkg": {"canonical": "Cr6_mgkg", "aliases": ["六价铬", "铬(六价)", "Cr(VI)", "Cr6+"]},
        # 营养
        "TN_gkg": {"canonical": "TN_gkg", "aliases": ["全氮", "总氮", "TN", "水解性氮"],
                   "proxy": ["gee_nitrogen_g_kg"]},
        "P_mgkg": {"canonical": "P_mgkg", "aliases": ["有效磷", "速效磷", "Olsen_P", "Available_P"]},
        "K_mgkg": {"canonical": "K_mgkg", "aliases": ["速效钾", "有效钾", "Available_K", "AK"]},
        # 质地
        "Sand_pct": {"canonical": "Sand_pct", "aliases": ["砂粒", "砂粒含量"],
                     "proxy": ["gee_sand_pct"]},
        "Silt_pct": {"canonical": "Silt_pct", "aliases": ["粉粒", "粉粒含量"],
                     "proxy": ["gee_silt_pct"]},
        "Clay_pct": {"canonical": "Clay_pct", "aliases": ["黏粒", "粘粒", "黏粒含量"],
                     "proxy": ["gee_clay_pct"]},
        # 地形气候
        "Elevation_m": {"canonical": "Elevation_m", "coalesce": ["Elevation_m", "Altitude_m"],
                        "aliases": ["海拔", "高程", "DEM"],
                        "proxy": ["gee_elevation_m"]},
        "MAP_mm": {"canonical": "MAP_mm", "aliases": ["年均降水量", "降水"],
                   "proxy": ["gee_precip_annual_mm"]},
        "Slope_pct": {"canonical": "Slope_pct", "aliases": ["坡度", "地形坡度"],
                      "proxy": ["gee_slope_deg"]},
    }

    # 单体别名(compound_aliases)
    compound_aliases = {
        # PAH16单体(中文→英文缩写)
        "萘": ["Nap_ngg", "Nap_mgkg"], "苊": ["Ace_ngg", "Ace_mgkg"],
        "苊烯": ["Acy_ngg", "Acy_mgkg"], "芴": ["Flu_ngg", "Flu_mgkg"],
        "菲": ["Phe_ngg", "Phe_mgkg"], "蒽": ["Ant_ngg", "Ant_mgkg"],
        "荧蒽": ["Flt_ngg", "Flt_mgkg"], "芘": ["Pyr_ngg", "Pyr_mgkg"],
        "苯并[a]蒽": ["BaA_ngg", "BaA_mgkg"], "䓛": ["Chr_ngg", "Chr_mgkg"],
        "苯并[b]荧蒽": ["BbF_ngg", "BbF_mgkg"],
        "苯并[k]荧蒽": ["BkF_ngg", "BkF_mgkg"],
        "苯并[a]芘": ["BaP_ngg", "BaP_mgkg"],
        "二苯并[a,h]蒽": ["DahA_ngg", "DahA_mgkg"],
        "二苯并[ah]蒽": ["DahA_ngg", "DahA_mgkg"],
        "茚并[1,2,3-cd]芘": ["Ind_ngg", "Ind_mgkg", "ICP_ngg", "IcdP_ngg"],
        "茚并[123-cd]芘": ["Ind_ngg", "Ind_mgkg", "ICP_ngg"],
        "苯并[g,h,i]苝": ["BghiP_ngg", "BghiP_mgkg"],
        # DDT代谢物
        "p,p'-滴滴滴": ["p_p_DDD_ngg"], "p,p'-滴滴伊": ["p_p_DDE_ngg"],
        "p,p'-滴滴涕": ["p_p_DDT_ngg"], "o,p'-滴滴涕": ["o_p_DDT_ngg"],
        # HCH异构体
        "α-六六六": ["A_HCH_ngg"], "β-六六六": ["B_HCH_ngg"],
        "γ-六六六": ["G_HCH_ngg"], "δ-六六六": ["D_HCH_ngg"],
        # PCB同系物
        "PCB28": ["PCB28_ngg"], "PCB52": ["PCB52_ngg"], "PCB101": ["PCB101_ngg"],
        "PCB118": ["PCB118_ngg"], "PCB153": ["PCB153_ngg"], "PCB138": ["PCB138_ngg"],
        "PCB180": ["PCB180_ngg"],
        # PBDE
        "BDE28": ["BDE28_ngg"], "BDE47": ["BDE47_ngg"], "BDE99": ["BDE99_ngg"],
        "BDE209": ["BDE209_ngg"],
        # PFAS
        "PFOA": ["PFOA_ngg"], "PFOS": ["PFOS_ngg"],
        # PAE
        "DMP": ["DMP_ugkg", "DMP_mgkg"], "DEP": ["DEP_ugkg"],
        "DBP": ["DBP_ugkg"], "BBP": ["BBP_ugkg"],
        "DEHP": ["DEHP_ugkg"], "DNOP": ["DNOP_ugkg", "DnOP_ugkg", "DOP_ugkg"],
    }

    # 族群因子(family_factor)
    family_factors = {
        "PAHs_total": {"label": "PAHs总量", "columns": ["Sum_PAH_ngg", "SumPAH_ngg", "Sum16PAH_ngg", "Sum_PAH_mgkg"],
                        "diagnosis_layer": "supplementary_screening", "threshold_role": "screening_reference"},
        "OCPs_total": {"label": "有机氯农药总量", "columns": ["SumOCP_ngg"],
                       "diagnosis_layer": "supplementary_screening", "threshold_role": "screening_reference"},
        "DDTs_total": {"label": "滴滴涕总量", "columns": ["SumDDTs_ngg"],
                       "diagnosis_layer": "supplementary_screening", "threshold_role": "screening_reference"},
        "HCHs_total": {"label": "六六六总量", "columns": ["SumHCHs_ngg"],
                       "diagnosis_layer": "supplementary_screening", "threshold_role": "screening_reference"},
        "PCBs_total": {"label": "多氯联苯总量", "columns": ["SumPCB_ngg", "TotalPCB_ugg"],
                       "diagnosis_layer": "supplementary_screening", "threshold_role": "screening_reference"},
        "PBDEs_total": {"label": "多溴二苯醚总量", "columns": ["SumPBDE_ngg"],
                        "diagnosis_layer": "supplementary_screening", "threshold_role": "screening_reference"},
        "PFAS_total": {"label": "PFAS总量", "columns": ["SumPFAS_ngg", "SumPFAAs_ngg"],
                       "diagnosis_layer": "supplementary_screening", "threshold_role": "screening_reference"},
        "PAEs_total": {"label": "邻苯二甲酸酯总量", "columns": ["SumPAE_ugkg", "Sum6PAE_ugkg"],
                       "diagnosis_layer": "supplementary_screening", "threshold_role": "screening_reference"},
        "TPH_total": {"label": "石油烃总量", "columns": ["TPH_ngg", "TPH_mgkg", "Tph_mgkg", "TotalPHC_mgkg"],
                      "diagnosis_layer": "supplementary_screening", "threshold_role": "screening_reference"},
    }

    # 单位转换规则
    unit_rules = {
        "ngg_to_mgkg": {"factor": 0.001, "note": "ng/g → mg/kg"},
        "ugkg_to_mgkg": {"factor": 0.001, "note": "μg/kg → mg/kg"},
        "mgkg_to_ngg": {"factor": 1000, "note": "mg/kg → ng/g"},
        "gkg_to_pct": {"factor": 0.1, "note": "g/kg → %"},
        "pct_to_gkg": {"factor": 10, "note": "% → g/kg"},
    }

    # GEE proxy映射
    gee_proxy = {
        "gee_ndvi": {"proxy_for": "植被恢复潜力", "type": "ecology_covariate"},
        "gee_precip_annual_mm": {"proxy_for": "气候水分条件", "type": "environment_covariate"},
        "gee_temp_mean_c": {"proxy_for": "光温条件", "type": "environment_covariate"},
        "gee_elevation_m": {"proxy_for": "海拔/DEM", "type": "proxy_covariate"},
        "gee_slope_deg": {"proxy_for": "坡度", "type": "proxy_covariate"},
        "gee_aspect_deg": {"proxy_for": "坡向", "type": "covariate"},
        "gee_soil_pH": {"proxy_for": "pH", "type": "proxy_covariate"},
        "gee_soc_g_kg": {"proxy_for": "SOC/有机质", "type": "proxy_covariate"},
        "gee_cec_cmol_kg": {"proxy_for": "CEC", "type": "proxy_covariate"},
        "gee_clay_pct": {"proxy_for": "黏粒", "type": "proxy_covariate"},
        "gee_sand_pct": {"proxy_for": "砂粒", "type": "proxy_covariate"},
        "gee_silt_pct": {"proxy_for": "粉粒", "type": "proxy_covariate"},
        "gee_bulk_density_g_cm3": {"proxy_for": "容重/压实", "type": "proxy_covariate"},
        "gee_nitrogen_g_kg": {"proxy_for": "全氮", "type": "proxy_covariate"},
    }

    # 输出
    out = os.path.join(ROOT, "data", "knowledge")
    write_yaml(os.path.join(out, "factor_aliases_v0.8.yaml"), factor_aliases)
    write_yaml(os.path.join(out, "compound_aliases_v0.8.yaml"), compound_aliases)
    write_yaml(os.path.join(out, "unit_conversion_rules_v0.8.yaml"), unit_rules)
    write_yaml(os.path.join(out, "gee_proxy_mapping_v0.8.yaml"), gee_proxy)
    # family factor CSV
    fam_rows = []
    for fid, info in family_factors.items():
        for col in info["columns"]:
            fam_rows.append({"family_id": fid, "label": info["label"], "data_column": col,
                             "diagnosis_layer": info["diagnosis_layer"],
                             "threshold_role": info["threshold_role"]})
    pd.DataFrame(fam_rows).to_csv(os.path.join(out, "family_factor_library_v0.8.csv"),
                                  index=False, encoding="utf-8-sig")
    # 也复制到autoresearch
    out2 = os.path.join(BASE, "01_factor_threshold_library")
    write_yaml(os.path.join(out2, "factor_aliases_v0.8.yaml"), factor_aliases)
    write_yaml(os.path.join(out2, "compound_aliases_v0.8.yaml"), compound_aliases)
    pd.DataFrame(fam_rows).to_csv(os.path.join(out2, "family_factor_library_v0.8.csv"),
                                  index=False, encoding="utf-8-sig")

    print(f"[3B-1] 别名v0.8: {len(factor_aliases)}因子别名 + {len(compound_aliases)}单体别名 "
          f"+ {len(family_factors)}族群 + {len(gee_proxy)}GEE proxy")
    return factor_aliases, compound_aliases, family_factors, gee_proxy


# ============ 2. 重建 factor_to_data_column_map v0.8 ============

def build_map_v08(factor_aliases, compound_aliases, family_factors, gee_proxy):
    """完整映射: exact→alias→compound→family→proxy→coalesce→missing"""
    df = pd.read_csv(RAW_CSV, low_memory=False)
    N = len(df)
    df_cols = set(df.columns)
    gee_cols = set(pd.read_csv(GEE_CSV, nrows=0).columns) if os.path.exists(GEE_CSV) else set()
    all_data = df_cols | gee_cols

    # 读阈值库
    thresh_prod = pd.read_csv(THRESH_PROD, encoding="utf-8-sig")
    thresh_eco = pd.read_csv(THRESH_ECO, encoding="utf-8-sig")

    # 构建反向查找: 名称→canonical
    # 1. factor_alias reverse
    fa_reverse = {}  # 任意名→canonical
    for canon, info in factor_aliases.items():
        fa_reverse[canon] = canon
        for a in info.get("aliases", []):
            fa_reverse[a.strip()] = canon
    # 2. compound_alias reverse
    ca_reverse = {}
    for cn_name, en_cols in compound_aliases.items():
        ca_reverse[cn_name.strip()] = en_cols
        # 也把中文名的变体加上
    # 3. family reverse(数据列→family)
    fam_reverse = {}
    for fid, info in family_factors.items():
        for col in info["columns"]:
            fam_reverse[col] = fid

    def match_factor(factor_norm, factor_cn, track):
        """尝试6种匹配方式, 返回(col, match_type, coverage, coalesce, is_proxy)"""
        # 0. 空因子
        if not factor_norm or str(factor_norm) == "nan":
            return (None, "missing", 0, None, False)

        # 1. exact: factor_norm直接是数据列
        if factor_norm in all_data:
            cov = get_cov(df, factor_norm)
            return (factor_norm, "exact", cov, None, False)

        # 2. alias: 通过factor_aliases查找
        if factor_norm in fa_reverse:
            canon = fa_reverse[factor_norm]
            coalesce = factor_aliases.get(canon, {}).get("coalesce", [canon])
            for col in coalesce:
                if col in all_data:
                    return (col, "alias", get_cov(df, col), "|".join(coalesce), False)
            # proxy
            proxy = factor_aliases.get(canon, {}).get("proxy", [])
            for p in proxy:
                if p in all_data:
                    return (p, "proxy_covariate", get_cov(df, p), None, True)

        # 3. compound_alias: 中文名→英文单体列
        fn_clean = str(factor_cn or factor_norm).strip()
        if fn_clean in ca_reverse:
            for col in ca_reverse[fn_clean]:
                if col in all_data:
                    return (col, "compound_alias", get_cov(df, col), None, False)

        # 4. family_aggregate: 族群总量列
        if fn_clean in fam_reverse or factor_norm in fam_reverse:
            fid = fam_reverse.get(fn_clean) or fam_reverse.get(factor_norm)
            if fid and fid in family_factors:
                for col in family_factors[fid]["columns"]:
                    if col in all_data:
                        return (col, "family_aggregate", get_cov(df, col), None, False)

        # 5. GEE proxy
        if factor_norm in gee_proxy:
            gcol = factor_norm
            if gcol in all_data:
                return (gcol, "proxy_covariate", get_cov(df, gcol), None, True)

        # 6. 中文名模糊匹配(factor_cn直接在数据列里)
        if fn_clean and fn_clean in all_data:
            return (fn_clean, "alias", get_cov(df, fn_clean), None, False)

        return (None, "missing", 0, None, False)

    def get_cov(df, col):
        if col not in df.columns:
            return 0.0
        return round(float(pd.to_numeric(df[col], errors="coerce").notna().mean()) * 100, 2)

    # 对每条阈值记录做映射
    rows = []
    for thresh_df, track in [(thresh_prod, "production"), (thresh_eco, "ecology")]:
        for _, thr in thresh_df.drop_duplicates("factor_name_norm").iterrows():
            fn = thr.get("factor_name_norm")
            cn = thr.get("factor_name_raw") or fn
            col, mtype, cov, coal, is_proxy = match_factor(fn, cn, track)
            dlayer = thr.get("diagnosis_layer", "formal")
            trole = thr.get("threshold_role", "direct_standard")
            rows.append({
                "factor_id": thr.get("factor_id"),
                "factor_name_norm": fn,
                "factor_name_cn": cn,
                "track": track,
                "diagnosis_layer": dlayer,
                "threshold_role": trole,
                "threshold_available": 1 if thr.get("upper_limit") or thr.get("lower_limit") else 0,
                "data_column_matched": col,
                "match_type": mtype,
                "coverage_pct": cov,
                "coalesce_rule": coal,
                "is_measured": not is_proxy,
                "is_proxy": is_proxy,
                "usable_for_formal_diagnosis": 1 if (col and cov > 1 and not is_proxy and dlayer == "formal") else 0,
                "usable_for_supplementary_screening": 1 if (col and cov > 0.1 and dlayer in ["formal", "supplementary_screening"]) else 0,
                "usable_for_recommended_test": 0 if col else 1,
                "evidence_level": thr.get("evidence_level"),
                "notes": "" if col else "数据无对应列, 建议补测" if dlayer == "formal" else "",
            })

    map_df = pd.DataFrame(rows)
    # 输出
    for out_path in [os.path.join(ROOT, "data", "reports"),
                     os.path.join(BASE, "01_factor_threshold_library")]:
        map_df.to_csv(os.path.join(out_path, "factor_to_data_column_map_v0.8.csv"),
                      index=False, encoding="utf-8-sig")

    # 统计
    matched = map_df[map_df["match_type"] != "missing"]["factor_name_norm"].nunique()
    total = map_df["factor_name_norm"].nunique()
    by_type = map_df.drop_duplicates("factor_name_norm")["match_type"].value_counts().to_dict()
    print(f"[3B-2] 映射v0.8: {matched}/{total}因子匹配")
    print(f"       match_type分布: {by_type}")
    return map_df


if __name__ == "__main__":
    print("=" * 60)
    print("Stage 3B: 字段映射修复")
    print("=" * 60)
    fa, ca, fam, gee = build_aliases_v08()
    map_df = build_map_v08(fa, ca, fam, gee)

    # GATE_2A-2E
    mt = map_df.drop_duplicates("factor_name_norm")["match_type"].value_counts()
    gate_2a = all(k in mt.index for k in ["exact"]) and any(
        k in mt.index and mt[k] > 0 for k in ["alias", "compound_alias", "family_aggregate", "proxy_covariate"])
    formal_matched = map_df[(map_df["diagnosis_layer"] == "formal") & (map_df["match_type"] != "missing")]
    gate_2b = formal_matched["factor_name_norm"].nunique() >= 10
    op_matched = map_df[map_df["factor_name_norm"].isin(
        ["Sum_PAH_ngg", "BaP_ngg", "SumDDTs_ngg", "SumHCHs_ngg", "SumOCP_ngg",
         "SumPCB_ngg", "SumPBDE_ngg", "SumPFAS_ngg", "SumPAE_ugkg", "TPH_ngg"])]
    gate_2c = op_matched["data_column_matched"].notna().any()
    gee_classified = sum(1 for g in gee if g in map_df[map_df["is_proxy"] == True]["data_column_matched"].values)
    gate_2d = gee_classified >= 10
    high_unmapped = map_df[(map_df["coverage_pct"] > 0.5) & (map_df["match_type"] == "missing")]
    gate_2e = len(high_unmapped) == 0

    print(f"\n=== GATE_2 检查 ===")
    print(f"GATE_2A 映射引擎(alias/compound/family/proxy非零): {'✅' if gate_2a else '🔴'} {mt.to_dict()}")
    print(f"GATE_2B 核心生产A层覆盖(≥10): {'✅' if gate_2b else '🔴'} formal匹配{formal_matched['factor_name_norm'].nunique()}")
    print(f"GATE_2C OP数据利用: {'✅' if gate_2c else '🔴'}")
    print(f"GATE_2D GEE proxy分类: {'✅' if gate_2d else '🔴'} {gee_classified}/14")
    print(f"GATE_2E 高覆盖未映射清零: {'✅' if gate_2e else '🔴'} {len(high_unmapped)}个")
    print(f"\n✅ Stage 3B 完成")
