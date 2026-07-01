# SRS 系统全链路修复任务书

生成日期: 2026-06-23

适用项目: `/Users/lensis/大语言模型/Projects/SRS`

面向执行代理: GLM5.2 + ultracode

面向审计代理: 项目组

## 0. 任务背景

当前系统经过 DeepSeek 调整后，大部分页面和接口已经能启动或部分运行，但仍存在会直接影响甲方验收的关键缺陷:

1. 正常数据导入/导出链路错误，导入可能错映射到旧的重金属模板或旧数据集。
2. 正常导入后，下游数据版本、重复导入、校验、场地状态和结果追溯仍有很多问题。
3. EDA 页面点进去失败，疑似后端模块名冲突和前端 React hooks 顺序问题共同导致。
4. SSUI 页面未点击分析就出现结果，历史结果与本次运行结果没有被明确区分。
5. ARG/技术库、方案推荐和 AI 功能不可用或不可诊断。
6. 还有地图风险等级口径不一致、测试串库、导出缺失、推荐结构化字段丢失等连锁问题。

本任务不是让页面看起来不报错，而是把真实数据导入、数据校验、长表入库、EDA、诊断、重构评价、SSUI、推荐、技术库、AI、地图、导出、审计日志和报告版本链全部打通。

## 1. 项目硬规则

执行代理必须遵守仓库规则和甲方需求优先级:

1. 不得修改原始检测值，不得伪造数据、标准、文献、模型性能。
2. 不得硬编码 API key、token、secret，不得提交 `.env`。
3. 不得回滚用户或 DeepSeek 已有修改，不得使用 `git reset --hard` 或破坏性 checkout。
4. 数据必须走长表 `measurements`，一项检测因子一行。
5. 阈值、权重、参数、模型版本、数据版本必须可追溯。
6. AI 只能辅助解释和检索，不能替代监管判定，不能编造修复方案。
7. 若源数据质量不足，必须隔离/人工复核，不能生成正式诊断、SSUI、推荐和报告结论。
8. 优先级为: 甲方需求闭环 > 数据真实性 > 算法可解释性 > 可验收交付 > UI > 工程优雅 > 研究探索。

## 2. 竞品基准

参考市场上成熟环境数据管理/环境监测产品:

1. EQuIS / EarthSoft  
   官方地址: https://earthsoft.com/products/  
   可借鉴点: 环境数据全生命周期管理、现场采集、实验室数据接收、QA/QC、标准交换格式、报告、地图、Power BI/ArcGIS 集成、权限和审计。

2. ESdat  
   官方地址: https://esdat.net/data-analysis-and-reports/  
   可借鉴点: 数据验证、合规报告、地下水趋势、化学表格、超标报告、仪表盘、地图和政府/监管流程适配。

3. Locus EIM  
   官方地址: https://www.locustec.com/applications/environmental-information-management/  
   可借鉴点: 分析数据管理、校验、计算、GIS、仪表盘、修复工作流、审计追踪。

4. Esri Environmental Monitoring  
   官方地址: https://www.esri.com/en-us/industries/earth-sciences/disciplines/environmental-monitoring  
   可借鉴点: 地图、实时监测、仪表盘、利益相关方视图、AI/数据科学/cloud 集成。

竞品共同经验:

1. 环境数据系统的第一能力是数据可信和版本追溯，不是 AI 文案。
2. 导入必须有字段映射、校验、QA/QC、错误报告和人工复核入口。
3. 图表、地图、报告必须绑定真实数据来源和当前数据版本。
4. 推荐和结论必须有规则、标准、参数、证据来源。
5. 导出、报告、下载、写操作必须记录审计日志。

## 3. 甲方需求闭环

需求基线文件:

1. `docs/requirements/SRS.md`
2. `docs/acceptance/acceptance_criteria.md`
3. `docs/architecture/database_schema.md`
4. `backend/app/models/__init__.py`

核心业务闭环:

