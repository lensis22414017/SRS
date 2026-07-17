"""FastAPI 入口。SRS系统 v1.0.2。

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
    yield

app = FastAPI(title=settings.app_name, version="1.0.2", lifespan=lifespan)

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
app.include_router(data_router)
app.include_router(diagnosis_router)
app.include_router(evaluation_router)
app.include_router(map_router)
app.include_router(workflow_router)
app.include_router(system_router)
app.include_router(ai_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": "1.0.2"}


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
