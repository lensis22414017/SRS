"""方案推荐引擎: 障碍因子 + 技术库 规则匹配。

输入: 场地 Top-N 障碍因子(污染物为主) + 用地类型 + 污染类型。
流程: 匹配适用污染物/用地 -> 禁用条件过滤 -> 打分 -> 结构化理由。
不让 LLM 编方案; 推荐绑定障碍因子; 含禁用条件判断。

纯 python(csv), 可独立测试。
"""
from __future__ import annotations

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TECH_CSV = os.path.join(HERE, "..", "..", "data", "knowledge_base",
                        "technology_library_seed.csv")

RULE_VERSION = "rule_v0.1"

# 障碍因子(元素中文) -> 大类, 用于与技术库 applicable_pollutants 文本匹配
METAL = {"砷", "铅", "铜", "锌", "镉", "铬", "汞", "镍", "铬(六价)", "六价铬"}
ORGANIC_HINT = ("PAHs", "PCBs", "OCPs", "PAEs", "石油烃", "TPH", "苯", "氯")


def load_tech_library(path: str = TECH_CSV) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _factor_class(factor: str) -> str:
    if factor in METAL:
        return "heavy_metal"
    if any(h in factor for h in ORGANIC_HINT):
        return "organic"
    return "other"


def _forbidden_hit(tech: dict, land_use_cn: str, has_organic: bool, has_metal: bool) -> str | None:
    fc = tech.get("forbidden_conditions", "")
    # 简单关键词判断(MVP)
    if "纯重金属污染不适用" in fc and has_metal and not has_organic:
        return fc
    if "永久农用地" in fc and land_use_cn in ("生产用地",):
        return None  # 仅提示, 不强制排除
    return None


def recommend(top_factors: list[str], land_use_cn: str = "生产用地",
              pollution_type: str = "heavy_metal",
              tech_lib: list[dict] | None = None, top_k: int = 5) -> list[dict]:
    techs = tech_lib if tech_lib is not None else load_tech_library()
    factors = [f for f in top_factors if _factor_class(f) in ("heavy_metal", "organic")]
    has_metal = any(_factor_class(f) == "heavy_metal" for f in factors)
    has_organic = any(_factor_class(f) == "organic" for f in factors)

    out = []
    for t in techs:
        pollutants_text = t.get("applicable_pollutants", "")
        land_types = [s.strip() for s in t.get("applicable_land_type", "").split(",")]
        # 用地类型匹配
        if land_use_cn not in land_types:
            continue
        # 适用污染物覆盖
        matched = []
        for f in factors:
            cls = _factor_class(f)
            if (cls == "heavy_metal" and ("重金属" in pollutants_text or f in pollutants_text)) \
               or (cls == "organic" and ("有机物" in pollutants_text or any(h in pollutants_text for h in ORGANIC_HINT))):
                matched.append(f)
        if not matched:
            continue
        # 禁用条件
        forbidden = _forbidden_hit(t, land_use_cn, has_organic, has_metal)
        if forbidden:
            continue
        coverage = len(matched) / max(len(factors), 1)
        cost_pen = {"低": 1.0, "中": 0.8, "高": 0.6}.get(t.get("cost_level", ""), 0.7)
        dur_pen = {"短": 1.0, "中": 0.85, "长": 0.7}.get(t.get("duration_level", ""), 0.8)
        score = round(coverage * 0.6 + cost_pen * 0.25 + dur_pen * 0.15, 4)
        reason = (
            f"针对本场地关键障碍因子 [{', '.join(matched)}]: {t['tech_name']} "
            f"适用于 {pollutants_text}; 适用用地含 {land_use_cn}; "
            f"优点: {t.get('advantages','')}; 局限: {t.get('limitations','')}; "
            f"成本{t.get('cost_level','')}/工期{t.get('duration_level','')}; "
            f"二次风险: {t.get('secondary_risk','')}; 禁用条件: {t.get('forbidden_conditions','')}; "
            f"来源: {t.get('source','')}。")
        out.append({
            "tech_name": t["tech_name"], "matched_factors": matched,
            "coverage": round(coverage, 3), "match_score": score,
            "cost_level": t.get("cost_level"), "duration_level": t.get("duration_level"),
            "applicable_stage": t.get("applicable_stage"),
            "forbidden_conditions": t.get("forbidden_conditions"),
            "source": t.get("source"), "reason": reason,
        })
    out.sort(key=lambda x: x["match_score"], reverse=True)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out[:top_k]
