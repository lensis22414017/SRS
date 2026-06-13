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


def seed_rows() -> list[dict]:
    return _gb15618_rows() + _gb36600_rows() + _hj255_rows()


def load(db) -> int:
    factors = {f.factor_code: f.id for f in db.query(FactorDictionary).all()}
    db.query(StandardThreshold).delete()
    rows = seed_rows()
    for row in rows:
        factor_id = factors.get(row["factor_name"])
        db.add(StandardThreshold(factor_id=factor_id, **row))
    db.commit()
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
