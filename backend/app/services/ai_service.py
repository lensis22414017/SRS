"""AI 助手: 知识库 RAG + OpenAI 兼容 LLM 网关。

设计原则(遵守 CLAUDE.md §9 LLM 集成规范):
- LLM 只作辅助问答/摘要, 不作监管判定源;
- 回答必须基于检索到的知识库内容(因子字典/阈值规则/技术库)与场地真实数据;
- 无数据来源时提示需人工复核, 不编造标准/文献。

RAG 检索为纯 DB 查询(可独立测试)。LLM 调用走 OpenAI 兼容 /chat/completions。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    DiagnosisResult, EvaluationResult, FactorDictionary, Site, TechnologyLibrary,
    ThresholdRule,
)

SYSTEM_PROMPT = (
    "你是污染场地土壤生态-生产功能重构监管系统的智能助手。"
    "你必须严格基于下方【知识库检索结果】与【场地数据】回答, 不得编造标准条文、阈值或文献。"
    "若检索结果不足以回答, 明确说明'资料不足, 建议人工复核', 不要臆测。"
    "你不能替代 RF/SHAP 诊断或阈值规则做最终达标判定, 只能解释与辅助。用简体中文、专业、简洁作答。"
)


def retrieve(db: Session, query: str, site_id: int | None = None, k: int = 8) -> dict:
    """知识库 + 场地数据检索, 返回结构化上下文。

    检索词经同义词/别称扩展(_expand_terms): 如 "砷"→As/重金属, "Pb"→铅,
    使因子/阈值/技术三类检索都受益于同义词容错, 提升命中率。
    """
    terms = [t for t in _tokenize(query) if len(t) >= 1]
    # 同义词扩展: 让因子/阈值 SQL 检索也享受 As↔砷、Pb↔铅 等别称容错
    expanded = _expand_terms(terms) if terms else []
    ctx: dict = {"factors": [], "thresholds": [], "technologies": [], "site": None}

    if expanded:
        # 因子字典: 用扩展词做 OR contains 查询
        fq = db.query(FactorDictionary).filter(
            or_(*[FactorDictionary.factor_name.contains(t) for t in expanded])).limit(k).all()
        ctx["factors"] = [{"因子": f.factor_name, "类别": f.level1_category,
                           "单位": f.default_unit} for f in fq]

        # 阈值规则: 同样用扩展词
        tq = (db.query(ThresholdRule, FactorDictionary)
              .join(FactorDictionary, ThresholdRule.factor_id == FactorDictionary.id)
              .filter(or_(*[FactorDictionary.factor_name.contains(t) for t in expanded]))
              .limit(k).all())
        ctx["thresholds"] = [{"因子": fd.factor_name, "用地": tr.land_type,
                              "范围": tr.threshold_original, "标准来源": tr.standard_source}
                             for tr, fd in tq]

        ctx["technologies"] = _match_technologies(db, expanded, limit=k)

    if site_id:
        site = db.get(Site, site_id)
        if site:
            diag = (db.query(DiagnosisResult).filter_by(site_id=site_id)
                    .order_by(DiagnosisResult.id.desc()).first())
            evals = (db.query(EvaluationResult).filter_by(site_id=site_id)
                     .order_by(EvaluationResult.id.desc()).all())
            seen = {}
            for e in evals:
                seen.setdefault(e.eval_type, {"得分": e.score, "等级": e.grade})
            ctx["site"] = {
                "名称": site.name, "编号": site.site_code,
                "污染类型": site.pollution_type, "用地类型": site.land_use_type,
                "诊断摘要": diag.summary if diag else None,
                "评价": seen,
            }
    return ctx


_SINGLE_FACTORS = set("砷铅铜锌镉汞镍铬钒钴铍锑锰钼银铊钛锡钡")  # 单字金属因子
_FACTOR_ALIASES = {
    # 重金属: 中文名 ↔ 元素符号 ↔ 类别
    "砷": ["As", "砐", "重金属"], "铅": ["Pb", "重金属"], "铜": ["Cu", "重金属"],
    "锌": ["Zn", "重金属"], "镉": ["Cd", "重金属"], "汞": ["Hg", "水银", "重金属"],
    "镍": ["Ni", "重金属"], "铬": ["Cr", "重金属"], "六价铬": ["Cr6+", "Cr(VI)", "重金属"],
    "钒": ["V", "重金属"], "钴": ["Co", "重金属"], "铍": ["Be", "重金属"],
    "锑": ["Sb", "重金属"], "锰": ["Mn", "重金属"], "钼": ["Mo", "重金属"],
    "铊": ["Tl", "重金属"], "钛": ["Ti", "重金属"], "锡": ["Sn", "重金属"],
    "银": ["Ag", "重金属"], "钡": ["Ba", "重金属"],
    # 符号反查中文(用户输入 As/Pb 时也能命中)
    "As": ["砷", "重金属"], "Pb": ["铅", "重金属"], "Cu": ["铜", "重金属"],
    "Zn": ["锌", "重金属"], "Cd": ["镉", "重金属"], "Hg": ["汞", "重金属"],
    "Ni": ["镍", "重金属"], "Cr": ["铬", "重金属"],
    # 有机物
    "PAH": ["PAHs", "多环芳烃", "有机物"], "PAHs": ["多环芳烃", "有机物"],
    "石油烃": ["TPH", "有机物"], "TPH": ["石油烃", "有机物"],
    "苯": ["BTEX", "有机物"], "BTEX": ["苯系物", "有机物"],
    "多氯联苯": ["PCB", "有机物"], "PCB": ["多氯联苯", "有机物"],
    "农药": ["有机氯", "有机磷", "有机物"], "有机氯": ["农药", "有机物"],
    # 常见错字/异体
    "砐": ["砷", "As"],
}
_GENERIC_TERMS = {
    "可以", "什么", "怎么", "如何", "修复", "技术", "方案", "超标",
    "污染", "场地", "土壤", "风险", "推荐", "处理",
}


def _tokenize(q: str) -> list[str]:
    import re
    en = re.findall(r"[A-Za-z]{2,}", q)
    zh = re.findall(r"[一-龥]{2,4}", q)
    singles = [c for c in q if c in _SINGLE_FACTORS]  # 单字金属
    return list(dict.fromkeys(en + zh + singles))[:12]


def _expand_terms(terms: list[str]) -> list[str]:
    expanded = []
    for term in terms:
        expanded.append(term)
        expanded.extend(_FACTOR_ALIASES.get(term, []))
        for factor, aliases in _FACTOR_ALIASES.items():
            if factor in term:
                expanded.append(factor)
                expanded.extend(aliases)
    return list(dict.fromkeys(t for t in expanded if t))


def _textify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _match_technologies(db: Session, terms: list[str], limit: int = 8) -> list[dict]:
    """技术库用 Python 侧匹配, 避免 SQLite JSON contains 对中英文/列表切分失配。"""
    expanded = _expand_terms(terms)
    strong_terms = [t for t in expanded if t not in _GENERIC_TERMS and len(t) >= 2]
    if not strong_terms:
        strong_terms = [t for t in expanded if t not in _GENERIC_TERMS]
    scored = []
    for tech in db.query(TechnologyLibrary).all():
        haystack = " ".join([
            tech.tech_name,
            _textify(tech.applicable_pollutants),
            _textify(tech.applicable_soil),
            _textify(tech.applicable_land_type),
            _textify(tech.advantages),
            _textify(tech.limitations),
            _textify(tech.forbidden_conditions),
        ])
        score = sum(1 for t in strong_terms if t and t in haystack)
        if score <= 0:
            continue
        scored.append((score, tech))
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return [{"技术": t.tech_name, "适用污染物": t.applicable_pollutants,
             "优点": t.advantages, "局限": t.limitations,
             "禁用条件": t.forbidden_conditions, "来源": t.source}
            for _, t in scored[:limit]]


def build_context_text(ctx: dict) -> str:
    parts = []
    if ctx.get("site"):
        parts.append("【场地数据】\n" + json.dumps(ctx["site"], ensure_ascii=False))
    if ctx.get("factors"):
        parts.append("【因子字典】\n" + json.dumps(ctx["factors"], ensure_ascii=False))
    if ctx.get("thresholds"):
        parts.append("【阈值规则】\n" + json.dumps(ctx["thresholds"], ensure_ascii=False))
    if ctx.get("technologies"):
        parts.append("【技术库】\n" + json.dumps(ctx["technologies"], ensure_ascii=False))
    return "\n\n".join(parts) or "(知识库未检索到直接相关条目)"


def _quality_issue(reply: str) -> bool:
    """识别模型返回的明显乱码, 避免把不可读内容直接呈现给用户。"""
    return reply.count("\ufffd") >= 1


def _rag_fallback_reply(ctx: dict, reason: str) -> str:
    """模型不可用时的结构化 RAG 答案, 只复述已检索到的证据。"""
    lines = [f"{reason}。以下为知识库检索结果, 建议结合人工复核使用。"]
    if ctx.get("site"):
        site = ctx["site"]
        lines.append(
            f"当前场地: {site.get('名称')}({site.get('编号')}), "
            f"污染类型: {site.get('污染类型')}, 用地类型: {site.get('用地类型')}。"
        )
    if ctx.get("technologies"):
        lines.append("可参考修复技术:")
        for tech in ctx["technologies"][:5]:
            lines.append(
                f"- {tech.get('技术')}: 适用污染物 {tech.get('适用污染物')}; "
                f"局限 {tech.get('局限') or '需结合场地条件复核'}; "
                f"禁用条件 {tech.get('禁用条件') or '暂无明确禁用条件'}。"
            )
    if ctx.get("thresholds"):
        lines.append("相关阈值/标准条目:")
        for rule in ctx["thresholds"][:5]:
            lines.append(
                f"- {rule.get('因子')} / {rule.get('用地')}: "
                f"{rule.get('范围')} ({rule.get('标准来源')})"
            )
    if ctx.get("factors"):
        names = "、".join(f.get("因子", "") for f in ctx["factors"][:5])
        lines.append(f"匹配障碍因子: {names}。")
    if not any(ctx.get(k) for k in ("technologies", "thresholds", "factors", "site")):
        lines.append("知识库未检索到直接相关条目, 资料不足, 建议人工复核。")
    return "\n".join(lines)


def chat(db: Session, message: str, site_id: int | None = None,
         history: list[dict] | None = None) -> dict:
    from app.core.ai_config import effective_ai
    cfg = effective_ai()
    base_url, api_key, model = cfg["base_url"], cfg["api_key"], cfg["model"]
    timeout = get_settings().ai_timeout
    ctx = retrieve(db, message, site_id=site_id)
    ctx_text = build_context_text(ctx)

    if not base_url or not api_key:
        return {
            "reply": ("⚠️ 尚未配置 AI 模型。请在『系统管理 → AI 模型配置』选择服务商并填写 API Key"
                      "(默认推荐: 智谱 GLM 官方免费模型)。\n\n"
                      "以下是知识库检索到的相关资料(已可直接参考):\n" + ctx_text),
            "context": ctx, "model": None, "configured": False,
        }

    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": "【知识库检索结果】\n" + ctx_text}]
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h.get("content", "")})
    # brief 4.7: 防御前端把当前 user 消息也放进 history → 末条重复时不再 append
    if not (messages and messages[-1].get("role") == "user"
            and messages[-1].get("content") == message):
        messages.append({"role": "user", "content": message})

    payload = json.dumps({"model": model, "messages": messages,
                          "temperature": 0.3}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data["choices"][0]["message"]["content"]
        if _quality_issue(reply):
            return {"reply": _rag_fallback_reply(ctx, "AI 模型返回内容存在乱码或质量异常, 已自动降级"),
                    "context": ctx, "model": model, "configured": True,
                    "degraded": True}
        return {"reply": reply, "context": ctx, "model": model, "configured": True}
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return {
                "reply": ("AI 模型当前额度或频率受限(HTTP 429: Too Many Requests)。"
                          "以下为知识库检索结果供参考:\n\n" + ctx_text),
                "context": ctx, "model": model, "configured": True,
                "error": str(e), "error_status": 429,
            }
        return {"reply": f"AI 调用失败(HTTP {e.code}: {e.reason})。以下为知识库检索结果供参考:\n\n{ctx_text}",
                "context": ctx, "model": model, "configured": True,
                "error": str(e), "error_status": e.code}
    except (urllib.error.URLError, KeyError, TimeoutError) as e:
        return {"reply": f"AI 调用失败({e})。以下为知识库检索结果供参考:\n\n{ctx_text}",
                "context": ctx, "model": model, "configured": True, "error": str(e)}


DIAGNOSIS_POLISH_PROMPT = (
    "你是污染场地土壤修复领域的科普专家。请将以下技术性诊断结果改写为通俗易懂的语言。\n"
    "要求:\n"
    "1. 用通俗语言解释障碍因子的含义和影响, 避免 SHAP、AUC、特征重要性等技术术语。\n"
    "2. 突出最关键的 2-3 个障碍因子, 说明它们在场地中的具体影响。\n"
    "3. 给出一个总体评价(优/良/中/差), 不用具体分数。\n"
    "4. 如果诊断置信度偏低, 要坦诚说明, 不要掩盖。\n"
    "5. 保持专业严谨, 不要编造数据。\n"
    "6. 字数控制在 200-400 字, 使用简体中文。\n"
)


def polish_diagnosis(db: Session, diagnosis_text: str) -> str | None:
    """使用已配置的 AI 模型润色诊断摘要, 失败时返回 None（前端回退到原始模板文本）。"""
    from app.core.ai_config import effective_ai
    cfg = effective_ai()
    base_url, api_key, model = cfg["base_url"], cfg["api_key"], cfg["model"]
    if not base_url or not api_key:
        return None  # 未配置 AI, 静默降级

    messages = [
        {"role": "system", "content": DIAGNOSIS_POLISH_PROMPT},
        {"role": "user", "content": f"原始诊断结果:\n{diagnosis_text}"},
    ]
    payload = json.dumps({"model": model, "messages": messages,
                          "temperature": 0.3, "max_tokens": 800}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    try:
        timeout = get_settings().ai_timeout
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data["choices"][0]["message"]["content"]
        if _quality_issue(reply):
            return None
        return reply.strip()
    except Exception:
        return None  # 静默降级, 不影响诊断主流程
