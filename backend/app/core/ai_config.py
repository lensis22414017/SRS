"""AI 大模型运行时配置覆盖层。

设计(遵守 CLAUDE.md §11 安全): 用户可在系统管理页自选模型/接入自己的 key。
- 覆盖配置存为应用数据目录下的 ai_config.json (与 .env 同级别的本机私密文件);
- 不入数据库、不进 Git、不随包分发 —— 仅落在用户本机, 避免密钥泄漏;
- 未配置覆盖时回退到 .env 的 AI_BASE_URL / AI_API_KEY / AI_MODEL;
- 默认模型: 智谱 GLM 官方 OpenAI 兼容接口的免费 Flash 模型。
"""
from __future__ import annotations

import json
import os

from app.core.config import _app_data_dir, get_settings

_OVERRIDE_PATH = os.path.join(_app_data_dir(), "ai_config.json")

# 默认: 智谱 GLM 官方(免费 Flash)。base_url 为 OpenAI 兼容端点。
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
DEFAULT_MODEL = "GLM-4.7-Flash"

# 预设服务商(均为 OpenAI 兼容 /chat/completions 端点), 供前端下拉选择。
PROVIDER_PRESETS = [
    {"id": "zhipu", "name": "智谱 GLM-5.2(官网·推荐)",
     "base_url": "https://open.bigmodel.cn/api/paas/v4",
     "model": "glm-5.2",
     "apply_url": "https://open.bigmodel.cn/usercenter/apikeys",
     "note": "智谱最新旗舰模型, OpenAI兼容, 思考模式已默认关闭以控延迟。"},
    {"id": "deepseek", "name": "DeepSeek 深度求索",
     "base_url": "https://api.deepseek.com", "model": "deepseek-chat",
     "apply_url": "https://platform.deepseek.com/api_keys", "note": "性价比高。"},
    {"id": "dashscope", "name": "阿里通义千问(DashScope)",
     "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus",
     "apply_url": "https://dashscope.console.aliyun.com/apiKey", "note": "兼容模式端点。"},
    {"id": "siliconflow", "name": "硅基流动 SiliconFlow",
     "base_url": "https://api.siliconflow.cn/v1", "model": "zai-org/GLM-5.2",
     "apply_url": "https://cloud.siliconflow.cn/account/ak",
     "note": "多模型聚合(GLM-5.2/DeepSeek-V4/Qwen3.5), 有免费额度, OpenAI兼容。"},
    {"id": "moonshot", "name": "月之暗面 Kimi",
     "base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k",
     "apply_url": "https://platform.moonshot.cn/console/api-keys", "note": "长上下文。"},
    {"id": "openai", "name": "OpenAI",
     "base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
     "apply_url": "https://platform.openai.com/api-keys", "note": "需海外网络。"},
    {"id": "ollama", "name": "本地 Ollama(离线)",
     "base_url": "http://127.0.0.1:11434/v1", "model": "qwen2.5",
     "apply_url": "https://ollama.com/", "note": "本机离线, key 可留空填 ollama。"},
    {"id": "custom", "name": "自定义(其他 OpenAI 兼容服务)",
     "base_url": "", "model": "", "apply_url": "", "note": "手动填写 base_url 与模型名。"},
]

_ALLOWED = {"base_url", "api_key", "model", "provider"}


def load_override() -> dict:
    """读取本机覆盖配置; 不存在或损坏则返回空 dict。"""
    if not os.path.isfile(_OVERRIDE_PATH):
        return {}
    try:
        with open(_OVERRIDE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if k in _ALLOWED}
    except Exception:  # noqa: BLE001 — 损坏文件不应让服务崩溃
        return {}


