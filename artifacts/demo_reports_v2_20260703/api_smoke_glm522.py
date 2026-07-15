"""GLM-5.2 系统闭环 API 冒烟测试: 登录→场地→诊断(HM/OP/HM+OP)→AI配置→AI对话→报告。
保存结构化结果到 artifacts/demo_reports_v2_20260703/api_smoke_result.json。
"""
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8011/api/v1"
RESULT = {"checks": [], "summary": {}}


def req(method, path, token=None, body=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode())
        except Exception:
            err_body = None
        return e.code, err_body
    except Exception as e:
        return -1, {"error": str(e)}


def check(name, ok, detail=""):
    RESULT["checks"].append({"name": name, "pass": ok, "detail": str(detail)[:300]})
    mark = "✅" if ok else "❌"
    print(f"{mark} {name}: {detail[:120] if detail else ('OK' if ok else 'FAIL')}")


# 1. 登录
code, data = req("POST", "/auth/login", body={"username": "admin", "password": "Demo@2026"})
token = data.get("access_token") if code == 200 else None
check("登录 admin/Demo@2026", code == 200 and token, f"HTTP {code}")

# 2. 场地列表
code, data = req("GET", "/sites", token)
sites = data.get("items", []) if code == 200 else []
check("场地列表", code == 200 and len(sites) >= 1, f"{len(sites)} 个场地")

    # 3. 场地诊断 (HM 生产轨) - POST 方法
if sites:
    sid = sites[0]["id"]
    code, data = req("POST", f"/sites/{sid}/kos-diagnosis?track=prod&subset=hm", token)
    obstacles = (data or {}).get("key_obstacles", []) or (data or {}).get("explicit_obstacles", [])
    hm_ok = code == 200 and len(obstacles) >= 1
    check("KOS诊断 HM 生产轨", hm_ok,
          f"HTTP {code}, key_obstacles={len((data or {}).get('key_obstacles', []))}")
    if data:
        RESULT["summary"]["hm_top3"] = [f.get("factor") for f in data.get("key_obstacles", [])[:3]]
        RESULT["summary"]["hm_model_status"] = data.get("model_status")
        RESULT["summary"]["hm_review_required"] = data.get("review_required")

    # 4. KOS诊断 HM+OP (探索性模型) - POST 方法
    code, data = req("POST", f"/sites/{sid}/kos-diagnosis?track=prod&subset=hm_op", token)
    hmop_ok = code == 200 and (data or {}).get("model_status") == "exploratory"
    check("KOS诊断 HM+OP(探索性+强制复核)", hmop_ok,
          f"HTTP {code}, status={data.get('model_status') if data else '-'}, review={data.get('review_required') if data else '-'}")

    # 5. AI 配置读取 (ai/status 端点)
    code, data = req("GET", "/ai/status", token)
    ai_ok = code == 200 and (data or {}).get("model") == "glm-5.2"
    check("AI配置=GLM-5.2智谱官网", ai_ok,
          f"HTTP {code}, provider={data.get('provider') if data else '-'}, model={data.get('model') if data else '-'}")

    # 6. AI 对话 (POST /ai/chat, body 带 site_id)
    code, data = req("POST", "/ai/chat",
                     token, {"message": "这个场地的镉污染风险如何？简要回答", "site_id": sid})
    ai_chat_ok = code == 200 and bool((data or {}).get("reply"))
    check("AI对话 GLM-5.2 真实调用", ai_chat_ok,
          f"HTTP {code}, reply长度={len(data.get('reply', '')) if data else 0}, model={data.get('model') if data else '-'}")
    if data:
        RESULT["summary"]["ai_reply_sample"] = data.get("reply", "")[:200]
        RESULT["summary"]["ai_configured"] = data.get("configured")

# 汇总
passed = sum(1 for c in RESULT["checks"] if c["pass"])
total = len(RESULT["checks"])
RESULT["summary"]["passed"] = passed
RESULT["summary"]["total"] = total
print(f"\n{'='*60}\nAPI 闭环结果: {passed}/{total} 通过\n{'='*60}")

with open("artifacts/demo_reports_v2_20260703/api_smoke_result.json", "w", encoding="utf-8") as f:
    json.dump(RESULT, f, ensure_ascii=False, indent=2)
print("结果已保存: artifacts/demo_reports_v2_20260703/api_smoke_result.json")
