# SRS 浏览器预验收记录（2026-06-24 夜间）

> 状态：预验收基线，不是最终验收。  
> 原因：验收过程中仍观察到 `claude --dangerously-skip-permissions /Users/lensis/Claude/Projects/SRS` 进程活跃，且 `backend/app/services/report_service.py`、`frontend/src/pages/TraceDetail.tsx` 等文件在 23:41-23:45 继续落盘。最终验收需要在 CC/GLM 停手、Docker 后端重建后再跑一遍。

## 一、运行环境

- 前端：本地 Vite，`http://localhost:5173`。
- 后端：Docker `deploy-backend-1`，`http://127.0.0.1:8000`，`/health` 正常。
- 数据库：Docker PostgreSQL `deploy-db-1`。
- 注意：Docker 后端不是源码挂载，而是镜像运行；本地源码的最新修改不一定已经进入当前浏览器验收环境。

## 二、已保存证据

- 截图目录：`docs/audit/browser_acceptance_20260624/screenshots/`
- 下载验证目录：`docs/audit/browser_acceptance_20260624/downloads/`
- 数据库备份目录：`docs/audit/browser_acceptance_20260624/db_backups/`

### 截图清单

- `00_login.png` 登录页
- `01_dashboard.png` 数据概览首页
- `02_sites_list.png` 场地管理列表
- `03_data_upload.png` 数据导入页
- `04_field_mapping.png` 字段映射 Wizard
- `05_site_detail_composite.png` 复合污染场地详情
- `06_site_detail_organic.png` 有机场地详情
- `07_site_detail_liaoning_label_check.png` 辽宁 HM+OP 场地污染类型核查
- `08_obstacle_analysis.png` 障碍因子分析页
- `09_reconstruction.png` 功能重构页初始态
- `10_ssui.png` SSUI 页初始态
- `11_recommendation.png` 推荐页
- `12_trace_list.png` 全流程追溯列表
- `13_trace_detail_site1.png` 追溯详情
- `14_system.png` 系统管理
- `15_site1_map_initial.png` 场地详情地图初始态
- `16_site1_map_imagery_toggle.png` 切换影像底图
- `17_site1_map_vector_after_toggle.png` 切回矢量底图
- `18_eda_统计体检.png` EDA 统计体检
- `19_eda_直方图.png` EDA 直方图
- `20_eda_箱线_小提琴.png` EDA 箱线/小提琴
- `21_eda_散点图.png` EDA 散点图
- `22_eda_相关热力图.png` EDA 相关热力图
- `23_eda_Q-Q_图.png` EDA Q-Q 图
- `24_eda_因子对比.png` EDA 因子对比
- `25_eda_分组对比.png` EDA 分组对比
- `26_eda_类别分布.png` EDA 类别分布
- `27_batch_import_selected.png` 批量导入已选文件
- `28_batch_import_result.png` 批量导入结果
- `29_ai_drawer_initial.png` AI 抽屉初始态
- `30_ai_drawer_response.png` AI/RAG 回答结果
- `31_obstacle_run_site1.png` 障碍因子点击运行后
- `32_reconstruction_run_site1.png` 功能重构点击运行后
- `33_ssui_run_site1.png` SSUI 点击运行后
- `34_recommendation_run_site1.png` 推荐点击运行后
- `35_ssui_op_site_selected.png` 选择 OP 场地
- `36_ssui_op_site_run.png` OP 场地 SSUI 运行后
- `37_reconstruction_op_site_run.png` OP 场地功能重构运行后
- `38_trace_before_upload.png` 追溯上传前
- `39_trace_upload_modal.png` 上传材料弹窗
- `40_trace_after_upload_netdisk.png` 上传后网盘区
- `41_trace_after_generate_pdf.png` 生成 PDF 后
- `42_trace_after_generate_docx.png` 浏览器点击 DOCX 后
- `43_trace_after_docx_api_generation.png` API 生成 DOCX 后刷新列表

### 下载物

- `downloads/report_site1_v7.pdf`：PDF 追溯报告，564K，`file` 识别为 PDF 1.7。
- `downloads/report_site1_v8.docx`：DOCX 追溯报告，71K，`file` 识别为 Microsoft OOXML。
- `downloads/workflow_attachment_survey_1.md`：追溯阶段附件下载验证文件。

## 三、通过项

1. 登录可用，首页、场地列表、导入、字段映射、详情、地图、EDA、障碍因子、重构、SSUI、推荐、追溯、系统管理均能打开并截图。
2. 当前库中已有多场地：导入前 16 个场地，覆盖 heavy_metal、organic、composite；批量导入后 18 个场地。
3. 数据概览页覆盖省份显示为 10 个，不再是 0。
4. site1 场地地图初始显示正常；影像切换后再切回矢量，DOM 仍有 62 个 Leaflet path、5 个 marker，未复现“矢量图切换后采样区完全消失”。
5. EDA 大部分子图均有 canvas 输出：直方图、箱线/小提琴、散点、热力图、Q-Q、因子对比、类别分布均能显示。
6. 批量导入前端流程可走通，2 个文件均返回成功并入库。
7. 功能重构、SSUI、推荐、障碍因子按钮均已实际点击运行，site1 能显示本次运行结果。
8. 追溯阶段附件上传可用，上传后“网盘 · 已上传文件库”出现附件，并可下载。
9. PDF 报告、DOCX 报告均可由后端生成并下载；PDF 文本包含地图、采样点、SHAP、功能重构、SSUI、附件等章节。
10. 前端 `npm run build` 通过。

