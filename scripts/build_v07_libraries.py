"""v0.7 阶段2+3: 项目schema + 因子master + 别名 + 双轨阈值库 + 权重库 + 字段映射。
从障碍因子集多版本xlsx构建，输出到 autoresearch/obstacle_diagnosis_v0.7/。"""
import os, sys, json, hashlib, math, yaml, re
import numpy as np
import pandas as pd
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASE = os.path.join(ROOT, "autoresearch", "obstacle_diagnosis_v0.7")
SRC = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
                   "..", "..", "obstacle_factor_sources", "1.障碍因子集")
# 修正: 障碍因子集在桌面
DESKTOP_SRC = "C:/Users/曾鸿/Desktop/obstacle_factor_sources/1.障碍因子集"
RAW_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_geocoded.csv")
GEE_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_gee_covariates.csv")
KB_CSV = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")
TS = datetime.now().strftime("%Y%m%d_%H%M")


def write_yaml(path, data):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============ 阶段2: Schema ============

def build_schemas():
    """00_project_schema/ 6个yaml"""
    S = os.path.join(BASE, "00_project_schema")
    project = {
        "project_name": "obstacle_diagnosis_v0.7",
        "version": "0.7",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "raw_data_path": "data/covariates/merged_std33_geocoded.csv",
        "gee_covariate_path": "data/covariates/merged_std33_gee_covariates.csv",
        "factor_source_paths": {
            "master": "20251015_生产生态障碍因子集V1.6.xlsx",
            "production_supplement": "20251028_生产障碍因子集V1.6.xlsx",
            "ecology_supplement": "3.生态障碍因子集-终版V1.7.xlsx",
            "reference": "1.生产障碍因子集-终版V1.7.xlsx",
            "knowledge_base": "统一障碍因子知识库_V1.0.csv",
        },
        "threshold_library_version": "v0.7",
        "weight_library_version": "v0.7",
        "tracks": ["production", "ecology"],
        "model_task": "regression",
        "target_names": ["OI_prod", "OI_eco"],
        "forbidden_feature_prefixes": ["标签", "B_", "R_", "KOS", "OI_",
                                       "threshold", "exceedance", "severity", "rule_"],
        "allowed_feature_groups": ["measured", "covariate", "gee_covariate",
                                   "missing_indicator", "censored_indicator"],
        "random_seed": 42,
        "environment": "Windows/python3.13",
    }
    write_yaml(os.path.join(S, "project_schema.yaml"), project)

    feature = {
        "measured": {"description": "场地或文献实测值(浓度+理化), 可入模"},
        "covariate": {"description": "非GEE背景协变量(地形/气候原始字段), 可入模"},
        "gee_covariate": {"description": "GEE/遥感/土壤栅格协变量, 可入模需审计"},
        "missing_indicator": {"description": "缺失指示(__missing), 可入模"},
        "censored_indicator": {"description": "检出限/未检出指示, 可入模"},
        "imputed": {"description": "插补值, 仅敏感性分析需标记"},
        "rule_derived_forbidden": {"description": "B/R/W/threshold/exceedance规则派生, 禁止入模"},
        "target_forbidden": {"description": "OI_prod/OI_eco目标, 禁止入模"},
        "posthoc_forbidden": {"description": "KOS/SHAP/排名后验字段, 禁止入模"},
    }
    write_yaml(os.path.join(S, "feature_schema.yaml"), feature)

    target = {
        "OI_prod": {"description": "生产轨连续障碍指数(回归目标)", "type": "continuous",
                     "range": "0-1", "source": "rule_engine", "note": "非二分类标签"},
        "OI_eco": {"description": "生态轨连续障碍指数(回归目标)", "type": "continuous",
                    "range": "0-1", "source": "rule_engine", "note": "非二分类标签"},
        "B_i_t": {"description": "规则层障碍存在性(0/1)", "type": "binary", "forbidden_in_model": True},
        "R_i_t": {"description": "规则严重度(0-1)", "type": "continuous", "forbidden_in_model": True},
        "W_i_t": {"description": "用途权重", "type": "continuous", "forbidden_in_model": True},
        "D_i": {"description": "是否已检测(0/1)", "type": "binary", "forbidden_in_model": True},
    }
    write_yaml(os.path.join(S, "target_schema.yaml"), target)

    track = {
        "production": {"name": "生产用途", "target": "OI_prod",
                       "functional_layers": ["污染安全限制", "生产适宜性限制", "肥力限制",
                                             "根系结构限制", "水盐酸碱限制", "地形土层限制"],
                       "threshold_source": "GB15618 + TD/T1036 + V1.6生产",
                       "diagnosis_layers": ["formal", "supplementary_screening", "recommended_test"]},
        "ecology": {"name": "生态用途", "target": "OI_eco",
                    "functional_layers": ["污染生态毒性限制", "植被恢复限制", "结构水文限制",
                                          "化学环境限制", "生物活性限制", "生态服务潜力限制"],
                    "threshold_source": "GB36600 + CJ/T340 + V1.7生态",
                    "diagnosis_layers": ["formal", "supplementary_screening", "recommended_test"]},
    }
    write_yaml(os.path.join(S, "track_schema.yaml"), track)

    split = {
        "strategies": ["GroupKFold_site_id", "GroupKFold_source", "LeaveOneRegionOut"],
        "forbidden": ["random_split"],
        "manifest_fields": ["sample_id", "site_id", "source_id", "province", "region",
                            "pollution_type", "track", "split", "split_strategy", "split_version"],
        "scenario_stratification": ["HM", "OP", "HM+OP"],
    }
    write_yaml(os.path.join(S, "split_schema.yaml"), split)

    artifact = {"version": "v0.7", "timestamp_field": "created_at",
                "naming_convention": "YYYYMMDD_HHMM_filename.ext"}
    write_yaml(os.path.join(S, "artifact_manifest.yaml"), artifact)
    print(f"[阶段2] 6个schema已生成 → 00_project_schema/")


