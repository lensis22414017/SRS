# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — SRS 污染场地监管系统 桌面打包。

构建:
  cd /Users/lensis/Claude/Projects/SRS
  backend/.venv/bin/pyinstaller packaging/srs.spec --clean

输出:
  dist/SRS.app/  (macOS .app bundle)
  dist/SRS/      (Linux/Windows 目录)
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path('/Users/lensis/Claude/Projects/SRS')

# ── 数据文件 ────────────────────────────────────────────────────
added_files = []

# 前端构建产物
frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.is_dir():
    added_files.append((str(frontend_dist), "frontend/dist"))

# 报告模板
report_templates = PROJECT_ROOT / "reporting" / "templates"
if report_templates.is_dir():
    added_files.append((str(report_templates), "reporting/templates"))

# 知识库 (阈值、技术库、修复案例)
kb_dir = PROJECT_ROOT / "data" / "knowledge_base"
if kb_dir.is_dir():
    added_files.append((str(kb_dir), "data/knowledge_base"))

# ML 模型工件 (如果存在)
ml_artifacts = PROJECT_ROOT / "ml" / "artifacts"
if ml_artifacts.is_dir() and any(ml_artifacts.iterdir()):
    added_files.append((str(ml_artifacts), "ml/artifacts"))

# 服务映射文件
mappings_dir = PROJECT_ROOT / "backend" / "app" / "services" / "mappings"
if mappings_dir.is_dir():
    added_files.append((str(mappings_dir), "app/services/mappings"))

# ── 隐藏导入 ────────────────────────────────────────────────────
hidden_imports = [
    # FastAPI / ASGI
    "uvicorn", "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
    "fastapi", "starlette",
    # SQLAlchemy
    "sqlalchemy", "sqlalchemy.ext.asyncio",
    # ML
    "sklearn", "sklearn.ensemble", "sklearn.ensemble._forest",
    "shap", "shap.explainers", "shap.explainers._tree",
    # 报告
    "jinja2", "xhtml2pdf", "reportlab",
    "reportlab.pdfbase", "reportlab.pdfbase.cidfonts",
    "weasyprint", "docx",
    # 数据处理
    "pandas", "numpy", "openpyxl",
    # 认证
    "bcrypt", "jose",
    # 工具
    "redis",
]

# ── 排除模块 ────────────────────────────────────────────────────
excluded_imports = [
    "pytest", "_pytest", "pluggy",
    "pip", "setuptools", "wheel",
    "tkinter", "_tkinter",
    "matplotlib", "PIL",  # 未使用
]

# ── macOS .app 信息 ─────────────────────────────────────────────
app_info = {
    "NSHighResolutionCapable": "True",
    "CFBundleName": "SRS",
    "CFBundleDisplayName": "污染场地监管系统",
    "CFBundleIdentifier": "com.srs.soil-remediation",
    "CFBundleVersion": "0.1.0",
    "CFBundleShortVersionString": "0.1.0",
    "NSHumanReadableCopyright": "© 2026 SRS Project",
}

# ── Analysis ────────────────────────────────────────────────────
a = Analysis(
    [str(PROJECT_ROOT / "packaging" / "launcher.py")],
    pathex=[str(PROJECT_ROOT), str(PROJECT_ROOT / "backend")],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_imports,
    noarchive=False,
    optimize=0,
)

# ── 过滤不必要的动态库 ──────────────────────────────────────────
a.binaries = [
    (name, path, typ) for name, path, typ in a.binaries
    if "tkinter" not in name.lower()
]

# ── PYZ ─────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data)

# ── EXE ─────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SRS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示终端窗口 (macOS .app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
)

# ── macOS .app Bundle ───────────────────────────────────────────
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="SRS.app",
        icon=str(PROJECT_ROOT / "packaging" / "icon.icns") if (PROJECT_ROOT / "packaging" / "icon.icns").exists() else None,
        bundle_identifier=app_info["CFBundleIdentifier"],
        info_plist=app_info,
    )
