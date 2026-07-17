#!/usr/bin/env python3
"""SRS 桌面启动器 — macOS / Windows / Linux 通用。

功能:
  1. 确保应用数据目录存在 (首次启动自动初始化数据库)
  2. 启动 FastAPI 后端服务
  3. 自动打开浏览器
  4. macOS: 菜单栏托盘图标 (右键退出)

启动方式:
  python packaging/launcher.py                     # 开发模式
  python packaging/launcher.py --no-browser         # 不自动打开浏览器
  python packaging/launcher.py --port 8080           # 自定义端口

打包后:
  PyInstaller 将本脚本作为入口点, 自动检测 sys.frozen 环境。
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
import webbrowser

# Windows 控制台默认 GBK, print emoji(🛡️🔍✅等)会 UnicodeEncodeError; 打包后无控制台但仍可能触发
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def ensure_app_dirs():
    """确保应用数据目录存在 (首次启动由 lifespan 自动建表)。"""
    from app.core.config import get_settings
    s = get_settings()
    storage = s.file_storage_dir
    os.makedirs(storage, exist_ok=True)
    # 数据库文件父目录
    db_url = s.database_url
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        db_dir = os.path.dirname(os.path.abspath(db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)


def inject_builtin_keys():
    """首次启动时将内置 API key 写入 AppData 的 override 配置 + 设环境变量。

    打包版内置 builtin_keys.py(不入 Git)，使甲方开箱即用 AI + 卫星地图。
    开发模式(builtin_keys 不存在)时静默跳过，不影响开发流程。
    裴总决策: 甲方开箱即用优先(覆盖 GPT M0-9 建议)。
    """
    try:
        import builtin_keys as bk
    except ImportError:
        return  # 开发模式无内置 key，跳过

    # 1. AI key → ai_config.json override(若已存在则不覆盖，尊重用户已配)
    try:
        from app.core.config import _app_data_dir
        override_path = os.path.join(_app_data_dir(), "ai_config.json")
        if not os.path.isfile(override_path):
            import json
            cfg = {"base_url": bk.AI_BASE_URL, "api_key": bk.AI_API_KEY,
                   "model": bk.AI_MODEL, "provider": "zhipu"}
            os.makedirs(os.path.dirname(override_path), exist_ok=True)
            with open(override_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            print(f"✅ 已预配 AI key 到 {override_path}")
    except Exception as e:
        print(f"⚠️ AI key 预配失败({e})，可在系统管理页手动配置。")

    # 2. 高德 key → 环境变量(全局生效，map.py 读 os.environ)
    gaode = getattr(bk, "GAODE_KEY", "")
    if gaode:
        os.environ["GAODE_KEY"] = gaode
        try:
            from app.core.config import get_settings
            get_settings().gaode_key = gaode
        except Exception:
            pass


def check_first_run_keys():
    """首次启动密钥检测(只读提示, 实际注入由 inject_builtin_keys 完成)。"""
    try:
        from app.core.config import get_settings
        s = get_settings()
    except Exception:  # noqa: BLE001
        return

    missing = []
    if not (getattr(s, "ai_api_key", None) or "").strip():
        missing.append("AI 大模型 API key")
    if not (getattr(s, "gaode_key", None) or os.environ.get("GAODE_KEY", "")).strip():
        missing.append("高德地图 key")

    if not missing:
        return

    msg = (
        "SRS 首次启动检测到以下密钥未配置:\n  - "
        + "\n  - ".join(missing)
        + "\n\n请在系统管理页配置相应 key:\n"
        "  • AI API key: 系统管理 → AI 模型设置\n"
        "  • 高德地图 key: 系统管理 → 地图服务\n"
        "未配置前相关功能(AI 问答、卫星影像底图)将自动降级, "
        "核心诊断与报告功能不受影响。"
    )
    print("⚠️  密钥未配置:")
    print("    " + "\n    ".join(missing))
    print("    请在系统管理页配置后再使用对应功能。\n")

    # 非阻塞提示(GUI 可用则弹窗一次, 失败时静默)
    try:
        if sys.platform == "darwin":
            try:
                import rumps  # type: ignore
                rumps.alert(title="SRS 密钥未配置", message=msg)
            except Exception:  # noqa: BLE001
                import tkinter as tk  # type: ignore
                from tkinter import messagebox  # type: ignore
                root = tk.Tk(); root.withdraw()
                messagebox.showwarning("SRS 密钥未配置", msg)
                root.destroy()
        else:
            import tkinter as tk  # type: ignore
            from tkinter import messagebox  # type: ignore
            root = tk.Tk(); root.withdraw()
            messagebox.showwarning("SRS 密钥未配置", msg)
            root.destroy()
    except Exception:  # noqa: BLE001
        # 无 GUI(纯终端/无 tkinter): 仅终端打印, 不阻断
        pass


def _check_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """检测端口是否被占用。"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            sock.bind((host, port))
            return False
        except OSError:
            return True


