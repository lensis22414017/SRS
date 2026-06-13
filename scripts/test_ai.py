"""OpenAI 兼容 AI 网关连通性 + 知识库 RAG 测试。
用法: cd backend && source .venv/bin/activate && python ../scripts/test_ai.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.ai_service import chat, retrieve  # noqa: E402

s = get_settings()
print("AI_BASE_URL:", s.ai_base_url)
print("AI_MODEL   :", s.ai_model)
print("AI_API_KEY :", "已配置" if s.ai_api_key else "(空)")

db = SessionLocal()
try:
    query = "砷超标可以用什么修复技术"
    ctx = retrieve(db, query, site_id=1)
    print("\nRAG 命中:")
    print("  因子:", len(ctx["factors"]))
    print("  阈值:", len(ctx["thresholds"]))
    print("  技术:", len(ctx["technologies"]), [t["技术"] for t in ctx["technologies"][:5]])
    print("  场地上下文:", "有" if ctx["site"] else "无")
    if not ctx["technologies"]:
        print("❌ RAG 未命中技术库，请先检查知识库/技术库入库")
        sys.exit(2)

    if not s.ai_base_url or not s.ai_api_key:
        print("\n⚠️ 未配置 AI 模型；RAG 检索已通过。")
        sys.exit(0)

    res = chat(db, "用一句话说明砷在农用地的风险管控筛选值随pH如何变化", site_id=1)
    if res.get("error_status") == 429:
        print("\n⚠️ AI 服务触达但当前限流/额度不足(HTTP 429)，RAG 降级可用。")
        print(res["reply"][:500])
        sys.exit(0)
    if res.get("error"):
        print("\n❌ AI 调用失败:", res["error"])
        print(res["reply"][:500])
        sys.exit(2)
    print("\n✅ AI 调用成功，回复:\n", res["reply"])
finally:
    db.close()
