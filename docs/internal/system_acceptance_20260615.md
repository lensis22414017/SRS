# SRS 系统级验收测试记录（2026-06-15）

## 结论摘要

- 后端、数据脚本、Docker 干净卷、极端 10 场地闭环均通过。
- EDA、障碍诊断、功能重构、SSUI、推荐、追溯报告、上传下载链路可用。
- 报告 DOCX 已补齐地图、检测摘要、质量校验、功能重构、SSUI、流程追溯、附件、人工复核区等章节。
- 地图采样点图层可用；地图服务底图未通过，原因是当前 key 返回 `IP不匹配`，需要在地图服务控制台修正 IP/域名白名单。
- Docker compose 已补传 AI 与地图服务相关环境变量；真实 `deploy/.env` 仍使用 SiliconFlow/Qwen，代码默认与 `.env.example` 为 GLM。
- macOS 单文件可执行 `dist/SRS` 可启动并返回前端；`dist/SRS.app` 仍不稳定，PyInstaller 已提示 onefile + .app 模式不推荐，正式安装包需改 onedir/Tauri/Electron。

## 关键证据

### 后端与数据

- `bash scripts/run_tests.sh`
  - 结果：`47 passed, 2 skipped, 7 warnings`
  - 残留 warning：诊断特征填充 DataFrame 碎片化、FastAPI TestClient/httpx2、group split 单类别 AUC undefined。
- `cd backend && .venv/bin/python ../scripts/build_dataset_splits.py`
  - 结果：真实 split 无 DOI/Source overlap；synthetic 与 real overlap 为 0。
  - 行数：train_real 18741；valid 5957；test 8855；external 5509；synthetic_train_augmented 2588；synthetic_scenario_benchmark_50sites 50。
- `cd backend && .venv/bin/python ../scripts/train_group_split_rf.py`
  - row_random ROC-AUC：0.9999；id_DOI/id_Source group split：1.0。
  - 解释：指标接近满分，必须标注为标签/阈值派生与规则特征导致的虚高风险，不可写成真实泛化证明。
- `cd backend && .venv/bin/python ../scripts/generate_synthetic_benchmark.py`
  - 结果：50 个场地、2588 个样点，覆盖 9 大区；HM 18、OP 16、HM+OP 16；全部 `is_synthetic=true`。

### AI/RAG

- `cd backend && .venv/bin/python ../scripts/test_ai.py`
  - RAG 命中：因子 1、阈值 8、技术 8。
  - 命中技术包含：固化/稳定化、植物修复、土壤淋洗、生物修复、热脱附等。
  - Docker 栈内复验 exit 0；模型回复质量异常时自动降级为可读 RAG 答案，未暴露真实 key。

### 极端 10 场地

- 本机：`cd backend && .venv/bin/python ../scripts/run_system_extreme_validation.py`
- Docker：`docker compose --env-file deploy/.env -f deploy/docker-compose.yml -p srs_codex_validation exec -T backend python /app/scripts/run_system_extreme_validation.py`
- 两轮结果一致：
  - `n_cases=10`
  - `keyword_hit_accuracy=1.0`
  - `avg_quality_score=100.0`
  - `closed_loop.import/diagnosis/evaluation/recommendation/report/workflow_traceability/file_upload_download/ai_rag = true`

### 前端与浏览器

- `cd frontend && npm run build`
  - 结果：通过。
  - 警告：主 JS 包约 2.5 MB，建议后续做路由级懒加载。
- 浏览器验收：
  - 登录成功；首页显示 10 个场地、408 个采样点。
  - 7+1 导航含“方案推荐”；enterprise 访问 `/system` 显示 403。
  - 场地详情含点位地图、采样点宽表、数据分析(EDA)、追溯报告。
  - EDA 表格和 ECharts canvas 正常渲染。
  - 障碍因子页含 RF/SHAP、Top-N、计算过程追溯。
  - 功能重构页含生产/生态评价和计算过程。
  - SSUI 页含指数、等级、计算过程。
  - 推荐页含 Top5 技术、匹配度、禁用条件、证据来源。
  - 追溯页含 5 阶段、上传材料、PDF/DOCX 生成、报告下载。

### 地图

- `/api/v1/sites/{site_id}/map/layers`
  - 返回 FeatureCollection；46 个点、14 个污染物；含 legend、selected_factor、exceedance、risk_level。
  - URL encode 后 `factor=砷` 筛选返回 200，样点含 threshold、exceedance、risk_level。
