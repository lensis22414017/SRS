# 每日开发计划 — 2026-06-25

[MODE: PLAN]

**辛特助** 巡检报告 | 日期：2026-06-25 | 当前模式：PLAN

---

## 昨日完成（2026-06-24）

| 工作 | 内容 |
|---|---|
| 浏览器全链路验收 | 2026-06-24 23:52 完成 44 张截图，覆盖登录→导入→诊断→评价→追溯→报告全流程 |
| 深度诊断报告 | `裴总11问题深度诊断与改进规划_20260624.md` 逐条验证、根因定位 |
| 竞品增量报告 | `SRS_COMPETITIVE_INCREMENT_20260624.md` 双轨架构能力总结 |
| 深度修复提示词 | `CC_SRS_DEEP_FIX_PROMPT_20260625.md` 整理为今日 EXECUTE 任务基线 |
| 验收最终报告 | `browser_acceptance_20260624/final_2352/FINAL_REPORT.md` 详细记录剩余硬问题 |

> **注意**：2026-06-24 无 git 提交（昨日工作为验收+规划文档，未进入 EXECUTE）。最新代码提交停留在 2026-06-23 `d253cfc`。

---

## 当前仓库状态

### MVP 闭环进度

| 环节 | 状态 | 说明 |
|---|---|---|
| 数据导入 | ✅ 已通 | 幂等导入、字段映射、版本链均通过 |
| 数据校验 | ✅ 已通 | validation_service + qc_service (RPD/加标回收) |
| 场地详情 | ✅ 存在 | SiteDetail.tsx；land_use_type 已可选择（前轮已修） |
| 障碍因子识别 | ⚠️ 部分 | HM/复合场地通过；OP 场地缺外部协变量（E③ 长期项） |
| RF/SHAP 解释 | ⚠️ 部分 | shap_service.py 已有；AUC≈1.0 标签泄漏已诚实标注 |
| 功能重构评价 | ⚠️ 缺口 | HM 场地通过；**OP(有机)场地返回 null / "无足够指标"** |
| SSUI 评价 | ⚠️ 缺口 | HM 场地通过；**OP(有机)场地 SSUI=null** |
| 方案推荐 | ✅ 已通 | recommend_service + 技术库 + GB36600 有机技术路线 |
| 全流程追溯 | ⚠️ 缺口 | 五阶段架构存在；**甲方直接反馈"上传文件仍实现不了"** |
| PDF 报告 | ✅ 存在 | report_service.py + HTML 模板；DOCX 同步未完整 |
| 操作日志 | ✅ 存在 | audit_service.py，写操作有记录 |

### 已知硬阻塞（不解决不能签收）

| 级别 | 问题 | 最新证据 |
|---|---|---|
| P0 | **pytest 2 failed**（test_api_batch_import_and_overview_badges + test_report_html_renders）| FINAL_REPORT §2：78 passed, 2 failed |
| P0 | **OP(有机)场地 SSUI=null / 功能重构=null** | FINAL_REPORT §6 问题7，CC_FIX §一-3 |
| P0 | **追溯五阶段文件上传不可用** | FINAL_REPORT §5d，CC_FIX §二-4/5，甲方直接反馈 |
| P1 | **AI/RAG HTTP 401**（configured≠connected） | FINAL_REPORT §2，CC_FIX §一-2 |
| P1 | **场地详情地图混入全国数据** | FINAL_REPORT §5b，CC_FIX §三-6 |
| P1 | **EDA 云雨图≠直方图，中文显示残缺** | FINAL_REPORT §5c，CC_FIX §四-7/8 |
| P2 | AntD `message` context 警告 | FINAL_REPORT §5 P1-6 |
| P2 | 前端 bundle 2.6 MB（无懒加载） | FINAL_REPORT §5 P2-1 |

---

## 今日最重要 3 个目标

---

### 目标 1：后端测试全绿（0 failed）

**为什么最高优先级：**
测试红灯是系统质量门槛。两条 failing test 直接说明批量导入逻辑 + 报告渲染存在口径矛盾，不修复则无法可信地声明任何环节"已通"。这是后续所有修复的安全网。

**文件路径与具体任务：**

