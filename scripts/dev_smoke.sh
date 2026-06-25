#!/usr/bin/env bash
# SRS 开发态一键冒烟: 启动后端(源码+venv, 真实库) → 逐接口打 → PASS/FAIL。
# 用途: 在本机拿到"导入/诊断/评价/推荐/地图/EDA/AI"的真实闭环结果, 杜绝"金玉其外"。
# 用法:  bash scripts/dev_smoke.sh [场地数据.xlsx]
#        不传文件则跳过导入, 用库中已有场地(id 取列表第一个)。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/backend/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
HOST=127.0.0.1; PORT=8011; BASE="http://$HOST:$PORT/api/v1"
PASS=0; FAIL=0
ok(){ echo "✅ $1"; PASS=$((PASS+1)); }
bad(){ echo "❌ $1"; FAIL=$((FAIL+1)); }

echo "▶ 启动后端(端口 $PORT, 源码态)..."
( cd backend && "$PY" -m uvicorn app.main:app --host "$HOST" --port "$PORT" --log-level warning ) &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 30); do
  curl -fs "http://$HOST:$PORT/health" >/dev/null 2>&1 && break; sleep 1
done
curl -fs "http://$HOST:$PORT/health" >/dev/null 2>&1 && ok "后端健康 /health" || { bad "后端起不来"; exit 1; }

echo "▶ 登录(admin/Demo@2026)..."
TOK=$(curl -fs -X POST "$BASE/auth/login" -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Demo@2026"}' | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["access_token"])' 2>/dev/null)
[ -n "${TOK:-}" ] && ok "登录拿到 token" || { bad "登录失败"; exit 1; }
H="Authorization: Bearer $TOK"

if [ "${1:-}" != "" ] && [ -f "${1:-}" ]; then
  echo "▶ 导入(auto 自动识别模板): $1"
  R=$(curl -fs -X POST "$BASE/import" -H "$H" -F "mapping_id=auto" -F "file=@$1")
  echo "   $R" | head -c 300; echo
  echo "$R" | grep -q '"site_id"' && ok "导入成功(auto)" || bad "导入失败"
fi

SID=$(curl -fs "$BASE/sites?size=1" -H "$H" | "$PY" -c 'import sys,json;d=json.load(sys.stdin);items=d.get("items") or d.get("data") or [];print(items[0]["id"] if items else "")' 2>/dev/null)
[ -n "${SID:-}" ] && ok "取到场地 id=$SID" || { bad "库中无场地, 先传数据文件"; echo "结果: $PASS 通过 / $FAIL 失败"; exit 1; }

probe(){ # $1=描述 $2=method $3=path
  local code
  if [ "$2" = POST ]; then code=$(curl -s -o /tmp/srs_smoke.out -w '%{http_code}' -X POST "$BASE$3" -H "$H");
  else code=$(curl -s -o /tmp/srs_smoke.out -w '%{http_code}' "$BASE$3" -H "$H"); fi
  if [ "$code" = 200 ]; then ok "$1 ($code)"; else bad "$1 (HTTP $code): $(head -c 160 /tmp/srs_smoke.out)"; fi
}

echo "▶ 闭环接口探测(场地 $SID)..."
probe "EDA 图表数据"      GET  "/sites/$SID/eda?max_points=500"
probe "诊断(运行RF+SHAP)" POST "/sites/$SID/diagnosis"
probe "评价(重构+SSUI)"   POST "/sites/$SID/evaluation"
probe "方案推荐"          POST "/sites/$SID/recommendation"
probe "场地地图图层"      GET  "/sites/$SID/map/layers"
probe "矢量行政区(省)"    GET  "/map/geo/boundaries?level=province"
probe "地图索引"          GET  "/map/geo/index"
probe "AI 状态"           GET  "/ai/status"
echo "▶ 高德瓦片代理(需外网):"
curl -s -o /dev/null -w '   gaode tile HTTP %{http_code}\n' "http://$HOST:$PORT/api/v1/map/tile/gaode/8/210/100"

echo "──────────────────────────────"
echo "结果: $PASS 通过 / $FAIL 失败"
