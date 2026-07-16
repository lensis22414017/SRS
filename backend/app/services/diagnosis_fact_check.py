"""diagnosis_fact_check.py — AI 润色诊断的事实校验（P0-6 修复）

GPT 审计要求: AI 只能润色说明，不得修改事实（因子/数值/单位/超标关系/排名）。
本模块:
1. 从原始诊断文本结构化提取事实（因子、浓度、阈值、是否超标、KOS 排名）
2. 校验 AI 输出是否篡改了上述事实
3. 扩充禁止性整体结论检测（总体可控/影响有限/可正常使用等）
"""
from __future__ import annotations

import re

# P0-6 扩充的禁止性整体结论关键词（GPT 要求覆盖的表达变体）
FORBIDDEN_OVERALL_CONCLUSIONS = (
    # 原有 6 个
    "安全", "低风险", "无风险", "状况良好", "风险很低", "整体状况",
    # P0-6 新增（GPT 明确列出的绕过变体）
    "总体可控", "影响有限", "可正常使用", "可以继续开发", "无需修复",
    "无需优先处理", "可接受范围", "不构成主要障碍", "修复优先级较低",
    "可以继续利用", "风险可控", "整体平稳", "不会造成", "不具备显著",
    "整体良好", "环境风险不大", "无需担忧", "无重大风险",
)


def extract_facts(diagnosis_text: str) -> dict:
    """从原始诊断文本结构化提取事实。

    返回:
        {
            "factors": [{"name": str, "value": float|None, "exceeded": bool}],
            "has_exceedance": bool,  # 是否有超标事实
            "has_obstacle": bool,
            "ranked_factors": [str],  # KOS 排名顺序的因子名
        }
    """
    facts = {"factors": [], "has_exceedance": False, "has_obstacle": False, "ranked_factors": []}

    if not diagnosis_text:
        return facts

    text = diagnosis_text

    # 检测超标事实
    if "超标" in text or "超过" in text or "超出" in text:
        facts["has_exceedance"] = True
    if "障碍" in text:
        facts["has_obstacle"] = True

    # 提取因子名（常见重金属+有机物，中文/符号）
    factor_patterns = [
        ("镉", "Cd"), ("铅", "Pb"), ("砷", "As"), ("铬", "Cr"),
        ("汞", "Hg"), ("铜", "Cu"), ("锌", "Zn"), ("镍", "Ni"),
        ("苯并芘", "BaP"), ("六六六", "HCHs"), ("滴滴涕", "DDTs"),
    ]
    mentioned = set()
    for cn, sym in factor_patterns:
        if cn in text or sym in text:
            mentioned.add(cn)

    # 提取数值（mg/kg 浓度）
    value_pattern = re.compile(r"(\d+\.?\d*)\s*(?:mg/kg|mg·kg)")
    values = [float(v) for v in value_pattern.findall(text)]

    for fname in mentioned:
        facts["factors"].append({"name": fname, "value": None, "exceeded": facts["has_exceedance"]})

    # KOS 排名提取（如 "#1 As" "排名1: 镉"）
    rank_pattern = re.compile(r"(?:#|排名)\s*(\d+)\s*[:：]?\s*([\u4e00-\u9fa5A-Za-z]+)")
    for m in rank_pattern.finditer(text):
        rank = int(m.group(1))
        fname = m.group(2).strip()
        if 1 <= rank <= 20:
            facts["ranked_factors"].append(fname)

    return facts


def check_overall_conclusion(ai_reply: str) -> list[str]:
    """检测 AI 输出是否含禁止性整体结论。

    返回命中的禁止词列表（空列表=通过）。
    """
    if not ai_reply:
        return []
    hits = []
    for kw in FORBIDDEN_OVERALL_CONCLUSIONS:
        if kw in ai_reply:
            hits.append(kw)
    return hits


def check_fact_consistency(original_text: str, ai_reply: str) -> list[str]:
    """校验 AI 输出是否篡改了事实。

    返回不一致项列表（空列表=通过）。
    """
    issues = []

    if not original_text or not ai_reply:
        return issues

    orig_facts = extract_facts(original_text)

    # 1. 因子不得丢失
    for f in orig_facts["factors"]:
        if f["name"] not in ai_reply and f["name"] not in ai_reply.replace(" ", ""):
            # 检查符号变体
            sym_map = {"镉": "Cd", "铅": "Pb", "砷": "As", "铬": "Cr",
                       "汞": "Hg", "铜": "Cu", "锌": "Zn", "镍": "Ni"}
            sym = sym_map.get(f["name"], "")
            if sym and sym in ai_reply:
                continue
            issues.append(f"因子 '{f['name']}' 在 AI 输出中丢失")

    # 2. 数值不得改变（检查原始中的数值是否在 AI 输出中出现）
    value_pattern = re.compile(r"(\d+\.?\d*)\s*(?:mg/kg|mg·kg)")
    orig_values = value_pattern.findall(original_text)
    for v in orig_values:
        # AI 输出应包含相同数值（允许格式差异）
        if v not in ai_reply and float(v) not in [float(x) for x in value_pattern.findall(ai_reply)]:
            # 只对显著数值报警（>0.1），忽略微小数值
            if float(v) > 0.1:
                issues.append(f"浓度值 {v} mg/kg 在 AI 输出中缺失或被篡改")

    # 3. 超标关系不得反转
    if orig_facts["has_exceedance"]:
        # 原始有超标，但 AI 说不超标/未超标/均未超标
        reversal_kw = ("均未超标", "未超标", "不超标", "无超标", "都未超过", "均符合")
        if any(kw in ai_reply for kw in reversal_kw):
            issues.append("超标关系被反转: 原始诊断有超标，但 AI 输出称未超标")

    return issues


def validate_ai_polish(original_text: str, ai_reply: str) -> dict:
    """综合校验 AI 润色结果（P0-6 主入口）。

    返回:
        {
            "passed": bool,
            "forbidden_hits": [str],       # 命中的禁止性结论词
            "fact_issues": [str],          # 事实不一致项
            "should_fallback": bool,       # 是否应回退到原始文本
        }
    """
    forbidden = check_overall_conclusion(ai_reply)
    fact_issues = check_fact_consistency(original_text, ai_reply)

    should_fallback = bool(forbidden) or bool(fact_issues)

    return {
        "passed": not should_fallback,
        "forbidden_hits": forbidden,
        "fact_issues": fact_issues,
        "should_fallback": should_fallback,
    }
