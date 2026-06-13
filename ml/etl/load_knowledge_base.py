"""统一障碍因子知识库 V1.0 -> factor_dictionary + threshold_rules。

设计: parse (纯 pandas, 可独立测试) 与 load (SQLAlchemy 入库) 分离。
可重复运行: load 采用 upsert 语义 (按 factor_code / 规则唯一键)。

源字段:
  unified_id, factor_id, level1_category, factor_name, application_scenario,
  applicable_scope, land_type_original, threshold_min, threshold_max, unit,
  threshold_original, standard_source, source
"""
from __future__ import annotations

import os
import sys

import pandas as pd

CATEGORY_TO_TYPE = {
    "化学性质": "chemical",
    "物理性质": "physical",
    "环境指标": "pollutant",
    "肥力指标": "fertility",
    "生物指标": "biological",
}
SCOPE_MAP = {"生产": "production", "生产用地": "production", "production": "production",
             "生态": "ecology", "生态用地": "ecology", "ecology": "ecology"}


def _num(v):
    try:
        if pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_knowledge_base(csv_path: str):
    """返回 (factors, rules)。factors 按 factor_name 去重。"""
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lstrip("﻿") for c in df.columns]

    factors: dict[str, dict] = {}
    rules: list[dict] = []
    for _, r in df.iterrows():
        name = str(r["factor_name"]).strip()
        if not name or name.lower() == "nan":
            continue
        cat = str(r.get("level1_category", "")).strip()
        if name not in factors:
            factors[name] = {
                "factor_code": name,
                "factor_name": name,
                "level1_category": cat or None,
                "factor_type": CATEGORY_TO_TYPE.get(cat),
                "default_unit": (str(r.get("unit")).strip()
                                 if pd.notna(r.get("unit")) else None),
                "source": "统一障碍因子知识库_V1.0",
            }
        scope_raw = str(r.get("applicable_scope", "")).strip()
        rules.append({
            "factor_code": name,
            "application_scenario": (str(r.get("application_scenario")).strip()
                                     if pd.notna(r.get("application_scenario")) else None),
            "applicable_scope": SCOPE_MAP.get(scope_raw, scope_raw or None),
            "land_type": (str(r.get("land_type_original")).strip()
                          if pd.notna(r.get("land_type_original")) else None),
            "threshold_min": _num(r.get("threshold_min")),
            "threshold_max": _num(r.get("threshold_max")),
            "unit": (str(r.get("unit")).strip() if pd.notna(r.get("unit")) else None),
            "threshold_original": (str(r.get("threshold_original")).strip()
                                   if pd.notna(r.get("threshold_original")) else None),
            "standard_source": (str(r.get("standard_source")).strip()
                                if pd.notna(r.get("standard_source")) else None),
            "version": "V1.0",
        })
    return list(factors.values()), rules


def load(db, csv_path: str):
    """入库 (SQLAlchemy)。仅在安装了 backend 依赖的环境中调用。"""
    from app.models import FactorDictionary, ThresholdRule  # 延迟导入

    factors, rules = parse_knowledge_base(csv_path)
    code_to_id: dict[str, int] = {}
    for f in factors:
        obj = db.query(FactorDictionary).filter_by(factor_code=f["factor_code"]).first()
        if obj is None:
            obj = FactorDictionary(**f)
            db.add(obj)
            db.flush()
        code_to_id[f["factor_code"]] = obj.id
    db.query(ThresholdRule).delete()  # 规则全量重建 (V1.0)
    for r in rules:
        fid = code_to_id.get(r.pop("factor_code"))
        if fid:
            db.add(ThresholdRule(factor_id=fid, **r))
    db.commit()
    return len(factors), len(rules)


def main():
    csv_path = (sys.argv[1] if len(sys.argv) > 1 else
                os.path.join(os.path.dirname(__file__), "..", "..",
                             "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv"))
    factors, rules = parse_knowledge_base(csv_path)
    print(f"解析: 因子 {len(factors)} 种, 阈值规则 {len(rules)} 条")
    cats = {}
    for f in factors:
        cats[f["level1_category"]] = cats.get(f["level1_category"], 0) + 1
    print("按一级分类:", cats)


if __name__ == "__main__":
    main()