```text
导入场地数据
→ 字段映射
→ 数据校验
→ 长表 measurements 入库
→ 场地列表/详情
→ EDA 数据体检
→ 障碍因子识别 / RF / SHAP
→ 功能重构可行性评价
→ SSUI 可持续利用评价
→ 重构方案推荐 / 技术库匹配
→ 五阶段追溯
→ PDF/DOCX/HTML 报告
→ 导出与审计日志
```

禁止伪验收:

1. 页面能打开但数据写死。
2. 按钮能点但无后端。
3. 后端返回但未持久化。
4. 模型能跑但结果未入库。
5. 报告能生成但无真实数据。
6. 权限页面显示但后端不拦截。
7. 图表或地图是静态假数据。
8. AI 直接编监管结论或修复方案。

## 4. 问题矩阵与修复要求

### 4.1 导入映射错误

相关文件:

1. `backend/app/api/data.py`
2. `backend/app/services/import_service.py`
3. `frontend/src/pages/DataUpload.tsx`
4. `frontend/src/pages/FieldMappingPage.tsx`
5. `backend/tests/test_data_import_batch.py`
6. `backend/tests/test_data_pipeline.py`

已知问题:

1. 单文件 `/import` 的 `auto` 路径和批量 `/import/batch` 的 `auto` 路径不一致。
2. 单文件 auto 只跑 `detect_mapping()`，失败后不 fallback 到 `smart_detect_and_map()`。
3. 批量 auto 会 fallback，因此单文件和批量同一文件可能得出不同结果。
4. 重金属识别使用 substring，`as/cd/pb` 等英文片段可能造成误判。
5. `site_code` 可能由含时间戳的存储文件名派生，导致重复导入同一源文件时产生不稳定场地编号或数据版本。
6. Wizard 可能不便于自定义因子代码，需确认前端 Select 是否支持自由输入。

修复要求:

1. 建立统一函数:

```python
def resolve_mapping_for_file(mapping_id: str, dest: str) -> tuple[str, dict, dict]:
    """返回 used_id, mapping, detection_report。单文件和批量必须共用。"""
```

2. auto 识别顺序:

```text
预设模板 detect_mapping
→ 若高置信命中则使用预设
→ 若未命中则 smart_detect_and_map
→ 若 smart 低置信或缺必需字段则返回 review_required
```

3. detection_report 至少包含:

```json
{
  "used_id": "smart_auto",
  "confidence": 0.0,
  "detected_sheet": "Sheet1",
  "point_code_column": "采样点编号",
  "longitude_column": "经度",
  "latitude_column": "纬度",
  "factor_columns": [],
  "warnings": [],
  "template_scores": []
}
```

4. 重金属/有机物识别必须基于规范 token:

```text
允许命中: As, Pb, Cd, Hg, Cr, Cu, Zn, Ni, 砷, 铅, 镉, 汞, 铬, 铜, 锌, 镍
不得命中: sample, case, baseline, class 等包含 as/cd/pb 的普通词
```

5. 错误处理:

低置信、无点位列、无数值因子、坐标列异常时，不得硬导入正式链路。返回 400 或 review_required，前端展示原因和建议使用 Wizard。

验收:

1. 单文件 auto 和批量 auto 对同一文件得到同一 mapping 决策。
2. 非重金属普通数据不会被误判为 `yunnan_gejiu` 或 heavy_metal。
3. 错误信息可解释，不是笼统“导入失败”。

### 4.2 导入后数据版本、幂等与追溯不足

相关文件:

1. `backend/app/services/ingest_service.py`
2. `backend/app/models/__init__.py`
3. `backend/app/services/evaluation_service.py`
4. `backend/app/services/diagnosis_service.py`
5. `backend/app/services/report_service.py`

已知问题:

1. `ImportBatch.mapping_snapshot` 已存在但当前写入为 `None`。
2. 重复导入同一数据可能堆叠 measurements。
3. `EvaluationResult.data_version` 当前类似 `site{site_id}_n{样本数}`，不能证明结果对应当前数据。
4. 诊断、评价、推荐、报告之间缺少强一致数据版本链。

修复要求:

1. `ingest()` 保存实际 `mapping_snapshot`。
2. 计算源文件 sha256 和 mapping hash。
3. 若不做迁移，至少把 hash 写入 `validation_report` 和 `mapping_snapshot`。若允许改模型，扩展:

