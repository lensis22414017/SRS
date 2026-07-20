"""FastAPI 入口。SRS系统 v1.0.1。

桌面打包模式: 若检测到 ../frontend/dist 存在, 自动挂载静态前端并启用 SPA 回退。
数据库: 首次启动自动建表 + 种子数据 (幂等, 不覆盖已有数据)。
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.setup import router as setup_router
from app.api.economic import router as economic_router
from app.api.backup import router as backup_router  # v1.0.2: 备份恢复
from app.api.data import router as data_router
from app.api.diagnosis import router as diagnosis_router
from app.api.evaluation import router as evaluation_router
from app.api.map import router as map_router
from app.api.system import router as system_router
from app.api.workflow import router as workflow_router
from app.core.config import get_settings

settings = get_settings()

# ── 启动事件: 自动建表 + 种子数据 (幂等) ──────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    import warnings
    if settings.secret_key == "CHANGE_ME_IN_ENV":
        warnings.warn(
            "[SRS] secret_key 使用默认值 'CHANGE_ME_IN_ENV'！"
            "请在 .env 中设置强随机密钥，否则 JWT 安全性为零。",
            stacklevel=2,
        )
    from app.db.init_db import create_all
    from app.db.seed_db import seed_if_empty
    create_all()
    seed_if_empty()
    # v1.0.1 final-audit: 启动时模型完整性健康检查(缺失直接警告, 诊断时阻断)
    app.state.model_health = _check_model_integrity()
    # 启动定时备份后台线程(每天凌晨2:00)
    from app.services.backup_service import init_scheduler
    backup_stop_event = init_scheduler()
    # 字段级加密钩子(User.email/phone)
    from app.models.crypto_hooks import init_crypto_hooks  # noqa: F401
    init_crypto_hooks()
    yield
    # 优雅关闭定时备份
    backup_stop_event.set()


def _check_model_integrity(root_override: str | None = None) -> dict:
    """启动时检查模型工件完整性(KOS诊断必需)。

    R3 审计第七类 7.6: 解析 registry, 逐一核对 frontend_enabled 模型的:
      1. joblib 存在且可加载
      2. shap_global parquet 存在且可读
      3. metrics json 存在且可解析
    缺失时返回 {ok: False, reason: ..., missing: [...], load_errors: [...]}
    """
    import os, sys, json
    root = root_override or (
        sys._MEIPASS if getattr(sys, "frozen", False)
        else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    # PyInstaller _internal 目录兼容
    if not os.path.isdir(os.path.join(root, "ml")):
        _internal = os.path.join(root, "_internal")
        if os.path.isdir(os.path.join(_internal, "ml")):
            root = _internal
    art_dir = os.path.join(root, "ml", "artifacts", "p3_alpha")
    registry = os.path.join(art_dir, "model_registry_v0.8.json")
    if not os.path.isfile(registry):
        return {"ok": False, "reason": f"模型注册表缺失: {registry}", "checked_at": _now()}

    try:
        with open(registry, encoding="utf-8") as f:
            reg_data = json.load(f)
    except Exception as e:
        return {"ok": False, "reason": f"注册表解析失败: {e}", "checked_at": _now()}

    checked_models = []
    missing = []
    load_errors = []
    n_ok = 0

    def _artifact_path(raw_path: str) -> str:
        normalized = raw_path.replace("\\", os.sep).replace("/", os.sep)
        return normalized if os.path.isabs(normalized) else os.path.join(root, normalized)

    for model_id, info in reg_data.get("models", {}).items():
        # 只核对 frontend_enabled 的模型(生产可用集)
        if not info.get("frontend_enabled", False):
            continue
        model_file = info.get("model_file", "")
        shap_file = info.get("shap_global_file", "")
        metrics_file = info.get("metrics_file", "")
        issues = []

        # 1. joblib 存在且可加载
        joblib_path = _artifact_path(model_file) if model_file else ""
        if not model_file or not os.path.isfile(joblib_path):
            issues.append(f"joblib缺失: {model_file}")
            missing.append(f"{model_id}/joblib")
        else:
            try:
                import joblib
                joblib.load(joblib_path)
            except Exception as e:
                issues.append(f"joblib加载失败: {e}")
                load_errors.append(f"{model_id}: {e}")

        # 2. shap parquet 存在且可读
        shap_path = _artifact_path(shap_file) if shap_file else ""
        if not shap_file or not os.path.isfile(shap_path):
            issues.append(f"parquet缺失: {shap_file}")
            missing.append(f"{model_id}/shap_parquet")
        else:
            try:
                import pandas as pd
                pd.read_parquet(shap_path)
            except Exception as e:
                issues.append(f"parquet读取失败: {e}")
                load_errors.append(f"{model_id}/shap: {e}")

        # 3. metrics json 存在且可解析
        metrics_path = _artifact_path(metrics_file) if metrics_file else ""
        if metrics_file and not os.path.isfile(metrics_path):
            issues.append(f"metrics缺失: {metrics_file}")
            missing.append(f"{model_id}/metrics")
        elif metrics_file:
            try:
                with open(metrics_path, encoding="utf-8") as f:
                    json.load(f)
            except Exception as e:
                issues.append(f"metrics解析失败: {e}")
                load_errors.append(f"{model_id}/metrics: {e}")

        if issues:
            checked_models.append({"model_id": model_id, "status": "error", "issues": issues})
        else:
            checked_models.append({"model_id": model_id, "status": "ok"})
            n_ok += 1

    n_required = len(checked_models)
    if n_required == 0:
        return {"ok": False, "reason": "注册表未声明 frontend_enabled 模型",
                "checked_models": checked_models, "missing": missing,
                "load_errors": load_errors, "checked_at": _now()}
    if n_ok != n_required:
        return {"ok": False, "reason": "一个或多个 frontend_enabled 模型工件不可用",
                "checked_models": checked_models, "missing": missing,
                "load_errors": load_errors, "checked_at": _now()}
    return {"ok": True, "n_models_ok": n_ok, "n_models_checked": len(checked_models),
            "checked_models": checked_models, "missing": missing,
            "load_errors": load_errors, "checked_at": _now()}


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat()

app = FastAPI(title=settings.app_name, version="1.0.1", lifespan=lifespan)

# ── CORS: 开发模式 (Vite dev server) + 同源部署均兼容 ──────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",  # Vite 开发
        "http://localhost:8000", "http://127.0.0.1:8000",  # 同源部署
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API 路由 ──────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(setup_router)  # R3 审计第六类: 首启管理员设置向导
app.include_router(economic_router)  # R3 审计第五类: SSUI D18-D25 经济数据
app.include_router(data_router)
app.include_router(diagnosis_router)
app.include_router(evaluation_router)
app.include_router(map_router)
app.include_router(workflow_router)
app.include_router(system_router)
app.include_router(ai_router)
app.include_router(backup_router)  # v1.0.2: 备份恢复


@app.get("/health")
def health():
    model_health = getattr(app.state, "model_health", {})
    # R3 审计第七类 7.7: 模型不完整时 status=degraded(不再恒为 ok)
    status = "ok" if model_health.get("ok") else "degraded"
    return {"status": status, "app": settings.app_name, "version": "1.0.1",
            "model_health": model_health}


@app.get(settings.api_v1_prefix + "/info")
def info():
    return {
        "name": settings.app_name,
        "mvp": "单场地闭环 v0.1",
        "modules": ["数据管理", "决策管理", "全流程追溯", "系统管理"],
    }


# ── 前端静态文件 + SPA 回退 (桌面打包模式) ─────────────────────────
# ⚠️ 必须在所有 API 路由之后注册, 否则 catch-all 会拦截 /health 等
def _candidate_dist_dirs() -> list[str]:
    """枚举前端 dist 的所有可能位置, 覆盖 源码运行 与 PyInstaller .app/onedir 各种布局。"""
    cands: list[str] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cands.append(os.path.join(meipass, "frontend", "dist"))
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        # macOS .app: Contents/MacOS/SRS → Contents/{Resources,Frameworks}/frontend/dist
        cands += [
            os.path.join(exe_dir, "frontend", "dist"),
            os.path.abspath(os.path.join(exe_dir, "..", "Resources", "frontend", "dist")),
            os.path.abspath(os.path.join(exe_dir, "..", "Frameworks", "frontend", "dist")),
            os.path.abspath(os.path.join(exe_dir, "_internal", "frontend", "dist")),
        ]
    cands += [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")),
        os.path.abspath(os.path.join(os.getcwd(), "frontend", "dist")),
    ]
    return cands


def _resolve_dist() -> str | None:
    """请求/导入时解析有效 dist 目录(含 index.html)。找不到返回 None。"""
    for p in _candidate_dist_dirs():
        if os.path.isdir(p) and os.path.isfile(os.path.join(p, "index.html")):
            return p
    return None


FRONTEND_DIST = _resolve_dist()
if FRONTEND_DIST:
    _assets = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(_assets):
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

_RESERVED = ("api/", "health", "docs", "redoc", "openapi.json", "assets/")
_DIAG_HTML = (
    "<!doctype html><meta charset=utf-8><title>SRS</title>"
    "<div style='font-family:system-ui;max-width:640px;margin:80px auto;color:#1f2937'>"
    "<h2 style='color:#0f3d6e'>SRS 后端已启动，但未找到前端页面</h2>"
    "<p>打包产物缺少 <code>frontend/dist</code>，或路径未被正确收集。</p>"
    "<p>请确认打包前已执行 <code>cd frontend &amp;&amp; npm run build</code>，"
    "且 <code>packaging/srs.spec</code> 的 datas 含 <code>(frontend/dist, frontend/dist)</code>。</p>"
    "<p>后端 API 正常可用：<a href='/docs'>/docs</a> · <a href='/health'>/health</a></p></div>"
)


@app.get("/")
async def spa_root():
    """根路径返回 index.html;dist 缺失时返回清晰诊断页(避免黑屏 + 裸 404)。"""
    dist = FRONTEND_DIST or _resolve_dist()
    if dist:
        return FileResponse(os.path.join(dist, "index.html"))
    return HTMLResponse(_DIAG_HTML, status_code=200)


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """非保留前缀的路径回退到 index.html, 支持前端 SPA 路由。"""
    if any(full_path == r.rstrip("/") or full_path.startswith(r) for r in _RESERVED):
        raise HTTPException(status_code=404, detail="Not Found")
    dist = FRONTEND_DIST or _resolve_dist()
    if not dist:
        return HTMLResponse(_DIAG_HTML, status_code=200)
    fp = os.path.join(dist, full_path)
    if os.path.isfile(fp):
        return FileResponse(fp)
    return FileResponse(os.path.join(dist, "index.html"))
