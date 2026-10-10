"""GB/HJ 标准阈值库入库。

说明:
- GB 15618-2018 / GB 36600-2018 为浓度阈值标准;
- HJ 25.5-2018 为污染地块风险管控与修复效果评估技术导则, 不提供单因子浓度筛选值,
  因此只入库标准元信息行, screening/control 保持 None。
"""
from __future__ import annotations

import os
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
    # v1.2: 表3 风险管制值(镉/汞/砷/铅/铬), 经生态环境部官方 PDF 核对; 铜/镍/锌无管制值
    controls = {
        "Cd": [1.5, 2.0, 3.0, 4.0],
        "Hg": [2.0, 2.5, 4.0, 6.0],
        "As": [200, 150, 120, 100],
        "Pb": [400, 500, 700, 1000],
        "Cr": [800, 850, 1000, 1300],
    }
    ph_conditions = ["pH<=5.5", "5.5<pH<=6.5", "6.5<pH<=7.5", "pH>7.5"]
    rows = []
    for factor, vals in values.items():
        for i, (ph, val) in enumerate(zip(ph_conditions, vals)):
            rows.append({
                "factor_name": factor,
                "land_use_type": "农用地",
                "standard_code": "GB 15618-2018",
                "standard_name": standard_name,
                "screening_value": float(val),
                "intervention_value": None,
                "control_value": (float(controls[factor][i]) if factor in controls else None),
                "unit": "mg/kg",
                "pH_condition": ph,
                "soil_condition": "其他农用地",
                "exposure_scenario": "agricultural_land",
                "effective_date": date(2018, 8, 1),
                "version": "2018",
                "source_reference": REF_GB15618,
                "notes": "农用地土壤污染风险筛选值(其他农用地口径)。",
            })
    # v1.2.1(R01/R03): 表1 水田口径(镉汞砷铅铬), 来源 data/standards/gb15618_2018_official.csv(官方 PDF 逐行核对),
    # 使课题一 KOS 与利用方向门禁在 farmland_type=水田 时采用同一筛选值。
    import csv as _csv
    from app.core.config import resource_root
    path = os.path.join(resource_root(), "data", "standards", "gb15618_2018_official.csv")
    ctl = {(r["factor"], r["pH_bin"]): float(r["value"]) for r in _csv.DictReader(open(path, encoding="utf-8"))
           if r["value_type"] == "control"}
    for r in _csv.DictReader(open(path, encoding="utf-8")):
        if r["value_type"] != "screening" or r["farmland"] != "水田":
            continue
        rows.append({
            "factor_name": r["factor"], "land_use_type": "水田", "standard_code": "GB 15618-2018",
            "standard_name": standard_name, "screening_value": float(r["value"]), "intervention_value": None,
            "control_value": ctl.get((r["factor"], r["pH_bin"])), "unit": r["unit"] or "mg/kg",
            "pH_condition": r["pH_bin"], "soil_condition": "水田", "exposure_scenario": "agricultural_land_paddy",
            "effective_date": date(2018, 8, 1), "version": "2018", "source_reference": REF_GB15618,
            "notes": f"[OFFICIAL] {r['source']}; 水田口径",
        })
    return rows


def _gb36600_official_records() -> list[dict]:
    """v1.2: GB 36600-2018 表1(45 项) + 表2(40 项) 全部筛选值/管制值。

    唯一来源: data/standards/gb36600_2018_official.csv, 由生态环境部官网发布的标准 PDF
    (W020190626596188930731.pdf, sha256 63accde7…696c) 逐行转录, 并与统一障碍因子知识库
    V1.0 的 170 条筛选值独立比对(164 条一致, 6 条为知识库 ×10⁻ⁿ 指数解析错误)。
    不再使用 v1.0.x 中的"族群匹配/等同/待复核"替代阈值。
    """
    import csv as _csv
    from app.core.config import resource_root
    path = os.path.join(resource_root(), "data", "standards", "gb36600_2018_official.csv")
    with open(path, encoding="utf-8") as fh:
        return list(_csv.DictReader(fh))