```python
class ImportBatch:
    source_sha256: str | None
    mapping_hash: str | None
    data_version: str | None
```

4. 提供统一数据版本函数:

```python
def current_site_data_version(db: Session, site_id: int) -> str:
    """基于该场地 import_batch_id/source hash/measurement count/max updated_at 生成稳定版本。"""
```

5. 评价、诊断、推荐、报告都必须记录该版本。
6. 重复导入策略:

```text
同 site + 同 source_sha256 + 同 mapping_hash:
  不重复写 measurements，返回 existing/reimported 状态
同 site + 不同 source_sha256:
  新建批次，并标记旧结果 stale
```

验收:

1. 同一文件重复导入不会让 measurements 翻倍。
2. 评价结果能判断是否 stale。
3. 报告 data_snapshot 能追溯到导入批次和数据版本。

### 4.3 数据导出缺失

相关文件:

1. `backend/app/api/data.py`
2. `frontend/src/api/client.ts`
3. `frontend/src/pages/SiteDetail.tsx`
4. `backend/app/services/audit_service.py`

已知问题:

1. 有 `data:export` 权限，但没有完整的真实数据导出接口。
2. 甲方验收要求导出内容与库内一致并记录日志。

修复要求:

新增接口之一:

```python
@router.get("/sites/{site_id}/measurements/export")
def export_site_measurements(
    site_id: int,
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    user: User = Depends(require_permission("data:export")),
    db: Session = Depends(get_db),
):
    ...
```

导出字段至少包含:

1. site_code
2. site_name
3. point_code
4. longitude
5. latitude
6. region
7. depth_top_cm
8. depth_bottom_cm
9. factor_code
10. factor_name
11. category
12. value
13. unit
14. source_file
15. import_batch_id
16. detected_at

错误处理:

1. 无权限返回 403。
2. 场地不存在返回 404。
3. 无数据返回 404 或空文件，但前端必须明确提示。
4. 每次导出写 audit log，action 建议 `export_measurements`。

验收:

1. 导出行数等于该场地 measurements 行数。
2. CSV/XLSX 可打开，中文不乱码。
3. audit log 有导出记录。

### 4.4 EDA 点击失败

相关文件:

1. `ml/eda/profile.py`
2. `backend/app/api/data.py`
3. `frontend/src/components/EdaPanel.tsx`
4. `backend/tests/test_eda.py`

已知问题:

1. `from profile import ...` 与 Python 标准库 `profile` 撞名。
2. 全量 pytest 中已出现 ImportError 风险。
3. `EdaPanel` 在 loading/empty early return 后才声明多个 `useMemo`，可能触发 React hooks 顺序错误。

修复要求:

1. 将 `ml/eda/profile.py` 重命名为 `ml/eda/eda_profile.py`。
2. 所有导入改为明确模块名。
3. 后端不要污染全局 `sys.path` 或至少避免通用模块名。
4. 前端所有 hooks 必须在任何 conditional return 之前声明。
5. EDA 请求失败时显示后端 detail 和重试入口。

验收:

1. `backend/tests/test_eda.py` 通过。
2. 全量 pytest 不再从标准库 `profile` 导入 EDA 函数。
3. 前端 build 通过。
4. EDA 页面不会因 hooks 顺序崩溃。

### 4.5 SSUI 未点击已有结果

相关文件:

1. `frontend/src/pages/SSUIAnalysis.tsx`
2. `frontend/src/pages/ReconstructionAnalysis.tsx`
3. `frontend/src/pages/ObstacleAnalysis.tsx`
4. `backend/app/api/evaluation.py`
5. `backend/app/services/evaluation_service.py`

已知问题:

1. 页面选中场地后自动 GET 旧结果并直接显示在主结果区。
2. 用户会理解为“还没点击分析就已经算出结果”。
3. 后端没有 stale/current data version 清楚提示。

修复要求:

1. 页面分为历史结果区和本次运行结果区。
2. 选场地只加载历史元信息:

```text
已有历史结果，生成时间 xxx，数据版本 xxx。
当前数据版本 yyy。
若版本不一致，请重新运行。
```

