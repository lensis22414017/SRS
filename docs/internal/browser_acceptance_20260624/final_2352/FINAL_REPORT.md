# SRS 最终浏览器验收记录（2026-06-24 深夜轮）

验收人：项目组  
验收时间：2026-06-24 23:52 - 2026-06-25 00:01（CST）  
项目目录：`/Users/lensis/Claude/Projects/SRS`  
运行环境：Docker 后端 `http://127.0.0.1:8000`，前端 `http://127.0.0.1:5173`  
验收结论：**当前版本有明显进展，但不建议作为最终交付签收。**

## 1. 本轮验收产物

- 截图目录：`/Users/lensis/Claude/Projects/SRS/docs/audit/browser_acceptance_20260624/final_2352/screenshots`
- 下载报告目录：`/Users/lensis/Claude/Projects/SRS/docs/audit/browser_acceptance_20260624/final_2352/downloads`
- 验收前数据库备份：`/Users/lensis/Claude/Projects/SRS/docs/audit/browser_acceptance_20260624/final_2352/db_backups/srs_final_before_235227.dump`
- 最新 PDF 报告：`/Users/lensis/Claude/Projects/SRS/docs/audit/browser_acceptance_20260624/final_2352/downloads/site1_v10_final.pdf`
- 最新 DOCX 报告：`/Users/lensis/Claude/Projects/SRS/docs/audit/browser_acceptance_20260624/final_2352/downloads/site1_v11_final.docx`

注意：本轮验收执行了真实批量导入、附件上传、PDF/DOCX 生成，因此数据库在备份之后继续新增了测试数据与报告记录。

## 2. 构建与测试结果

| 检查项 | 命令/方式 | 结果 |
| --- | --- | --- |
| 前端构建 | `cd frontend && npm run build` | 通过；仍有 Vite 大 chunk 警告，主 bundle 约 2.6 MB |
| 后端测试 | `cd backend && .venv/bin/pytest -q` | **未通过**：78 passed, 2 failed, 2 skipped |
| 浏览器全链路 | Playwright 手工流程脚本 | 完成 44 张截图，未出现页面崩溃 |
| 报告下载 | API 下载 report_id=12/13 | PDF/DOCX 均可下载 |
| AI 配置测试 | `POST /api/v1/system/ai-config/test` | **失败**：HTTP 401 Unauthorized |

后端失败用例：

1. `tests/test_data_pipeline.py::test_api_batch_import_and_overview_badges`
   - 失败点：测试断言导入后至少一个场地 `n_exceed > 0`，当前测试数据/导入逻辑下不满足。
   - 风险：批量导入和首页统计之间仍存在测试口径不稳定问题。

2. `tests/test_workflow_report.py::test_report_html_renders`
   - 失败点：测试仍要求报告包含“操作日志摘要”。
   - 判断：这与项目组要求“报告中关于系统操作摘要可以不提”冲突，代码删除该章节是合理方向，但测试需要同步更新。

## 3. 浏览器覆盖范围与截图清单

本轮共 44 张截图，覆盖登录、首页、场地管理、导入、字段映射、地图、EDA、障碍因子、功能重构、SSUI、方案推荐、AI/RAG、全流程追溯、附件上传、报告生成与下载入口。

