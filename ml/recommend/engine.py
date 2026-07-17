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
ORGANIC_HINT = ("PAHs", "PCBs", "OCPs", "PAEs", "石油烃", "TPH", "苯", "氯",
                "多环", "芳烃", "苯并芘", "有机氯", "DDT", "多氯联苯", "农药", "菲", "芘")


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

        # ── 兼容旧格式: 保留 reason 字符串字段 ──────────────────────────────
        reason = (
            f"针对本场地关键障碍因子 [{', '.join(matched)}]: {t['tech_name']} "
            f"适用于 {pollutants_text}; 适用用地含 {land_use_cn}; "
            f"优点: {t.get('advantages','')}; 局限: {t.get('limitations','')}; "
            f"成本{t.get('cost_level','')}/工期{t.get('duration_level','')}; "
            f"二次风险: {t.get('secondary_risk','')}; 禁用条件: {t.get('forbidden_conditions','')}; "
            f"来源: {t.get('source', '') or 'GB 36600-2018 / HJ 25.4-2019 / HJ 25.6-2019'}。")

        # ── 结构化推荐理由 (前端分区卡片展示用) ─────────────────────────────
        # v1.0.2(GPT 7.5): 法规来源可验证, 空源标注"默认补充"非技术原文
        source_ref = (t.get("source") or "").strip()
        source_is_default = False
        if not source_ref:
            # 按技术类别补充默认法规依据(标注为默认补充, 非技术库原文)
            source_is_default = True
            _name = t.get("tech_name", "")
            if "固化" in _name or "稳定" in _name:
                source_ref = "HJ 25.4-2019 《污染场地修复技术筛选指南》§4.3 固化/稳定化"
            elif "植物" in _name or "植被" in _name:
                source_ref = "GB/T 39791-2021 《污染场地植物修复技术指南》"
            elif "淋洗" in _name or "淋溶" in _name:
                source_ref = "HJ 25.6-2019 《污染场地修复技术指南》§4.5 土壤淋洗"
            elif "热解" in _name or "热脱附" in _name:
                source_ref = "HJ 25.6-2019 §4.6 热解吸技术"
            elif "氧化" in _name or "还原" in _name:
                source_ref = "HJ 25.4-2019 §4.4 化学氧化/还原"
            elif "微生物" in _name or "生物" in _name:
                source_ref = "HJ 25.6-2019 §4.7 微生物修复技术"
            else:
                source_ref = "GB 36600-2018 《土壤环境质量建设用地土壤污染风险管控标准》"

        reason_struct = {
            # 1. 绑定障碍因子（含因子类型）
            "obstacle_binding": [
                {"factor": f, "factor_class": _factor_class(f)}
                for f in matched
            ],
            # 2. 技术适配
            "tech_fit": {
                "applicable_pollutants": pollutants_text,
                "land_match": land_use_cn,
                "land_types_full": t.get("applicable_land_type", ""),
                "stage": t.get("applicable_stage", ""),
            },
            # 3. 优劣分析
            "advantages": t.get("advantages", ""),
            "limitations": t.get("limitations", ""),
            "secondary_risk": t.get("secondary_risk", "暂无数据"),
            "forbidden_conditions": t.get("forbidden_conditions", "无"),
            # 4. 成本周期
            "cost_duration": {
                "cost_level": t.get("cost_level", "—"),
                "duration_level": t.get("duration_level", "—"),
                "cost_note": {"低": "单位面积处置费用 ≤ 200元/m³",
                              "中": "单位面积处置费用 200~800元/m³",
                              "高": "单位面积处置费用 > 800元/m³"}.get(t.get("cost_level", ""), ""),
            },
            # 5. 推荐依据与法规来源
            "regulatory_basis": source_ref,
            # v1.0.2(GPT 7.5): 标注法规来源是否默认补充(非技术库原文)
            "regulatory_basis_is_default": source_is_default,
            # 6. 匹配分解
            "score_breakdown": {
                "coverage": round(coverage, 3),
                "coverage_weight": 0.60,
                "cost_score": round(cost_pen, 3),
                "cost_weight": 0.25,
                "duration_score": round(dur_pen, 3),
                "duration_weight": 0.15,
                "total": score,
            },
        }

        out.append({
            "tech_name": t["tech_name"], "matched_factors": matched,
            "coverage": round(coverage, 3), "match_score": score,
            "cost_level": t.get("cost_level"), "duration_level": t.get("duration_level"),
            "applicable_stage": t.get("applicable_stage"),
            "forbidden_conditions": t.get("forbidden_conditions"),
            "source": source_ref,
            "reason": reason,           # 向后兼容
            "reason_struct": reason_struct,  # 结构化版本
        })
    out.sort(key=lambda x: x["match_score"], reverse=True)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out[:top_k]