# ============ 阶段3a: 因子别名系统 ============

def build_aliases():
    """因子别名v0.7, 覆盖25+映射组"""
    aliases = {
        "pH": ["SoilpH", "pH", "pH_merged", "pH值", "酸碱度"],
        "OC_pct": ["OC_pct", "SOC", "SOM", "有机质", "有机碳含量", "有机质(g/kg)", "有机碳"],
        "CEC_cmolkg": ["CEC_cmolkg", "阳离子交换量", "CEC", "阳离子交换量(cmol/kg)"],
        "SoilBD_gcm3": ["SoilBD_gcm3", "BD", "bulk_density", "土壤容重", "容重", "压实", "土壤容重(g/cm3)"],
        "EC_mScm": ["EC_mScm", "EC", "electrical_conductivity", "电导率", "含盐量", "盐渍化程度"],
        "Cd_mgkg": ["Cd_mgkg", "镉", "Cd", "cd", "镉(mg/kg)"],
        "Pb_mgkg": ["Pb_mgkg", "铅", "Pb", "pb", "铅(mg/kg)"],
        "As_mgkg": ["As_mgkg", "砷", "As", "as", "砷(mg/kg)"],
        "Cr_mgkg": ["Cr_mgkg", "铬", "Cr", "cr", "总铬", "铬(mg/kg)"],
        "Cr6_mgkg": ["六价铬", "铬(六价)", "Cr(VI)", "Cr6+", "六价铬(mg/kg)", "CrVI"],
        "Hg_mgkg": ["Hg_mgkg", "汞", "Hg", "hg", "汞(mg/kg)"],
        "Cu_mgkg": ["Cu_mgkg", "铜", "Cu", "cu", "铜(mg/kg)"],
        "Zn_mgkg": ["Zn_mgkg", "锌", "Zn", "zn", "锌(mg/kg)"],
        "Ni_mgkg": ["Ni_mgkg", "镍", "Ni", "ni", "镍(mg/kg)"],
        "BaP_ngg": ["BaP_ngg", "BaP_mgkg", "苯并[a]芘", "苯并 [a] 芘", "苯并芘", "BaP", "bap", "苯并[a]芘(ng/g)"],
        "Sum_PAH_ngg": ["Sum_PAH_ngg", "SumPAH", "PAHs总量", "多环芳烃总量", "PAHs", "PAH", "多环芳烃"],
        "SumHCHs_ngg": ["SumHCHs_ngg", "HCHs", "HCH", "六六六总量", "六六六", "α-六六六", "β-六六六", "γ-六六六"],
        "SumDDTs_ngg": ["SumDDTs_ngg", "DDTs", "DDT", "滴滴涕总量", "滴滴涕", "p,p'-滴滴滴", "p,p'-滴滴伊"],
        "SumOCP_ngg": ["SumOCP_ngg", "OCPs", "OCP", "有机氯农药", "有机氯农药总量"],
        "SumPCB_ngg": ["SumPCB_ngg", "PCBs", "PCB", "多氯联苯", "多氯联苯总量"],
        "SumPBDE_ngg": ["SumPBDE_ngg", "PBDEs", "PBDE", "多溴二苯醚"],
        "SumPFAS_ngg": ["SumPFAS_ngg", "PFAS", "PFAS总量"],
        "SumPAE_ugkg": ["SumPAE_ugkg", "PAEs", "邻苯二甲酸酯"],
        "TPH_ngg": ["TPH_ngg", "TPH", "石油烃", "石油烃(C10-C40)", "总石油烃", "石油烃总量"],
        "TN_gkg": ["TN_gkg", "全氮", "总氮", "TN", "全氮(g/kg)"],
        "Elevation_m": ["Elevation_m", "Altitude_m", "海拔", "高程", "DEM"],
        "MAP_mm": ["MAP_mm", "年均降水量", "降水", "precipitation"],
    }
    out = os.path.join(BASE, "01_factor_threshold_library", "factor_aliases_v0.7.yaml")
    write_yaml(out, aliases)
    # 也写到data/knowledge
    write_yaml(os.path.join(ROOT, "data", "knowledge", "factor_aliases.yaml"), aliases)
    # 反向映射: 别名→标准名
    alias_audit = []
    for std, alts in aliases.items():
        for a in alts:
            alias_audit.append({"alias": a, "canonical": std})
    pd.DataFrame(alias_audit).to_csv(
        os.path.join(ROOT, "data", "reports", "factor_alias_audit.csv"),
        index=False, encoding="utf-8-sig")
    print(f"[阶段3a] 别名系统: {len(aliases)}组, {len(alias_audit)}条映射")
    return aliases


