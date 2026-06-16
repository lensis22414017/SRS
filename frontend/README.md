# 前端 — 污染场地监管系统

React + TypeScript + Vite + Ant Design + ECharts + Leaflet(天地图底图)。

## 启动

```bash
# 1) 先启动后端(另开终端)
cd ../backend && source .venv/bin/activate && uvicorn app.main:app --reload

# 2) 启动前端
bash ../scripts/run_frontend.sh
# 或手动:
npm install
cp .env.example .env.local   # 填入天地图 key
npm run dev                  # http://localhost:5173
```

演示账号:admin / enterprise / agency / regulator,密码均 `Demo@2026`。

## 地图(天地图)

推荐在后端 `.env` 配置 `TIANDITU_KEY`,由 `/api/v1/map/tile/...` 本地代理转发瓦片,key 不进前端包。
开发演示也兼容 `.env.local` 的 `VITE_TIANDITU_KEY`;两者都未配置时地图保留点位空态并提示配置问题。
天地图用 CGCS2000 坐标,与场地 WGS84 经纬度小范围一致,无需转换。

## 页面

- 登录:JWT 认证
- 数据概览:KPI + 场地分布地图
- 场地管理:列表/筛选(企业用户仅见本企业)
- 场地详情:点位地图、采样点、障碍因子诊断(SHAP 图)、重构/SSUI 评价、方案推荐、五阶段追溯、PDF 报告下载;并提供一键运行各算法的按钮

## 代理

`vite.config.ts` 已把 `/api` 代理到 `http://127.0.0.1:8000`,无需改 CORS。