3. 点击运行按钮后才展示本次结果，并显示 `created_at`、`data_version`、`param_version`。
4. GET `/evaluation` 返回:

```json
{
  "site_id": 1,
  "current_data_version": "...",
  "results": {
    "ssui": {
      "data_version": "...",
      "is_stale": false
    }
  }
}
```

验收:

1. 新选场地不会直接把历史结果伪装成本次分析。
2. 历史结果有明确标签。
3. 数据变更后旧评价显示 stale。

### 4.6 技术库 / ARG / 推荐不可用

相关文件:

1. `backend/app/api/system.py`
2. `backend/app/services/recommend_service.py`
3. `backend/app/api/evaluation.py`
4. `ml/recommend/engine.py`
5. `frontend/src/api/client.ts`
6. `frontend/src/pages/SystemManagement.tsx`
7. `frontend/src/pages/RecommendationPage.tsx`

已知问题:

1. 后端已有 `/system/technologies` CRUD，但前端没有技术库管理入口。
2. 推荐引擎生成 `reason_struct`，但入库只保存 `reason`。
3. GET recommendation 不返回 `reason_struct`、`matched_factors`、成本、工期、来源等结构化字段。
4. 前端卡片期待 `reason_struct`，导致大量字段显示为空。
5. 代码中未发现明确名为 ARG 的独立库，需按技术库/推荐库/RAG 方向修复；若甲方另有 ARG 定义，需再补。

修复要求:

1. 前端 `api.client.ts` 增加:

```ts
technologies(params?)
createTechnology(body)
updateTechnology(id, body)
deleteTechnology(id)
```

2. `SystemManagement.tsx` 新增“技术库管理” Tab。
3. 技术库管理支持:

```text
列表、搜索、新增、编辑、删除、适用污染物、适用土壤、适用用地、
阶段、优点、局限、成本、工期、二次风险、禁用条件、来源
```

4. 推荐结果必须返回结构化字段:

```json
{
  "rank": 1,
  "technology": "...",
  "match_score": 0.9,
  "matched_factors": ["砷", "铅"],
  "reason": "...",
  "reason_struct": {
    "obstacle_binding": [],
    "tech_fit": {},
    "advantages": "...",
    "limitations": "...",
    "cost_duration": {},
    "regulatory_basis": "...",
    "score_breakdown": {}
  }
}
```

5. 推荐不能由 LLM 编造，必须来自技术库规则匹配。

验收:

1. 系统管理能管理技术库。
2. 推荐页卡片字段不再大片为空。
3. 推荐结果绑定障碍因子和技术库来源。

### 4.7 AI 功能不可诊断

相关文件:

1. `backend/app/services/ai_service.py`
2. `backend/app/api/ai.py`
3. `backend/app/core/ai_config.py`
4. `frontend/src/components/AiAssistant.tsx`
5. `frontend/src/pages/SystemManagement.tsx`

已知问题:

1. 未配置或调用失败时，前端提示过粗。
2. history 可能重复发送当前用户消息。
3. 用户不知道当前是否绑定场地、是否走 RAG 降级、是否模型真的可用。

修复要求:

1. 前端发送 history 时不要包含当前最新 user message，避免后端再次 append 后重复。
2. AI drawer 顶部展示:

```text
模型状态: 未配置 / 已配置 / 调用失败 / RAG 降级
场地上下文: 已绑定 #id / 未绑定
知识库上下文: 命中 n 条因子、n 条阈值、n 条技术
```

3. catch 中展示后端 `detail` 或 `reply`，不是笼统“AI 服务暂不可用”。
4. 后端继续保持:

```text
资料不足 → 建议人工复核
无 API key → RAG fallback
HTTP 429 → 额度受限提示 + RAG fallback
```

验收:

1. 未配置 API key 时 AI 不崩，能显示知识库检索结果。
2. 配置错误时用户能看到明确错误。
3. AI 回答不伪造监管结论。

### 4.8 地图风险等级不一致

相关文件:

1. `backend/app/api/map.py`
2. `frontend/src/components/SiteMap.tsx`
3. `backend/tests/test_map_api.py`