| 序号 | 截图 | 覆盖点 |
| --- | --- | --- |
| 00 | `00_login.png` | 登录页 |
| 01 | `01_dashboard.png` | 数据概览、污染类型分布、超标排名、场地分布地图 |
| 02 | `02_sites_list.png` | 场地列表 |
| 03 | `03_data_upload.png` | 数据导入页 |
| 04 | `04_field_mapping.png` | 字段映射 Wizard |
| 05 | `05_site_detail_composite.png` | 复合污染场地详情 |
| 06 | `06_site_detail_organic.png` | 有机场地详情 |
| 07 | `07_site_detail_liaoning_label_check.png` | 辽宁 HM+OP 命名/污染类型核验 |
| 08 | `08_obstacle_analysis_initial.png` | 障碍因子分析初始页 |
| 09 | `09_reconstruction_initial.png` | 功能重构初始页 |
| 10 | `10_ssui_initial.png` | SSUI 初始页 |
| 11 | `11_recommendation_initial.png` | 方案推荐初始页 |
| 12 | `12_trace_list.png` | 全流程追溯列表 |
| 13 | `13_trace_detail_site1.png` | 全流程追溯详情 |
| 14 | `14_system.png` | 系统管理 |
| 15 | `15_site1_map_initial.png` | 场地详情地图初始态 |
| 16 | `16_site1_map_imagery_toggle.png` | 影像底图切换 |
| 17 | `17_site1_map_vector_after_toggle.png` | 矢量图切回后状态 |
| 18 | `18_eda_统计体检.png` | EDA 统计体检 |
| 19 | `19_eda_直方图.png` | EDA 直方图 |
| 20 | `20_eda_箱线_小提琴.png` | EDA 箱线/小提琴 |
| 21 | `21_eda_散点图.png` | EDA 散点图 |
| 22 | `22_eda_相关热力图.png` | EDA 相关热力图 |
| 23 | `23_eda_Q-Q_图.png` | EDA Q-Q 图 |
| 24 | `24_eda_因子对比.png` | EDA 因子对比 |
| 25 | `25_eda_分组对比.png` | EDA 分组对比 |
| 26 | `26_eda_类别分布.png` | EDA 类别分布 |
| 27 | `27_batch_import_selected.png` | 批量导入选择文件 |
| 28 | `28_batch_import_result.png` | 批量导入结果 |
| 29 | `29_ai_drawer_initial.png` | AI 助手初始态 |
| 30 | `30_ai_drawer_response.png` | AI/RAG 响应 |
| 31 | `31_obstacle_run_site1.png` | 场地 1 障碍因子运行结果 |
| 32 | `32_reconstruction_run_site1.png` | 场地 1 功能重构运行结果 |
| 33 | `33_ssui_run_site1.png` | 场地 1 SSUI 运行结果 |
| 34 | `34_recommendation_run_site1.png` | 场地 1 方案推荐运行结果 |
| 35 | `35_ssui_op_site_selected.png` | OP 场地选择 |
| 36 | `36_ssui_op_site_run.png` | OP 场地 SSUI 运行结果 |
| 37 | `37_reconstruction_op_site_run.png` | OP 场地功能重构运行结果 |
| 38 | `38_trace_before_upload.png` | 追溯上传前 |
| 39 | `39_trace_upload_modal.png` | 追溯附件上传弹窗 |
| 40 | `40_trace_after_upload_netdisk.png` | 网盘/已上传文件库 |
| 41 | `41_trace_after_generate_pdf.png` | PDF 报告生成后 |
| 42 | `42_trace_after_generate_docx.png` | DOCX 报告生成后 |
| 43 | `43_trace_after_report_generation_reload.png` | 报告生成后刷新态 |

## 4. 已修复或明显改善的点

1. **场地地图功能基本可用。**
   - 场地 1 初始地图可显示采样区域、矢量边界和采样点。
   - 影像底图切换后再切回矢量图，未复现“刚加载能显示、后续失败”的问题。
   - Playwright 统计：场地 1 初始态约 62 个 Leaflet path、5 个 marker；切换后仍保持约 62 个 path、5 个 marker。

2. **首页不再只有一个重金属场地。**
   - 截图时首页显示 18 个场地、10 个省份、1,920 个采样点、1,216 条超标记录。
   - 本轮最后又批量导入 2 个场地，数据库实际已达到 20 个场地。
   - 数据库污染类型分布：`composite=7`、`heavy_metal=7`、`organic=6`。

3. **批量导入基本可用。**
   - 本轮导入 `site_山东_OP_92点.xlsx` 与 `site_湖南_HM_200点.xlsx`，界面显示 2/2 成功。
   - 导入后数据库新增 site_id 19、20。

4. **全流程追溯补上附件上传、下载与网盘列表。**
   - 调查评估阶段可上传附件。
   - 页面显示“网盘 · 已上传文件库”，并提供下载按钮。
   - 报告生成列表能显示 PDF/DOCX 版本。

5. **PDF 报告质量有明显提升。**
   - 最新 PDF 为 v10，共 6 页。
   - `pdfimages -list` 显示 2 张主图：地图/采样点空间分布图、SHAP 障碍因子图。
   - `pdftotext` 确认 PDF 包含“地图图件与采样点空间分布”“关键障碍因子识别（RF + SHAP）”“功能重构可行性评价”“SSUI”“五阶段全流程追溯记录”“附件清单”等内容。
   - PDF 不再包含“系统操作摘要”或“操作日志摘要”，符合项目组要求。

## 5. 仍未通过/不建议签收的问题

### P0-1 后端测试仍失败，不能算工程闭环

后端测试还有 2 个失败。即使其中一个是测试未同步需求，也必须在交付前处理，否则 CI/回归验收口径不可信。

