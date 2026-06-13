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


def start_server(host: str, port: int):
    """在守护线程中启动 uvicorn。"""
    import uvicorn
    # 确保工作目录正确 (PyInstaller 打包后 __file__ 指向临时目录)
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


def open_browser(url: str, delay: float = 1.5):
    """延迟打开浏览器, 等待服务器就绪。"""
    time.sleep(delay)
    webbrowser.open(url)


def create_tray_app(host: str, port: int, server_thread: threading.Thread):
    """macOS 菜单栏托盘应用 (使用 rumps)。"""
    try:
        import rumps
    except ImportError:
        print("⚠️  rumps 未安装, 跳过托盘图标。终端 Ctrl+C 退出。")
        return None

    app_url = f"http://{host}:{port}"

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
        tray = create_tray_app(args.host, args.port, server_thread)

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
