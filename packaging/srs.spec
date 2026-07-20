# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — SRS 污染场地监管系统 桌面打包。

构建:
  cd <项目根目录>
  backend/.venv/bin/pyinstaller packaging/srs.spec --clean --distpath dist_new

输出:
  dist_new/SRS.app/  (macOS .app bundle)
  dist_new/SRS/      (Linux/Windows 目录, ARTIFACT_ROOT)
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

# 前端构建产物 — v1.0.2(GPT 9.5): 强制依赖, 缺失则构建失败
frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if not frontend_dist.is_dir():
    raise SystemExit("BUILD FAILED: frontend/dist 不存在, 请先 npm run build (GPT 9.5 强制依赖)")
# v1.0.2(GPT 8.2): 校验 7 张流程图在 dist/assets/flows/ 下
_flows_in_dist = frontend_dist / "assets" / "flows"
_expected_flows = ["obstacle_analysis.svg", "reconstruction_eval.svg", "ssui_eval.svg",
                   "recommendation.svg", "trace_workflow.svg", "data_import.svg", "report_generation.svg"]
if not _flows_in_dist.is_dir():
    raise SystemExit("BUILD FAILED: frontend/dist/assets/flows 整体缺失")
_missing_flows = [f for f in _expected_flows if not (_flows_in_dist / f).is_file()]
if _missing_flows:
    raise SystemExit(f"BUILD FAILED: 流程图缺失: {_missing_flows}")
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

# ML 模型工件 — v1.0.2(GPT P0-1/P0-7): 强制依赖, 缺失则构建失败
ml_artifacts = PROJECT_ROOT / "ml" / "artifacts"
if not (ml_artifacts.is_dir() and any(ml_artifacts.iterdir())):
    raise SystemExit("BUILD FAILED: ml/artifacts 缺失, KOS诊断无法运行 (GPT P0-1 强制依赖)")
# 校验 registry 中全部 frontend_enabled 模型及配套工件
_registry = ml_artifacts / "p3_alpha" / "model_registry_v0.8.json"
if not _registry.is_file():
    raise SystemExit("BUILD FAILED: model_registry_v0.8.json 缺失 (GPT P0-1 强制依赖)")
import json as _json
import joblib as _joblib
import pandas as _pd
with _registry.open(encoding="utf-8") as _handle:
    _registry_data = _json.load(_handle)
_required_models = {
    model_id: info for model_id, info in _registry_data.get("models", {}).items()
    if info.get("frontend_enabled") is True
}
if not _required_models:
    raise SystemExit("BUILD FAILED: registry 未声明 frontend_enabled 模型")
for _model_id, _info in sorted(_required_models.items()):
    for _field in ("model_file", "metrics_file", "shap_global_file"):
        _raw = _info.get(_field)
        if not _raw:
            raise SystemExit(f"BUILD FAILED: {_model_id}/{_field} 未声明")
        _path = PROJECT_ROOT / str(_raw).replace("\\", "/")
        if not _path.is_file():
            raise SystemExit(f"BUILD FAILED: {_model_id}/{_field} 缺失: {_path}")
    _local = _info.get("shap_local_file")
    if _local and not (PROJECT_ROOT / str(_local).replace("\\", "/")).is_file():
        raise SystemExit(f"BUILD FAILED: {_model_id}/shap_local_file 缺失")
    _joblib.load(PROJECT_ROOT / str(_info["model_file"]).replace("\\", "/"))
    _pd.read_parquet(PROJECT_ROOT / str(_info["shap_global_file"]).replace("\\", "/"))
    with (PROJECT_ROOT / str(_info["metrics_file"]).replace("\\", "/")).open(encoding="utf-8") as _handle:
        _json.load(_handle)
added_files.append((str(ml_artifacts), "ml/artifacts"))

# ML 关键 JSON 资源(诊断特征映射 + GEE 协变量标签) — v1.0.2: 强制依赖
for _json in ("ml/models/feature_mapping.json", "ml/covariates/gee_labels.json"):
    _f = PROJECT_ROOT / _json
    if not _f.is_file():
        raise SystemExit(f"BUILD FAILED: {_json} 缺失 (GPT P0-7 强制依赖)")
    added_files.append((str(_f), "/".join(_json.split("/")[:-1])))

# 标准阈值 CSV(诊断/评价/超标判定依赖)
std_dir = PROJECT_ROOT / "data" / "standards"
_required_standard_files = [
    std_dir / "ssui_economic_reference_v1.csv",
    PROJECT_ROOT / "ml" / "params" / "evaluation_params.json",
]
for _required in _required_standard_files:
    if not _required.is_file():
        raise SystemExit(f"BUILD FAILED: 评价/标准资源缺失: {_required}")
