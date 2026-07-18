"""GB/HJ 标准阈值库入库。

说明:
- GB 15618-2018 / GB 36600-2018 为浓度阈值标准;
- HJ 25.5-2018 为污染地块风险管控与修复效果评估技术导则, 不提供单因子浓度筛选值,
  因此只入库标准元信息行, screening/control 保持 None。
"""
from __future__ import annotations

from datetime import date

from app.db.init_db import create_all
from app.db.session import SessionLocal
from app.models import FactorDictionary, StandardThreshold

REF_GB15618 = "https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/trhj/201807/t20180703_446029.shtml"
REF_GB36600 = "https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/trhj/201807/t20180703_446027.shtml"
REF_HJ255 = "https://www.mee.gov.cn/ywgz/fgbz/bz/bzwb/trhj/201901/t20190107_688646.shtml"


def _gb15618_rows() -> list[dict]:
    standard_name = "土壤环境质量 农用地土壤污染风险管控标准（试行）"
    # 农用地风险筛选值，其他农用地口径，单位 mg/kg。
    values = {
        "Cd": [0.3, 0.3, 0.3, 0.6],
        "Hg": [1.3, 1.8, 2.4, 3.4],
        "As": [40, 40, 30, 25],
        "Pb": [70, 90, 120, 170],
        "Cr": [150, 150, 200, 250],
        "Cu": [50, 50, 100, 100],
        "Ni": [60, 70, 100, 190],
        "Zn": [200, 200, 250, 300],
    }
    ph_conditions = ["pH<=5.5", "5.5<pH<=6.5", "6.5<pH<=7.5", "pH>7.5"]
    rows = []
    for factor, vals in values.items():
        for ph, val in zip(ph_conditions, vals):
            rows.append({
                "factor_name": factor,
                "land_use_type": "农用地",
                "standard_code": "GB 15618-2018",
                "standard_name": standard_name,
                "screening_value": float(val),
                "intervention_value": None,
                "control_value": None,
                "unit": "mg/kg",
                "pH_condition": ph,
                "soil_condition": "其他农用地",
                "exposure_scenario": "agricultural_land",
                "effective_date": date(2018, 8, 1),
                "version": "2018",
                "source_reference": REF_GB15618,
                "notes": "农用地土壤污染风险筛选值; 水田/果园等特殊口径后续按标准表扩展。",
            })
    return rows


def _gb36600_rows() -> list[dict]:
    standard_name = "土壤环境质量 建设用地土壤污染风险管控标准（试行）"
    # 建设用地土壤污染风险筛选值/管制值，单位 mg/kg。
    values = {
        "As": [(20, 120), (60, 140)],
        "Cd": [(20, 47), (65, 172)],
        "Cr(VI)": [(3.0, 30), (5.7, 78)],
        "Cu": [(2000, 8000), (18000, 36000)],
        "Pb": [(400, 800), (800, 2500)],
        "Hg": [(8, 33), (38, 82)],
        "Ni": [(150, 600), (900, 2000)],
    }
    scenarios = [("第一类用地", "development_land_class_1"),
                 ("第二类用地", "development_land_class_2")]
    rows = []
    for factor, pair in values.items():
        for (land, scenario), (screening, control) in zip(scenarios, pair):
            rows.append({
                "factor_name": factor,
                "land_use_type": land,
                "standard_code": "GB 36600-2018",
                "standard_name": standard_name,
                "screening_value": float(screening),
                "intervention_value": None,
                "control_value": float(control),
                "unit": "mg/kg",
                "pH_condition": "not_applicable",
                "soil_condition": None,
                "exposure_scenario": scenario,
                "effective_date": date(2018, 8, 1),
                "version": "2018",
                "source_reference": REF_GB36600,
                "notes": "建设用地土壤污染风险筛选值与管制值。",
            })
    return rows


def _hj255_rows() -> list[dict]:
    return [{
        "factor_name": "remediation_effect_assessment",
        "land_use_type": "建设用地污染地块",
        "standard_code": "HJ 25.5-2018",
        "standard_name": "污染地块风险管控与土壤修复效果评估技术导则（试行）",
        "screening_value": None,
        "intervention_value": None,
        "control_value": None,
        "unit": None,
        "pH_condition": "not_applicable",
        "soil_condition": None,
        "exposure_scenario": "risk_control_and_remediation_effect_assessment",
        "effective_date": date(2018, 12, 29),
        "version": "2018",
        "source_reference": REF_HJ255,
        "notes": "效果评估导则规定风险管控与土壤修复效果评估的内容、程序、方法和技术要求; 非浓度阈值表。",
    }]


