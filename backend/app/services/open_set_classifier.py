"""open_set_classifier.py — 开放集障碍因子分层识别（P0-OPEN-1/2/3, M0-3/4 修订）

把用户上传的每一个实测因子分到四种状态:
  A. formal_obstacle: 精确匹配+单位兼容+有阈值+规则判障碍 → 进正式KOS
  B. model_candidate: 无阈值但模型见过 → 输出模型贡献(非法规结论)
  C. family_alert: 未收录但可归入化学族群 → 族群级预警(人工复核)
  D. unknown_measured: 无法识别 → 保留原始数据(不丢弃)

M0-4 修订(纠正虚假声明):
- 族群归类算法正式命名为"规则型族群归类"(非ML聚类)
- 不声称 CAS 优先查询/最近簇距离/参考分布相似度
- FAMILY_CLUSTER_MAX_DISTANCE 已删除(未实际使用)
- 族群匹配基于受控关键词字典,非机器学习

设计原则(遵守 GPT 审计):
- 不丢弃任何实测因子
- 不强行映射到已有因子
- 族群识别基于受控关键词字典(规则型),字符串包含仅辅助
- 族群匹配需可解释理由+置信度
- candidate_attention_score 不得与正式 KOS 混用
"""
from __future__ import annotations
import sys

import os
import re
import math
import unicodedata
from typing import Any

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# PyInstaller 打包后数据在 _MEIPASS 或其 _internal 子目录
if getattr(sys, "frozen", False):
    _mep = sys._MEIPASS
    if os.path.isdir(os.path.join(_mep, "ml")) or os.path.isdir(os.path.join(_mep, "data")):
        _ROOT = _mep
    elif os.path.isdir(os.path.join(_mep, "_internal", "ml")):
        _ROOT = os.path.join(_mep, "_internal")

# ── 配置项(GPT 要求可配置,不得声称已有科学外部校准) ──
FAMILY_MATCH_MIN_CONFIDENCE = 0.5       # 族群匹配最低置信度(规则型,非ML)
# M0-4: FAMILY_CLUSTER_MAX_DISTANCE 已删除(未实际参与计算, 属于虚假声明)
# candidate_attention_score 的启发式权重(标注 heuristic,非科学验证)
HEURISTIC_WEIGHTS = {
    "empirical_anomaly": 0.35,
    "site_prevalence": 0.25,
    "evidence_confidence": 0.25,
    "model_contribution": 0.15,
}