if not std_dir.is_dir() or not any(std_dir.glob("*.csv")):
    raise SystemExit("BUILD FAILED: data/standards CSV 资源缺失")
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
    "weasyprint", "docx", "PIL", "PIL.Image", "PIL._imaging",
    # 报告内采样点静态图件(离线渲染, 不依赖地图服务)
    "matplotlib", "matplotlib.pyplot", "matplotlib.backends.backend_agg",
    # 数据处理
    "pandas", "numpy", "openpyxl",
    # R3 审计第二类: 显式 pyarrow(KOS 读 SHAP parquet, 避免 pandas 隐式依赖丢失)
    "pyarrow", "pyarrow.parquet", "pyarrow.pandas_compat",
    # 认证
    "bcrypt", "jose",
    # 工具
    "redis",
    # 桌面原生窗口 (pywebview, 可选; 若未安装则降级到 webbrowser)
    "webview", "webview.platforms.cocoa", "webview.platforms.winforms",
    "webview.platforms.gtk",
    # pkg_resources 运行时依赖(weasyprint/reportlab 间接引入)
    "jaraco", "jaraco.text", "jaraco.functools", "jaraco.context",
    # 项目方要求演示包内置 AI/地图 key，保证甲方开箱即用
    "builtin_keys",
    # M0 新增服务模块(需显式声明, 否则 PyInstaller 不收集动态 import)
    "app.services.factor_normalizer",
    "app.services.open_set_classifier",
    "app.services.diagnosis_fact_check",
    "app.services.threshold_resolver",
    # v1.0.1 final-audit: PyYAML 及其数据(factor_normalizer 依赖)
    "yaml",
]

# 强制收集 app.services 全部子模块(确保 M0 新增的都被打包)
# collect_submodules 对源码目录(非site-packages)可能不生效,
# 额外把 app/services 整目录作为 datas 打包(运行时 import 能找到)
_services_dir = PROJECT_ROOT / "backend" / "app" / "services"
if _services_dir.is_dir():
    added_files.append((str(_services_dir), "app/services"))
_migrations_dir = PROJECT_ROOT / "backend" / "app" / "migrations"
if _migrations_dir.is_dir():
    added_files.append((str(_migrations_dir), "app/migrations"))

# ── 排除模块 ────────────────────────────────────────────────────
excluded_imports = [
    "pytest", "_pytest", "pluggy",
    "pip", "setuptools", "wheel",
    "tkinter", "_tkinter",
    # Qt bindings: matplotlib backend 探测会引入 PyQt5/PySide6, 两者冲突且 SRS 不需要(Qt 桌面框架)
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "matplotlib.backends.backend_qt5agg", "matplotlib.backends.backend_qt",
    # v1.0.1: 排除冗余大型依赖(项目实际用 sklearn, 不用 catboost/plotly/googleapiclient)
    "catboost", "catboost_core", "catboost_evaluator",
    "googleapiclient", "googleapiclient.discovery", "googleapiclient.errors",
    "googleapiclient.discovery_cache",
    "plotly", "plotly.graph_objects", "plotly.express", "plotly.subplots",
    "plotly.offline", "plotly.io",
]

# ── macOS .app 信息 ─────────────────────────────────────────────
app_info = {
    "NSHighResolutionCapable": "True",
    "CFBundleName": "SRS",
    "CFBundleDisplayName": "污染场地监管系统",
    "CFBundleIdentifier": "com.srs.soil-remediation",
    "CFBundleVersion": "1.0.1",
    "CFBundleShortVersionString": "1.0.1",
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

# ── EXE + COLLECT (onedir: Windows/Linux 输出 dist_new/SRS/ (ARTIFACT_ROOT) 目录含 SRS.exe) ─
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
    icon=str(PROJECT_ROOT / "packaging" / "srs_icon_v6.ico") if (PROJECT_ROOT / "packaging" / "srs_icon_v6.ico").exists() else (str(PROJECT_ROOT / "packaging" / "srs_icon_v5.ico") if (PROJECT_ROOT / "packaging" / "srs_icon_v5.ico").exists() else None),  # v6重构之盾(深蓝+白盾+双叶+数据节点), 回退v5
    version_info=_VI,  # Windows 版本信息对象(公司名/版权/版本)
)

# Windows/Linux: COLLECT 收集全部依赖到 dist_new/SRS/ (ARTIFACT_ROOT) 目录
# v1.0.1: 过滤掉 .db 文件(— 打包不含开发库残留, 首启用全新空库)
_filtered_binaries = [b for b in a.binaries if not b[0].endswith(".db")]
_filtered_datas = [d for d in a.datas if not d[0].endswith(".db") and ".db;" not in d[0]]

coll = COLLECT(
    exe,
    _filtered_binaries,
    _filtered_datas,
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
            "CFBundleVersion": "1.0.1",
            "CFBundleShortVersionString": "1.0.1",
            "NSHumanReadableCopyright": "© 2026 SRS Project",
            "LSMinimumSystemVersion": "11.0",
        },
    )
