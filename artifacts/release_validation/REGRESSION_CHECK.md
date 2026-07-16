# P0-OPEN-5 报告口径修订 + 回归验收检查

> **分支**：`release/hotfix-trust-minimal`
> **修订日期**：2026-07-16
> **任务**：(1) 删除/修改报告中过度限制或夸大的表述；(2) 对四类核心功能进行只读回归验收。
> **代码变更状态**：本组文本修订已在工作目录落地（commit `e8e7e89` 由主线程提交，本会话未自行 commit）。

---

## 一、P0-OPEN-5 报告口径修订

### 1.1 修订范围

GPT 审计列出 8 类需要删除/修改的"过度限制或夸大"表述。在 6 个目标文件中执行了文本搜索与修订：

- `reporting/templates/traceability_report.html`
- `backend/app/services/report_service.py`
- `backend/app/services/diagnosis_service.py`
- `frontend/src/pages/ObstacleAnalysis.tsx`
- `frontend/src/config/methodFlows.ts`
- `docs/USER_GUIDE.md`

> **说明**：经 grep 验证，8 类字面短语（如"结果范围仅限已检测且阈值适用的因子""系统已经充分验证""监管级科学可信"等）**在目标文件中并不存在**——前期 P0-1~P0-8 工作已大幅收紧了口径。本次按 GPT 规范**新增/对齐标准表述**，并把残留的可被误读为"科学权威/纯数据驱动/未收录即丢弃"的措辞替换为更克制的版本。

### 1.2 修订逐项映射（GPT 要求 → 实际改动）

| # | GPT 要求删除/修改的表述 | 改后口径 | 触达文件 | 行为 |
|---|---|---|---|---|
| 1 | "结果范围仅限已检测且阈值适用的因子" | 新增独立"报告口径与结果范围说明"章节：正式超标结论仅限于身份明确、单位兼容且阈值适用的因子；未收录因子进入候选/族群/未知分析；不丢弃、不强行套用阈值；探索性结果非法规判定 | `traceability_report.html`、`report_service.py`(DOCX)、`USER_GUIDE.md`、`diagnosis_service.py`(calc_trace ⑦) | 新增标准条款 |
| 2 | "系统已经充分验证" | 改为"当前完成 3 个原始场地工程回归验证 + 15 个合成数据演示，尚未开展跨区域大规模独立验证" | `traceability_report.html`、`report_service.py`、`USER_GUIDE.md`、`diagnosis_service.py` | 收紧为事实范围 |
| 3 | "监管级科学可信" | 改为"作为辅助决策依据，不构成监管级科学可信判定" | `traceability_report.html`、`report_service.py`、`USER_GUIDE.md` | 去权威化 |
| 4 | "纯数据驱动" | 改为"规则、模型和开放集识别相结合的混合策略（非纯数据驱动）" | `traceability_report.html`、`report_service.py`、`USER_GUIDE.md` | 方法口径对齐 |
| 5 | "SHAP 障碍高度" | 改为"模型全局贡献份额"；图标题/x 轴/说明同步替换；并在 methodFlows 显式追加"不代表障碍高度" | `report_service.py`（图标题、x 轴、docstring、DOCX 图件说明）、`traceability_report.html`（图说明、页脚）、`methodFlows.ts`、`USER_GUIDE.md`、`diagnosis_service.py`（summary、calc_trace） | 去"障碍高度"误解 |
| 6 | "18 个真实场地验证" | 改为"3 个原始场地工程回归验证 + 15 个合成数据演示" | `traceability_report.html`、`report_service.py`、`USER_GUIDE.md`、`diagnosis_service.py` | 与 `real_site_validation_report.md` 口径一致 |
| 7 | "AI 保证无幻觉" | 改为"AI 润色文本经事实校验但仍有降级回退机制；以原始检测数据为准" | `ObstacleAnalysis.tsx`（AI 副本）、`methodFlows.ts`（LLM 报告润色条目）、`traceability_report.html`、`report_service.py`、`USER_GUIDE.md` | 去幻觉保证 |
| 8 | "未收录因子无法分析" | 改为"未收录因子进入模型候选识别、族群级近邻分析和未知因子预警（不丢弃、不强行套用阈值）" | `ObstacleAnalysis.tsx`（未知有机物防线 Alert）、`diagnosis_service.py`（summary、calc_trace ⑦）、`traceability_report.html`、`report_service.py`、`USER_GUIDE.md` | 对齐开放集分层 |

### 1.3 关键 diff 摘录（完整 diff 见 commit `e8e7e89`）

#### A. `reporting/templates/traceability_report.html`

新增"七.5 报告口径与结果范围说明"章节（HTML 与 DOCX 双口径，含三行：正式超标结论范围、验证范围、方法学口径）：