# ============ 阶段3b: Master factor universe ============

def build_factor_master(aliases):
    """从V1.6合并版构建master factor universe"""
    # 读V1.6合并版(123因子/1149行/12列最全)
    v16_path = os.path.join(DESKTOP_SRC, "8.历史版本", "20251015_生产生态障碍因子集V1.6.xlsx")
    df16 = pd.read_excel(v16_path, sheet_name=0)
    # 列名规范化(去换行符+strip)
    df16.columns = [c.replace("\n", "").replace("（", "(").replace("）", ")").strip() for c in df16.columns]

    # 读V1.6生产单独(21因子/691行)
    v16p_path = os.path.join(DESKTOP_SRC, "8.历史版本", "20251028_生产障碍因子集V1.6.xlsx")
    df16p = pd.read_excel(v16p_path, sheet_name=0)
    df16p.columns = [c.replace("\n", "").replace("（", "(").replace("）", ")").strip() for c in df16p.columns]

    # 读V1.7生态(116因子/220行)
    v17e_path = os.path.join(DESKTOP_SRC, "3.生态障碍因子集-终版V1.7.xlsx")
    df17e = pd.read_excel(v17e_path, sheet_name=0)
    df17e.columns = [c.replace("\n", "").replace("（", "(").replace("）", ")").strip() for c in df17e.columns]

    # 读知识库(补factor_id)
    kb = pd.read_csv(KB_CSV, encoding="utf-8")

    # 合并: V1.6合并版作为master
    raw_rows = []
    for _, r in df16.iterrows():
        raw_rows.append({
            "source_file": "20251015_V1.6合并版", "source_version": "V1.6",
            "source_row_id": r.get("编号"),
            "track_raw": r.get("用途", ""),
            "track_normalized": "production" if "生产" in str(r.get("用途", "")) else
                               ("ecology" if "生态" in str(r.get("用途", "")) else "both"),
            "factor_name_raw": str(r.get("二级指标(障碍因子名称)", "")).strip(),
            "level1_category": r.get("一级指标", ""),
            "scenario": r.get("三级指标(应用场景)", ""),
            "land_use_target": r.get("用地类型", ""),
            "threshold_text": str(r.get("阈值", "")),
            "unit": r.get("标准化单位", ""),
            "standard_source": r.get("相关标准", ""),
            "standard_level": r.get("标准层级", ""),
            "risk_level": r.get("风险等级", ""),
            "notes": r.get("备注", ""),
        })
    # 补充V1.6生产单独版(去重后新增的)
    existing_factors = set(r["factor_name_raw"] for r in raw_rows)
    for _, r in df16p.iterrows():
        fname = str(r.get("二级指标", "")).strip()
        if fname and fname not in existing_factors:
            raw_rows.append({
                "source_file": "20251028_V1.6生产单独", "source_version": "V1.6",
                "source_row_id": r.get("编号"),
                "track_raw": "生产", "track_normalized": "production",
                "factor_name_raw": fname,
                "level1_category": r.get("一级指标", ""),
                "scenario": r.get("三级指标", ""),
                "land_use_target": r.get("用地类型", ""),
                "threshold_text": str(r.get("阈值", "")),
                "unit": r.get("标准化单位", ""),
                "standard_source": r.get("参考标准", ""),
                "standard_level": r.get("标准层级", ""),
                "risk_level": "", "notes": r.get("备注", ""),
            })
            existing_factors.add(fname)
    # 补充V1.7生态(新增的有机氯/挥发性)
    for _, r in df17e.iterrows():
        fname = str(r.get("二级指标(障碍因子名称)", "")).strip()
        if fname and fname not in existing_factors:
            raw_rows.append({
                "source_file": "V1.7生态终版", "source_version": "V1.7",
                "source_row_id": r.get("编号"),
                "track_raw": "生态", "track_normalized": "ecology",
                "factor_name_raw": fname,
                "level1_category": r.get("一级指标", ""),
                "scenario": r.get("三级指标(应用场景)", ""),
                "land_use_target": r.get("用地类型", ""),
                "threshold_text": str(r.get("阈值", "")),
                "unit": "", "standard_source": "", "standard_level": "",
                "risk_level": "", "notes": r.get("备注", ""),
            })
            existing_factors.add(fname)

    raw_df = pd.DataFrame(raw_rows)
    # 归一化因子名(用别名表)
    alias_reverse = {}
    for std, alts in aliases.items():
        for a in alts:
            alias_reverse[a] = std
        alias_reverse[std] = std
    raw_df["factor_name_norm"] = raw_df["factor_name_raw"].map(
        lambda x: alias_reverse.get(x.strip(), x.strip()))
    raw_df.to_csv(os.path.join(BASE, "01_factor_threshold_library",
                               "factor_master_raw.csv"), index=False, encoding="utf-8-sig")

    # 去重: 每个norm因子取一条(优先V1.6合并版)
    dedup = raw_df.sort_values("source_version").drop_duplicates(
        subset="factor_name_norm", keep="first").copy()
    # 补factor_id from知识库
    kb_map = dict(zip(kb["factor_name"], kb["factor_id"]))
    dedup["factor_id"] = dedup["factor_name_raw"].map(kb_map)
    # 生产/生态适用性
    track_app = raw_df.groupby("factor_name_norm")["track_normalized"].apply(
        lambda x: list(set(x))).to_dict()
    dedup["production_applicable"] = dedup["factor_name_norm"].map(
        lambda f: 1 if "production" in track_app.get(f, []) or "both" in track_app.get(f, []) else 0)
    dedup["ecology_applicable"] = dedup["factor_name_norm"].map(
        lambda f: 1 if "ecology" in track_app.get(f, []) or "both" in track_app.get(f, []) else 0)
    dedup["factor_name_cn"] = dedup["factor_name_raw"]
    dedup["factor_name_en"] = dedup["factor_name_norm"]
    dedup["factor_type"] = dedup["level1_category"].map({
        "环境指标": "pollutant", "物理性质": "physical", "化学性质": "chemical",
        "肥力指标": "fertility", "生物指标": "biological"})
    dedup["evidence_level"] = dedup["standard_source"].apply(
        lambda s: "A" if "GB" in str(s) else ("B" if s else "C"))
    dedup["default_unit"] = dedup["unit"]
    dedup.to_csv(os.path.join(BASE, "01_factor_threshold_library",
                              "factor_master_dedup.csv"), index=False, encoding="utf-8-sig")
    print(f"[阶段3b] master factor universe: raw {len(raw_df)}行 → dedup {len(dedup)}因子")

    # track applicability
    app_rows = []
    for _, r in dedup.iterrows():
        fn = r["factor_name_norm"]
        prod = r["production_applicable"]
        eco = r["ecology_applicable"]
        app_rows.append({
            "factor_id": r.get("factor_id"), "factor_name_norm": fn,
            "production_applicable": prod, "ecology_applicable": eco,
            "production_formal_diagnosis": prod and r["evidence_level"] in ["A", "B"],
            "ecology_formal_diagnosis": eco and r["evidence_level"] in ["A", "B"],
            "production_supplementary_screening": 0, "ecology_supplementary_screening": 0,
            "production_recommend_supplementary_test": 0, "ecology_recommend_supplementary_test": 0,
            "basis": r.get("standard_source", ""), "notes": ""})
    pd.DataFrame(app_rows).to_csv(os.path.join(BASE, "01_factor_threshold_library",
        "factor_track_applicability.csv"), index=False, encoding="utf-8-sig")
    return dedup, aliases