## 四、发现的问题

### P0 / 必须回头修

1. **OP 场地 SSUI 仍未闭环**  
   北京 OP 场地点运行 SSUI 后，结果仍为 `null / 无足够指标`，截图见 `36_ssui_op_site_run.png`。

2. **OP 场地功能重构仍未闭环**  
   北京 OP 场地点运行功能重构后，生产/生态两条均为 `null分 / 无足够指标`，截图见 `37_reconstruction_op_site_run.png`。

3. **AI 状态显示已配置，但真实模型调用失败**  
   `/ai/status` 显示 configured=true；`/ai/chat` 实测返回模型调用 `401 Unauthorized`，仅 RAG 降级可用。截图见 `30_ai_drawer_response.png`。

4. **批量导入幂等/去重不稳**  
   再次导入已有测试文件后新增 #17/#18，同名场地重复进入列表。site_code 规范化也不一致，例如已有 `AUTO-site_海南_HM+OP_58点`，新导入为 `AUTO-site海南HMOP58点`。

5. **批量导入结果把带校验错误的数据仍标为成功**  
   `28_batch_import_result.png` 中海南文件显示校验错误 58、辽宁文件显示校验错误 16，但总结果仍为成功 2/2。需要明确“成功入库”和“质量通过”的语义边界。

6. **运行态报告缺少 EDA/SHAP 图片嵌入**  
   已下载 PDF 只有 1 张图片，DOCX 也只有 `word/media/image1.png`。PDF 文本有 SHAP 表述，但未见 EDA/SHAP 图像嵌入。  
   注：本地源码随后已新增 SHAP 图生成逻辑，但 Docker 后端尚未重建，需重建后复测。

7. **后端测试未全绿**  
   `cd backend && .venv/bin/pytest -q` 结果：`78 passed, 2 failed, 2 skipped`。失败项：
   - `tests/test_data_pipeline.py::test_api_batch_import_and_overview_badges`
   - `tests/test_workflow_report.py::test_report_html_renders`

8. **运行镜像与本地源码可能不同步**  
   当前 Docker image 创建于约 3 小时前；验收过程中本地 `report_service.py` 又新增 SHAP 图逻辑。最终验收必须先重建/重启 Docker 后端。

### P1 / 需要产品与数据口径确认

1. **辽宁 HM+OP 场地显示 heavy_metal 不能简单判为代码 bug**  
   该场地名称为 `site_辽宁_HM+OP_16点`，但实际检测因子只有 pH、有机质、镍，没有有机污染物检测项。因此更像“测试数据命名/数据源内容不一致”。建议数据源增加显式 `pollution_type_declared` 字段，并让系统同时展示“声明类型”和“检测因子推断类型”。

2. **EDA 分组对比在 site1 显示暂无数据**  
   `25_eda_分组对比.png` 显示暂无数据。需要判断是该场地缺少 region/depth 分组信息，还是 EDA grouped API 没按当前数据返回。

3. **障碍因子页进入即显示结果，未区分历史/本次**  
   SSUI 和功能重构已有“历史结果”和“本次运行”分离；障碍因子页进入时直接显示结果。若甲方要求所有分析页都必须点击后才显示，应同步改造。

4. **报告测试与新需求冲突**  
   甲方要求报告里“系统操作摘要可以不提”，但后端旧测试仍要求章节“操作日志摘要”存在，导致测试失败。需要更新测试，改为验证“附件/审批/版本/人工复核”等监管需要的内容。

5. **前端构建存在大包告警**  
   `npm run build` 通过，但主 JS chunk 约 2.6MB，Vite 提示超过 500KB。后续可做代码分割，不影响当前功能验收。

## 五、命令结果

```bash
cd frontend && npm run build
# 通过；Vite 大 chunk warning。
```

```bash
cd backend && .venv/bin/pytest -q
# 78 passed, 2 failed, 2 skipped, 6 warnings
```

PDF/DOCX 验证：

```bash
pdfinfo downloads/report_site1_v7.pdf
# Pages: 6; PDF version: 1.7

pdfimages -list downloads/report_site1_v7.pdf
# 1 image on page 2
```

DOCX 验证：

```text
media_count 1
word/media/image1.png
地图 True
采样点 True
SHAP False
系统操作摘要 False
全流程 True
附件 True
SSUI True
功能重构 True
数据分析 False
```

## 六、明早最终验收建议

1. 等 CC/GLM 明确停手后，先重建 Docker 后端：`cd deploy && docker compose up -d --build backend`。
2. 刷新 Vite 或重启前端，确保当前源码进入浏览器。
3. 重新跑完整浏览器截图，覆盖本目录所有页面。
4. 重新生成 PDF/DOCX，重点确认 SHAP 图和 1-5 张 EDA/分析图是否真实嵌入。
5. 重新跑：
   - `cd backend && .venv/bin/pytest -q`
   - `cd frontend && npm run build`
6. 若仍存在 OP-SSUI/OP-重构 null、AI 401、批量导入重复、校验错误仍标成功，则不能进入最终交付。