```
1. [backend/tests/test_data_pipeline.py::test_api_batch_import_and_overview_badges]
   - 原因：断言 any(it["n_exceed"] > 0 for it in sites["items"]) 失败
     → 可能是测试数据库 bootstrap 后无超标测量值，或 n_exceed 字段计算逻辑未在测试环境触发
   - 具体改动：
     · 在测试 fixture 中确认使用真实个旧重金属数据（GEJIU = data/processed/...）路径可达
     · 若路径问题：更新测试中 GEJIU 常量为 sandbox 可读路径或写入内联样本数据
     · 若计算问题：检查 backend/app/api/data.py 的 sites 列表接口中 n_exceed 聚合 SQL
     · 确认 thresholds 已在 bootstrap 时加载（load_kb()）
   - 影响范围：test_data_pipeline.py，不影响生产代码（除非 n_exceed SQL 需修）
   - 验证方式：cd backend && .venv/bin/pytest tests/test_data_pipeline.py::test_api_batch_import_and_overview_badges -v → PASSED
   - 失败回滚：测试数据 fixture 独立，不影响生产库

2. [backend/tests/test_workflow_report.py::test_report_html_renders]
   - 原因：CC_FIX 要求"报告中操作日志摘要可以不提"，但测试仍在 L147 断言"操作日志摘要"字符串存在
     → 代码层面报告模板已删除该章节，但测试未同步
   - 具体改动：
     · 删除 test_report_html_renders 中对"操作日志摘要"的断言
     · 改为断言报告包含：["附件清单", "报告版本", "人工复核意见区", "采样点", "检测数据", "障碍因子"]
     · 同时核查报告 HTML 模板是否确已包含这些必要章节
   - 影响范围：test_workflow_report.py L147（纯测试文件修改）
   - 验证方式：cd backend && .venv/bin/pytest tests/test_workflow_report.py::test_report_html_renders -v → PASSED
   - 失败回滚：git revert 测试修改，不影响主代码

3. [全量验证]
   - 执行 cd backend && .venv/bin/pytest -q
   - 目标：80+ passed, 0 failed
   - 记录测试通过截图或输出文本作为验收证据
```

**风险：**
- `GEJIU` 路径在 sandbox 环境可能不同于用户本机 `.venv` 路径；需用本地 pytest 而非 sandbox python
- `n_exceed` 失败若根因是 SQL 聚合逻辑，改动范围扩大到 `backend/app/api/data.py` 的 sites 列表接口

---

### 目标 2：OP 有机场地评价闭环（消灭裸 null/NaN）

**为什么高优先级：**
`2.20250731_有机污染场地数据表(南京栖霞)` 是三套真实数据之一（49 个样本）。当前 SSUI=null、功能重构=null，整个有机污染场地的评价链断裂。甲方演示时有机场地全部失效，是 MVP 核心缺口。目标不是立即算出精确分数，而是建立**可解释降级路径**：有数据时给分，无元指标时给清晰说明+可用诊断。

**文件路径与具体任务：**