# ============ 阶段3c: 双轨阈值库v0.7 ============

def build_threshold_v07(dedup, aliases):
    """生产轨三层(A/B/C) + 生态轨四分类 阈值库"""
    rows = []
    # 有机污染物(扩展筛查B层)
    org_screening = ["Sum_PAH_ngg", "BaP_ngg", "SumHCHs_ngg", "SumDDTs_ngg", "SumOCP_ngg",
                     "SumPCB_ngg", "SumPBDE_ngg", "SumPFAS_ngg", "SumPAE_ugkg", "TPH_ngg"]
    # 建议补测C层
    prod_test = ["TN_gkg", "有效磷", "速效钾", "灌排能力", "有效耕作层厚度",
                 "地下水埋深", "光温生产潜力", "生物多样性"]

    for _, r in dedup.iterrows():
        fn = r["factor_name_norm"]
        for track in ["production", "ecology"]:
            if track == "production" and not r["production_applicable"]:
                continue
            if track == "ecology" and not r["ecology_applicable"]:
                continue
            # 判定diagnosis_layer
            if fn in org_screening:
                dlayer = "supplementary_screening" if track == "production" else "formal"
            elif fn in prod_test or any(k in str(r.get("factor_name_cn", "")) for k in
                                        ["全氮", "有效磷", "速效钾", "灌排", "地下水", "光温", "生物多样"]):
                dlayer = "recommended_test"
            else:
                dlayer = "formal"

            # threshold_type推断
            ttext = str(r.get("threshold_text", ""))
            if any(k in str(r.get("factor_name_cn", "")) for k in ["坡度", "质地", "构型", "障碍层", "灌排"]):
                ttype = "ordinal"
            elif "-" in ttext and not ttext.startswith("-"):
                ttype = "interval"
            elif "≤" in ttext or "<" in ttext:
                ttype = "upper"
            elif "≥" in ttext or ">" in ttext:
                ttype = "lower"
            else:
                ttype = "conditional"

            rows.append({
                "factor_id": r.get("factor_id"),
                "factor_name_norm": fn,
                "factor_name_raw": r.get("factor_name_cn"),
                "track": track,
                "diagnosis_layer": dlayer,
                "threshold_role": "direct_standard" if dlayer == "formal" else
                                ("screening_reference" if dlayer == "supplementary_screening" else "proxy_indicator"),
                "land_use_target": r.get("land_use_target"),
                "scenario": r.get("scenario"),
                "standard_source": r.get("standard_source"),
                "standard_level": r.get("standard_level"),
                "threshold_type": ttype,
                "upper_limit": r.get("threshold_text") if ttype == "upper" else None,
                "lower_limit": r.get("threshold_text") if ttype == "lower" else None,
                "ideal_min": None, "ideal_max": None,
                "unit": r.get("unit"),
                "threshold_version": "v0.7",
                "evidence_level": r.get("evidence_level"),
                "source_file": r.get("source_file"),
                "source_version": r.get("source_version"),
                "source_row_id": r.get("source_row_id"),
                "notes": r.get("notes"),
            })

    df = pd.DataFrame(rows)
    prod = df[df["track"] == "production"]
    eco = df[df["track"] == "ecology"]
    prod.to_csv(os.path.join(BASE, "01_factor_threshold_library",
        "dual_track_threshold_library_production_v0.7.csv"), index=False, encoding="utf-8-sig")
    eco.to_csv(os.path.join(BASE, "01_factor_threshold_library",
        "dual_track_threshold_library_ecology_v0.7.csv"), index=False, encoding="utf-8-sig")
    # 也复制到data/thresholds
    prod.to_csv(os.path.join(ROOT, "data", "thresholds",
        "threshold_library_production_v0.7.csv"), index=False, encoding="utf-8-sig")
    eco.to_csv(os.path.join(ROOT, "data", "thresholds",
        "threshold_library_ecology_v0.7.csv"), index=False, encoding="utf-8-sig")
    print(f"[阶段3c] 阈值库v0.7: 生产{len(prod)}条({prod['diagnosis_layer'].value_counts().to_dict()}), "
          f"生态{len(eco)}条")