# ──────────────────────────────────────────────────────────────────────────
# GB 36600-2018 有机物筛选值/管制值(单位 mg/kg)
#
# 项目组 2026-06-25 补录(授权: "如果有添加进去…备注情况")。
# 根因: 原 _gb36600_rows() 只录 7 种重金属, 有机物全部缺失 → organic_risk
#       查不到阈值 → 南京栖霞四氯乙烯(实测43900, 阈值11, 超标3990倍)被误判"无阈值"。
#
# 置信度三档(遵守 [[ocr-scan-table-hallucination]] 教训, 不凭记忆补阈值):
#   HIGH   — 项目组矢量PDF多模态识别(非扫描OCR, 幻觉风险低),
#            与乙苯7.2/28(项目组亲口纠正web搜28错)同源交叉印证;
#   MEDIUM — 权威CSV "项目组核对原文,high"(项目组未亲识别该行, 采纳项目组核对值, 待最终复核);
#   LOW    — 国标无单项筛选值, 族群匹配参考同族(仅作超标筛查, 必须补权威阈值后方可定论)。
# 录入 factor_name 与因子字典保持一致(如"䓛"=国标"䓬/䓝"异体字; "苯并芘"=苯并[a]芘简称)。
# ──────────────────────────────────────────────────────────────────────────
# 结构: factor_name -> (scr_class1, scr_class2, ctrl_class1, ctrl_class2, table_ref, confidence, note)
_GB36600_ORGANIC: dict[str, tuple] = {
    # ── 挥发性有机物(表1, HIGH) ──
    "四氯乙烯": (11, 53, 34, 183, "表1#20", "high", None),
    "1,2-二氯苯": (560, 560, 560, 560, "表1#28", "high", None),
    "1,4-二氯苯": (5.6, 20, 56, 200, "表1#29", "high", None),
    "二氯甲烷": (94, 616, 300, 2000, "表1#16", "high", None),
    "氯仿": (0.3, 0.9, 5, 10, "表1#9", "high", None),
    "四氯化碳": (0.9, 2.8, 9, 36, "表1#8", "high", None),
    "苯": (1, 4, 10, 40, "表1#26", "high", None),
    "甲苯": (1200, 1200, 1200, 1200, "表1#32", "high", None),
    "乙苯": (7.2, 28, 72, 280, "表1#30", "high", "项目组亲口纠正(web搜28错), 已交叉印证"),
    "氯苯": (68, 270, 200, 1000, "表1#27", "high", None),
    "苯乙烯": (1290, 1290, 1290, 1290, "表1#31", "high", None),
    "邻-二甲苯": (222, 640, 640, 640, "表1#34", "high", None),
    "三氯乙烯": (0.7, 2.8, 7, 20, "表1#23", "high", None),
    "1,2-二氯乙烷": (0.52, 5, 6, 21, "表1#12", "high", None),
    "氯乙烯": (0.12, 0.43, 1.2, 4.3, "表1#25", "high", None),
    # ── 半挥发性有机物 / PAH 单体(表1, HIGH) ──
    "硝基苯": (34, 76, 190, 760, "表1#35", "high", None),
    "苯胺": (92, 260, 211, 663, "表1#36", "high", None),
    "2-氯酚": (250, 2256, 500, 4500, "表1#37", "high", None),
    "苯并[a]蒽": (5.5, 15, 55, 151, "表1#38", "high", None),
    "苯并[a]芘": (0.55, 1.5, 5.5, 15, "表1#39", "high", "GB36600 标志值"),
    "苯并[b]荧蒽": (5.5, 15, 55, 151, "表1#40", "high", None),
    "苯并[k]荧蒽": (55, 151, 550, 1500, "表1#41", "high", None),
    "䓛": (490, 1293, 4900, 12900, "表1#42", "high",
           "因子字典异体字䓛 = 国标䓬(䓝), 同一物质(4环PAH, 䓛)"),
    "茚并[1,2,3-cd]芘": (5.5, 15, 55, 151, "表1#44", "high", None),
    "二苯并[a,h]蒽": (0.55, 1.5, 5.5, 15, "表1#43", "high", None),
    "萘": (25, 70, 255, 700, "表1#45", "high", None),
    # ── 表2 其他项目(HIGH) ──
    "邻苯二甲酸二(2-乙基己基)酯": (42, 121, 420, 1210, "表2#17", "high", None),
    "邻苯二甲酸丁基苄酯": (312, 900, 3120, 9000, "表2#18", "high", None),
    "五氯酚": (1.1, 2.7, 12, 27, "表2#16", "high", None),
    "六氯环戊二烯": (1.1, 5.2, 2.3, 10, "表2#11", "high", None),
    # ── MEDIUM(项目组核对原文权威CSV, 项目组 2026-06-25 未亲识别, 待最终复核) ──
    "多氯联苯": (0.2, 2.0, None, None, "表1末", "medium",
                 "项目组核对原文(权威CSV); 项目组未亲识别, cat2语义待最终复核"),
    "石油烃": (826, 4500, None, None, "附录B", "medium",
              "项目组核对原文(权威CSV); 石油烃(C10-C40); 项目组未亲识别"),
    "DDT类": (1.0, 4.0, None, None, "表1", "medium",
              "项目组核对原文(权威CSV); p,p'-DDT总量; 项目组未亲识别"),
    "六六六": (0.4, 2.0, None, None, "表1", "medium",
              "项目组核对原文(权威CSV); HCH总量; 项目组未亲识别"),
    # ── LOW(族群匹配, 国标无单项筛选值, 仅作超标筛查) ──
    "荧蒽": (490, 1293, None, None, "族群匹配", "low",
             "参考同族䓛(4环非致癌PAH)判别超标; 国标GB36600无单项筛选值, 置信度低"),
    "芘": (490, 1293, None, None, "族群匹配", "low",
           "参考同族䓛(4环非致癌PAH); 国标无单项, 置信度低"),
    "蒽": (25, 70, None, None, "族群匹配", "low",
           "参考同族萘(低环PAH); 国标无单项, 置信度低"),
    "菲": (25, 70, None, None, "族群匹配", "low",
           "参考同族萘(低环PAH); 国标无单项, 置信度低"),
    "苯并[j]荧蒽": (5.5, 15, None, None, "族群匹配", "low",
                    "参考同族苯并[b]荧蒽(5环致癌PAH); j异构体国标无, 置信度低"),
    "苯并芘": (0.55, 1.5, None, None, "等同", "low",
              "等同苯并[a]芘(简称, 因子字典无[a]后缀); 非国标单项命名"),
    "多环芳烃总量": (0.55, 1.5, None, None, "族群匹配", "low",
                    "以BaP计参考苯并[a]芘; 国标无PAHs总量筛选值, 置信度低"),
    "有机氯农药": (1.0, 4.0, None, None, "族群匹配", "low",
                 "参考同族DDT类; 国标无OCP总量筛选值, 置信度低"),
}