```
1. [ml/evaluation/ssui.py]
   - 原因：SSUI C1（安全性维度）依赖 pH/有机质/CEC 等物理化学元指标；
     OP 场地无这些字段 → C1=None → SSUI=None
   - 具体改动：
     · 新增 _organic_exceedance_score(measurements, threshold_resolver) → float [0,1]：
       基于有机因子（苯并芘/多环芳烃/DDT/PAH/石油烃等）的阈值超标比率（超标因子数/总有机因子数）
       返回 1-超标比率（超标越多分越低，全超标→0，全达标→1）
     · 在 evaluate() 中：若物理化学元指标缺失（C1=None）但存在有机检测因子，
       则 C1 = _organic_exceedance_score()，explanation 补注"有机安全性基于阈值超标比率估算"
     · 新增字段 ssui_mode: "standard" | "organic_proxy"，便于报告区分计算路径
   - 影响范围：ssui.py，不影响 HM 场地（C1 有物理化学指标时走原逻辑）
   - 验证方式：
     · 单测：用南京栖霞 OP 场地数据调用 ssui.evaluate() → ssui_score 不为 None
     · 前端：SSUIAnalysis.tsx 显示有机场地 SSUI 分数 + ssui_mode="organic_proxy" 提示
   - 失败回滚：_organic_exceedance_score 为独立函数，可直接删除

2. [ml/evaluation/reconstruction.py]
   - 原因：功能重构评价指标体系（生产功能：氮磷钾/有机质/pH/土壤容重/重金属综合）
     OP 场地无氮磷钾/有机质 → 指标覆盖率 0 → 返回 null / "无足够指标"
   - 具体改动：
     · 新增 OP 场地降级评价路径 evaluate_organic_site()：
       仅使用可用指标（如 pH、有机污染超标比率、坐标/面积信息）
       给出 reconstruction_mode: "organic_limited"，comprehensive_score 基于可用指标子集
       必须在解释字段中列出"缺失指标清单"和"当前评价限制"
     · evaluate() 入口：若指标覆盖率 < 阈值（如 <30%），自动路由到 evaluate_organic_site()
   - 影响范围：reconstruction.py + evaluation_service.py（需判断路由逻辑）
   - 验证方式：
     · OP 场地功能重构页不再显示"无足够指标"，改为显示降级结果 + 限制说明
   - 失败回滚：evaluate_organic_site() 独立函数，不影响 HM 场地主路径

3. [前端消灭裸 null 显示]
   - 文件：frontend/src/pages/SSUIAnalysis.tsx, ReconstructionAnalysis.tsx
   - 改动：所有 score/value 字段显示前检查 null：
     · null → 显示带 Tooltip 的"—（数据不足，点击查看原因）"
     · 原因来自后端返回的 explanation / missing_indicators 字段
   - 禁止：任何情况下 UI 展示裸 "null" 字符串或 "NaN 分"
   - 验证方式：OP 场地 SSUI/重构页不再出现 null 字符串，改为清晰降级提示
```

**风险：**
- `_organic_exceedance_score` 需要 threshold_resolver 已加载有机阈值规则（GB36600 权威值已在 `data/standards/GB36600_有机阈值_权威.csv` 中）
- 降级分数不是精确评价，报告中必须明确标注"降级估算"，不得作为正式结论

---

### 目标 3：追溯五阶段文件上传真实持久化

**为什么高优先级：**
甲方明确反馈"全流程追溯上传文件功能仍实现不了"。这是甲方四大需求之一（全流程追溯）的核心交互，也是 MVP 15 项验收标准第 12 条（能录入五阶段追溯记录）的直接依据。不修复则追溯模块完全不可演示。

**文件路径与具体任务：**

```
1. [backend/app/api/workflow.py] 检查并修复文件上传接口
   - 原因：甲方说"上传功能仍实现不了"，上传后可能刷新丢失或根本无法写入
   - 具体改动：
     · grep 确认 POST /workflow/{site_id}/stages/{stage}/attachments 接口存在
     · 接口必须接受 multipart/form-data，字段：file（文件内容）、file_role（原始报告/审批意见/盖章版/补充材料）
     · 中文文件名：确保 Content-Disposition 使用 RFC5987（filename*=UTF-8''...）
     · 写入 workflow_attachments 表：site_id / stage / file_object_id / file_role / operator_id / created_at
     · 同时写入 audit_log
   - 影响范围：workflow.py API + workflow_service.attach_file() + file_service.store()
   - 验证方式：
     · curl POST 上传中文文件名 PDF → 返回 200 + file_object_id
     · GET /workflow/{site_id}/stages/{stage}/attachments → 返回上传记录
     · 刷新后 GET 结果仍存在（持久化验证）
   - 失败回滚：独立接口，不影响追溯阶段状态流转主逻辑

2. [backend/app/services/workflow_service.py + file_service.py]
   - 检查 attach_file() 是否真正写库而非只写内存
   - 检查 storage/ 目录权限，确认文件落盘
   - 确认下载接口按 file_object_id 读取，内容与上传一致

3. [frontend/src/pages/TraceDetail.tsx] 修复上传 UI 交互
   - 原因：可能是前端 Upload 组件未正确携带 stage / file_role / site_id
   - 具体改动：
     · Ant Design Upload 组件：action 指向正确 API 路径（/api/v1/workflow/{site_id}/stages/{stage}/attachments）
     · 携带 Authorization header（Bearer token）
     · 上传成功后刷新当前阶段的附件列表（onSuccess callback → refetch）
     · 每条附件记录显示：阶段 / 文件角色 / 上传人 / 上传时间 / 下载按钮
     · 文件角色枚举：原始报告 / 审批意见 / 盖章版报告 / 补充材料
   - 验证方式：
     · 浏览器操作：选择 PDF 文件 → 上传 → 页面刷新 → 附件记录仍存在 → 下载 → 内容一致
     · 覆盖全部五个阶段（调查评估/方案审批/施工监理/效果评估/后期管护）各上传一次
     · 截图 5 张作为验收证据
   - 失败回滚：仅改 TraceDetail.tsx 的 Upload 组件配置，不影响追溯状态流转

4. [新增单测]
   - [backend/tests/test_workflow_report.py] 新增 test_attachment_upload_and_persist：
     · 上传测试文件 → 查询附件列表 → 断言 site_id/stage/file_role 正确
     · 下载并断言文件内容 hash 一致
```

