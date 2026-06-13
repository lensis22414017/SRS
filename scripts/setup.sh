#!/usr/bin/env bash
# 一键初始化: 建虚拟环境 -> 装依赖 -> 建表 -> 种子 -> 知识库/标准/案例入库 -> 跑测试
# 用法: bash scripts/setup.sh   (在仓库根目录执行)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

echo "==> [1/6] 创建虚拟环境 .venv"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install -U pip

echo "==> [2/6] 安装依赖 (requirements.txt)"
pip install -r requirements.txt

echo "==> [3/6] 准备环境变量 (开发默认 sqlite)"
export DATABASE_URL="${DATABASE_URL:-sqlite:///./srs_dev.db}"
export SECRET_KEY="${SECRET_KEY:-dev_secret_change_me}"
export DEMO_PASSWORD="${DEMO_PASSWORD:-Demo@2026}"
echo "    DATABASE_URL=$DATABASE_URL"

echo "==> [4/6] 建表 + 种子数据(4角色/4账号/技术库)"
python -m app.db.bootstrap

echo "==> [5/6] 知识库/标准阈值/修复案例入库"
python -m app.db.load_kb
python -m app.db.load_standard_thresholds
python -m app.db.load_remediation_cases

echo "==> [6/6] 运行测试"
pytest -q || { echo "测试未全绿, 请看上方输出"; exit 1; }

echo ""
echo "✅ 初始化完成。启动后端: "
echo "   cd backend && source .venv/bin/activate && uvicorn app.main:app --reload"
echo "   健康检查: http://127.0.0.1:8000/health"
echo "   演示账号: admin / enterprise / agency / regulator  密码: ${DEMO_PASSWORD:-Demo@2026}"
