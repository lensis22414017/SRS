"""AI 助手: 知识库 RAG + OpenAI 兼容 LLM 网关。

设计原则(遵守 CLAUDE.md §9 LLM 集成规范):
- LLM 只作辅助问答/摘要, 不作监管判定源;
- 回答必须基于检索到的知识库内容(因子字典/阈值规则/技术库)与场地真实数据;
- 无数据来源时提示需人工复核, 不编造标准/文献。

RAG 检索为纯 DB 查询(可独立测试)。LLM 调用走 OpenAI 兼容 /chat/completions。
"""
from __future__ import annotations

import json
import os
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
    "输出格式要求: 用纯文本自然段表达, 禁止使用 markdown 加粗(**)、标题(#)、列表标记(-/*)、"
    "中文装饰引号("")、无意义的重复标点。直接陈述事实, 不加修饰性符号。"
    "关于系统的诊断原理和方法论，请仔细阅读【方法论文档】中的内容并用通俗语言解释。"
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

    # 向量语义检索(混合检索): 补充 SQL 关键词检索遗漏的同义/近义条目
    vctx = vector_retrieve(db, query, k=k)
    existing_f = {f.get("因子") for f in ctx["factors"]}
    for v in vctx["factors"]:
        if v["名称"] not in existing_f:
            ctx["factors"].append({"因子": v["名称"], "相似度": v["相似度"], "来源": "向量检索"})
    existing_t = {t.get("因子") for t in ctx["thresholds"]}
    for v in vctx["thresholds"]:
        if v["名称"] not in existing_t:
            ctx["thresholds"].append({"因子": v["名称"], "相似度": v["相似度"], "来源": "向量检索"})
    existing_tech = {t.get("技术") or t.get("name") or t.get("名称") for t in ctx["technologies"]}
    for v in vctx["technologies"]:
        if v["名称"] not in existing_tech:
            ctx["technologies"].append({"技术": v["名称"], "相似度": v["相似度"], "来源": "向量检索"})
    # v1.0.2: 方法论文档检索（解释系统如何诊断障碍因子等）
    ctx["methodologies"] = vctx.get("methodologies", [])
    return ctx


# ── 向量语义检索层(TF-IDF + 余弦相似度, 混合检索) ──────────────────────
# AI-RAG 向量化: 在 SQL 关键词检索(精确)之上, 加 TF-IDF 语义检索(同义/近义),
# 两者结果合并去重。无需外部 embedding 服务, sklearn 即可实现。
_VECTOR_CACHE: dict = {}  # {cache_key: {"matrix": ..., "names": ..., "vec": ...}}


def _build_tfidf_index(db: Session) -> dict | None:
    """构建因子字典+阈值规则+技术库+RAG文档的 TF-IDF 索引(惰性, 缓存到进程级)。"""
    import hashlib
    cache_key = "tfidf_v2"  # v2: 新增 rag_docs
    if cache_key in _VECTOR_CACHE:
        return _VECTOR_CACHE[cache_key]
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
    except ImportError:
        return None

    docs, names, types, contents = [], [], [], []  # contents 存储完整文档正文

    # ── RAG 方法论文档（优先加载）──
    import glob as _glob
    rag_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))), "data", "knowledge", "rag_docs")
    if os.path.isdir(rag_dir):
        for mdfile in sorted(_glob.glob(os.path.join(rag_dir, "*.md"))):
            with open(mdfile, encoding="utf-8") as f:
                content = f.read()
            # 按 ## 标题拆分为多个段落，每段作为一个独立文档
            sections = content.split("\n## ")
            for sec in sections:
                sec = sec.strip()
                if not sec or len(sec) < 20:
                    continue
                # 取第一行作为标题
                lines = sec.split("\n", 1)
                title = lines[0].lstrip("#").strip()[:80]
                body = sec[:3000]  # 截断过长段落
                docs.append(body)
                names.append(f"[方法论文档] {title}")
                types.append("methodology")
                contents.append(body)

    # ── 因子字典 ──
    for f in db.query(FactorDictionary).all():
        text = " ".join(filter(None, [f.factor_name, f.level1_category, f.default_unit]))
        docs.append(text); names.append(f.factor_name); types.append("factor"); contents.append("")

    # ── 阈值规则 ──
    for tr, fd in (db.query(ThresholdRule, FactorDictionary)
                   .join(FactorDictionary, ThresholdRule.factor_id == FactorDictionary.id).all()):
        text = " ".join(filter(None, [fd.factor_name, tr.land_type, tr.threshold_original, tr.standard_source]))
        docs.append(text); names.append(fd.factor_name); types.append("threshold"); contents.append("")

    # ── 技术库 ──
    for t in db.query(TechnologyLibrary).all():
        poll = t.applicable_pollutants
        if isinstance(poll, (list, dict)):
            poll = " ".join(str(p) for p in (poll.values() if isinstance(poll, dict) else poll))
        elif poll is not None:
            poll = str(poll)
        else:
            poll = ""
        adv = t.advantages or ""
        text = " ".join(filter(None, [t.tech_name, poll, adv]))
        docs.append(text); names.append(t.tech_name); types.append("technology"); contents.append("")

    if not docs:
        return None

    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(1, 3))  # ngram_range=3 适配更长的中文段落
    matrix = vec.fit_transform(docs)
    _VECTOR_CACHE[cache_key] = {"matrix": matrix, "names": names, "types": types,
                                "contents": contents, "vec": vec, "n_docs": len(docs)}
    print(f"[AI-RAG] TF-IDF 索引构建完成: {len(docs)} 文档 (含 {sum(1 for t in types if t=='methodology')} 篇方法论文档)")
    return _VECTOR_CACHE[cache_key]