整改要求：

- 更新报告测试：不再强制要求“操作日志摘要”，改为检查地图、采样点、SHAP、功能重构、SSUI、附件清单。
- 修复或重构批量导入统计测试：明确导入数据、标准阈值、超标统计的预期关系。

### P0-2 AI 真实调用仍不可用，只是 RAG 降级可用

接口结果：

- `/api/v1/ai/status` 显示 `configured=true`。
- `/api/v1/system/ai-config/test` 返回 `HTTP 401: Unauthorized`。
- AI 聊天返回“AI 调用失败(HTTP 401: Unauthorized)。以下为知识库检索结果供参考...”

判断：

- RAG fallback 可用，但真实 LLM 没接通。
- 当前配置为 OpenAI base_url + `Qwen3.5-9B-MLX-4bit`，模型/端点/key 组合明显不一致。

整改要求：

- 管理页必须允许切换并保存智谱/DeepSeek/DashScope/SiliconFlow/Ollama 等兼容配置。
- 配置测试通过前，不应在状态里只显示“configured=true”造成误导；应区分“已填写配置”和“连通性已验证”。

### P0-3 OP 有机场地的 SSUI 与功能重构仍是 null

场地 2：`site_北京_OP_200点`，污染类型为 `organic`。浏览器和接口一致显示：

- SSUI：`score=null`，等级“无足够指标”，说明“C1 限制因子无可用元指标”。
- 功能重构：生产/生态均 `score=null`，说明“无可评价指标”。
- 方案推荐：`GET /api/v1/sites/2/recommendation` 返回 404。

判断：

- 系统对复合污染/重金属场地已有闭环，但对纯有机场地评价体系仍断裂。
- 若甲方目标是“诊断所有污染类型场地”，这里不能靠空结果交付。

整改要求：

- 对有机场地建立可解释的 OP 评价口径：至少给出有机污染风险、空间分布、超标/检出、处置适配、数据缺口说明。
- 若确实缺少 SSUI 所需农业/生态元指标，前端要给“数据源缺项方案”，不能只显示 null/NaN。

### P1-1 DOCX 报告没有同步 SHAP 图和数据分析图

文件检查：

- 最新 DOCX：v11，`media_count=1`。
- 文档 XML 包含“地图”“采样点”“全流程”“附件”“SSUI”“功能重构”。
- 文档 XML 不包含 `SHAP`，也不包含“数据分析”。

判断：

- PDF 已经补上 SHAP 图，但 DOCX 未同步。
- 甲方通常会用 DOCX 流转审批，DOCX 不能比 PDF 少关键图件。

整改要求：

- DOCX 至少同步嵌入地图图件、SHAP 排名图、1-5 张 EDA/分析图。
- DOCX 与 PDF 章节口径应一致。

### P1-2 EDA 分组对比仍是空图

截图 `25_eda_分组对比.png` 显示：

- 分组维度为“按区域”，因子为 `pH(化学性质)`。
- 页面显示“暂无数据”。

判断：

- EDA 功能整体比上一轮完整，但不是所有页签都真正可用。
- 如果区域字段缺失，应自动降级为“按深度/污染等级/采样点簇/超标等级”分组，而不是空图。

整改要求：

- 分组变量为空时，前端必须提示原因并给可用维度。
- 后端 EDA metadata 应返回每个图可用/不可用原因。

### P1-3 批量导入会重复造场地，缺少去重/覆盖策略

数据库中同一来源文件已经出现多个重复场地，例如：

- `site_辽宁_HM+OP_16点` 出现 site_id 16 和 18。
- `site_海南_HM+OP_58点` 出现 site_id 14 和 17。
- `site_山东_OP_92点` 出现 site_id 4 和 19。
- `site_湖南_HM_200点` 出现 site_id 15 和 20。

判断：

- 批量导入“能成功”，但缺少业务级幂等策略。
- 多次验收/多次导入后，首页统计会被重复数据污染。

整改要求：

- 以 `site_code`、文件内容 hash、场地名+省份+采样点坐标摘要建立导入幂等判断。
- UI 提供“跳过/覆盖/作为新版本导入”三种选择。
- 首页统计应默认按最新版本或有效场地统计，避免重复导入污染管理视图。

### P1-4 辽宁 HM+OP 命名场地被识别为 heavy_metal，需明确是数据源问题还是识别问题

场地：

- site_id 16 / 18 名称：`site_辽宁_HM+OP_16点`
- 系统污染类型：`heavy_metal`
- 检测因子数：3