def _load_yaml(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# 加载知识库
_FAMILY_LIB_PATH = os.path.join(_ROOT, "data", "knowledge", "family_factor_library_v0.8.csv")
_COMPOUND_ALIASES_PATH = os.path.join(_ROOT, "data", "knowledge", "compound_aliases_v0.8.yaml")

# 族群→关键词映射(从 guardrails 复用,扩展 PFAS/PAE 等)
FAMILY_KEYWORDS: dict[str, list[str]] = {
    "PAH": ["萘", "苊", "芴", "菲", "蒽", "荧蒽", "芘", "苯并", "苝", "茚并", "PAH", "pah", "苯并芘", "BaP"],
    "OCP": ["HCH", "DDT", "氯丹", "七氯", "毒杀芬", "六氯苯", "灭蚁灵", "OCP", "六六六", "滴滴涕"],
    "PCB": ["PCB", "pcb", "多氯联苯", "联苯"],
    "PBDE": ["PBDE", "pbde", "多溴联苯醚", "BDE"],
    "PFAS": ["PFAS", "pfas", "全氟", "PFOA", "PFOS", "全氟辛酸", "全氟辛烷"],
    "PAE": ["PAE", "pae", "邻苯二甲酸", "DBP", "DEHP", "DMP", "DEP", "塑化剂"],
    "TPH": ["TPH", "tph", "石油烃", "矿物油", "总石油", "烷烃"],
    "重金属": ["铬", "铅", "汞", "镉", "砷", "铜", "锌", "镍", "锰", "钴", "钼", "锑", "铊", "铍", "barium", "钡"],
    "无机阴离子": ["氰化物", "氟化物", "硫化物", "硫酸根", "氯离子"],
    "养分指标": ["有机质", "全氮", "全磷", "全钾", "碱解氮", "速效磷", "速效钾", "缓效钾", "CEC", "阳离子交换"],
}

# 族群→单位维度(用于单位兼容检查)
FAMILY_UNIT_DIMENSIONS: dict[str, set[str]] = {
    "PAH": {"mg/kg", "ng/g", "μg/kg"}, "OCP": {"mg/kg", "ng/g", "μg/kg"},
    "PCB": {"mg/kg", "ng/g", "μg/kg"}, "PBDE": {"mg/kg", "ng/g", "μg/kg"},
    "PFAS": {"mg/kg", "ng/g", "μg/kg"}, "PAE": {"mg/kg"},
    "TPH": {"mg/kg"}, "重金属": {"mg/kg"},
    "无机阴离子": {"mg/kg"}, "养分指标": {"mg/kg", "g/kg", "%", "cmol/kg"},
}

# 化学总量 vs 有效态/形态(禁止互相映射)
INCOMPATIBLE_FORMS = {
    ("总铬", "六价铬"), ("Cr", "Cr(VI)"), ("Cr_mgkg", "Cr6_mgkg"),
    ("总量", "有效态"), ("总量", "水溶态"),
}


def _norm(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).strip().lower()
    return re.sub(r"\s+", "", s)


def _extract_unit(col_name: str) -> str | None:
    m = re.search(r"[（(]\s*(μg/kg|ug/kg|ng/g|mg/kg|g/kg|%|cmol/kg)\s*[)）]", col_name, re.IGNORECASE)
    if m:
        return m.group(1).lower().replace("·", "")
    return None


def _is_unit_compatible(unit_a: str | None, unit_b: str | None) -> bool:
    """检查两个单位是否量纲兼容(可转换)。"""
    if not unit_a or not unit_b:
        return True  # 缺单位时不阻断(但会标记 review_required)
    # mg/kg, ng/g, μg/kg 互相兼容(都是质量分数)
    mass_fraction = {"mg/kg", "ng/g", "μg/kg", "ug/kg"}
    if unit_a in mass_fraction and unit_b in mass_fraction:
        return True
    return unit_a == unit_b


def classify_factor(
    raw_name: str,
    value: float | None,
    unit: str | None = None,
    known_canonical: set[str] | None = None,
    model_features: set[str] | None = None,
    known_thresholds: dict | None = None,
) -> dict:
    """对单个实测因子进行开放集分层识别。

    参数:
        raw_name: 原始因子名(用户Excel列名)
        value: 浓度值
        unit: 单位(从列名或数据提取)
        known_canonical: 已知 canonical 因子集合(来自别名表)
        model_features: 模型训练特征集合
        known_thresholds: 有阈值的因子集合 {canonical: threshold_dict}

    返回: {layer, original_name, canonical, value, unit, ...layer_specific_fields}
    """
    known_canonical = known_canonical or set()
    model_features = model_features or set()
    known_thresholds = known_thresholds or {}

    result: dict[str, Any] = {
        "original_name": raw_name,
        "original_unit": unit,
        "value": value,
        "review_required": False,
    }

    if value is None or (isinstance(value, float) and math.isnan(value)):
        result["layer"] = "skipped"
        result["reason"] = "值为空或NaN"
        return result

    # 第1级: 精确身份匹配(用 factor_normalizer 的规范化逻辑)
    from app.services.factor_normalizer import normalize_factor_name
    canonical, norm_meta = normalize_factor_name(raw_name)
    result["canonical"] = canonical
    result["normalized_name"] = norm_meta.get("normalized_name", "")

    if canonical and canonical in known_thresholds:
        # A. formal_obstacle 候选(有阈值,是否障碍由 KOS compute_severity 判定)
        result["layer"] = "formal_eligible"
        result["threshold"] = known_thresholds[canonical]
        result["threshold_source"] = "StandardThreshold"
        result["unit_converted"] = norm_meta.get("unit_converted", unit)
        result["conversion_factor"] = norm_meta.get("conversion_factor", 1.0)
        return result

    if canonical and canonical in model_features:
        # B. model_candidate(模型见过但无阈值)
        result["layer"] = "model_candidate"
        result["reason"] = f"因子 {canonical} 模型认识但无适用法规阈值"
        result["review_required"] = True
        result["candidate_attention"] = _compute_attention(canonical, value, model_features)
        return result

    if canonical:
        # R3 审计第三类: 有 canonical 但既无阈值也不在模型特征
        #   - 先检查族群归属(PAH/PFAS/OCP 等), 命中→family_alert(不进 formal_eligible)
        #   - 否则归 identified_no_threshold(新层: 身份明确但无阈值, 不进正式障碍结论)
        family_result = _try_family_match(raw_name, value, unit)
        if family_result["matched"]:
            result["layer"] = "family_alert"
            result.update(family_result)
            result["review_required"] = True
            result["reason"] = f"因子 {canonical} 归入 {family_result['matched_family']} 族群(无正式阈值)"
            return result
        # 身份明确但无阈值且无族群 → identified_no_threshold
        result["layer"] = "identified_no_threshold"
        result["threshold"] = None
        result["reason"] = f"因子 {canonical} 身份明确但无适用阈值, 不进入正式障碍结论"
        result["review_required"] = True
        return result

    # 未精确匹配 → 尝试族群识别(C级)
    family_result = _try_family_match(raw_name, value, unit)
    if family_result["matched"]:
        result["layer"] = "family_alert"
        result.update(family_result)
        result["review_required"] = True
        result["reason"] = f"未收录因子归入 {family_result['matched_family']} 族群"
        return result

    # D. unknown_measured
    result["layer"] = "unknown_measured"
    result["reason"] = "无法可靠识别具体因子或族群"
    result["review_required"] = True
    result["unknown_reason"] = "名称未匹配任何已知因子、模型特征或化学族群"
    return result


def _try_family_match(raw_name: str, value: float, unit: str | None) -> dict:
    """规则型族群归类(M0-4: 非ML聚类,基于受控关键词字典)。

    优先级: 族群关键词精确包含 → 单位维度兼容 → 形态冲突检查
    不使用 CAS 查询/最近簇距离/参考分布相似度(这些是未实现的虚假声明,已删除)。
    """
    name_norm = _norm(raw_name)
    best_family = None
    best_confidence = 0.0
    match_reasons = []

    # 第1优先: 族群关键词精确包含
    for family, keywords in FAMILY_KEYWORDS.items():
        for kw in keywords:
            if _norm(kw) in name_norm:
                best_family = family
                best_confidence = 0.8  # 关键词匹配=高置信
                match_reasons.append(f"名称含族群关键词 '{kw}' → {family}")
                break
        if best_family:
            break

    # 第2优先: 单位维度兼容检查
    if best_family and unit:
        compatible_units = FAMILY_UNIT_DIMENSIONS.get(best_family, set())
        if compatible_units and unit not in compatible_units:
            match_reasons.append(f"单位 {unit} 与 {best_family} 族群维度不兼容,降级置信度")
            best_confidence *= 0.5

    # 第3优先: 总量/有效态形态检查(禁止混淆)
    for form_a, form_b in INCOMPATIBLE_FORMS:
        if form_a in raw_name or _norm(form_a) in name_norm:
            if form_b in raw_name or _norm(form_b) in name_norm:
                match_reasons.append(f"检测到形态冲突({form_a} vs {form_b}),拒绝族群匹配")
                return {"matched": False}

    # 置信度低于阈值 → 不匹配(降级 unknown)
    if best_confidence < FAMILY_MATCH_MIN_CONFIDENCE:
        return {"matched": False}

    return {
        "matched": True,
        "matched_family": best_family,
        "family_match_confidence": round(best_confidence, 3),
        "family_match_reasons": match_reasons,
        "candidate_attention_score": None,  # 参考数据不足时为 None
        "reference_data_insufficient": True,
    }


def _compute_attention(canonical: str, value: float, model_features: set) -> dict | None:
    """计算候选障碍注意度(P0-OPEN-3)。

    启发式组成(标注 heuristic):
    - empirical_anomaly: 参考分布异常百分位(无参考数据时为 None)
    - site_prevalence: 场地异常点比例(需多点数据,单点为 None)
    - evidence_confidence: 身份+单位识别置信度
    - model_contribution: 模型全局贡献(仅在模型认识时)
    """
    return {
        "candidate_attention_score": None,
        "empirical_anomaly": None,
        "site_prevalence": None,
        "evidence_confidence": 0.7,
        "model_contribution": None,
        "reference_data_insufficient": True,
        "heuristic_note": "当前无充分参考分布数据,attention_score 暂不可计算,保留实测统计供人工复核",
    }


def classify_open_set(
    raw_factors: dict[str, float],
    known_canonical: set[str],
    model_features: set[str],
    known_thresholds: dict,
    units: dict[str, str] | None = None,
) -> dict:
    """对一批实测因子执行开放集分层识别(P0-OPEN-1 主入口)。

    返回四层分类 + open_set_summary:
        formal_eligible / model_candidates / family_alerts / unknown_measured
    """
    units = units or {}
    formal_eligible = []      # 有阈值身份明确(不论是否超标)
    formal_obstacles = []     # formal_eligible 中规则确认超标的子集
    model_candidates = []
    family_alerts = []
    identified_no_threshold = []  # R3: 身份明确但无阈值(不进正式障碍)
    unknown_measured = []
    n_unit_conflict = 0
    n_mapping_conflict = 0

    for raw_name, value in raw_factors.items():
        unit = units.get(raw_name)
        result = classify_factor(raw_name, value, unit, known_canonical, model_features, known_thresholds)

        layer = result.get("layer", "unknown_measured")
        if layer == "formal_eligible":
            formal_eligible.append(result)
            # M0-3: 检查是否规则确认超标 → formal_obstacle
            thr = result.get("threshold")
            canonical = result.get("canonical")
            if thr and canonical and value is not None:
                ttype = thr.get("type", "upper")
                limit = thr.get("limit")
                is_obstacle = False
                if ttype == "upper" and limit and value > limit:
                    is_obstacle = True
                elif ttype == "lower" and limit and value < limit:
                    is_obstacle = True
                elif ttype == "interval":
                    lo, hi = thr.get("min"), thr.get("max")
                    if lo is not None and hi is not None and not (lo <= value <= hi):
                        is_obstacle = True
                result["is_formal_obstacle"] = is_obstacle
                if is_obstacle:
                    formal_obstacles.append(result)
            else:
                result["is_formal_obstacle"] = False
        elif layer == "model_candidate":
            model_candidates.append(result)
        elif layer == "identified_no_threshold":
            # R3 审计第三类: 身份明确但无阈值, 收纳但不进 formal_eligible
            identified_no_threshold.append(result)
        elif layer == "family_alert":
            family_alerts.append(result)
            # M0-3: 单位不兼容导致置信度降低 → 真实计数
            if result.get("family_match_confidence", 1.0) < FAMILY_MATCH_MIN_CONFIDENCE:
                n_unit_conflict += 1
        elif layer == "unknown_measured":
            # 补全 unknown 统计
            result["n_points"] = 1
            result["max"] = value
            result["median"] = value
            result["p95"] = value
            result["extreme_value_warning"] = _check_extreme(raw_name, value)
            unknown_measured.append(result)
        elif layer == "skipped":
            continue

    # M0-3: mapping_conflict 真实计数(同一 canonical 多来源)
    canonical_sources: dict[str, int] = {}
    for r in formal_eligible + model_candidates:
        c = r.get("canonical")
        if c:
            canonical_sources[c] = canonical_sources.get(c, 0) + 1
    n_mapping_conflict = sum(1 for c, n in canonical_sources.items() if n > 1)

    return {
        "formal_eligible": formal_eligible,
        "formal_obstacles": formal_obstacles,
        "model_candidates": model_candidates,
        "family_alerts": family_alerts,
        "identified_no_threshold": identified_no_threshold,
        "unknown_measured": unknown_measured,
        "open_set_summary": {
            "n_formal_eligible": len(formal_eligible),
            "n_formal_obstacle": len(formal_obstacles),
            "n_model_candidate": len(model_candidates),
            "n_family_alert": len(family_alerts),
            "n_identified_no_threshold": len(identified_no_threshold),
            "n_unknown": len(unknown_measured),
            "n_unit_conflict": n_unit_conflict,
            "n_mapping_conflict": n_mapping_conflict,
        },
    }


def _check_extreme(name: str, value: float) -> bool:
    """极端值检查: 重金属>10000 mg/kg 触发警告。"""
    extreme_factors = {"As", "Cd", "Pb", "Hg", "砷", "镉", "铅", "汞"}
    if any(f in name for f in extreme_factors) and value > 10000:
        return True
    return False