# ============ 阶段3d: 权重库v0.7(含fallback) ============

def build_weights_v07(dedup):
    """权重v0.7: 课题二有则用, 无则功能层fallback"""
    # 课题二权重(从已有track_weight_library读)
    tw_path = os.path.join(ROOT, "data", "weights", "track_weight_library.csv")
    tw = pd.read_csv(tw_path) if os.path.exists(tw_path) else pd.DataFrame()
    tw_dict = {}
    if len(tw) > 0:
        for _, r in tw.iterrows():
            tw_dict[(r["factor_name"], r["track"])] = {
                "function_layer": r.get("功能层"), "function_layer_weight": r.get("功能层权重"),
                "indicator_weight": r.get("指标层权重"), "final_weight": r.get("W_normalized")}

    # 功能层fallback权重(裴总指令)
    prod_fallback = {"污染安全限制": 0.30, "生产适宜性限制": 0.20, "肥力限制": 0.15,
                     "根系结构限制": 0.15, "水盐酸碱限制": 0.10, "地形土层限制": 0.10}
    eco_fallback = {"污染生态毒性限制": 0.25, "植被恢复限制": 0.20, "结构水文限制": 0.20,
                    "化学环境限制": 0.15, "生物活性限制": 0.10, "生态服务潜力限制": 0.10}

    # 因子→功能层映射
    def get_func_layer(factor_name, track):
        cn = str(factor_name)
        if any(k in cn for k in ["镉", "铅", "砷", "铬", "汞", "铜", "锌", "镍", "苯并", "PAH",
                                  "滴滴涕", "六六六", "多氯联苯", "石油", "OCP", "PCB", "PBDE", "PFAS"]):
            return "污染安全限制" if track == "production" else "污染生态毒性限制"
        if any(k in cn for k in ["pH", "含盐", "电导", "盐渍"]):
            return "水盐酸碱限制" if track == "production" else "化学环境限制"
        if any(k in cn for k in ["容重", "入渗", "孔隙", "压实", "质地", "土层", "坡度"]):
            return "根系结构限制" if track == "production" else "结构水文限制"
        if any(k in cn for k in ["有机质", "有机碳", "全氮", "有效磷", "速效钾", "CEC", "阳离子"]):
            return "肥力限制" if track == "production" else "生物活性限制"
        return "生产适宜性限制" if track == "production" else "植被恢复限制"

    rows = []
    for _, r in dedup.iterrows():
        fn = r["factor_name_norm"]
        cn = r.get("factor_name_cn", fn)
        for track in (["production"] if r["production_applicable"] else []) + \
                      (["ecology"] if r["ecology_applicable"] else []):
            key = (cn, track)
            if key in tw_dict:
                t = tw_dict[key]
                rows.append({"factor_id": r.get("factor_id"), "factor_name_norm": fn,
                             "track": track, "function_layer": t["function_layer"],
                             "function_layer_weight": t["function_layer_weight"],
                             "indicator_weight": t["indicator_weight"],
                             "fallback_weight": None, "standard_priority": 0.5,
                             "final_weight": t["final_weight"],
                             "weight_source": "topic2_direct",
                             "weight_version": "v0.7", "sensitivity_flag": False, "notes": ""})
            else:
                fl = get_func_layer(cn, track)
                fb = (prod_fallback if track == "production" else eco_fallback).get(fl, 0.1)
                rows.append({"factor_id": r.get("factor_id"), "factor_name_norm": fn,
                             "track": track, "function_layer": fl,
                             "function_layer_weight": fb, "indicator_weight": None,
                             "fallback_weight": fb, "standard_priority": 0.3,
                             "final_weight": fb / 10,  # fallback均分
                             "weight_source": "domain_fallback",
                             "weight_version": "v0.7", "sensitivity_flag": True,
                             "notes": f"课题二无此因子权重, 用{fl}功能层fallback"})

    df = pd.DataFrame(rows)
    # 按track归一化final_weight
    for track in ["production", "ecology"]:
        mask = df["track"] == track
        total = df.loc[mask, "final_weight"].sum()
        if total > 0:
            df.loc[mask, "final_weight_normalized"] = df.loc[mask, "final_weight"] / total
        else:
            df.loc[mask, "final_weight_normalized"] = 0
    df.to_csv(os.path.join(BASE, "01_factor_threshold_library",
        "dual_track_weight_library_v0.7.csv"), index=False, encoding="utf-8-sig")
    df.to_csv(os.path.join(ROOT, "data", "weights",
        "track_weight_library_v0.7.csv"), index=False, encoding="utf-8-sig")
    prod_n = len(df[df["track"] == "production"])
    eco_n = len(df[df["track"] == "ecology"])
    topic2_n = len(df[df["weight_source"] == "topic2_direct"])
    fallback_n = len(df[df["weight_source"] == "domain_fallback"])
    print(f"[阶段3d] 权重库v0.7: 生产{prod_n}/生态{eco_n}, "
          f"课题二直供{topic2_n}/fallback{fallback_n}")