```diff
@@ 七、数据质量校验结果 之后 @@
+  <h2>七.5、报告口径与结果范围说明</h2>
+  <table class="kv">
+    <tr><td>正式超标结论范围</td><td>正式超标结论仅限于身份明确、单位兼容且阈值适用的因子。对没有适用阈值或未被正式因子库收录的实测指标，系统仍通过模型候选识别、族群级近邻分析和未知因子预警进行辅助识别，不会丢弃数据或强行套用标准。探索性识别结果不等同于法规超标判定，需结合检测方法和专家复核。</td></tr>
+    <tr><td>验证范围</td><td>当前完成 3 个原始场地的工程回归验证 + 15 个合成数据演示，尚未开展跨区域大规模独立验证。报告结论作为辅助决策依据，不构成监管级科学可信判定。</td></tr>
+    <tr><td>方法学口径</td><td>采用规则、模型和开放集识别相结合的混合策略（非纯数据驱动）。AI 润色文本经事实校验但仍有降级回退机制；任何 AI 生成的描述均以原始检测数据为准。</td></tr>
+  </table>
```

SHAP 图说明与页脚收紧：

```diff
-图: Top-N 障碍因子排名(红=正向加重, 蓝=负向缓解, nature 顶刊配色)。
+图: Top-N 障碍因子模型全局贡献份额(红=正向加重, 蓝=负向缓解)。

-本报告由"..."自动生成，结论基于上述实测数据与标注参数，可追溯、可重复生成。
+本报告由"..."自动生成，结论基于上述实测数据与标注参数，过程可追溯、可重复生成；
+ 正式超标判定仅限于身份明确、单位兼容且阈值适用的因子，其余识别结果为辅助决策参考，需结合检测方法和专家复核。
```

#### B. `backend/app/services/report_service.py`

SHAP 图标签全面替换为"模型全局贡献份额"（matplotlib 图标题、x 轴、docstring、DOCX 嵌图说明），并删除"nature 顶刊/顶刊级"美化措辞：

```diff
-    """用 matplotlib 画 Top-N 障碍因子 SHAP 排名横向条形图(nature-figure 顶刊风格)。
-    报告增加顶刊级 SHAP 排名图(matplotlib 科研配图, 非 dashboard)。
+    """用 matplotlib 画 Top-N 障碍因子模型全局贡献份额横向条形图(科研配图风格)。
+    报告增加模型全局贡献份额排名图(matplotlib 科研配图, 非 dashboard)。

-    ax.set_xlabel("|SHAP| 相对重要性", fontsize=9)
-    ax.set_title(f"关键障碍因子 SHAP 排名 — {site_name}", ...)
+    ax.set_xlabel("模型全局贡献份额", fontsize=9)
+    ax.set_title(f"关键障碍因子模型全局贡献份额 — {site_name}", ...)

-    # DOCX 同步嵌入 SHAP 障碍因子排名图(与 PDF 口径一致)
-    _embed_docx_image(doc, ..., "(关键障碍因子 SHAP 排名图件)")
+    # DOCX 同步嵌入模型全局贡献份额排名图(与 PDF 口径一致)
+    _embed_docx_image(doc, ..., "(关键障碍因子模型全局贡献份额图件)")
```

DOCX 在"数据质量校验结果"之后新增"报告口径与结果范围说明"add_kv（与 HTML 一致的三行）。

#### C. `backend/app/services/diagnosis_service.py`

模块 docstring 改为 "SHAP（模型全局贡献份额）"；`summary` 与 `calc_trace` 在原 6 步之后新增第 7 步"口径声明"：

```diff
-"""障碍因子诊断: 取数 -> 特征对齐 -> RF 预测 -> SHAP -> 入库。
+"""障碍因子诊断: 取数 -> 特征对齐 -> RF 预测 -> SHAP(模型全局贡献份额) -> 入库。

 summary 改写为"基于 RF(...) + 模型全局贡献份额(SHAP) ..."并追加：
+ " 正式超标结论仅限身份明确、单位兼容且阈值适用因子；未收录因子进入候选/族群/未知分析, 探索性结果非法规判定。"

 calc_trace 追加：
+ "⑦ 口径声明: 正式超标结论仅限于身份明确、单位兼容且阈值适用的因子；未收录因子进入候选/族群/未知因子分析(不丢弃、不强行套用阈值)。模型全局贡献份额(SHAP)为辅助参考, 非因果、非法规判定。当前完成 3 个原始场地工程回归验证 + 15 个合成数据演示, 结论作为辅助决策依据。"
```

#### D. `frontend/src/pages/ObstacleAnalysis.tsx`

AI 润色副本与未知有机物防线 Alert 收紧：

