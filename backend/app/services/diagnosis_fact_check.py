"""diagnosis_fact_check.py — AI 润色诊断的事实校验（P0-6 修复 + M0-7 强化）

GPT 审计要求: AI 只能润色说明，不得修改事实（因子/数值/单位/超标关系/排名）。
本模块:
1. 从原始诊断文本结构化提取事实（因子→{value, unit, threshold, exceeded, rank}）
2. 逐因子校验 AI 输出是否篡改了上述事实绑定:
   - 同一因子的浓度值不得移花接木到另一因子
   - 单位不得改变 (mg/kg → μg/kg)
   - 排名顺序不得改变
   - 阈值与实测值不得互换
   - 不得删除正式障碍因子
3. 扩充禁止性整体结论检测（总体可控/影响有限/可正常使用等）

M0-7 强化:
- extract_facts 改为返回每因子聚合事实 (factor, value, unit, threshold, exceeded, rank)
- check_fact_consistency 做严格的因子-数值-单位-排名绑定校验
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

# 中文→符号/反向符号映射（用于宽松匹配因子是否仍出现）
_FACTOR_SYMBOL_MAP = {
    "镉": "Cd", "铅": "Pb", "砷": "As", "铬": "Cr",
    "汞": "Hg", "铜": "Cu", "锌": "Zn", "镍": "Ni",
    "苯并芘": "BaP", "六六六": "HCHs", "滴滴涕": "DDTs",
}
_SYMBOL_TO_CN = {v: k for k, v in _FACTOR_SYMBOL_MAP.items()}


def _factor_present(factor: str, text: str) -> bool:
    """宽松判定因子是否在文本中出现(中文/符号任一形式)。"""
    if not factor or not text:
        return False
    if factor in text:
        return True
    sym = _FACTOR_SYMBOL_MAP.get(factor)
    if sym and sym in text:
        return True
    cn = _SYMBOL_TO_CN.get(factor)
    if cn and cn in text:
        return True
    return False


def extract_facts(diagnosis_text: str) -> dict:
    """从原始诊断文本结构化提取事实（M0-7: 每因子绑定）。

    返回:
        {
            "factors": [
                {
                    "factor": str,            # 中文名(如 砷/铅/铜)
                    "value": float|None,      # 实测浓度值
                    "unit": str|None,         # 单位(如 mg/kg)
                    "threshold": float|None,  # 阈值
                    "exceeded": bool,         # 是否超标
                    "rank": int|None,         # KOS 排名(1 起)
                },
                ...
            ],
            "has_exceedance": bool,
            "has_obstacle": bool,
            "ranked_factors": [str],          # KOS 排名顺序的因子名
        }
    """
    facts = {"factors": [], "has_exceedance": False, "has_obstacle": False, "ranked_factors": []}

    if not diagnosis_text:
        return facts

    text = diagnosis_text

    # 整体超标/障碍标记
    if "超标" in text or "超过" in text or "超出" in text:
        facts["has_exceedance"] = True
    if "障碍" in text:
        facts["has_obstacle"] = True

    # ── Step 1: 识别文本中出现的因子集合 ──
    factor_patterns = [
        ("镉", "Cd"), ("铅", "Pb"), ("砷", "As"), ("铬", "Cr"),
        ("汞", "Hg"), ("铜", "Cu"), ("锌", "Zn"), ("镍", "Ni"),
        ("苯并芘", "BaP"), ("六六六", "HCHs"), ("滴滴涕", "DDTs"),
    ]
    mentioned: list[str] = []
    for cn, _sym in factor_patterns:
        if cn in text:
            mentioned.append(cn)

    # ── Step 2: 提取因子→数值绑定（"砷...12420 mg/kg" / "浓度 1279" 等） ──
    # 数值提取: 支持整数/小数 + 可选单位
    value_pattern = re.compile(r"(\d+\.?\d*)\s*(mg/kg|mg·kg|μg/kg|ug/kg|ng/g)?", re.IGNORECASE)
    # 因子附近的浓度值（因子名后 12 字符窗口内的数值视为该因子的实测值）
    factor_value_map: dict[str, list[float]] = {}
    factor_unit_map: dict[str, str] = {}
    factor_threshold_map: dict[str, list[float]] = {}
    for fname in mentioned:
        # 实测值: 因子名附近数值，避开"超标 N 倍"的倍数
        window_pat = re.compile(
            re.escape(fname) + r"[^0-9－－—\n]{0,16}?"
            r"(?:浓度[是为约]?\s*)?(\d+\.?\d*)\s*(mg/kg|mg·kg|μg/kg|ug/kg|ng/g)?",
            re.IGNORECASE,
        )
        vals: list[float] = []
        units: list[str] = []
        for m in window_pat.finditer(text):
            try:
                v = float(m.group(1))
            except (TypeError, ValueError):
                continue
            # 排除"超标 N 倍"中的倍数(向后看 4 字符)
            tail = text[m.end():m.end() + 4]
            if "倍" in tail:
                continue
            vals.append(v)
            if m.group(2):
                units.append(m.group(2).lower().replace("·", ""))
        if vals:
            # 取最大值作为该因子的代表实测值
            factor_value_map[fname] = vals
            if units:
                factor_unit_map[fname] = units[0]

        # 阈值: "阈值 60" / "标准 60" / "限值 60"
        thr_pat = re.compile(
            r"(?:阈值|标准值?|限值|筛选值)\s*[是为约:：]?\s*(\d+\.?\d*)\s*(mg/kg|mg·kg|μg/kg|ug/kg|ng/g)?",
            re.IGNORECASE,
        )
        thr_vals: list[float] = []
        for m in thr_pat.finditer(text):
            try:
                thr_vals.append(float(m.group(1)))
            except (TypeError, ValueError):
                continue
        if thr_vals:
            factor_threshold_map[fname] = thr_vals

    # ── Step 3: 提取 KOS 排名 (#1 砷 / 排名1: 砷) ──
    rank_pattern = re.compile(r"(?:#|排名)\s*(\d+)\s*[:：]?\s*([\u4e00-\u9fa5A-Za-z]+)")
    factor_rank_map: dict[str, int] = {}
    ranked_order: list[str] = []
    for m in rank_pattern.finditer(text):
        try:
            rank = int(m.group(1))
        except (TypeError, ValueError):
            continue
        fname = m.group(2).strip()
        if 1 <= rank <= 20:
            # 中文名或符号名都接受
            cn_name = _SYMBOL_TO_CN.get(fname, fname) if fname in _SYMBOL_TO_CN else fname
            factor_rank_map[cn_name] = rank
            if cn_name not in ranked_order:
                ranked_order.append(cn_name)
            # 也用符号变体记录
            sym = _FACTOR_SYMBOL_MAP.get(cn_name)
            if sym:
                factor_rank_map[sym] = rank
    facts["ranked_factors"] = ranked_order

    # ── Step 4: 组装每因子结构 ──
    for fname in mentioned:
        vals = factor_value_map.get(fname, [])
        value = max(vals) if vals else None
        unit = factor_unit_map.get(fname)
        thr_list = factor_threshold_map.get(fname, [])
        threshold = min(thr_list) if thr_list else None
        exceeded = facts["has_exceedance"]  # 文本级标记
        rank = factor_rank_map.get(fname)
        facts["factors"].append({
            "factor": fname,
            "value": value,
            "unit": unit,
            "threshold": threshold,
            "exceeded": exceeded,
            "rank": rank,
        })

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
    """M0-7: 逐因子校验 AI 输出是否篡改了事实绑定。

    返回不一致项列表（空列表=通过）。

    校验项(每因子):
      1. 因子不得丢失(正式障碍必须保留)
      2. 因子之间数值不得交换(As 的值不能套到 Pb 上)
      3. 单位不得改变 (mg/kg → μg/kg 视为篡改)
      4. 排名顺序不得改变 (#1 ↔ #2 互换视为篡改)
      5. 阈值与实测值不得互换
    """
    issues: list[str] = []

    if not original_text or not ai_reply:
        return issues

    orig_facts = extract_facts(original_text)
    ai_facts = extract_facts(ai_reply)

    orig_by_factor = {f["factor"]: f for f in orig_facts["factors"]}
    ai_by_factor = {f["factor"]: f for f in ai_facts["factors"]}

    # ── 1. 因子不得丢失（特别是有超标/排名的"正式障碍"因子） ──
    for fname, orig_f in orig_by_factor.items():
        if not _factor_present(fname, ai_reply):
            # 已超标的因子或参与排名的因子属于正式障碍，必须保留
            if orig_f["exceeded"] or orig_f["rank"] is not None:
                issues.append(f"正式障碍因子 '{fname}' 在 AI 输出中丢失")
            else:
                # 非障碍因子也保留告警, 但用更轻的措辞
                issues.append(f"因子 '{fname}' 在 AI 输出中丢失")

    # ── 2. 数值篡改/交换检测: As 的值不能给 Pb, 也不能被改为别的数字 ──
    # 对每个有值的因子 A，检查其原值在 AI 输出中是否仍与 A 绑定
    for fname_a, orig_a in orig_by_factor.items():
        val_a = orig_a.get("value")
        if val_a is None or float(val_a) <= 0.1:
            # 仅对显著数值(>0.1)做严格校验, 忽略微小数值避免格式差异误报
            continue
        # A 的原值在 AI 中是否仍和 A 绑定（A 附近窗口内有该值）
        a_kept = _value_near_factor(ai_reply, fname_a, val_a)
        if a_kept:
            continue
        # A 的原值是否被错配到别的因子 B
        exchanged = False
        for fname_b in orig_by_factor.keys():
            if fname_b == fname_a:
                continue
            if _value_near_factor(ai_reply, fname_b, val_a):
                issues.append(
                    f"数值交换: 因子 '{fname_a}' 的实测值 {val_a} 在 AI 输出中被错配到因子 '{fname_b}'"
                )
                exchanged = True
                break
        if exchanged:
            continue
        # 原值既不在 A 附近，也不在其他因子附近 → 数值被篡改或缺失
        issues.append(
            f"浓度值 {val_a} mg/kg 在 AI 输出中缺失或被篡改（原始绑定因子 '{fname_a}'）"
        )

    # ── 3. 单位不得改变 ──
    for fname, orig_f in orig_by_factor.items():
        orig_unit = orig_f.get("unit")
        if not orig_unit:
            continue
        ai_f = ai_by_factor.get(fname)
        ai_unit = ai_f.get("unit") if ai_f else None
        # AI 文本中该因子附近出现的单位
        if not ai_unit:
            ai_unit = _unit_near_factor(ai_reply, fname)
        if ai_unit and ai_unit != orig_unit:
            issues.append(
                f"单位篡改: 因子 '{fname}' 原单位 {orig_unit}，AI 输出改为 {ai_unit}"
            )

    # ── 4. 排名顺序不得改变 ──
    orig_ranked = orig_facts["ranked_factors"]
    if len(orig_ranked) >= 2:
        # 比较 AI 输出中相邻排名对是否顺序被颠倒
        for i in range(len(orig_ranked) - 1):
            f1 = orig_ranked[i]
            f2 = orig_ranked[i + 1]
            # 在 AI 文本中两者是否都带排名标记
            if not (_has_rank_marker(ai_reply, f1) and _has_rank_marker(ai_reply, f2)):
                continue
            r1 = _rank_of(ai_reply, f1)
            r2 = _rank_of(ai_reply, f2)
            if r1 is not None and r2 is not None and r1 > r2:
                issues.append(
                    f"排名篡改: 原排名 #{i + 1} {f1} → #{i + 2} {f2}，"
                    f"AI 输出中顺序被颠倒为 #{r2} {f2} → #{r1} {f1}"
                )
                break  # 一次颠倒足以告警

    # ── 5. 阈值与实测值不得互换 ──
    for fname, orig_f in orig_by_factor.items():
        val = orig_f.get("value")
        thr = orig_f.get("threshold")
        if val is None or thr is None or val == thr:
            continue
        # 原始 val 在 AI 中是否变成了阈值标记附近的值
        if _value_as_threshold(ai_reply, val):
            issues.append(
                f"阈值/实测值互换: 因子 '{fname}' 实测值 {val} 在 AI 输出中被标注为阈值"
            )
        # 原始 thr 在 AI 中是否变成了实测值附近的数
        if _value_as_measurement(ai_reply, fname, thr):
            issues.append(
                f"阈值/实测值互换: 因子 '{fname}' 阈值 {thr} 在 AI 输出中被标注为实测值"
            )

    # ── 6. 超标关系不得反转 ──
    if orig_facts["has_exceedance"]:
        reversal_kw = ("均未超标", "未超标", "不超标", "无超标", "都未超过", "均符合")
        if any(kw in ai_reply for kw in reversal_kw):
            issues.append("超标关系被反转: 原始诊断有超标，但 AI 输出称未超标")

    return issues


def _value_near_factor(text: str, factor: str, value: float, window: int = 16) -> bool:
    """检查文本中因子名附近 window 字符内是否出现指定数值。"""
    if not text or value is None:
        return False
    pat = re.compile(
        re.escape(factor) + r"[^0-9\n]{0," + str(window) + r"}?" + re.escape(_num_repr(value)),
    )
    return pat.search(text) is not None


def _unit_near_factor(text: str, factor: str, window: int = 16) -> str | None:
    """提取文本中因子附近的单位。"""
    if not text:
        return None
    pat = re.compile(
        re.escape(factor) + r".{0," + str(window) + r"}?"
        r"(mg/kg|mg·kg|μg/kg|ug/kg|ng/g)",
        re.IGNORECASE,
    )
    m = pat.search(text)
    if m:
        return m.group(1).lower().replace("·", "")
    return None


def _find_factor_position(text: str, factor: str) -> int | None:
    """返回因子在文本中首次出现的字符位置。"""
    if not text:
        return None
    idx = text.find(factor)
    if idx >= 0:
        return idx
    sym = _FACTOR_SYMBOL_MAP.get(factor)
    if sym:
        idx2 = text.find(sym)
        if idx2 >= 0:
            return idx2
    return None


def _has_rank_marker(text: str, factor: str) -> bool:
    """判断文本中该因子是否带 #N / 排名N 标记。"""
    if not text:
        return False
    pat = re.compile(r"(?:#|排名)\s*\d+\s*[:：]?\s*" + re.escape(factor))
    if pat.search(text):
        return True
    sym = _FACTOR_SYMBOL_MAP.get(factor)
    if sym:
        pat2 = re.compile(r"(?:#|排名)\s*\d+\s*[:：]?\s*" + re.escape(sym))
        return pat2.search(text) is not None
    return False


def _rank_of(text: str, factor: str) -> int | None:
    """提取文本中因子对应的排名数字。"""
    if not text:
        return None
    pat = re.compile(r"(?:#|排名)\s*(\d+)\s*[:：]?\s*" + re.escape(factor))
    m = pat.search(text)
    if m:
        try:
            return int(m.group(1))
        except (TypeError, ValueError):
            return None
    sym = _FACTOR_SYMBOL_MAP.get(factor)
    if sym:
        pat2 = re.compile(r"(?:#|排名)\s*(\d+)\s*[:：]?\s*" + re.escape(sym))
        m2 = pat2.search(text)
        if m2:
            try:
                return int(m2.group(1))
            except (TypeError, ValueError):
                return None
    return None


def _value_as_threshold(text: str, value: float) -> bool:
    """检查数值在文本中是否紧邻"阈值/标准/限值"标记。"""
    if not text or value is None:
        return False
    val_repr = re.escape(_num_repr(value))
    pat = re.compile(
        r"(?:阈值|标准值?|限值|筛选值)\s*[是为约:：]?\s*" + val_repr,
    )
    if pat.search(text):
        return True
    pat2 = re.compile(val_repr + r"\s*[，。、 ]\s*(?:阈值|标准值?|限值|筛选值)")
    return pat2.search(text) is not None


def _value_as_measurement(text: str, factor: str, value: float) -> bool:
    """检查数值是否同时出现在因子附近(被当作实测值)。"""
    return _value_near_factor(text, factor, value)


def _num_repr(value: float) -> str:
    """数字字符串化，整数去尾零。"""
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return repr(float(value))


def validate_ai_polish(original_text: str, ai_reply: str) -> dict:
    """综合校验 AI 润色结果（P0-6 主入口 + M0-7 强化）。

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