判断：

- 初步看更像数据源命名和实际因子不一致：该场地仅有 pH、有机质、镍等少量指标，没有有机污染物支撑“OP”。
- 但系统必须把这种情况标为“命名/数据内容冲突”，而不是静默显示 heavy_metal。

整改要求：

- 导入时输出污染类型识别证据：来自文件名、字段、因子类别、实测因子数量。
- 当文件名 HM+OP 但实测无 OP 因子时，给出“需人工确认”的数据质量警告。

### P1-5 首页图表仍偏管理可用，未达到“政府机关软件 + 好看图件”的目标

首页可读性已改善，但仍存在：

- 污染类型分布是普通环图，视觉质量一般。
- 污染类型分布图三类颜色不应使用同色系，应与场地详情统一：重金属=红色，有机=紫色，复合污染=橙色。
- 各场地超标记录排行 x 轴标签截断严重。
- 各场地超标记录排行的横轴/标签应使用短标签：单个省份场地显示“北京场地”“新疆场地”等；同省多个场地显示“北京1”“北京2”或“北京场地1”“北京场地2”，不显示长文件名。
- 地图有采样区域框线，但标签和点位视觉仍偏粗糙。

整改要求：

- 首页保留政务风格：克制、稳定、密度适中。
- 图表可参考用户目录中的 ipynb/可视化案例，但不能牺牲真实性。
- 超标排名建议改横向条形图或雨云图/分布图，保证场地名可读。
- 污染类型颜色必须全系统一致，不能在首页和场地详情各用一套语义颜色。

### P1-5b 场地详情地图与全国总览地图边界混淆（用户复测反馈）

项目组新增反馈：

- 点击具体场地详情后，弹出的地图像是全国采样点/全国边界数据。
- 场地详情地图不能与系统首页“全部场地地图”混为一谈。

判断：

- 首页地图应展示全部场地分布。
- 场地详情地图只应展示该场地采样点、该场地采样区域/外包边界、该场地相关污染物分级。
- 如果详情页仍加载全国场地集合或全国采样点集合，属于数据作用域错误。

整改要求：

- 明确拆分接口语义：`overview map` 只服务首页，`site detail map` 只服务单场地。
- 场地详情页请求必须携带并只使用 `site_id`。
- 后端返回图层应校验所有采样点都属于当前 `site_id`，测试中断言不会混入其他场地点位。
- 浏览器验收必须截图：首页全国地图、场地 1 详情地图、场地 2 详情地图，并说明各自点位数量。

### P1-5c EDA 中“云雨图”与直方图区分错误，且仍有文字不显示（用户复测反馈）

项目组新增反馈：

- EDA 中标称“云雨图”的图实际仍是直方图。
- 部分图中文字仍显示不出来。

判断：

- 云雨图/raincloud plot 至少应包含分布云（density/half violin）、雨点（jittered points）和箱线/摘要三类元素之一或组合，不能只是频数直方图。
- 中文坐标轴、图例、标题、tooltip、导出图中的文字必须可读。

整改要求：

- 若实现云雨图，必须命名为“云雨图”，并使用真实 raincloud 结构。
- 若仅实现直方图，不得命名为云雨图。
- 前端图表字体需统一设置中文字体 fallback，导出图/PDF/DOCX 也要检查中文不乱码、不缺字。
- 验收截图必须同时包含直方图和云雨图，肉眼能区分两者。

### P1-5d 全流程追溯上传文件仍需复测并修到真实可用（用户复测反馈）

项目组新增反馈：

- 全流程追溯中，上传文件功能仍然实现不了。

判断：

- 项目组昨晚只验证到“页面可弹窗、上传后网盘列表出现记录、下载按钮存在”；但用户复测认为业务上传仍不可用，说明还需要按真实用户路径复测。
- 可能问题包括：按钮不可触发、上传后不保存、刷新丢失、下载失败、权限错误、阶段不匹配、文件类型/中文文件名失败、审批盖章后的二次上传缺失。

整改要求：

- 对五个阶段逐一验证上传：调查评估、方案审批、施工监理、效果评估、后期管护。
- 支持常见文件：PDF、DOCX、XLSX、PNG/JPG、Markdown/文本；支持中文文件名。
- 上传后必须刷新仍存在，下载内容与原文件一致。
- 文件必须绑定正确 `site_id + stage + file_role + operator + timestamp`。
- “监理上传报告 -> 甲方审批 -> 盖章后再上传”的业务路径必须能走通，至少以状态和文件角色体现。