def vector_retrieve(db: Session, query: str, k: int = 5) -> dict:
    """TF-IDF 向量语义检索: 用余弦相似度找最相关的知识库条目(补充关键词检索的遗漏)。"""
    idx = _build_tfidf_index(db)
    if not idx:
        return {"factors": [], "thresholds": [], "technologies": []}
    try:
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np
    except ImportError:
        return {"factors": [], "thresholds": [], "technologies": []}

    qvec = idx["vec"].transform([query])
    sims = cosine_similarity(qvec, idx["matrix"]).flatten()
    top_idx = np.argsort(sims)[::-1][:k * 3]  # 多取再按类型分

    factors, thresholds, technologies, methodologies = [], [], [], []
    seen_names = set()
    for i in top_idx:
        if sims[i] < 0.05:
            break
        name = idx["names"][i]; t = idx["types"][i]
        if name in seen_names:
            continue
        seen_names.add(name)
        entry = {"名称": name, "相似度": round(float(sims[i]), 3)}
        # methodology 类型附带完整文档正文
        if t == "methodology":
            entry["内容"] = idx["contents"][i][:3000]  # 最长 3000 字符
        if t == "factor" and len(factors) < k:
            factors.append(entry)
        elif t == "threshold" and len(thresholds) < k:
            thresholds.append(entry)
        elif t == "technology" and len(technologies) < k:
            technologies.append(entry)
        elif t == "methodology" and len(methodologies) < k:
            methodologies.append(entry)
    return {"factors": factors, "thresholds": thresholds, "technologies": technologies,
            "methodologies": methodologies}


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
    if ctx.get("methodologies"):
        parts.append("【方法论文档（系统诊断原理与方法论）】\n" +
                     "\n---\n".join(m.get("内容", m.get("名称", "")) for m in ctx["methodologies"]))
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


