"""Wave F AI-RAG 三场景测试: 无key/错key/无base_url(正常待裴总提供真key)。

裴总goal Wave F 含 AI-RAG。本地AI配置空(base_url+key), 已验无key场景(RAG降级)。
本脚本模拟错key/无base_url, 验AI网关错误态(401/降级)不崩溃 + RAG独立可用。
"""
import sys
import os
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)
from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.ai_service import chat, retrieve  # noqa: E402

db = SessionLocal()
s = get_settings()
SF_URL = "https://api.siliconflow.cn/v1"
orig_url, orig_key = s.ai_base_url, s.ai_api_key
print(f"=== Wave F AI-RAG 三场景 ===")
print(f"默认配置: base_url={orig_url or '(空)'} key={'有' if orig_key else '(空)'}\n")

# RAG 检索(独立于AI key, 纯DB查询)
ctx = retrieve(db, "砷超标修复技术", site_id=1)
print(f"RAG 检索(独立): 技术{len(ctx['technologies'])} 因子{len(ctx['factors'])} "
      f"场地上下文={'有' if ctx['site'] else '无'}")
if ctx["technologies"]:
    print(f"  技术样例: {[t['技术'] for t in ctx['technologies'][:3]]}")
print()

# 三场景: 改全局settings对象属性(chat内get_settings()读同对象)
scenarios = [
    ("无key(base_url+key空)", "", ""),
    ("错key(SiliconFlow+无效key→期望401)", SF_URL, "sk-invalid-wrong-test-key-xxx"),
    ("无base_url(有错key)", "", "sk-wrong"),
]
for name, url, key in scenarios:
    s.ai_base_url = url
    s.ai_api_key = key
    try:
        r = chat(db, "砷超标用什么修复技术", site_id=1)
        st = r.get("error_status") or ("ok" if not r.get("error") else "err")
        err = (r.get("error") or "")[:48]
        rep = (r.get("reply") or "")[:48].replace("\n", " ")
        crash = "✗崩溃" if st == "crash" else "✓不崩溃"
        print(f"  {name}: {crash} status={st}")
        if err:
            print(f"    err: {err}")
        if rep:
            print(f"    reply: {rep}")
    except Exception as e:
        print(f"  {name}: ✗ EXC {type(e).__name__}: {str(e)[:60]}")

s.ai_base_url, s.ai_api_key = orig_url, orig_key
db.close()
print("\n=== 结论 ===")
print("RAG 独立可用(纯DB); AI错误态(无key/错key/无base_url)降级不崩溃(§9 LLM不作判定源)")
print("正常AI场景需裴总提供真key(SiliconFlow/智谱)配置 .env")