已知问题:

1. 后端 `_risk()` 返回 `high/medium/low/unknown`。
2. 后端 legend 返回 `none/low/med1/med2/high/severe/extreme/unknown`。
3. 前端用超标倍数连续分桶着色。
4. 测试仍可能期待旧口径。

修复要求:

统一风险等级:

```text
none: exceedance < 1
low: 1 <= exceedance < 3
med1: 3 <= exceedance < 10
med2: 10 <= exceedance < 30
high: 30 <= exceedance < 80
severe: 80 <= exceedance < 200
extreme: exceedance >= 200
unknown: 无阈值/无数据
```

`_risk()`、legend、前端颜色、popup 文案、测试断言全部一致。

验收:

1. map API feature risk_level 只返回上述枚举。
2. legend 与前端颜色一致。
3. map 测试通过。

### 4.9 测试隔离问题

相关文件:

1. `backend/tests`
2. `backend/app/db/session.py`
3. `backend/app/core/config.py`

已知问题:

1. 多个测试使用 `os.environ.setdefault("DATABASE_URL", "...")`。
2. `get_settings()` 使用 `lru_cache`。
3. `backend/app/db/session.py` 模块 import 时创建全局 engine。
4. 全量测试中可能出现 auth/eda/map 串库。

修复要求:

1. 建立统一 pytest fixture 或测试工具函数，确保每个测试模块初始化前设置 DATABASE_URL。
2. 必要时提供 `reset_engine_for_tests(database_url: str)`。
3. 每次 bootstrap 前清理 settings cache 和 engine。
4. 不要让某个测试模块的 DATABASE_URL 污染后续模块。

验收:

1. `cd backend && .venv/bin/pytest -q` 不出现因为串库导致的角色为空、audit log 缺失、场地不存在。
2. 测试失败若是旧口径，必须同步解释和更新测试。

## 5. 数据源问题处理方案

当源文件有以下问题时:

1. 无法可靠识别点位列。
2. 无法可靠识别检测因子列。
3. 坐标缺失或不在合理范围。
4. 单位不明或单位混乱。
5. 样本量过小，不足以支撑 EDA/诊断/SSUI。
6. 因子覆盖不足。
7. 来源文件 hash 与历史记录冲突。
8. 文件结构明显不是检测数据。

系统应执行:

```text
保存原始文件
→ 生成 ImportBatch
→ status = review_required 或 quarantined
→ 保存 detection_report / validation_report
→ 允许查看、下载、人工修正 mapping
→ 禁止正式诊断、SSUI、推荐、报告结论
→ 人工确认后转入正式分析链
```

不得执行:

1. 不得硬套重金属模板。
2. 不得静默丢弃大量列。
3. 不得用 AI 猜字段后直接出正式结论。
4. 不得把低质量数据包装成可发表/可验收结论。

## 6. 建议执行顺序

1. 先修导入映射统一和误判。
2. 再修 mapping snapshot、source hash、data version。
3. 补数据导出。
4. 修 EDA 后端撞名和前端 hooks。
5. 修 SSUI 历史/本次运行语义和 stale 判断。
6. 修推荐结构化返回。
7. 接前端技术库管理。
8. 修 AI 状态和错误诊断。
9. 修地图等级一致。
10. 修测试隔离。
11. 跑全量后端测试和前端 build。
12. 做真实端到端手工验收。

## 7. 必跑验证

```bash
cd /Users/lensis/大语言模型/Projects/SRS/backend
.venv/bin/pytest -q
```

```bash
cd /Users/lensis/大语言模型/Projects/SRS/frontend
npm run build
```

若失败:

1. 区分环境问题、旧测试口径问题、真实代码问题。
2. 真实代码问题必须修。
3. 旧测试口径问题可以同步更新测试，但必须解释原因。
4. 不能仅为了绿测试而牺牲甲方真实需求。

## 8. 端到端验收脚本

建议最终人工演示:

