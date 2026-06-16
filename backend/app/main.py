"""FastAPI 入口。MVP 单场地闭环 v0.1。

桌面打包模式: 若检测到 ../frontend/dist 存在, 自动挂载静态前端并启用 SPA 回退。
数据库: 首次启动自动建表 + 种子数据 (幂等, 不覆盖已有数据)。
"""
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

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
    return {"status": "ok", "app": settings.app_name, "version": "0.1.0"}


@app.get(settings.api_v1_prefix + "/info")
def info():
    return {
        "name": settings.app_name,
        "mvp": "单场地闭环 v0.1",
        "modules": ["数据管理", "决策管理", "全流程追溯", "系统管理"],
    }


# ── 前端静态文件 + SPA 回退 (桌面打包模式) ─────────────────────────
# ⚠️ 必须在所有 API 路由之后注册, 否则 catch-all 会拦截 /health 等
def _frontend_dist_dir() -> str:
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(os.path.join(getattr(sys, "_MEIPASS", os.getcwd()),
                                       "frontend", "dist"))
    candidates.extend([
        os.path.abspath(os.path.join(os.path.dirname(__file__),
                                     "..", "..", "frontend", "dist")),
        os.path.abspath(os.path.join(os.getcwd(), "frontend", "dist")),
    ])
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]


FRONTEND_DIST = _frontend_dist_dir()
if os.path.isdir(FRONTEND_DIST):
    ASSETS_DIR = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """非 /api /health 路径回退到 index.html, 支持前端 SPA 路由。"""
        fp = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(fp) and not full_path.startswith("api/"):
            return FileResponse(fp)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
