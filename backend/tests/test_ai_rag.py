"""AI/RAG 检索与限流降级测试。"""
import os
import json
import urllib.error

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEJIU = os.path.join(ROOT, "data", "raw",
                     "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ai_rag.db")


def _has(*mods):
    try:
        for m in mods:
            __import__(m)
        return True
    except ImportError:
        return False


needs_db = pytest.mark.skipif(not _has("sqlalchemy", "fastapi"), reason="需 venv")


@needs_db
def test_rag_technology_hits_for_arsenic_remediation():
    """中文砷问题应能命中技术库, 不只返回因子/阈值。"""
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.services.ai_service import retrieve
    from app.services.diagnosis_service import run_diagnosis
    from app.services.evaluation_service import run_evaluation
    from app.services.pipeline import run_import
    from app.services.recommend_service import run_recommendation

    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        imp = run_import(db, GEJIU, "yunnan_gejiu")
        sid = imp["site_id"]
        run_diagnosis(db, sid, top_n=10)
        run_evaluation(db, sid)
        run_recommendation(db, sid, top_k=5)
        ctx = retrieve(db, "砷超标可以用什么修复技术", site_id=sid)
        names = {t["技术"] for t in ctx["technologies"]}
        assert names & {"植物修复(超富集/植物提取)", "固化/稳定化(S/S)", "客土/换土"}
        assert ctx["site"]["名称"] == "云南个旧重金属污染场地"
    finally:
        db.close()


@needs_db
def test_chat_429_returns_quota_fallback_with_context(monkeypatch):
    """模型 429 时应说明限流/额度, 并保留知识库上下文。"""
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.services import ai_service

    bootstrap(); load_kb()
    monkeypatch.setattr(ai_service.get_settings(), "ai_base_url", "https://example.test/v1")
    monkeypatch.setattr(ai_service.get_settings(), "ai_api_key", "test-key")
    monkeypatch.setattr(ai_service.get_settings(), "ai_model", "test-model")

    def raise_429(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            "https://example.test/v1/chat/completions", 429, "Too Many Requests", hdrs=None, fp=None)

    monkeypatch.setattr(ai_service.urllib.request, "urlopen", raise_429)
    db = SessionLocal()
    try:
        res = ai_service.chat(db, "砷超标可以用什么修复技术")
        assert res["configured"] is True
        assert res["context"]["technologies"]
        assert "限流" in res["reply"] or "额度" in res["reply"] or "429" in res["reply"]
        assert "知识库检索结果" in res["reply"]
    finally:
        db.close()


@needs_db
def test_chat_garbled_model_reply_degrades_to_rag(monkeypatch):
    """模型返回明显乱码时, 前端应收到可读的知识库降级答案。"""
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.services import ai_service

    bootstrap(); load_kb()
    monkeypatch.setattr(ai_service.get_settings(), "ai_base_url", "https://example.test/v1")
    monkeypatch.setattr(ai_service.get_settings(), "ai_api_key", "test-key")
    monkeypatch.setattr(ai_service.get_settings(), "ai_model", "test-model")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({
                "choices": [{"message": {"content": "砷�值�回答�"}}]
            }).encode("utf-8")

    monkeypatch.setattr(ai_service.urllib.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    db = SessionLocal()
    try:
        res = ai_service.chat(db, "砷超标可以用什么修复技术")
        assert res["configured"] is True
        assert res["degraded"] is True
        assert "乱码" in res["reply"] or "自动降级" in res["reply"]
        assert "可参考修复技术" in res["reply"]
        assert "\ufffd" not in res["reply"]
    finally:
        db.close()


# ---------- 同义词扩展(纯函数, 沙箱可跑) ----------
def test_expand_terms_chinese_to_symbol():
    """中文污染物名应扩展出元素符号: 砷→As, 铅→Pb。"""
    from app.services.ai_service import _expand_terms
    expanded = _expand_terms(["砷"])
    assert "As" in expanded and "重金属" in expanded
    expanded2 = _expand_terms(["铅"])
    assert "Pb" in expanded2


def test_expand_terms_symbol_to_chinese():
    """元素符号应反查中文: As→砷, Pb→铅(双向容错)。"""
    from app.services.ai_service import _expand_terms
    assert "砷" in _expand_terms(["As"])
    assert "铅" in _expand_terms(["Pb"])


def test_expand_terms_typo_correction():
    """常见错字砐→砷容错。"""
    from app.services.ai_service import _expand_terms
    expanded = _expand_terms(["砐"])
    assert "砷" in expanded


def test_expand_terms_dedup():
    """扩展后应去重, 不产生重复词。"""
    from app.services.ai_service import _expand_terms
    expanded = _expand_terms(["砷", "As"])
    assert len(expanded) == len(set(expanded))


@needs_db
def test_retrieve_uses_synonyms_for_factor_search():
    """检索时同义词应生效: 用 'Pb' 查询也能命中铅的因子/阈值。"""
    from app.db.bootstrap import main as bootstrap
    from app.db.load_kb import main as load_kb
    from app.db.session import SessionLocal
    from app.services.ai_service import retrieve

    bootstrap(); load_kb()
    db = SessionLocal()
    try:
        # 用元素符号 Pb 查询(库里因子名是中文"铅"), 同义词扩展后应命中
        ctx = retrieve(db, "Pb 超标修复")
        factor_names = {f["因子"] for f in ctx["factors"]}
        assert any("铅" in n for n in factor_names), f"Pb 查询应命中铅因子, 实际: {factor_names}"
        # 阈值也应命中
        th_factors = {t["因子"] for t in ctx["thresholds"]}
        assert any("铅" in n for n in th_factors), f"Pb 查询应命中铅阈值, 实际: {th_factors}"
    finally:
        db.close()