### P1-6 控制台仍有 Ant Design message context 警告

浏览器控制台多次出现：

`Warning: [antd: message] Static function can not consume context like dynamic theme. Please use 'App' component instead.`

判断：

- 不导致主流程崩溃，但属于前端工程质量问题。
- 主题上下文、通知提示、暗色/政务主题后续可能受影响。

整改要求：

- 全局使用 AntD `App` provider 和 `messageApi`。
- 避免在组件外或静态函数里直接调用 `message`。

### P2-1 前端 bundle 偏大

Vite build 通过，但主 JS chunk 约 2.6 MB。

整改要求：

- 对 ECharts、地图、KaTeX、AI Drawer 等做懒加载。
- 路由级 code splitting。
- 地图瓦片/边界数据分层缓存。

## 6. 对“项目组提出的 11 点”的逐条核验

| 用户问题 | 当前核验结论 |
| --- | --- |
| 1. 矢量图采样区域加载后失败 | 场地 1 未复现；初始、影像切换、矢量切回均可显示 |
| 2. 复合污染却只显示重金属 | site 1/3/5 等 composite 正常；辽宁 HM+OP 显示 heavy_metal，疑似数据源命名与实测因子冲突，仍需显式告警 |
| 3. 场地批量导入和管理 | 已测，可导入；但重复导入会重复造场地 |
| 4. 数据概览地图及可视化 | 地图可用；图表仍一般，超标排行标签截断 |
| 5. EDA 图 | 多数页签可用；分组对比仍空，整体美观度仍需提升 |
| 6. 障碍因子图顶刊风格颜色 | PDF SHAP 图已使用红/蓝说明；前端障碍因子图仍需继续统一风格 |
| 7. 功能重构可行性评价 | 场地 1 可用；OP 场地为 null/无足够指标 |
| 8. AI/RAG/API 切换 | RAG 降级可用；真实 AI API 401，不通过 |
| 9. 多场地稳定性 | 已导入到 20 个场地，列表/首页可显示；重复导入和 OP 评价断裂仍是风险 |
| 10. UI 政府机关风格 | 有改善，但首页、EDA、报告页仍可继续打磨 |
| 11. context7/最新稳定代码 | 本轮未见可证明的 Context7 检索证据；应要求 CC/GLM 提供依赖升级依据和回归测试证据 |

## 7. 数据源问题时的处理方案

如果某些场地本身数据源就不完整或命名错误，系统不应硬算，也不应静默给 null。建议建立“数据源质量闸门”：

1. 导入阶段生成 `DataQualityReport`
   - 文件名推断污染类型。
   - 实测因子推断污染类型。
   - 阈值库可匹配因子数。
   - 可用于 SSUI/功能重构/推荐的指标覆盖率。
   - 缺失关键指标清单。

2. 场地状态分为四类
   - `ready`：可完整分析。
   - `partial`：可部分分析，报告中必须显示限制条件。
   - `needs_review`：文件名/因子/阈值冲突，需人工确认。
   - `blocked`：缺少坐标或核心检测值，不能生成正式报告。

3. 分析功能按状态降级
   - OP 场地缺 SSUI 指标时，显示“有机污染诊断可用，SSUI 缺农业/生态元指标，不生成 SSUI 分数”。
   - 报告中写清“不可评价原因”和“补充数据清单”。
   - 首页统计默认排除 blocked 数据，partial 单独标记。

## 8. 建议给 CC/GLM 的下一轮整改优先级

1. 先修后端测试，保证 `pytest -q` 通过。
2. 修 AI 配置状态：区分“已配置”和“已连通”，修复 OpenAI/Qwen 模型不匹配。
3. 补 OP 场地评价闭环，至少不能出现 null/NaN 裸露。
4. 给批量导入加去重/版本策略。
5. DOCX 同步 PDF 的 SHAP 与 EDA 图。
6. EDA 分组对比做自动可用维度降级。
7. 首页图表改横向排行/雨云图/更稳的政务风格图件。
8. 清理 AntD message warning 和前端 chunk 过大问题。

## 9. 最终判断

这轮整改已经把“地图、批量导入、追溯上传、PDF 报告、首页多场地”推进到了可演示状态；但 **AI 未通、OP 场地评价断裂、后端测试失败、DOCX 报告不同步、批量导入重复造场地** 仍是不能签收的硬问题。

建议下一轮以“测试全绿 + OP 场地闭环 + AI 连通性验证 + 报告双格式一致”为交付门槛。
