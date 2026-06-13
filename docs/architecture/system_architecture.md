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

## 6. 待补
- 接口时序图、ER 图导出、瓦片代理、报告静态图表、前端拆包。