def _gb36600_organic_rows() -> list[dict]:
    """GB36600-2018 有机物筛选值/管制值 → standard_thresholds 行(两类用地各一行)。

    organic_risk 取 min(所有 screening_value) 作最严档阈值, 故两类用地都录入,
    自动实现"取严档"保守判定(符合宁可复查不可漏判原则)。
    """
    standard_name = "土壤环境质量 建设用地土壤污染风险管控标准（试行）"
    scenarios = [("第一类用地", "development_land_class_1"),
                 ("第二类用地", "development_land_class_2")]
    rows = []
    for factor_name, vals in _GB36600_ORGANIC.items():
        scr1, scr2, ctrl1, ctrl2, table_ref, conf, note = vals
        for (land, scenario), screening, control in zip(
                scenarios, (scr1, scr2), (ctrl1, ctrl2)):
            rows.append({
                "factor_name": factor_name,
                "land_use_type": land,
                "standard_code": "GB 36600-2018",
                "standard_name": standard_name,
                "screening_value": float(screening),
                "intervention_value": None,
                "control_value": float(control) if control is not None else None,
                "unit": "mg/kg",
                "pH_condition": "not_applicable",
                "soil_condition": None,
                "exposure_scenario": scenario,
                "effective_date": date(2018, 8, 1),
                "version": "2018",
                "source_reference": REF_GB36600,
                "notes": (f"[{conf.upper()}] {table_ref}; "
                          + (note or "项目组2026-06-25矢量PDF多模态识别(与乙苯7.2/28同源交叉印证)")),
            })
    return rows


def seed_rows() -> list[dict]:
    return _gb15618_rows() + _gb36600_rows() + _gb36600_organic_rows() + _hj255_rows()


# 英文符号→中文因子名映射: standard_thresholds 存英文(As/Hg/Pb), factor_dictionary 存中文(砷/汞/铅)
# 修复 load 键不匹配致 factor_id 全 NULL(问题6 三重根因之一)
_EN2ZH = {"As": "砷", "Hg": "汞", "Pb": "铅", "Cr": "铬", "Zn": "锌", "Cd": "镉",
          "Cu": "铜", "Ni": "镍", "Cr(VI)": "铬(六价)", "pH": "pH",
          "benzene": "苯", "toluene": "甲苯", "ethylbenzene": "乙苯", "xylene": "二甲苯"}


def load(db) -> int:
    """v1.0.1 final-audit: 幂等 upsert(按唯一键 standard_code+factor_name+land_use_type+pH_condition)。

    不再全删重建, 只插入缺失记录, 保留已有数据。
    """
    from sqlalchemy import and_
    factors: dict[str, int] = {}
    for f in db.query(FactorDictionary).all():
        factors[f.factor_code] = f.id
        factors[f.factor_name] = f.id
    rows = seed_rows()
    inserted = 0
    skipped = 0
    for row in rows:
        fn = row["factor_name"]
        factor_id = factors.get(fn) or factors.get(_EN2ZH.get(fn, fn))
        # 唯一键: standard_code + factor_name + land_use_type + pH_condition
        existing = db.query(StandardThreshold).filter(and_(
            StandardThreshold.standard_code == row.get("standard_code", ""),
            StandardThreshold.factor_name == fn,
            StandardThreshold.land_use_type == row.get("land_use_type", ""),
            StandardThreshold.pH_condition == row.get("pH_condition", ""),
        )).first()
        if existing:
            skipped += 1
            continue
        db.add(StandardThreshold(factor_id=factor_id, **row))
        inserted += 1
    db.commit()
    print(f"标准阈值幂等upsert: 新增 {inserted} 条, 已存在跳过 {skipped} 条")
    return len(rows)


def main():
    create_all()
    db = SessionLocal()
    try:
        n = load(db)
        print(f"标准阈值库入库完成: {n} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main()
