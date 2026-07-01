# 污染场地土壤生态-生产功能重构监管系统

面向甲方验收的污染场地监管系统。当前阶段:**SRS系统 v1.0**。

闭环目标:导入场地数据 → 数据校验 → 场地详情 → 障碍因子识别(RF/SHAP) → 功能重构可行性评价 → SSUI 可持续利用评价 → 方案推荐 → 五阶段追溯 → PDF 报告 → 操作日志。

## 目录结构

```
docs/         需求/架构/算法/UI/验收文档
data/         raw(原始,不改值) / processed / knowledge_base(知识库+参数)
backend/      FastAPI + SQLAlchemy + Alembic
ml/           etl / models / explain / evaluation / recommend / params
reporting/    Jinja2 模板 + PDF
deploy/       docker-compose / Dockerfile / .env.example
```

## 技术栈

React+TS+AntD+ECharts(前端,待建) · FastAPI+SQLAlchemy+Alembic(后端) · PostgreSQL+Redis · scikit-learn+SHAP · Jinja2+WeasyPrint · Docker Compose。

> 当前架构取舍:暂以本地文件存储替代 MinIO、numeric 经纬度散点替代 PostGIS,后续有余力再补。

## 本地启动(开发)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 默认 sqlite, 快速起步
python -m app.db.seed_db          # 建表 + 种子(4 角色 + 4 演示账号 + 技术库)
python ../ml/etl/load_knowledge_base.py   # 查看知识库解析(入库见下)
uvicorn app.main:app --reload     # http://127.0.0.1:8000/health
```

## Docker 部署(PostgreSQL)

```bash
cd deploy
cp .env.example .env   # 填写 POSTGRES_PASSWORD / SECRET_KEY
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.db.seed_db
```

## 演示账号

| 账号 | 角色 | 数据范围 |
|---|---|---|
| admin | 系统管理员 | 全部 |
| enterprise | 企业用户 | 本企业 |
| agency | 第三方机构 | 授权项目 |
| regulator | 监管人员 | 监管范围 |

默认密码由 `.env` 的 `DEMO_PASSWORD` 决定(默认 `Demo@2026`),哈希存储。

## 测试

```bash
cd backend && pytest -q          # 需安装 requirements
```

## 已实现 API(MVP)

认证:`POST /api/v1/auth/login`、`GET /api/v1/auth/me`(JWT;所有业务接口需 `Authorization: Bearer <token>`)
数据:`POST /api/v1/import`(需 data:input)、`GET /sites`(企业用户仅见本企业)、`/sites/{id}`、`/sites/{id}/points`、`/sites/{id}/measurements`、`/import-batches/{id}/validation-report`
诊断:`POST/GET /sites/{id}/diagnosis`
评价:`POST/GET /sites/{id}/evaluation`
推荐:`POST/GET /sites/{id}/recommendation`
追溯:`POST /sites/{id}/workflow/init`、`GET /sites/{id}/workflow`、`POST /sites/{id}/workflow/{stage}`、`POST /sites/{id}/workflow/{stage}/attachment`
报告:`POST /sites/{id}/report`、`GET /sites/{id}/reports`、`GET /reports/{id}/download`

完整闭环演示:`bash scripts/run_demo.sh`(导入→诊断→评价→推荐→五阶段追溯→PDF报告)。

## 前端界面(React)

```bash
# 终端1: 后端
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload
# 终端2: 前端
bash scripts/run_frontend.sh   # http://localhost:5173
```

React+TS+AntD+ECharts+Leaflet(天地图底图)。登录后:数据概览(KPI+地图)、场地列表、场地详情(地图/诊断 SHAP 图/评价/推荐/五阶段追溯/报告下载,含一键运行算法)。详见 `frontend/README.md`。地图用天地图(免费 key、合规、高精度),未配 key 回退 OSM。

## 文档

需求 `docs/requirements/SRS.md` · 数据库 `docs/architecture/database_schema.md` · 算法 `docs/algorithms/` · 验收 `docs/acceptance/acceptance_criteria.md`。
