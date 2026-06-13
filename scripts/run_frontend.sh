#!/usr/bin/env bash
# 启动前端开发服务器 (需先启动后端: uvicorn app.main:app --reload)
# 用法: bash scripts/run_frontend.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/frontend"

if [ ! -d node_modules ]; then
  echo "==> 安装前端依赖 (首次)"
  npm install
fi
if [ ! -f .env.local ]; then
  cp .env.example .env.local
  echo "==> 已生成 .env.local，请填入天地图 key(VITE_TIANDITU_KEY);未填将回退 OSM 底图"
fi
echo "==> 启动 Vite (http://localhost:5173)，API 代理到 127.0.0.1:8000"
npm run dev