# 名称别名: 因子字典/历史数据中使用的写法 → 标准原文名称(同一物质, 非替代)
GB36600_NAME_ALIASES = {
    "苯并芘": "苯并[a]芘",
    "石油烃": "石油烃(C10-C40)",
    "多氯联苯": "多氯联苯(总量)",
    "间二甲苯+对二甲苯": "间-二甲苯+对-二甲苯",
    "邻二甲苯": "邻-二甲苯",
}
_GB36600_SYMBOL = {"砷": "As", "镉": "Cd", "铬（六价）": "Cr(VI)", "铜": "Cu", "铅": "Pb", "汞": "Hg", "镍": "Ni"}


def _gb36600_rows() -> list[dict]:
    standard_name = "土壤环境质量 建设用地土壤污染风险管控标准（试行）"
    scenarios = [("第一类用地", "development_land_class_1", "screening_cat1", "control_cat1"),
                 ("第二类用地", "development_land_class_2", "screening_cat2", "control_cat2")]
    recs = _gb36600_official_records()
    names_by_official = {}
    for alias, off in GB36600_NAME_ALIASES.items():
        names_by_official.setdefault(off, []).append(alias)
    rows = []
    for rec in recs:
        official = rec["pollutant"]
        names = [_GB36600_SYMBOL.get(official, official)] + names_by_official.get(official, [])
        for name in names:
            for land, scenario, sk, ck in scenarios:
                rows.append({
                    "factor_name": name,
                    "land_use_type": land,
                    "standard_code": "GB 36600-2018",
                    "standard_name": standard_name,
                    "screening_value": float(rec[sk]),
                    "intervention_value": None,
                    "control_value": float(rec[ck]),
                    "unit": "mg/kg",
                    "pH_condition": "not_applicable",
                    "soil_condition": None,
                    "exposure_scenario": scenario,
                    "effective_date": date(2018, 8, 1),
                    "version": "2018",
                    "source_reference": REF_GB36600,
                    "notes": (f"[OFFICIAL] {rec['table']}#{rec['item_no']} CAS {rec['cas']}; {rec['page']}"
                              + (f"; 别名→{official}" if name not in (official, _GB36600_SYMBOL.get(official)) else "")),
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
    corrected: list[tuple] = []
    # v1.2: 删除 v1.0.x 系统种子中的非标准替代阈值(族群匹配/等同/待复核, notes 以 [LOW]/[MEDIUM] 开头)。
    # 这些名称不在 GB 36600 表1/表2 中, 保留会让"无标准值"的物质被判为"未超标/已超标"。
    removed = (db.query(StandardThreshold)
               .filter(StandardThreshold.standard_code == "GB 36600-2018")
               .filter((StandardThreshold.notes.like("[LOW]%")) | (StandardThreshold.notes.like("[MEDIUM]%")))
               .delete(synchronize_session=False))
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
            # v1.2: GB 36600 官方值为唯一来源 — 旧库中数值不一致的系统种子行就地更正(记日志)
            if (row.get("standard_code") in ("GB 36600-2018", "GB 15618-2018")
                    and (existing.screening_value != row["screening_value"]
                         or existing.control_value != row["control_value"])):
                corrected.append((fn, row["land_use_type"], existing.screening_value,
                                  existing.control_value, row["screening_value"], row["control_value"]))
                existing.screening_value = row["screening_value"]
                existing.control_value = row["control_value"]
                existing.notes = row["notes"] + " (v1.2 由旧种子值更正)"
            skipped += 1
            continue
        db.add(StandardThreshold(factor_id=factor_id, **row))
        inserted += 1
    db.commit()
    print(f"标准阈值幂等upsert: 新增 {inserted} 条, 已存在 {skipped} 条, 更正 {len(corrected)} 条, "
          f"移除非标准替代阈值 {removed} 条")
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
