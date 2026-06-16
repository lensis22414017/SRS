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


def run_preflight(port: int, host: str = "127.0.0.1") -> list[dict]:
    """首启环境自检: 端口/DB/Redis/AI key/天地图 key。

    返回 [{name, level, message}], level ∈ ok/warn/fail。
    严格"只读": 不写任何文件、不改配置, 仅探测与提示。
    """
    from app.core.config import get_settings
    s = get_settings()
    results: list[dict] = []

    # 1. 端口占用
    if _check_port_in_use(port, host):
        results.append({"name": "端口检测", "level": "fail",
                        "message": f"端口 {port} 已被占用。请关闭占用程序, 或用 --port 指定其他端口。"})
    else:
        results.append({"name": "端口检测", "level": "ok",
                        "message": f"端口 {port} 空闲可用。"})

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

    # 5. 天地图 key(配置态)
    if s.tianditu_key:
        results.append({"name": "地图底图", "level": "ok",
                        "message": "已配置 TIANDITU_KEY, 地图底图可加载(需在天地图控制台配置出口 IP 白名单)。"})
    else:
        results.append({"name": "地图底图", "level": "warn",
                        "message": "未配置 TIANDITU_KEY。地图底图不可用, 采样点坐标仍可显示但无影像底图。报告内的静态图件不受影响。"})

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
    # 确保工作目录正确 (PyInstaller 打包后 __file__ 指向临时目录)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


def open_browser(url: str, delay: float = 1.5):
    """延迟打开浏览器, 等待服务器就绪。"""
    time.sleep(delay)
    webbrowser.open(url)


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

        @rumps.clicked("打开 SRS 系统")
        def open_app(self, _):
            webbrowser.open(app_url)

        @rumps.clicked("环境自检")
        def show_preflight(self, _):
            # 重新跑一次自检(端口此时已被自身占用, 状态会变化)
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
            # rumps 的 quit_button 会处理退出

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

    print(f"🛡️  SRS 污染场地监管系统 v0.1")
    print(f"   数据目录: {_get_data_dir()}")
    print(f"   启动地址: http://{args.host}:{args.port}")
    print()

    ensure_app_dirs()

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

    # 启动服务器线程
    server_thread = threading.Thread(
        target=start_server,
        args=(args.host, args.port),
        daemon=True,
    )
    server_thread.start()

    # 打开浏览器
    if not args.no_browser:
        url = f"http://{args.host}:{args.port}"
        browser_thread = threading.Thread(
            target=open_browser,
            args=(url,),
            daemon=True,
        )
        browser_thread.start()

    # macOS: 菜单栏托盘
    tray = None
    if sys.platform == "darwin" and not args.no_tray:
        tray = create_tray_app(args.host, args.port, server_thread, preflight_results)

    if tray is not None:
        tray.run()
    else:
        # 无托盘: 等待 Ctrl+C
        print("✅ SRS 服务已启动。按 Ctrl+C 退出。")
        try:
            while server_thread.is_alive():
                server_thread.join(timeout=1)
        except KeyboardInterrupt:
            print("\n🛑 正在关闭 SRS...")


def _get_data_dir() -> str:
    from app.core.config import _app_data_dir
    return _app_data_dir()


if __name__ == "__main__":
    main()
