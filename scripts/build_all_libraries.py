"""P1: 因子字典 + 因子别名表 + 双轨阈值库 + 权重库。
从知识库+年度报告提取, 输出机读库文件。"""
import os
import sys
import json
import yaml
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
KB_CSV = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")
OUT_KNOWLEDGE = os.path.join(ROOT, "data", "knowledge")
OUT_THRESH = os.path.join(ROOT, "data", "thresholds")
OUT_WEIGHTS = os.path.join(ROOT, "data", "weights")
for d in [OUT_KNOWLEDGE, OUT_THRESH, OUT_WEIGHTS]:
    os.makedirs(d, exist_ok=True)


def build_factor_dictionary():
    """P1-1: 因子字典 from 知识库122因子。"""
    kb = pd.read_csv(KB_CSV, encoding="utf-8")
    factors = kb.groupby("factor_id").first().reset_index()[
        ["factor_id", "factor_name", "level1_category", "unit"]]
    factors["factor_type"] = factors["level1_category"].map({
        "环境指标": "pollutant", "物理性质": "physical", "化学性质": "chemical",
        "肥力指标": "fertility", "生物指标": "biological"})
    factors["track_applicable"] = "both"
    factors.rename(columns={"factor_name": "factor_name_cn"}, inplace=True)

    # 英文映射(与训练数据列名对齐)
    en_map = {"镉": "Cd_mgkg", "铅": "Pb_mgkg", "砷": "As_mgkg", "铬": "Cr_mgkg",
              "汞": "Hg_mgkg", "铜": "Cu_mgkg", "锌": "Zn_mgkg", "镍": "Ni_mgkg",
              "苯并[a]芘": "BaP_ngg", "多环芳烃总量": "Sum_PAH_ngg",
              "滴滴涕": "SumDDTs_ngg", "六六六": "SumHCHs_ngg", "多氯联苯": "SumPCB_ngg",
              "pH": "SoilpH", "有机质": "OC_pct", "阳离子交换量": "CEC_cmolkg"}
    factors["factor_name_en"] = factors["factor_name_cn"].map(en_map)
    factors.to_csv(os.path.join(OUT_KNOWLEDGE, "factor_dictionary.csv"),
                   index=False, encoding="utf-8-sig")

    yaml_dict = {"factors": []}
    for _, r in factors.iterrows():
        yaml_dict["factors"].append({k: (v if pd.notna(v) else None)
                                      for k, v in r.to_dict().items()})
    with open(os.path.join(OUT_KNOWLEDGE, "factor_dictionary.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(yaml_dict, f, allow_unicode=True, default_flow_style=False)
    print(f"[P1-1] 因子字典: {len(factors)}因子 → factor_dictionary.csv/yaml")


def build_factor_aliases():
    """P1-1b: 因子别名表(同义写法归一)。"""
    aliases = {
        # 重金属
        "Cd_mgkg": ["镉", "Cd", "cd", "镉(mg/kg)"],
        "Pb_mgkg": ["铅", "Pb", "pb", "铅(mg/kg)"],
        "As_mgkg": ["砷", "As", "as", "砷(mg/kg)"],
        "Cr_mgkg": ["铬", "Cr", "cr", "铬(mg/kg)", "总铬"],
        "Hg_mgkg": ["汞", "Hg", "hg", "汞(mg/kg)"],
        "Cu_mgkg": ["铜", "Cu", "cu", "铜(mg/kg)"],
        "Zn_mgkg": ["锌", "Zn", "zn", "锌(mg/kg)"],
        "Ni_mgkg": ["镍", "Ni", "ni", "镍(mg/kg)"],
        # 六价铬特殊
        "Cr6_mgkg": ["六价铬", "铬(六价)", "Cr(VI)", "Cr6+", "六价铬(mg/kg)"],
        # 有机
        "BaP_ngg": ["苯并[a]芘", "苯并 [a] 芘", "苯并芘", "BaP", "bap", "苯并[a]芘(ng/g)"],
        "Sum_PAH_ngg": ["多环芳烃总量", "PAHs", "PAH", "多环芳烃", "Sum_PAH", "PAHs总量"],
        "SumDDTs_ngg": ["滴滴涕", "DDT", "DDTs", "SumDDT", "滴滴涕总量"],
        "SumHCHs_ngg": ["六六六", "HCH", "HCHs", "六六六总量"],
        "SumPCB_ngg": ["多氯联苯", "PCB", "PCBs", "多氯联苯总量"],
        "SumOCP_ngg": ["有机氯农药", "OCP", "OCPs"],
        "TPH_ngg": ["石油烃", "石油烃(C10-C40)", "TPH", "总石油烃", "石油烃总量"],
        # 理化
        "SoilpH": ["pH", "pH值", "酸碱度"],
        "OC_pct": ["有机质", "有机碳", "SOC", "有机质(g/kg)", "有机碳含量"],
        "CEC_cmolkg": ["阳离子交换量", "CEC", "阳离子交换量(cmol/kg)"],
        "SoilBD_gcm3": ["土壤容重", "容重", "BD", "土壤容重(g/cm3)"],
    }
    with open(os.path.join(OUT_KNOWLEDGE, "factor_aliases.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(aliases, f, allow_unicode=True, default_flow_style=False)
    print(f"[P1-1b] 因子别名表: {len(aliases)}主因子 → factor_aliases.yaml")


def build_threshold_library():
    """P1-2: 双轨阈值库 from 知识库403条。"""
    kb = pd.read_csv(KB_CSV, encoding="utf-8")

    def parse_threshold_type(row):
        tmin, tmax = row.get("threshold_min"), row.get("threshold_max")
        name = str(row.get("factor_name", ""))
        if any(k in name for k in ["坡度", "质地", "构型", "障碍层", "灌排"]):
            return "ordinal"
        if pd.notna(tmin) and pd.notna(tmax) and tmin > 0:
            return "interval"
        if pd.notna(tmax) and (pd.isna(tmin) or tmin == 0):
            return "upper"
        if pd.notna(tmin) and pd.isna(tmax):
            return "lower"
        return "conditional"

    rows = []
    for _, r in kb.iterrows():
        scope = r.get("applicable_scope", "")
        track = "production" if "生产" in scope else ("ecology" if "生态" in scope else "both")
        rows.append({
            "factor_id": r.get("factor_id"),
            "factor_name": r.get("factor_name"),
            "track": track,
            "land_use_target": r.get("land_type_original"),
            "standard_source": r.get("standard_source"),
            "threshold_type": parse_threshold_type(r),
            "upper_limit": r.get("threshold_max"),
            "lower_limit": r.get("threshold_min"),
            "ideal_min": r.get("threshold_min"),
            "ideal_max": r.get("threshold_max"),
            "pH_condition": None,
            "soil_texture_condition": None,
            "region_condition": str(r.get("threshold_original", ""))[:80],
            "unit": r.get("unit"),
            "threshold_version": "V1.0",
            "evidence_level": "A" if "GB" in str(r.get("standard_source", "")) else "B",
            "notes": str(r.get("application_scenario", "")),
        })

    df = pd.DataFrame(rows)
    prod = df[df["track"].isin(["production", "both"])]
    eco = df[df["track"].isin(["ecology", "both"])]
    prod.to_csv(os.path.join(OUT_THRESH, "threshold_library_production.csv"),
                index=False, encoding="utf-8-sig")
    eco.to_csv(os.path.join(OUT_THRESH, "threshold_library_ecology.csv"),
               index=False, encoding="utf-8-sig")
    print(f"[P1-2] 阈值库: 生产{len(prod)}条, 生态{len(eco)}条")


def build_weight_library():
    """P1-3: 权重库 from 年度报告表13(生产)/表14(生态)。"""
    # 生产轨权重(年度报告表13, 功能层×指标层)
    prod_data = [
        # (功能层, 功能层权重, 指标, 指标层权重)
        ("土壤质量", 0.2524, "有效土层厚度", 0.4047),
        ("土壤质量", 0.2524, "pH", 0.2030),
        ("土壤质量", 0.2524, "土壤容重", 0.1184),
        ("土壤质量", 0.2524, "生物多样性", 0.0870),
        ("土壤质量", 0.2524, "盐渍化程度", 0.0594),
        ("土壤质量", 0.2524, "全氮", 0.0492),
        ("土壤质量", 0.2524, "有效磷", 0.0310),
        ("土壤质量", 0.2524, "速效钾", 0.0261),
        ("土壤质量", 0.2524, "阳离子交换量", 0.0214),
        ("修复潜力", 0.5664, "汞", 0.2838),
        ("修复潜力", 0.5664, "砷", 0.1858),
        ("修复潜力", 0.5664, "镉", 0.1244),
        ("修复潜力", 0.5664, "六价铬", 0.0858),
        ("修复潜力", 0.5664, "苯并[a]芘", 0.0925),
        ("修复潜力", 0.5664, "铅", 0.0617),
        ("修复潜力", 0.5664, "滴滴涕", 0.0588),
        ("修复潜力", 0.5664, "六六六", 0.0458),
        ("修复潜力", 0.5664, "镍", 0.0272),
        ("修复潜力", 0.5664, "铜", 0.0195),
        ("修复潜力", 0.5664, "锌", 0.0146),
        ("功能利用潜力", 0.0808, "光温/气候生产潜力", 0.6411),
        ("功能利用潜力", 0.0808, "灌排能力", 0.1800),
        ("功能利用潜力", 0.0808, "地下水埋深", 0.1107),
        ("功能利用潜力", 0.0808, "地形坡度", 0.0682),
        ("固碳减排潜力", 0.1004, "表土质地", 0.4274),
        ("固碳减排潜力", 0.1004, "有机碳含量", 0.2293),
        ("固碳减排潜力", 0.1004, "剖面构型", 0.1140),
        ("固碳减排潜力", 0.1004, "C库变化因子", 0.2293),
    ]
    # 生态轨权重(年度报告表14核心指标)
    eco_data = [
        ("土壤质量", 0.4967, "有效土层厚度", 0.1805),
        ("土壤质量", 0.4967, "土壤容重", 0.1658),
        ("土壤质量", 0.4967, "土壤入渗率", 0.1125),
        ("土壤质量", 0.4967, "含盐量", 0.0788),
        ("土壤质量", 0.4967, "阳离子交换量", 0.0788),
        ("土壤质量", 0.4967, "pH", 0.0537),
        ("土壤质量", 0.4967, "可溶性氯", 0.0788),
        ("土壤质量", 0.4967, "水解性氮", 0.0363),
        ("土壤质量", 0.4967, "有效磷", 0.0363),
        ("土壤质量", 0.4967, "速效钾", 0.0363),
        ("修复潜力", 0.3135, "汞", 0.4202),
        ("修复潜力", 0.3135, "铬(VI)", 0.2452),
        ("修复潜力", 0.3135, "镉", 0.1383),
        ("修复潜力", 0.3135, "砷", 0.0786),
        ("修复潜力", 0.3135, "铅", 0.0578),
        ("修复潜力", 0.3135, "铜", 0.0378),
        ("修复潜力", 0.3135, "镍", 0.0221),
    ]

    rows = []
    for func_layer, func_w, indicator, ind_w in prod_data:
        global_w = func_w * ind_w
        rows.append({"factor_name": indicator, "track": "production",
                     "功能层": func_layer, "功能层权重": func_w,
                     "指标层权重": ind_w, "全局权重": round(global_w, 4),
                     "standard_priority": 0.5, "weight_version": "v0.1_课题二表13"})
    for func_layer, func_w, indicator, ind_w in eco_data:
        global_w = func_w * ind_w
        rows.append({"factor_name": indicator, "track": "ecology",
                     "功能层": func_layer, "功能层权重": func_w,
                     "指标层权重": ind_w, "全局权重": round(global_w, 4),
                     "standard_priority": 0.5, "weight_version": "v0.1_课题二表14"})

    df = pd.DataFrame(rows)
    # λ组合: W = Normalize(0.5*功能层 + 0.4*指标层 + 0.1*标准优先级)
    df["lambda_weight"] = (0.5 * df["功能层权重"] + 0.4 * df["指标层权重"] + 0.1 * df["standard_priority"])
    # 按轨道归一化
    for track in ["production", "ecology"]:
        mask = df["track"] == track
        total = df.loc[mask, "lambda_weight"].sum()
        df.loc[mask, "W_normalized"] = df.loc[mask, "lambda_weight"] / total
    df.to_csv(os.path.join(OUT_WEIGHTS, "track_weight_library.csv"),
              index=False, encoding="utf-8-sig")
    print(f"[P1-3] 权重库: 生产{len(prod_data)}指标, 生态{len(eco_data)}指标 → track_weight_library.csv")
    print(f"        来源: 课题二年度报告表2.10(AHP+熵值法, CR=0.065通过)")


if __name__ == "__main__":
    build_factor_dictionary()
    build_factor_aliases()
    build_threshold_library()
    build_weight_library()
    print("\n✅ P1 库建设完成")