def _clean_markdown_punct(text: str) -> str:
    """剥离 LLM 输出中的 markdown 装饰和多余标点, 产出纯文本。
    清理: **加粗**、##标题、列表标记、中文装饰引号、连续重复标点。
    """
    import re
    if not text:
        return text
    # 去除 markdown 加粗 **text** 或 __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # 去除 markdown 标题前缀 ## ###
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # 去除 markdown 列表标记 - * 或 1. 2.
    text = re.sub(r'^[\s]*[-*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    # 中文装饰引号 → 去掉(保留内容)
    text = text.replace('\u201c', '').replace('\u201d', '')  # ""
    text = text.replace('\u2018', '').replace('\u2019', '')  # ''
    # 去除行首行尾多余空格
    text = re.sub(r'[ \t]+', ' ', text)
    # 连续句号/逗号压缩为单个
    text = re.sub(r'[。]{2,}', '。', text)
    text = re.sub(r'[，]{2,}', '，', text)
    # 多余空行压缩
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


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


# v1.0.1 final-audit: 意图路由 — 判断用户问题是 domain_rag 还是 general
_DOMAIN_KEYWORDS = [
    # 法规/标准
    "标准", "阈值", "筛选值", "管制值", "GB15618", "GB36600", "GB", "mg/kg", "超标",
    "筛选", "管控", "修复", "风险管控", "土壤环境",
    # 污染物
    "镉", "铅", "砷", "铜", "锌", "铬", "汞", "镍", "重金属", "有机物", "PAH", "多环芳烃",
    "农药", "石油烃", "多氯联苯", "PCB", "二噁英",
    # 场地/诊断
    "场地", "诊断", "障碍因子", "KOS", "污染", "用地", "生态", "生产", "农用地", "建设用地",
    "采样", "检测", "实测", "浓度", "pH",
    # 修复技术
    "植物修复", "固化", "稳定化", "客土", "淋洗", "生物修复", "热脱附",
]


def _route_intent(message: str, site_id: int | None = None) -> str:
    """意图路由: 判断问题是 domain_rag(法规/阈值/场地) 还是 general(普通知识)。

    规则:
    1. 有 site_id → domain_rag(场地相关问题)
    2. 消息含领域关键词 → domain_rag
    3. 其他 → general(普通知识问答)
    """
    if site_id is not None:
        return "domain_rag"
    msg_lower = message.lower()
    for kw in _DOMAIN_KEYWORDS:
        if kw.lower() in msg_lower:
            return "domain_rag"
    return "general"


def chat(db: Session, message: str, site_id: int | None = None,
         history: list[dict] | None = None) -> dict:
    from app.core.ai_config import effective_ai
    cfg = effective_ai()
    base_url, api_key, model = cfg["base_url"], cfg["api_key"], cfg["model"]
    timeout = get_settings().ai_timeout

    # v1.0.1 final-audit: 意图路由 — domain_rag(法规/阈值/场地) vs general(普通知识)
    answer_mode = _route_intent(message, site_id)

    ctx = retrieve(db, message, site_id=site_id)
    ctx_text = build_context_text(ctx)

    if not base_url or not api_key:
        return {
            "reply": ("⚠️ 尚未配置 AI 模型。请在『系统管理 → AI 模型配置』选择服务商并填写 API Key"
                      "(默认推荐: 智谱 GLM 官方免费模型)。\n\n"
                      "以下是知识库检索到的相关资料(已可直接参考):\n" + ctx_text),
            "context": ctx, "model": None, "configured": False,
            "answer_mode": answer_mode,
        }

    # domain_rag 模式: 绑定知识库+场地来源; general 模式: 可用模型通用知识
    if answer_mode == "general":
        # 普通知识问答: 不注入知识库上下文, 用模型通用知识
        messages = [{"role": "system", "content": "你是 SRS 系统的 AI 智能助手。请用简体中文回答用户的普通知识问题, 可以使用你的通用知识。"}]
    else:
        # domain_rag 模式: 法规/阈值/场地诊断必须绑定知识库
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
                          "temperature": 0.3,
                          "thinking": {"type": "disabled"}}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data["choices"][0]["message"]["content"]
        reply = _clean_markdown_punct(reply)
        if _quality_issue(reply):
            return {"reply": _rag_fallback_reply(ctx, "AI 模型返回内容存在乱码或质量异常, 已自动降级"),
                    "context": ctx, "model": model, "configured": True,
                    "degraded": True}
        return {"reply": reply, "context": ctx, "model": model, "configured": True,
                "answer_mode": answer_mode}
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
    "3. 只如实复述超标因子、浓度水平、KOS 排名等客观事实。禁止给出优/良/中/差等"
    "整体评价档次, 禁止使用安全/低风险/无风险/状况良好等整体安全性结论。\n"
    "4. 如果诊断置信度偏低, 要坦诚说明, 不要掩盖。\n"
    "5. 保持专业严谨, 不要编造数据。\n"
    "6. 字数控制在 200-400 字, 使用简体中文。\n"
    "7. 输出纯文本, 禁止使用 markdown 加粗(**)、标题(#)、列表编号(1. 2.)、"
    "中文装饰引号。用自然段落陈述, 不加多余标点修饰。\n"
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
                          "temperature": 0.3, "max_tokens": 800,
                          "thinking": {"type": "disabled"}}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {api_key}"})
    try:
        timeout = get_settings().ai_timeout
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reply = data["choices"][0]["message"]["content"]
        reply = _clean_markdown_punct(reply)
        if _quality_issue(reply):
            return None
        # P0-6: 综合事实校验（替代旧的 6 关键词检查）
        # 校验: 禁止性整体结论 + 因子不丢失 + 数值不改 + 超标关系不反转
        from app.services.diagnosis_fact_check import validate_ai_polish
        validation = validate_ai_polish(diagnosis_text, reply)
        if validation["should_fallback"]:
            return None  # 校验失败，回退到原始确定性诊断
        return reply.strip()
    except Exception:
        return None  # 静默降级, 不影响诊断主流程