def save_override(base_url: str, api_key: str | None, model: str,
                  provider: str = "custom") -> dict:
    """保存覆盖配置到本机 JSON。api_key 为 None/空时保留原 key(仅改模型/端点)。"""
    cur = load_override()
    out = {
        "provider": provider,
        "base_url": (base_url or "").strip(),
        "model": (model or "").strip() or DEFAULT_MODEL,
    }
    if api_key:  # 仅在显式传入新 key 时覆盖, 避免前端不回显 key 导致被清空
        out["api_key"] = api_key.strip()
    elif cur.get("api_key"):
        out["api_key"] = cur["api_key"]
    os.makedirs(os.path.dirname(_OVERRIDE_PATH), exist_ok=True)
    with open(_OVERRIDE_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(_OVERRIDE_PATH, 0o600)  # 仅当前用户可读写
    except OSError:
        pass
    return out


def effective_ai() -> dict:
    """返回当前生效的 AI 配置: 本机覆盖 > .env > 内置默认 base_url/model。

    返回 {base_url, api_key, model, source, configured, provider}。
    """
    s = get_settings()
    ov = load_override()
    base_url = ov.get("base_url") or s.ai_base_url or ""
    api_key = ov.get("api_key") or s.ai_api_key or ""
    model = ov.get("model") or s.ai_model or DEFAULT_MODEL
    source = "override" if ov else ("env" if (s.ai_base_url or s.ai_api_key) else "default")
    return {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "provider": ov.get("provider", "custom"),
        "source": source,
        "configured": bool(base_url and api_key),
    }


def mask_key(key: str | None) -> str:
    if not key:
        return ""
    return key[:6] + "***" + key[-4:] if len(key) > 12 else "***"


# ============ 连通性缓存(写时测试 + 读时缓存, 避免高频 GET /ai/status 真实调端点) ============
# 设计: PUT 配置 / POST test 时真实调一次端点 → 落盘 ai_connectivity.json {ok,last_checked,error};
#       GET status 只读缓存(瞬时返回); TTL 10 分钟, 过期标 stale 由前端提示重测。
_CONNECTIVITY_PATH = os.path.join(_app_data_dir(), "ai_connectivity.json")
_CONNECTIVITY_TTL = 600  # 秒


def load_connectivity() -> dict | None:
    """读取最近一次连通性测试结果; 不存在/损坏返回 None。"""
    if not os.path.isfile(_CONNECTIVITY_PATH):
        return None
    try:
        with open(_CONNECTIVITY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def save_connectivity(ok: bool, error: str | None = None) -> dict:
    """落盘连通性结果 + 当前时间戳。"""
    import time as _time
    data = {"ok": bool(ok), "last_checked": _time.time(), "error": error}
    os.makedirs(os.path.dirname(_CONNECTIVITY_PATH), exist_ok=True)
    with open(_CONNECTIVITY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    try:
        os.chmod(_CONNECTIVITY_PATH, 0o600)
    except OSError:
        pass
    return data


def connectivity_status() -> dict:
    """供 GET /ai/status 直接用: {ok, last_checked, error, stale}。
    ok=None 表示从未测试过; stale=True 表示缓存过期需重测。"""
    c = load_connectivity()
    if not c:
        return {"ok": None, "last_checked": None, "error": None, "stale": True}
    import time as _time
    stale = (_time.time() - float(c.get("last_checked") or 0)) > _CONNECTIVITY_TTL
    return {"ok": bool(c.get("ok")), "last_checked": c.get("last_checked"),
            "error": c.get("error"), "stale": stale}


def test_connectivity() -> tuple[bool, str | None]:
    """真实调一次 AI /chat/completions 端点; 成功 (True, None) 并落盘; 失败 (False, error) 并落盘。

    遵守 CLAUDE.md §11: 不硬编码 key, 用 effective_ai() 当前生效配置。
    """
    import urllib.error
    import urllib.request
    cfg = effective_ai()
    if not cfg["base_url"] or not cfg["api_key"]:
        save_connectivity(False, "未配置 base_url 或 api_key")
        return False, "未配置 base_url 或 api_key"
    payload = json.dumps({"model": cfg["model"],
                          "messages": [{"role": "user", "content": "你好"}],
                          "max_tokens": 8, "temperature": 0}).encode("utf-8")
    req = urllib.request.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cfg['api_key']}"})
    try:
        with urllib.request.urlopen(req, timeout=get_settings().ai_timeout) as resp:
            json.loads(resp.read().decode("utf-8"))
        save_connectivity(True, None)
        return True, None
    except urllib.error.HTTPError as e:
        err = f"HTTP {e.code}: {e.reason}"
        save_connectivity(False, err)
        return False, err
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {e}"
        save_connectivity(False, err)
        return False, err