# ============ 阶段3e: 字段映射 ============

def build_column_map(dedup, aliases):
    """因子→数据列映射"""
    df_cols = list(pd.read_csv(RAW_CSV, nrows=0).columns)
    gee_cols = list(pd.read_csv(GEE_CSV, nrows=0).columns) if os.path.exists(GEE_CSV) else []
    all_data_cols = set(df_cols) | set(gee_cols)
    alias_reverse = {a: std for std, alts in aliases.items() for a in alts}
    alias_reverse.update({std: std for std in aliases})

    rows = []
    for _, r in dedup.iterrows():
        fn = r["factor_name_norm"]
        cn = r.get("factor_name_cn", fn)
        # 尝试匹配: 标准名/中文名/别名
        matched = None
        match_type = "missing"
        for candidate in [fn, cn] + aliases.get(fn, []):
            if candidate in all_data_cols:
                matched = candidate
                match_type = "exact" if candidate == fn else "alias"
                break
        coverage = 0.0
        if matched and matched in df_cols:
            try:
                s = pd.read_csv(RAW_CSV, usecols=[matched], low_memory=False)[matched]
                coverage = round(float(s.notna().mean()) * 100, 2)
            except Exception:
                pass
        for track in ["production", "ecology"]:
            rows.append({
                "factor_id": r.get("factor_id"), "factor_name_norm": fn, "track": track,
                "threshold_available": 1 if r.get("threshold_text") else 0,
                "data_column_matched": matched, "match_type": match_type,
                "coverage_pct": coverage,
                "usable_for_formal_diagnosis": 1 if matched and coverage > 5 else 0,
                "usable_for_supplementary_screening": 1 if matched and coverage <= 5 else 0,
                "usable_for_recommended_test": 1 if not matched else 0,
                "notes": ""})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(BASE, "01_factor_threshold_library",
        "factor_to_data_column_map_v0.7.csv"), index=False, encoding="utf-8-sig")
    df.to_csv(os.path.join(ROOT, "data", "reports",
        "factor_to_data_column_map_v0.7.csv"), index=False, encoding="utf-8-sig")
    matched_n = len(df[df["match_type"] != "missing"]["factor_name_norm"].unique())
    total_n = len(df["factor_name_norm"].unique())
    print(f"[阶段3e] 字段映射: {matched_n}/{total_n}因子匹配到数据列")
    return df


if __name__ == "__main__":
    build_schemas()
    aliases = build_aliases()
    dedup, aliases = build_factor_master(aliases)
    build_threshold_v07(dedup, aliases)
    build_weights_v07(dedup)
    col_map = build_column_map(dedup, aliases)
    print(f"\n✅ 阶段2+3完成。输出在 autoresearch/obstacle_diagnosis_v0.7/01_factor_threshold_library/")