**风险：**
- storage/ 目录在 Docker 容器内需挂载持久化卷，否则容器重启后文件丢失；需检查 docker-compose.yml 挂载配置
- 中文文件名在不同 OS 编码可能有问题；测试时用实际中文文件名（如"调查评估报告.pdf"）

---

## 今日次优目标（P1，目标 1-3 完成后处理）

若目标 1-3 全部完成，建议按此顺序继续：

1. **AI 连通性真实修复**：区分 `has_config` vs `connectivity_ok`；修复 OpenAI 模型名不匹配（`Qwen3.5-9B-MLX-4bit` ≠ SiliconFlow 服务端模型名）；UI 不得显示"已配置=可用"。
   - 文件：`backend/app/services/ai_service.py`，`backend/app/api/system.py`，`frontend/src/pages/SystemManagement.tsx`

2. **地图作用域拆分**：场地详情地图后端接口必须 `WHERE sampling_point.site_id = {site_id}`，禁止返回全国数据。
   - 文件：`backend/app/api/map.py`，`frontend/src/components/SiteMap.tsx`

---

## 昨日完成 / 今日建议 / 阻塞项

```
昨日完成：
  - 浏览器全链路验收（44 张截图，FINAL_REPORT.md）
  - 裴总11问题深度诊断与根因定位
  - CC 执行提示词 CC_SRS_DEEP_FIX_PROMPT_20260625.md 准备完毕
  - import_service.py 污染类型 if-elif 短路 bug 已在上轮修复（L321-328 已三路判断）

今日建议：
  优先在本地（backend/.venv/bin/pytest）运行测试确认 2 failed 根因，
  再进入 EXECUTE 修复目标 1→2→3，每个目标修完立即跑测试验证。

阻塞项：
  - AI/RAG 401 需要有效的 API Key 或本地可用 Provider（依赖外部配置，非代码问题）
  - OP 场地外部协变量缺失（E③）是长期项，降级路径是 MVP 可接受方案

高风险文件（改动需谨慎）：
  - backend/app/services/import_service.py（上轮已改污染类型，再改需全量测试）
  - ml/evaluation/ssui.py（HM 场地 SSUI 已通过，改动不得破坏 HM 路径）
  - backend/app/services/file_service.py（文件存储路径，改动影响所有附件）

建议不要动的文件：
  - ml/artifacts/（模型文件，勿覆盖）
  - data/raw/（原始数据，禁止修改）
  - data/standards/GB36600_有机阈值_权威.csv（上轮已锚定，勿改）
  - reporting/templates/traceability_report.html（报告模板，改动需同步测试）
```

---

## 验收标准

本日工作完成标志：

```
1. cd backend && .venv/bin/pytest -q → 0 failed（当前 2 failed）
2. 南京栖霞 OP 场地 → SSUI 页面显示降级分数，不出现 null 字符串
3. 追溯页上传 PDF → 刷新后附件记录仍存在 → 下载内容与原文件一致
```

---

裴总确认后，可另开 Cowork 任务发送 `ENTER EXECUTE MODE` 执行。