1. 登录管理员账号。
2. 上传一个真实场地 Excel。
3. 使用 auto mapping，确认没有误套旧重金属模板。
4. 查看导入批次、校验报告、mapping snapshot。
5. 打开场地详情，确认点位、检测长表、地图均为真实数据。
6. 导出 measurements，确认行数与数据库一致。
7. 打开 EDA，确认统计、直方图、箱线、相关热力图不崩。
8. 运行障碍因子诊断。
9. 运行重构评价。
10. 运行 SSUI，确认点击前只显示历史结果提示。
11. 运行方案推荐，确认推荐绑定障碍因子和技术库。
12. 在系统管理中新增/编辑/删除技术库条目。
13. 打开 AI 助手，测试未配置和已配置状态。
14. 生成报告，确认报告 data_snapshot 有版本链。
15. 查看 audit log，确认导入、导出、报告生成等写操作有记录。

## 9. 交付格式

GLM5.2 完成后必须输出:

1. 已改文件清单。
2. 每个 bug 的根因。
3. 每个 bug 的修复说明。
4. 数据结构变更说明。
5. 测试命令和结果。
6. 未完成项或风险。
7. 给项目组二次审计的重点。

---

# 给 GLM5.2 的 Dynamic Workflow 提示词

```text
你是 GLM5.2，启用 ultracode。任务是在 /Users/lensis/大语言模型/Projects/SRS 中修复污染场地监管系统核心 bug，目标是让真实数据导入、导出、EDA、SSUI、推荐/技术库、AI、地图与审计闭环真实可用。

强制规则:
1. 全程读取当前工作树，不得凭记忆改。
2. 不得回滚用户或 DeepSeek 已有修改，不得 git reset/checkout。
3. 不得修改原始检测值，不得伪造数据、标准、文献、模型性能。
4. 不得硬编码 API key、token、secret，不得提交 .env。
5. 每个结果必须绑定数据版本、参数版本、来源证据。
6. 修复优先级: 甲方需求闭环 > 数据真实性 > 算法可解释性 > 可验收交付 > UI > 工程优雅。
7. 小步提交式工作: 每完成一类问题，运行相关测试并记录结果。

阶段 1: 研究
- 读取 AGENTS.md、CLAUDE.md、docs/requirements/SRS.md、docs/acceptance/acceptance_criteria.md。
- 读取 backend/app/api/data.py、backend/app/services/import_service.py、backend/app/services/ingest_service.py、backend/app/models/__init__.py。
- 读取 EDA、SSUI、推荐、AI、地图、系统管理相关文件。
- 输出当前问题矩阵，不改代码。

阶段 2: 计划
- 把问题拆成导入映射、数据版本、导出、EDA、SSUI、推荐技术库、AI、地图、测试隔离九条线。
- 为每条线列出文件、函数、数据结构、测试。

阶段 3: 执行
按顺序修改:
1. 统一单文件/批量导入 auto mapping。
2. 加固重金属/有机/复合识别，输出 mapping confidence。
3. 保存 mapping snapshot、source hash、data version，保证重复导入不污染。
4. 新增真实数据导出接口和前端入口，写 audit log。
5. 修复 EDA profile 撞名和 React hooks 顺序。
6. 修复 SSUI 历史结果/本次运行语义，增加 stale 判断。
7. 接通技术库管理前端，修复推荐结构化返回。
8. 修复 AI 状态、错误、RAG 降级、history 重复问题。
9. 统一地图 risk_level 和 legend。
10. 修复测试数据库隔离。

阶段 4: 验证
必须运行:
- cd backend && .venv/bin/pytest -q
- cd frontend && npm run build

如果失败:
- 判断是环境问题、旧测试口径问题、还是真实代码问题。
- 真实代码问题必须修。
- 旧测试口径问题可以同步测试，但必须说明为什么测试应改。

阶段 5: 交付
输出最终报告:
- 已改文件
- 每个 bug 的根因和修复
- 数据源问题处理策略
- 测试结果
- 剩余风险
- 给项目组审计的重点清单

完成标准:
- 不允许只让页面不报错。
- 不允许静态假数据。
- 不允许 AI 编造方案。
- 不允许未绑定数据版本的 SSUI/推荐/报告。
- 不允许导入错映射到旧重金属模板。
```