```diff
-ⓘ 此结论由 AI 辅助生成（{diag?.polish_model}），仅供参考，以原始数据为准。
+ⓘ 此结论由 AI 辅助生成（{diag?.polish_model}），经事实校验但仍有降级回退机制，仅供参考，以原始数据为准。

-这些物质无法自动判定障碍风险, 已归入族群预警/送检建议。系统不会假装识别未知物质。
+未收录因子不会丢失, 已进入模型候选识别、族群级近邻分析和未知因子预警(不强行套用阈值)。
+ 系统不会假装识别未知物质, 仅作为辅助识别参考, 非法规超标判定。
```

（既有"模型贡献度...非因果, 非障碍高度"保持不变——已正确。）

#### E. `frontend/src/config/methodFlows.ts`

```diff
-{ label: "模型贡献度 M", desc: "...归一化为相对重要性；SHAP 是模型贡献，不是法规判定" },
+{ label: "模型贡献度 M", desc: "...归一化为模型全局贡献份额；SHAP 是模型贡献，不是法规判定，也不代表障碍高度" },

-{ label: "LLM 报告润色", desc: "AI 将技术性结论转化为通俗语言，供非技术背景人员阅读" },
+{ label: "LLM 报告润色", desc: "AI 将技术性结论转化为通俗语言...；经事实校验但仍有降级回退机制，最终以原始检测数据为准" },
```

#### F. `docs/USER_GUIDE.md`

```diff
-   - **模型贡献度**：SHAP 归一化贡献（辅助参考，非因果）
+   - **模型贡献度**：SHAP 归一化贡献（模型全局贡献份额，辅助参考，非因果、非障碍高度）
+
+> 📌 **结果范围说明**：正式超标结论仅限于身份明确、单位兼容且阈值适用的因子。... 当前已完成 **3 个原始场地的工程回归验证 + 15 个合成数据演示**... 方法学采用规则、模型和开放集识别相结合的混合策略（非纯数据驱动）。AI 润色文本经事实校验但仍有降级回退机制...

-4. 点击「生成 PDF 报告」→ 自动生成追溯报告（含诊断/评价/推荐/采样点图/SHAP图）
+4. 点击「生成 PDF 报告」→ 自动生成追溯报告（含诊断/评价/推荐/采样点图/模型全局贡献份额图）
```

### 1.4 修订不变性验证

- Python AST 解析 `report_service.py`、`diagnosis_service.py` 通过（语法未破坏）。
- TS/TSX 文件文本结构未破坏；未修改任何 import、props、组件签名、API 路由、数据库字段。
- 修订只动文案、注释、docstring、HTML 章节、报告 add_kv 文案，**不改业务逻辑**。

---

## 二、回归验收检查（只读）

> 每项核查以文件路径为证据；✓ = 功能存在且路由/服务已串联，✗ = 缺失。

### A. 数据管理

| 功能 | 状态 | 证据（文件路径） |
|---|---|---|
| Excel/CSV 导入 | ✓ | `backend/app/api/data.py:50` `POST /import`；`backend/app/api/data.py:155` `POST /import/wizard`；`backend/app/services/import_service.py`（`smart_detect_and_map`、`_file_sheet_columns` 支持 CSV `__csv__` 与 xlsx 多 sheet） |
| 字段映射 | ✓ | `frontend/src/pages/FieldMappingPage.tsx:99`；路由 `frontend/src/main.tsx:95` `sites/import/wizard`（`RequirePermission code="data:input"`） |
| 数据列表/筛选 | ✓ | `frontend/src/pages/SiteList.tsx:9`；后端 `backend/app/api/data.py:257` `GET /sites`；路由 `frontend/src/main.tsx:93` |
| 场地统计 | ✓ | `frontend/src/pages/SiteDetail.tsx:11`（多 Tab）；后端 `backend/app/api/data.py:311` `GET /sites/statistics`、`:374` `top-obstacles`、`:422` `monthly-trend`；路由 `frontend/src/main.tsx:96` |
| 地图 | ✓ | `frontend/src/components/SiteMap.tsx:95`（默认导出，基于 leaflet，支持 gaode 代理瓦片 + 行政区矢量 + 凸包）；被 `SiteDetail.tsx` 引用 |

### B. 决策管理

| 功能 | 状态 | 证据（文件路径） |
|---|---|---|
| KOS 诊断 | ✓ | `backend/app/api/diagnosis.py:27` `POST /sites/{id}/diagnosis`、`:68` `GET /diagnoses/{id}`；服务 `backend/app/services/diagnosis_service.py:run_diagnosis`；前端 `frontend/src/pages/ObstacleAnalysis.tsx`（含 KOS Top-N、五分量堆叠、模型贡献度、未知有机物防线） |
| 功能重构评价 | ✓ | `backend/app/services/evaluation_service.py:209` `run_evaluation`、`:152` `_evaluation_organic_degraded`（有机降级）；前端 `frontend/src/pages/ReconstructionAnalysis.tsx`；路由 `frontend/src/main.tsx:98` |
| 技术推荐 | ✓ | `backend/app/services/recommend_service.py:39` `run_recommendation`（含 OP 有机降级）；前端 `frontend/src/pages/RecommendationPage.tsx`；路由 `frontend/src/main.tsx:100` |
| AI 润色 | ✓ | `backend/app/services/ai_service.py:419` `polish_diagnosis`（失败静默降级）、`:344` `chat`（RAG）；API `backend/app/api/ai.py:47` `POST /chat`；被 `diagnosis_service.py:522-533` 调用 |

