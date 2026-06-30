#!/bin/bash
# SRS 桌面快速启动脚本 (macOS/Linux)
# 双击 .command 文件即可启动 (macOS)
#
# 使用方式:
#   chmod +x packaging/start.sh
#   ./packaging/start.sh              # 默认端口 8000
#   ./packaging/start.sh 8080          # 自定义端口
#   ./packaging/start.sh --no-browser  # 不打开浏览器

set -e

PORT="${1:-8000}"
NO_BROWSER=""

if [ "$1" = "--no-browser" ]; then
    PORT="${2:-8000}"
    NO_BROWSER="--no-browser"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 检查虚拟环境
VENV_PYTHON="$PROJECT_DIR/backend/.venv/bin/python"
if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ 虚拟环境未找到, 请先运行 scripts/setup.sh"
    exit 1
fi

echo "🛡️  SRS 污染场地监管系统"
echo "   项目目录: $PROJECT_DIR"
echo "   启动地址: http://127.0.0.1:$PORT"
echo ""

# macOS: 设置 DYLD_LIBRARY_PATH 以便 weasyprint 找到 Homebrew 库
if [ "$(uname)" = "Darwin" ]; then
    export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"
fi

# 自动打开浏览器 (后台)
if [ -z "$NO_BROWSER" ]; then
    (sleep 2 && open "http://127.0.0.1:$PORT" 2>/dev/null || \
     sleep 2 && xdg-open "http://127.0.0.1:$PORT" 2>/dev/null) &
fi

# 启动后端
export DATABASE_URL="sqlite:///$PROJECT_DIR/backend/srs_dev.db"
export FILE_STORAGE_DIR="$PROJECT_DIR/backend/storage"

cd "$PROJECT_DIR/backend"
exec "$VENV_PYTHON" -m uvicorn app.main:app \
    --host 127.0.0.1 \
    --port "$PORT" \
    --log-level info