def _check_srs_already_running(port: int, host: str = "127.0.0.1") -> bool:
    """检测占用端口的是否是 SRS 自身(通过探测 GET /health 响应)。

    返回 True  → SRS 已在运行, 可以直接复用
    返回 False → 被其他程序占用, 真正冲突
    """
    import urllib.request
    # SRS 暴露的健康检查端点: GET /health → {"status":"ok","app":"...","version":"..."}
    try:
        req = urllib.request.Request(
            f"http://{host}:{port}/health",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = resp.read().decode("utf-8", errors="ignore")
            # 只要 /health 能通且包含 "status" 字段，即认定为 SRS 自身
            return '"status"' in data
    except Exception:  # noqa: BLE001
        # /health 不通: 再试根路径 (SRS 前端 SPA 返回 200)
        try:
            with urllib.request.urlopen(
                f"http://{host}:{port}/", timeout=1.5
            ) as resp:
                return resp.status == 200
        except Exception:  # noqa: BLE001
            # 端口占用但完全无法 HTTP 连接 → 判定为其他程序
            return False


def run_preflight(port: int, host: str = "127.0.0.1") -> list[dict]:
    """首启环境自检: 端口/DB/Redis/AI key/地图服务 key。

    返回 [{name, level, message}], level ∈ ok/warn/fail。
    严格"只读": 不写任何文件、不改配置, 仅探测与提示。
    """
    from app.core.config import get_settings
    s = get_settings()
    results: list[dict] = []

    # 1. 端口占用检测
    #    分三种情况:
    #    a) 空闲               → ok
    #    b) 被 SRS 自身占用    → warn (直接复用已有服务, 无需重启)
    #    c) 被其他程序占用      → fail (真正冲突, 需手动处理)
    if _check_port_in_use(port, host):
        if _check_srs_already_running(port, host):
            results.append({
                "name": "端口检测", "level": "warn",
                "message": (
                    f"端口 {port} 已有 SRS 服务在运行。"
                    "本次启动将直接连接已有服务（无需重新启动后端）。"
                    "如需完全重启，请先在任务管理器/活动监视器中关闭 SRS 进程。"
                ),
                "srs_already_running": True,   # 供 main() 判断是否跳过 server 启动
            })
        else:
            results.append({
                "name": "端口检测", "level": "fail",
                "message": (
                    f"端口 {port} 已被其他程序占用（非 SRS）。"
                    "请关闭占用程序，或用 --port 参数指定其他端口（如 --port 8001）。"
                ),
                "srs_already_running": False,
            })
    else:
        results.append({
            "name": "端口检测", "level": "ok",
            "message": f"端口 {port} 空闲可用。",
            "srs_already_running": False,
        })

    # 2. 数据库目录可写(SQLite 场景)
    db_url = s.database_url
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        db_dir = os.path.dirname(os.path.abspath(db_path)) or "."
        if os.access(db_dir, os.W_OK):
            results.append({"name": "数据库", "level": "ok",
                            "message": f"SQLite 目录可写: {db_path}"})
        else:
            results.append({"name": "数据库", "level": "fail",
                            "message": f"数据库目录不可写: {db_dir}。请检查权限。"})
    else:
        # PostgreSQL 等远程库: 仅提示连接串, 不实测(避免启动卡顿)
        masked = db_url.split("@")[-1] if "@" in db_url else db_url
        results.append({"name": "数据库", "level": "ok",
                        "message": f"使用外部数据库: {masked}"})

    # 3. Redis(可选, 仅探测可达性)
    try:
        import redis  # type: ignore
        r = redis.from_url(s.redis_url, socket_connect_timeout=1.5, socket_timeout=1.5)
        r.ping()
        results.append({"name": "Redis", "level": "ok", "message": f"可达: {s.redis_url}"})
    except ImportError:
        results.append({"name": "Redis", "level": "warn",
                        "message": "redis 库未安装(缓存功能不可用, 核心功能不受影响)。"})
    except Exception as e:  # noqa: BLE001
        results.append({"name": "Redis", "level": "warn",
                        "message": f"Redis 不可达: {e}。缓存功能降级, 核心功能不受影响。"})

    # 4. AI key(配置态, 不实测可达)
    if s.ai_api_key:
        masked = s.ai_api_key[:6] + "***" + s.ai_api_key[-4:] if len(s.ai_api_key) > 12 else "***"
        results.append({"name": "AI 大模型", "level": "ok",
                        "message": f"已配置 key({masked}) + 模型 {s.ai_model}。AI 问答可用。"})
    else:
        results.append({"name": "AI 大模型", "level": "warn",
                        "message": "未配置 AI_API_KEY。AI 问答将降级为纯知识库检索答案。若需 AI 生成请在 .env 配置。"})

    # 5. 高德地图 key(推荐在线影像, 无 IP 白名单限制)
    gaode_key = getattr(s, "gaode_key", None) or os.environ.get("GAODE_KEY", "")
    if gaode_key:
        masked = gaode_key[:4] + "***" + gaode_key[-4:] if len(gaode_key) > 8 else "***"
        results.append({"name": "地图底图", "level": "ok",
                        "message": f"已配置 GAODE_KEY({masked})。高德影像底图可用，无 IP 白名单限制。"})
    else:
        results.append({"name": "地图底图", "level": "warn",
                        "message": "未配置 GAODE_KEY。影像底图不可用，矢量行政区底图仍正常显示。"
                                   "如需影像底图，请在高德开放平台申请 Web 服务 key 并写入 .env: GAODE_KEY=your_key"})

    return results


def _preflight_summary(results: list[dict]) -> str:
    """把自检结果渲染为可读文本(托盘弹窗/终端共用)。"""
    lines = ["SRS 环境自检结果", "=" * 30]
    for r in results:
        icon = {"ok": "✅", "warn": "⚠️", "fail": "❌"}[r["level"]]
        lines.append(f"{icon} [{r['name']}] {r['message']}")
    fails = [r for r in results if r["level"] == "fail"]
    warns = [r for r in results if r["level"] == "warn"]
    lines.append("=" * 30)
    lines.append(f"结果: {len(fails)} 项阻断, {len(warns)} 项警告, {len(results)-len(fails)-len(warns)} 项正常")
    if fails:
        lines.append("⚠️ 存在阻断项, 部分功能可能无法启动, 请处理后重试。")
    else:
        lines.append("✅ 无阻断项, 可正常启动(警告项不影响核心功能)。")
    return "\n".join(lines)


def start_server(host: str, port: int):
    """在守护线程中启动 uvicorn。"""
    import uvicorn
    from app.main import app
    # 打包后 __file__ 在临时目录, 需切回项目根(backend 的父目录)以使相对路径正常。
    # 开发模式: __file__ = packaging/launcher.py → 父级的父级 = 项目根
    # 打包模式: sys._MEIPASS 为解包根, backend/ 已在其中
    if getattr(sys, "frozen", False):
        # PyInstaller: 解包目录即为工作目录基准
        project_root = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


def _has_pywebview() -> bool:
    """检测 pywebview 是否可用(不触发实际导入副作用)。"""
    try:
        import importlib.util
        return importlib.util.find_spec("webview") is not None
    except Exception:  # noqa: BLE001
        return False


def open_browser_fallback(url: str, delay: float = 1.5):
    """降级路径: 延迟打开系统浏览器(无 pywebview 时使用)。"""
    time.sleep(delay)
    webbrowser.open(url)


def run_webview_main_thread(url: str, delay: float = 1.5):
    """在【主线程】启动 pywebview 原生窗口。

    ⚠️  macOS(Cocoa) / Windows(Edge/WebView2) 要求 GUI 事件循环在主线程运行。
    本函数必须从 main() 直接调用, 不得在子线程中调用。

    功能:
    - 等待后端就绪后显示原生窗口(无地址栏, 纯 App 体验)
    - 窗口关闭时发送 SIGINT 终止整个进程(等同 Ctrl+C)
    """
    import webview  # type: ignore[import]
    time.sleep(delay)
    win = webview.create_window(
        title="污染场地监管系统",
        url=url,
        width=1440,
        height=900,
        min_size=(1200, 700),
        background_color="#0f3d6e",
    )

    def on_closed():
        """窗口关闭 → 通知主进程退出。"""
        print("\n🛑 SRS 窗口已关闭, 正在停止服务器...")
        os.kill(os.getpid(), signal.SIGINT)

    win.events.closed += on_closed
    webview.start(debug=False)  # 阻塞直到所有窗口关闭


def create_tray_app(host: str, port: int, server_thread: threading.Thread,
                    preflight_results: list[dict] | None = None):
    """macOS 菜单栏托盘应用 (使用 rumps)。"""
    try:
        import rumps
    except ImportError:
        print("⚠️  rumps 未安装, 跳过托盘图标。终端 Ctrl+C 退出。")
        return None

    app_url = f"http://{host}:{port}"
    preflight_results = preflight_results or []

    class SRSApp(rumps.App):
        def __init__(self):
            super().__init__(
                name="SRS",
                title="🛡️",
                quit_button=None,  # 自定义退出
            )

        # ── 主入口 ──────────────────────────────────────────────
        @rumps.clicked("打开 SRS 系统")
        def open_app(self, _):
            threading.Thread(target=open_browser_fallback, args=(app_url, 0), daemon=True).start()

        # ── 深链接快捷入口 ───────────────────────────────────────
        @rumps.clicked("→ 场地列表")
        def open_sites(self, _):
            threading.Thread(target=open_browser_fallback,
                             args=(f"{app_url}/sites", 0), daemon=True).start()

        @rumps.clicked("→ 导入数据")
        def open_import(self, _):
            threading.Thread(target=open_browser_fallback,
                             args=(f"{app_url}/sites/import", 0), daemon=True).start()

        @rumps.clicked("→ 障碍因子分析")
        def open_obstacle(self, _):
            threading.Thread(target=open_browser_fallback,
                             args=(f"{app_url}/obstacle", 0), daemon=True).start()

        @rumps.clicked("→ 全流程追溯")
        def open_trace(self, _):
            threading.Thread(target=open_browser_fallback,
                             args=(f"{app_url}/trace", 0), daemon=True).start()

        @rumps.clicked("→ 生成报告")
        def open_report(self, _):
            threading.Thread(target=open_browser_fallback,
                             args=(f"{app_url}/report", 0), daemon=True).start()

        # ── 系统管理 ─────────────────────────────────────────────
        @rumps.clicked("环境自检")
        def show_preflight(self, _):
            fresh = run_preflight(port, host)
            rumps.alert(title="SRS 环境自检", message=_preflight_summary(fresh))

        @rumps.clicked("服务器状态")
        def server_status(self, _):
            if server_thread.is_alive():
                rumps.alert(
                    title="SRS 服务器状态",
                    message=f"✅ 运行中\n地址: {app_url}",
                )
            else:
                rumps.alert(
                    title="SRS 服务器状态",
                    message="❌ 服务器已停止",
                )

        @rumps.clicked("退出 SRS")
        def quit_app(self, _):
            print("\n🛑 正在关闭 SRS 服务器...")
            os.kill(os.getpid(), signal.SIGINT)

    return SRSApp()


def main():
    parser = argparse.ArgumentParser(description="SRS 污染场地监管系统 - 桌面启动器")
    parser.add_argument("--host", default="127.0.0.1", help="绑定地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="端口 (默认: 8000)")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--no-tray", action="store_true", help="不使用托盘图标")
    args = parser.parse_args()

    # 确保在项目根目录 (打包后由 PyInstaller 设置)
    if not getattr(sys, "frozen", False):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.chdir(project_root)
        sys.path.insert(0, os.path.join(project_root, "backend"))

    print(f"🛡️  SRS 污染场地监管系统 v1.0.0")
    print(f"   开发者: 生态环境部土壤与农业农村生态环境监管技术中心")
    print(f"   协议: MIT License  © 2026 生态环境部土壤与农业农村生态环境监管技术中心")
    print(f"   数据目录: {_get_data_dir()}")
    print(f"   启动地址: http://{args.host}:{args.port}")
    print()

    ensure_app_dirs()
    # 裴总决策: 内置 key 预配(甲方开箱即用), inject 后再 check 提示缺失项
    inject_builtin_keys()
    check_first_run_keys()

    # 首启环境自检(只读探测, 不改任何配置)
    print("🔍 正在执行环境自检...")
    preflight_results = run_preflight(args.port, args.host)
    print(_preflight_summary(preflight_results))
    print()
    n_fail = sum(1 for r in preflight_results if r["level"] == "fail")
    # 关键阻断项: 用原生提示框告知用户(GUI 环境), 仍继续启动(部分功能可降级)
    if n_fail:
        msg = _preflight_summary(preflight_results)
        try:
            if sys.platform == "darwin":
                # macOS: 优先用 rumps alert(若已导入), 否则 tkinter
                try:
                    import rumps  # type: ignore
                    rumps.alert(title="SRS 启动自检发现阻断项", message=msg)
                except Exception:  # noqa: BLE001
                    import tkinter as tk  # type: ignore
                    from tkinter import messagebox  # type: ignore
                    root = tk.Tk(); root.withdraw()
                    messagebox.showwarning("SRS 启动自检", msg)
                    root.destroy()
            else:
                import tkinter as tk  # type: ignore
                from tkinter import messagebox  # type: ignore
                root = tk.Tk(); root.withdraw()
                messagebox.showwarning("SRS 启动自检", msg)
                root.destroy()
        except Exception:  # noqa: BLE001
            # 无 GUI(纯终端/无 tkinter): 仅终端打印, 不阻断
            pass

    url = f"http://{args.host}:{args.port}"

    # 判断是否需要启动服务器(SRS 已运行则复用)
    port_result = next((r for r in preflight_results if r["name"] == "端口检测"), {})
    srs_already_running = port_result.get("srs_already_running", False)
    port_conflict = port_result.get("level") == "fail"

    if port_conflict:
        print("❌ 端口被其他程序占用, 无法启动。请关闭占用程序后重试。")
        return  # 真正冲突: 直接退出, 不尝试启动

    # 启动服务器线程(SRS 已运行则跳过)
    if srs_already_running:
        print(f"ℹ️  检测到 SRS 服务已在 {url} 运行, 跳过后端启动, 直接打开窗口...")
        server_thread = None
    else:
        server_thread = threading.Thread(
            target=start_server,
            args=(args.host, args.port),
            daemon=True,
        )
        server_thread.start()

    # ── 主线程事件循环决策 ────────────────────────────────────────────────
    # macOS / Windows GUI 框架要求事件循环在主线程运行。
    # pywebview 和 rumps 均独占主线程, 两者互斥, 按优先级选择:
    #   优先级1: pywebview (原生无地址栏窗口, 最佳体验)
    #   优先级2: rumps 托盘 + 系统浏览器 (macOS fallback)
    #   优先级3: 仅等待 Ctrl+C (Linux / --no-tray)
    # ─────────────────────────────────────────────────────────────────────
    if not args.no_browser and _has_pywebview():
        # ── pywebview 路径 (主线程) ──────────────────────────────────────
        print(f"🖥️  使用 pywebview 原生窗口 (无浏览器标题栏)...")
        try:
            run_webview_main_thread(url, delay=1.5)
            return  # webview.start() 退出 = 窗口关闭, 进程即将收到 SIGINT
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  pywebview 启动失败({e}), 降级为系统浏览器...")
            # 继续走下方的 browser/tray fallback

    # ── 浏览器 + 托盘路径 ────────────────────────────────────────────────
    if not args.no_browser:
        browser_thread = threading.Thread(
            target=open_browser_fallback, args=(url,), daemon=True)
        browser_thread.start()

    tray = None
    if sys.platform == "darwin" and not args.no_tray:
        # server_thread 可能为 None(SRS 已在运行), 托盘状态检查时需兼容
        tray = create_tray_app(args.host, args.port,
                               server_thread or threading.current_thread(),
                               preflight_results)

    if tray is not None:
        tray.run()   # 阻塞主线程 (rumps 事件循环)
    else:
        if server_thread is not None:
            print("✅ SRS 服务已启动。按 Ctrl+C 退出。")
        try:
            while server_thread is None or server_thread.is_alive():
                if server_thread is None:
                    time.sleep(1)
                else:
                    server_thread.join(timeout=1)
        except KeyboardInterrupt:
            print("\n🛑 正在关闭 SRS...")


def _get_data_dir() -> str:
    from app.core.config import _app_data_dir
    return _app_data_dir()


if __name__ == "__main__":
    main()