- `/api/v1/map/tile/img/1/0/0`
  - Docker 后端在 `TIANDITU_KEY` 为空时返回 503。
  - 前端 `.env.local` key 直连地图服务返回 403：`IP不匹配`。
  - 结论：系统点位图层可用，底图当前受 key 白名单限制未通过。

### 报告

- Docker live API 生成下载：
  - PDF：`application/pdf`，文件头 `%PDF-1.7`。
  - DOCX：`application/vnd.openxmlformats-officedocument.wordprocessingml.document`，可解包。
  - Compose 复验中 PDF/DOCX 报告生成接口均返回 200，PDF 下载文件头为 `%PDF-1.7`。
- DOCX 章节校验均通过：
  - 地图图件、检测数据摘要、数据质量校验、功能重构可行性、SSUI、推荐修复方案矩阵、五阶段全流程追溯、附件清单、人工复核意见区。

### Docker

- `docker build -f backend/Dockerfile -t srs-backend:codex-validation .`
  - 结果：通过。
- `docker run --rm srs-backend:codex-validation pytest -q`
  - 结果：`47 passed, 2 skipped`。
- `docker compose --env-file deploy/.env -f deploy/docker-compose.yml -p srs_codex_validation up -d --build`
  - 结果：PostgreSQL healthy，Redis/backend 启动。
- 2026-06-15 最终复验：
  - 重新构建 `srs-backend:codex-validation` 后执行 `docker run --rm srs-backend:codex-validation pytest -q`，结果 `47 passed, 2 skipped, 7 warnings`。
  - 刷新 Compose 栈后 `/health` 返回 200；未登录 `/api/v1/sites` 返回 401；登录后返回 10 个场地。
  - 当前 Compose 栈内再次运行极端验证，结果 `n_cases=10`、`keyword_hit_accuracy=1.0`、`avg_quality_score=100.0`，所有 closed_loop 项为 true。
- 容器内：
  - `alembic upgrade head`
  - `python -m app.db.bootstrap`
  - `python -m app.db.load_kb`
  - `python -m app.db.load_standard_thresholds`
  - `python -m app.db.load_remediation_cases`
  - `pytest -q`
  - 结果：全部通过。

### 打包

- `backend/.venv/bin/pyinstaller -y packaging/srs.spec --clean`
  - 结果：生成 `dist/SRS`、`dist/SRS.app`、`build/srs/SRS.pkg`。
- `dist/SRS --no-browser --no-tray --port 18082`
  - `/health`：200。
  - `/login`：返回前端 HTML。
- `dist/SRS.app/Contents/MacOS/SRS`
  - 仍不稳定；`spctl` rejected；PyInstaller 提示 onefile + `.app` bundle 模式不推荐。

## 已修复项目

1. DOCX 报告章节不完整。
   - 修改：`backend/app/services/report_service.py`
   - 测试：`backend/tests/test_workflow_report.py`
2. Docker compose 未向后端传 AI/地图服务环境变量。
   - 修改：`deploy/docker-compose.yml`
3. `scripts/test_ai.py` 对模型 SSL/网络失败 exit 2，导致 RAG 已可用仍被判失败。
   - 修改：`scripts/test_ai.py`
4. PyInstaller launcher 字符串导入 `app.main` 失败。
   - 修改：`packaging/launcher.py`
5. 打包后前端静态目录无法定位，`/login` 404。
   - 修改：`backend/app/main.py`

## 残留风险

1. 地图服务底图未通过：当前 key 返回 `IP不匹配`，需在地图服务控制台配置本机/Docker 出口 IP 或使用后端 `TIANDITU_KEY`。
2. `deploy/.env` 仍是 SiliconFlow/Qwen；若要按甲方要求使用 GLM，需要人工更新真实 `.env`，代码默认和示例文件已是 GLM。
3. 模型指标接近 1.0，必须持续标注为标签/阈值派生风险，不可包装成真实泛化性能。
4. 前端主包 2.5 MB，后续应做路由级懒加载。
5. 前端数据导入 UI 仍是单文件导入；后端/脚本可多次导入，但“多文件批量上传 UI”未完整实现。
6. `dist/SRS` 单文件可执行可用；`.app/.pkg` 尚未达到正式安装包标准，需要迁移 onedir/Tauri/Electron、签名、公证、安装后自检。
7. 打包日志提示 WeasyPrint 动态库可能不完整；Docker PDF 正常，本机 `.app` 报告生成仍需专门验收。

## 当前 Docker 栈

验证栈仍在运行：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml -p srs_codex_validation ps
```

关闭并删除验证卷：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml -p srs_codex_validation down -v
```
