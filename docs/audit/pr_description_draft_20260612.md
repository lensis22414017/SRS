# PR: 数据切分零泄漏 + 报告 UX + 地图健壮性 + 迁移基线 + 审计

## 摘要
本 PR 面向"可辩护、可复现、可评审", 修复头号风险(数据切分泄漏)并补齐若干 PR 就绪项。**不改原始数据, 不混入模拟数据, 不夸大模拟指标为真实泛化。**

## 变更
### 1. 数据切分零泄漏(核心)
- 重写 `ml/models/dataset_splits.py`: 以 `(DOI, Source)` 连通分量为单位分配, 保证四个真实切分在 **DOI 与 Source 双键**上零跨集。
- 修复前实测 6 对泄漏(train-test DOI 重叠 125 等), 修复后 12 项检查全 0。
- 强化 `backend/tests/test_dataset_splits.py`: 交叉夹具 + 全配对双键断言 + 负对照 + 已提交 CSV 校验。
- 重建 `data/splits/*` 与 `dataset_split_registry.json`(`all_passed=true`)。

### 2. 报告 UX(PDF/DOCX)
- 前端 `TraceDetail` 增 PDF/DOCX 双按钮; 报告列表显示真实 `format`; 下载用正确扩展名。
- `api.generateReport(id, format)` 透传 `format`。后端三格式早已支持。

### 3. 地图健壮性
- `SiteMap` 增空坐标与瓦片加载失败覆盖层; 未配 key 回退 OSM。

### 4. 迁移基线
- 新增 `backend/alembic/versions/0001_baseline.py`(以 ORM metadata 落全量 schema, 可 upgrade/downgrade)。

### 5. PR 清洁
- `.gitignore` 补: 生成态大 CSV(splits/synthetic/model_ready 视图)、`frontend/.env.local`、scratch。

### 6. 审计文档
- `docs/audit/` 6 份: pr_readiness / data_split_leakage / product_flow / report_quality / docker_validation / pr_description。

## 测试
- 沙箱(pandas/numpy)实测: 切分零泄漏与 3 个新测试通过; 字段标准化、model_ready 派生、import 解析、模板章节核查通过。
- **待本机**: `bash scripts/run_tests.sh`(期望 ≥38 passed)、`npm run build`、Docker 全流程、`scripts/test_ai.py`(429 视为限流, RAG 仍命中)。

## 评审注意
- 重训后分组泛化指标会低于旧行级随机 AUC 0.9991, 属预期且正确。
- 报告静态图表/人工复核区为已知缺口(report_quality 审计), 留后续 PR。

## 不在本 PR
- 瓦片代理 `/api/v1/map/tile/...`(已在部署文档说明 key 白名单方案)。
- 报告图表渲染、前端拆包。