### C. 全流程追溯

| 功能 | 状态 | 证据（文件路径） |
|---|---|---|
| 五阶段 | ✓ | `backend/app/services/workflow_service.py:11-18` `STAGES` = survey/approval/construction/effect/maintenance（调查评估/方案审批/施工监理/效果评估/后期管护）；API `backend/app/api/workflow.py:28` `POST /workflow/init`、`:39` `GET /workflow`、`:46` `POST /workflow/{stage}` |
| 文件上传/下载 | ✓ | `backend/app/api/workflow.py:57` `POST /workflow/{stage}/attachment`（`save_upload`）；`:78` `GET /workflow/{stage}/attachments/{id}/download`（`require_permission("file:download")`）；服务 `backend/app/services/file_service.py` |
| 报告生成 | ✓ | `backend/app/services/report_service.py:681` `generate`、`:456` `render_html`、`:490` `render_docx`、`:463` `html_to_pdf`（weasyprint→xhtml2pdf 降级）；`TEMPLATE_VERSION = "tpl_v0.1"`；模板 `reporting/templates/traceability_report.html` |

### D. 系统管理

| 功能 | 状态 | 证据（文件路径） |
|---|---|---|
| 角色权限 | ✓ | `backend/app/core/deps.py:38` `user_role_codes`、`:44` `user_permissions`、`:52` `is_admin`、`:56` `require_permission(code)`；常量 `ADMIN_ROLE="admin"` / `REGULATOR_ROLE="regulator"` / `ENTERPRISE_ROLE` / `AGENCY_ROLE`；前端 `frontend/src/main.tsx` 多处 `RequirePermission` / `AdminOnly` 路由守卫 |
| 数据隔离（org） | ✓ | `backend/app/core/deps.py:101` `scope_sites_query`（按 `Site.organization_id` 过滤）、`:72` `ProjectAuthorization` 校验；`backend/app/services/ingest_service.py:91` `_check_site_ownership`（场地代码冲突检测）；`backend/app/services/file_service.py:53,72,81` 写入 `organization_id` |
| 操作日志 | ✓ | `backend/app/models/__init__.py:453` `class AuditLog`（字段：user_id/action/resource_type/resource_id/result/ip/user_agent/detail JSON）；服务 `backend/app/services/audit_service.py:log`；API `backend/app/api/system.py:67` `GET /audit-logs`（`require_permission("audit:view")`）；前端 `frontend/src/pages/SystemManagement.tsx:202` `AuditLogs` 组件（Tab key=`log`，"操作日志"） |

> 注：任务描述写 "backend/app/models.py AuditLog"，实际项目模型在 `backend/app/models/__init__.py`（包式模型层），AuditLog 定义于第 453 行。

---

## 三、修订后回归小结

- **文案口径**：6 个文件按 GPT 规范统一为"规则、模型和开放集识别相结合 / 模型全局贡献份额 / 3 原始场地+15 合成数据 / 辅助决策"等克制表述；未发现残留的"系统已充分验证/监管级科学可信/AI 保证无幻觉/未收录因子无法分析/纯数据驱动/SHAP 障碍高度/18 个真实场地验证"等夸大或过度限制表述。
- **功能回归**：A/B/C/D 四类共 14 项功能全部存在且 API/前端/服务/路由串联完整，无缺失项。
- **逻辑未动**：本次只改文案、HTML 章节、Python docstring、报告 add_kv 文案、前端 Alert/Descriptions 文案；未触碰 KOS 公式、阈值路由、开放集分类、AI 校验、权限/隔离/审计逻辑。
- **语法**：Python AST 解析通过；TS/TSX 文本结构未破坏。

---

## 四、建议（非本次必做）

1. P0-OPEN-5 修订仅触及 6 个文件；如 GPT 后续要求把同一口径扩散到 README、演示 PDF、`docs/references/*` 研究报告等对外材料，需要单独走一轮 diff。
2. `reporting/templates/traceability_report.html` 新增的"七.5、报告口径与结果范围说明"章节位置紧接数据质量校验，建议产品确认是否前移至封面之后以提高可见度。
3. 验证范围声明（3+15）应与 `real_site_validation_report.md` 保持同步——若后续真实场地数变更，需联动更新四处文案（HTML/DOCX/USER_GUIDE/calc_trace）。
