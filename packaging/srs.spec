# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — SRS 污染场地监管系统 桌面打包。

构建:
  cd <项目根目录>
  backend/.venv/bin/pyinstaller packaging/srs.spec --clean

输出:
  dist/SRS.app/  (macOS .app bundle)
  dist/SRS/      (Linux/Windows 目录)
"""

import os
import sys
from pathlib import Path

# Windows exe 版本信息: 无条件 import + 对象内联到 EXE(version_info=...), onedir 入口 exe 有效
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
        StringStruct, VarFileInfo, VarStruct,
    )
    _VI = VSVersionInfo(
        ffi=FixedFileInfo(filevers=(1,0,1,0), prodvers=(1,0,1,0), mask=0x3f,
                          flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0,0)),
        kids=[StringFileInfo([StringTable('040904B0', [
            StringStruct('CompanyName', '生态环境部土壤与农业农村生态环境监管技术中心'),
            StringStruct('FileDescription', 'Soil Remediation Supervision System (SRS)'),
            StringStruct('FileVersion', '1.0.1.0'),
            StringStruct('InternalName', 'SRS'),
            StringStruct('LegalCopyright', 'Copyright (c) 2026 生态环境部土壤与农业农村生态环境监管技术中心'),
            StringStruct('OriginalFilename', 'SRS.exe'),
            StringStruct('ProductName', 'SRS - Contaminated Site Supervision System'),
            StringStruct('ProductVersion', '1.0.1.0'),
        ])]), VarFileInfo([VarStruct('Translation', [0x0409, 1200])])])
else:
    _VI = None
_version_file = None  # 不用 version_file(spec 内 version_info 对象更直接)

# 自动定位项目根: SPECPATH 是 PyInstaller 注入的 spec 文件所在目录(packaging/), 父级即项目根
# 跨平台跨机器通用, 不依赖 __file__(spec 执行时未定义)
PROJECT_ROOT = Path(SPECPATH).resolve().parent

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

# 离线地图行政区数据 (三级金字塔: 省/地市/县 GeoJSON + 索引, ~27MB, 随 exe 分发)
geo_dir = PROJECT_ROOT / "data" / "geo"
if geo_dir.is_dir():
    added_files.append((str(geo_dir), "data/geo"))

# 离线地图影像 MBTiles (可选, 由 download_tianditu_mbtiles.py 生成; 存在则打包)
tiles_dir = PROJECT_ROOT / "data" / "geo" / "tiles"
if tiles_dir.is_dir() and any(tiles_dir.glob("*.mbtiles")):
    added_files.append((str(tiles_dir), "data/geo/tiles"))

# ML 模型工件 (如果存在)
ml_artifacts = PROJECT_ROOT / "ml" / "artifacts"
if ml_artifacts.is_dir() and any(ml_artifacts.iterdir()):
    added_files.append((str(ml_artifacts), "ml/artifacts"))

# ML 关键 JSON 资源(诊断特征映射 + GEE 协变量标签)
for _json in ("ml/models/feature_mapping.json", "ml/covariates/gee_labels.json"):
    _f = PROJECT_ROOT / _json
    if _f.is_file():
        added_files.append((str(_f), "/".join(_json.split("/")[:-1])))

# 标准阈值 CSV(诊断/评价/超标判定依赖)
std_dir = PROJECT_ROOT / "data" / "standards"
if std_dir.is_dir() and any(std_dir.glob("*.csv")):
    added_files.append((str(std_dir), "data/standards"))

# M0-9: 开放集识别运行时必需的知识库文件(别名表 / 单位转换 / 族群库 / 化合物别名)
# 这些文件由 factor_normalizer.py + open_set_classifier.py 在运行时按需读取,
# 单独追加(非整目录打包)以避免把 data/knowledge 全量分发(部分文件仅开发态使用)。
_knowledge_dir = PROJECT_ROOT / "data" / "knowledge"
if _knowledge_dir.is_dir():
    # 别名与单位转换(factor_normalizer 必读)
    for _kn in ("factor_aliases_v0.8.yaml", "unit_conversion_rules_v0.8.yaml"):
        _kf = _knowledge_dir / _kn
        if _kf.is_file():
            added_files.append((str(_kf), "data/knowledge"))
    # 族群库 + 化合物别名(open_set_classifier 必读)
    for _kn in ("family_factor_library_v0.8.csv", "compound_aliases_v0.8.yaml"):
        _kf = _knowledge_dir / _kn
        if _kf.is_file():
            added_files.append((str(_kf), "data/knowledge"))

# ML 源码子目录: 后端服务运行时 sys.path.insert(resource_root()/ml/<sub>) 后再 import,
# 这些 .py 必须随包分发, 否则打包后 诊断/评价/推荐/知识库入库 会 ImportError。
for _sub in ("etl", "models", "explain", "recommend", "evaluation", "cleaning", "eda", "params", "covariates", "ranking", "rules"):
    _d = PROJECT_ROOT / "ml" / _sub
    if _d.is_dir() and (any(_d.glob("*.py")) or any(_d.glob("*.json"))):
        added_files.append((str(_d), f"ml/{_sub}"))

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
    # 报告内采样点静态图件(离线渲染, 不依赖地图服务)
    "matplotlib", "matplotlib.pyplot", "matplotlib.backends.backend_agg",
    # 数据处理
    "pandas", "numpy", "openpyxl",
    # 认证
    "bcrypt", "jose",
    # 工具
    "redis",
    # 桌面原生窗口 (pywebview, 可选; 若未安装则降级到 webbrowser)
    "webview", "webview.platforms.cocoa", "webview.platforms.winforms",
    "webview.platforms.gtk",
    # pkg_resources 运行时依赖(weasyprint/reportlab 间接引入)
    "jaraco", "jaraco.text", "jaraco.functools", "jaraco.context",
    # 裴总决策: 恢复内置 key 预配(甲方开箱即用), builtin_keys.py 随包分发
    # .gitignore 排除不入仓库, 但 PyInstaller 打包时需能 import
    "builtin_keys",
    # M0 新增服务模块(需显式声明, 否则 PyInstaller 不收集动态 import)
    "app.services.factor_normalizer",
    "app.services.open_set_classifier",
    "app.services.diagnosis_fact_check",
    "app.services.threshold_resolver",
]

# ── 排除模块 ────────────────────────────────────────────────────
excluded_imports = [
    "pytest", "_pytest", "pluggy",
    "pip", "setuptools", "wheel",
    "tkinter", "_tkinter",
    "PIL",  # 未使用
    # Qt bindings: matplotlib backend 探测会引入 PyQt5/PySide6, 两者冲突且 SRS 不需要(Qt 桌面框架)
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "matplotlib.backends.backend_qt5agg", "matplotlib.backends.backend_qt",
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
    pathex=[str(PROJECT_ROOT), str(PROJECT_ROOT / "backend"), str(PROJECT_ROOT / "packaging")],
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

# ── EXE + COLLECT (onedir: Windows/Linux 输出 dist/SRS/ 目录含 SRS.exe) ─
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # onedir: 二进制/数据由 COLLECT 收集
    name="SRS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # GUI 模式不显示终端(pyperforms 窗口/浏览器降级)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(PROJECT_ROOT / "packaging" / "srs_icon_v4.ico") if (PROJECT_ROOT / "packaging" / "srs_icon_v4.ico").exists() else (str(PROJECT_ROOT / "packaging" / "srs_icon_v3.ico") if (PROJECT_ROOT / "packaging" / "srs_icon_v3.ico").exists() else None),  # v4蓝盾双层+绿芽(加宽), 回退v3
    version_info=_VI,  # Windows 版本信息对象(公司名/版权/版本)
)

# Windows/Linux: COLLECT 收集全部依赖到 dist/SRS/ 目录
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SRS",
)

# ── macOS .app Bundle (仅 darwin) ─
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SRS.app",
        icon=str(PROJECT_ROOT / "packaging" / "srs.icns") if (PROJECT_ROOT / "packaging" / "srs.icns").exists() else None,
        bundle_identifier="com.srs.soil-remediation",
        info_plist={
            "CFBundleName": "SRS",
            "CFBundleDisplayName": "污染场地监管系统",
            "CFBundleIdentifier": "com.srs.soil-remediation",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "NSHumanReadableCopyright": "© 2026 SRS Project",
            "LSMinimumSystemVersion": "11.0",
        },
    )
