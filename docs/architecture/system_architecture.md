# 系统架构设计（骨架 v0.1）

> 状态: 骨架。满足 CLAUDE.md §4.1 文档存在要求, 后续随模块完善补全部署拓扑与时序图。

## 1. 总体分层
```
前端(React+TS+AntD+ECharts+Leaflet)
   │  HTTP /api/v1/*  (JWT Bearer)
后端(FastAPI)
   ├─ api/        路由层: auth/data/diagnosis/evaluation/workflow/system/ai
   ├─ core/       config(env注入) / security(bcrypt+JWT) / deps(RBAC+企业隔离)
   ├─ services/   import/validation/ingest/pipeline/threshold_resolver/
   │              diagnosis/evaluation/recommend/workflow/report/ai/audit/file
   ├─ models/     SQLAlchemy ORM(24 表, 长表 measurements)
   └─ db/         session / bootstrap(create_all) / alembic(基线迁移) / 各 loader
ML(ml/)          eda / cleaning / models(RF+dataset_splits) / explain(SHAP) /
                 evaluation(reconstruction+ssui) / recommend / params
数据(data/)      raw(immutable) / processed / model_ready / splits / synthetic / knowledge_base
报告(reporting/) Jinja2 模板 → PDF(xhtml2pdf)/DOCX(python-docx)/HTML
存储             本地 storage(MVP, 替代 MinIO) / sqlite(开发) / PostgreSQL(部署)
```

## 2. 权限与数据隔离
- RBAC: roles/permissions/user_roles/role_permissions; `deps.require_permission(code)`。
- 企业隔离: `deps.assert_site_access` — 企业用户仅可访问本企业 `organization_id` 的场地;
  已覆盖 data / workflow / **diagnosis / evaluation / recommendation**(2026-06-13 补齐)。
- 前端: 业务页 `Protected`(登录), `/system` 用 `AdminOnly`(仅 admin)。

## 3. MVP 单场地闭环
导入→校验(threshold_resolver, pH分段)→场地详情→障碍因子(RF+SHAP, 计算轨迹)→
功能重构评价→SSUI→方案推荐(技术库匹配)→五阶段追溯(附件)→PDF/DOCX 报告→操作日志。

## 4. 数据治理与验证(防泄漏)
- raw 不可变; 派生表带 `evidence_level`/`is_synthetic`/`source_file_sha256`。
- 真实切分按 (DOI,Source) 连通分量分配, 双键零跨集(`dataset_splits.py`)。
- 模拟数据仅训练增强/压力/演示, 永不进 real 验证集。

## 5. 部署拓扑(MVP)
- 开发: uvicorn + sqlite + Vite(proxy /api→8000)。
- 容器: docker-compose(postgres + redis + backend); 初始化 bootstrap/alembic + loaders。
- 桌面打包/天地图白名单: 见 `docs/deployment_desktop.md`。

## 6. 地图服务层（2026-06-13 新增）

### 6.1 三层架构

| 层级 | 内容 | 离线能力 | 依赖 |
|---|---|---|---|
| **L1 矢量底图（默认）** | 全国省/地市/县行政区边界 GeoJSON | ✅ 完全离线 | `data/geo/*.geojson`（阿里 DataV 开放数据） |
| **L2 MBTiles 离线影像（可选）** | 指定区域卫星影像，按需导入 | ✅ 离线 | `data/geo/tiles/*.mbtiles` |
| **L3 天地图在线影像（可选）** | 实时卫星/矢量影像 | ❌ 需外网+白名单 | 天地图 key（`TIANDITU_KEY` 环境变量） |

### 6.2 后端瓦片代理（`backend/app/api/map.py`）

- 路由：`GET /api/v1/map/tile/{layer}/{z}/{x}/{y}`
- 优先级：本地 MBTiles → 天地图在线 → 503
- **后端持有天地图 key**，前端通过本代理访问，key 不暴露到浏览器
- 支持图层：`img`（影像）、`cia`（影像注记）、`vec`（矢量）、`cva`（矢量注记）
- 场地点位 GeoJSON：`GET /api/v1/map/sites/geo`，`GET /api/v1/map/sites/{site_id}/points/geo`

### 6.3 前端地图组件（`frontend/src/components/SiteMap.tsx`）

- 渲染库：Leaflet（`react-leaflet` 封装）
- 行政区三级懒加载：缩放 1–5 显示省界，6–8 显示地市，9+ 显示县
- 污染状态色：`danger=#dc2626 / warning=#f59e0b / success=#16a34a / info=#3b82f6`
- 地图默认使用 L1 矢量底图（无 key、无外网即可运行）
- 天地图 key 通过 `VITE_TIANDITU_KEY` 环境变量注入；未配置时自动降级至矢量底图

### 6.4 报告中的地图图件

- 报告 PDF 中的地图使用 `matplotlib` 离线渲染（`ml/artifacts/`），不依赖天地图，内网环境可生成含图报告

## 7. 待补
- 接口时序图、ER 图导出、报告静态图表、前端拆包。
