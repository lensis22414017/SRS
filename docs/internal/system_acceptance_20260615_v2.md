# SRS 系统级验收测试记录 v2（2026-06-15）

> 本轮在 代码工具 v1（`system_acceptance_20260615.md`）主干闭环基础上，**补齐项目组指出的体验级/可用性缺口**，并完成系统级复验。
> 遵循 RIPER-5；优先级：甲方需求闭环 > 数据真实性 > 可解释性 > 可验收 > UI > 工程优雅。

## 结论摘要

- **6 个缺口全部补齐并验收**：EDA 科研级可视化、批量导入+场地概览、阶段附件下载、报告地图图件、打包首启自检、RAG 同义词容错。
- **后端测试**：`68 passed, 2 skipped, 7 warnings`（比 v1 的 47 passed 多 21 个新测试，全部通过）。
- **极端 10 场地闭环**：`n_cases=10, keyword_hit_accuracy=1.0, avg_quality_score=100.0`，8 项 closed_loop 全 true。
- **数据闭环**：split 无 DOI/Source 泄漏，`all_passed=True`；synthetic 未混入 real。
- **报告**：PDF（`%PDF-1.4`，含 2 个 Image 对象）+ DOCX（含 `word/media/image1.png` 52KB）**均嵌入 matplotlib 采样点静态图件**。
- **API 复验**：EDA 新字段（boxplot/distribution/qq/correlation）、批量导入（2/2 成功）、附件下载（正常 200 + 越权 404/401）、报告生成下载全通过。
- **打包自检**：端口空闲→✅ 全绿；端口被占→❌ 阻断提示正确。
- **如实标注**：RAG 实质为关键词检索（无向量库）；模型 AUC≈1.0 为阈值派生虚高风险；地图服务底图仍受 key 白名单限制；`.app/.pkg` 仍未达正式安装包标准。

---

## 一、本轮补齐的 6 个缺口

### 缺口 1｜EDA 科研级可视化（最重）

**问题**：v1 前端 EDA 只有"统计体检表 + 单因子直方图"，无箱线/小提琴/散点/热力/QQ/柱状图。

**改动**：
- `ml/eda/profile.py`：新增 `boxplot_summary`（五数+须线+离群点，采样上限 200）、`distribution_sample`（原始分布等距采样 ≤2000）、`correlation_matrix`（Pearson 矩阵，自动剔除常数列）、`grouped_stats`（按区域/深度/因子分层）；复用已有 `qq_points`。
- `backend/app/api/data.py:175`：`/sites/{site_id}/eda` 加 query 参数 `include`（逗号分隔按需返回）、`group_by`（region/depth/factor）、`factor`（单因子）、`max_points`（采样上限）。默认全返回，兼容旧前端。
- `frontend/src/components/EdaPanel.tsx`：重构为 8 个 Tab——统计体检 / 直方图 / **箱线+小提琴**（boxplot + KDE 多边形）/ **散点图**（双因子分位点对照+线性拟合 r）/ **相关热力图** / **Q-Q 图** / **因子对比柱状图**（均值+CV 双 Y 轴）/ **分组对比**（按区域/深度/因子）+ 筛选控件。
- `backend/tests/test_eda.py`（新增）：7 个纯算法测试（五数单调、采样上限、相关对称/对角/常数列剔除、分组排序）+ 6 个 API 测试。

**验收**：
- 沙箱纯算法测试 `7 passed`。
- API 复验（个旧 14 因子）：boxplot q1=4.9、distribution n_total=134、qq 134 点、correlation 14×14 labels；`include=boxplot` 精简模式正确排除其余字段。
- 前端 build 通过；产物含 `boxplot(11)/heatmap(6)/Q-Q(3)/小提琴(3)/相关系数(2)` 关键逻辑。

### 缺口 2｜批量导入 + 场地概览徽章

**问题**：v1 前端仅单文件上传、单模板；首页无因子/超标/质量概览。

**改动**：
- `backend/app/api/data.py`：新增 `POST /api/v1/import/batch`，多文件共用 mapping_id，**串行跑 pipeline 避免写库竞态**，单文件失败不阻断其余，返回 `{total, succeeded, failed, results[]}`。
- `list_sites` 补 `n_factors`/`n_exceed`/`data_quality` 三字段（批量查询避免 N+1）。
- `frontend/src/pages/DataUpload.tsx`：`Upload.Dragger` 改 `multiple`，逐文件校验结果表（文件/状态/场地/采样点/超标因子 Tag/错误信息）。
- `frontend/src/pages/SiteList.tsx`：表格补"因子数/超标/数据质量"三列。
- `backend/tests/test_data_pipeline.py`：新增批量导入+概览徽章测试。

**验收**：
- API：同文件 2 份 → `total=2, succeeded=2, failed=0`，每文件 134 点、536 超标项。
- 场地概览：`n_points=134, n_factors=14, n_exceed=4512, data_quality=大量超标`。

### 缺口 3｜阶段附件下载端点

**问题**：v1 五阶段可上传附件但**无独立下载端点**，只能下报告。

**改动**：
- `backend/app/api/workflow.py`：新增 `GET /sites/{site_id}/workflow/{stage}/attachments/{attachment_id}/download`，三层校验（site 归属 + attachment→workflow_record→site_id+stage 反向匹配）防越权。
- `frontend/src/pages/TraceDetail.tsx`：附件 Tag 内嵌"下载"按钮。
- `backend/tests/test_workflow_report.py`：新增下载+越权测试（错误 stage 404、不存在 site 404、无 token 401）。

**验收**：
- 正常下载 HTTP 200，内容与上传一致（37 bytes）。
- 越权：错误 stage 404、不存在 site 404、无 token 401——全部正确。

### 缺口 4｜报告地图图件（matplotlib 静态图替代文字）

**问题**：v1 报告第五章"地图图件"只是文字描述，无真图；底图失败时报告内无空间可视化。

**改动**（方案：用 matplotlib 离线画采样点散点，**不依赖地图服务 key**，符合"数据真实性 > UI"）：
- `backend/app/services/report_service.py`：新增 `_render_points_map_png`（按超标倍数着色：未超标灰/1-2倍橙/2-5倍红/>5倍深红，自适应坐标+图例）；中文字体检测，缺失自动降级英文标题（避免方块）；`docx_emu_width` 辅助 DOCX 图片自适应页宽。
- `collect`：计算每个采样点最大超标倍数（value/threshold_max），生成 map_image 注入 `map_summary.map_image`。
- `reporting/templates/traceability_report.html`：第五章嵌 `<img src="data:image/png;base64,...">`，matplotlib 不可用时回退文字。
- `render_docx`：DOCX 也嵌入图片（`word/media/image1.png`）。
- `requirements.txt`：新增 `matplotlib>=3.8`（Docker 镜像同步）。

**验收**：
- HTML：`map_image 非空=True`，base64 长度 69958；含 1 个 base64 img 标签。
- PDF：HTTP 200, 91KB, `%PDF-1.4`，内含 **2 个 Image 对象**。
- DOCX：HTTP 200, 91KB，内含 `word/media/image1.png`（52450 字节）。

### 缺口 5｜打包首启自检 + 友好提示

**问题**：v1 launcher 只起服务+托盘，无环境自检；端口/DB/key 异常时无清晰提示。

**改动**（`packaging/launcher.py`）：
- 新增 `run_preflight`：检测端口占用 / SQLite 目录可写 / Redis 可达性 / AI key 配置态 / 地图服务 key 配置态。**只读探测，不改任何配置**。
- `_preflight_summary`：渲染为可读文本（✅/⚠️/❌ 图标）。
- `main`：启动前跑自检并打印摘要；有阻断项时弹原生提示框（macOS rumps/tkinter）。
- 托盘新增"环境自检"菜单项（可随时重看，重新跑实时自检）。
- **不动 onefile/onedir 重构**（项目组选"后续"）。

**验收**：
- 场景 1（端口 18099 空闲）：端口✅、数据库✅、Redis✅、AI key✅（脱敏 `sk-akl***oaod`）、地图服务⚠️→"0 阻断 1 警告，可正常启动"。
- 场景 2（端口 8002 被占）：端口❌→"1 阻断...请关闭占用程序或用 --port 指定"，正确提示。

### 缺口 6｜RAG 同义词容错

**问题**：v1 `_FACTOR_ALIASES` 只在技术库匹配用，因子/阈值 SQL 检索未享受同义词扩展（查"Pb"可能漏命中"铅"）。

**改动**（`backend/app/services/ai_service.py`）：
- `retrieve`：因子字典 + 阈值规则查询改用 `_expand_terms` 扩展后的词（中英符号互查），三类检索统一受益。
- 扩充 `_FACTOR_ALIASES`：11→20 个金属（钒钴铍锑锰钼铊等）+ 符号反查中文（As→砷）+ 有机物（PAH/TPH/BTEX/PCB）+ 错字容错（砐→砷）。
- `backend/tests/test_ai_rag.py`：4 个纯函数测试（中→英、英→中、错字、去重）+ 1 个 API 测试（Pb 查询命中铅因子/阈值）。

**验收**：纯函数测试 `4 passed`；Pb 查询命中铅因子/阈值。
- **如实标注**：RAG 实质仍是**关键词 SQL 检索 + Python 子串打分**，无 embedding/向量库/语义召回；本轮只提升同义词容错，未改架构（向量 RAG 列为后续可选增强）。

---

## 二、系统级验收清单（本机 venv）

| # | 验收项 | 方法 | 结果 |
|---|---|---|---|
| 1 | 后端测试 | `pytest -q` | ✅ 68 passed, 2 skipped, 7 warnings（44s） |
| 2 | 数据闭环 | build_dataset_splits | ✅ all_passed=True, 13 项 overlap_count=0 |
| 3 | 极端 10 场地 | run_system_extreme_validation | ✅ n=10, accuracy=1.0, quality=100, 8 闭环 true |
| 4 | EDA 新接口 | curl `/eda` 默认+include | ✅ 14 因子，boxplot/distribution/qq/correlation 齐全 |
| 5 | 批量导入 | curl `/import/batch` | ✅ 2/2 成功，每文件 134 点 536 超标 |
| 6 | 附件下载 | curl 正常+越权 | ✅ 200 + 错误 stage 404 + 不存在 site 404 + 无 token 401 |
| 7 | 报告 PDF | curl 生成+下载 | ✅ 91KB `%PDF-1.4`，2 个 Image 对象 |
| 8 | 报告 DOCX | curl 生成+下载 | ✅ 91KB，含 `word/media/image1.png`(52KB) |
| 9 | 场地概览徽章 | curl `/sites` | ✅ 134 点/14 因子/4512 超标/大量超标 |
| 10 | 打包自检-空闲 | run_preflight(18099) | ✅ 0 阻断 1 警告 |
| 11 | 打包自检-占用 | run_preflight(8002) | ✅ 1 阻断，提示换端口 |
| 12 | 前端构建 | npm run build + tsc | ✅ EXIT=0，3690 模块，产物含 EDA 图件逻辑 |
| 13 | RAG 同义词 | pytest test_ai_rag 纯函数 | ✅ 4 passed |

---

## 三、残留风险（如实标注）

1. **地图服务底图**：前端 key 直连返回"IP不匹配"；后端 `TIANDITU_KEY` 为空时瓦片代理正确返回 503。需在地图服务控制台配置出口 IP/域名白名单。**报告内静态图件不依赖地图服务 key，已解决报告层地图可视化**。
2. **真实 deploy/.env** 仍是 SiliconFlow/Qwen；代码默认与 `.env.example` 已是 GLM。若要按甲方要求用 GLM，需人工更新真实 `.env`。
3. **模型 AUC≈1.0**：必须持续标注为标签/阈值派生与规则特征导致的虚高风险，**不可包装成真实泛化性能**。
4. **前端主包 2.5MB**：后续应做路由级懒加载。
5. **RAG 架构**：实质为关键词检索，无向量语义召回；对同义词/错字已容错，但语义近似仍弱。后续可选增强（sqlite-vss/bge-m3）。
6. **`.app/.pkg` 打包**：`dist/SRS` 单文件可用；`.app` onefile 模式不稳，需迁移 onedir/Tauri/Electron + 签名公证 + 安装向导（本轮未做，已加首启自检作为过渡）。
7. **WeasyPrint**：本机缺 pango 系统库，PDF 走 xhtml2pdf 降级（Docker 内 WeasyPrint 正常）；本轮报告图件在两种路径下均验证可嵌入。

---

## 四、本轮新增/修改文件清单

**后端**：
- `ml/eda/profile.py`（+5 函数）
- `backend/app/api/data.py`（EDA 扩展 + `/import/batch` + 概览徽章）
- `backend/app/api/workflow.py`（附件下载端点）
- `backend/app/services/report_service.py`（matplotlib 图件 + DOCX 嵌图）
- `backend/app/services/ai_service.py`（同义词扩展接入 retrieve）
- `backend/requirements.txt`（+matplotlib）
- `backend/tests/test_eda.py`（新增）
- `backend/tests/test_data_pipeline.py`（+批量导入测试）
- `backend/tests/test_workflow_report.py`（+附件下载测试）
- `backend/tests/test_ai_rag.py`（+同义词测试）

**前端**：
- `frontend/src/components/EdaPanel.tsx`（8 Tab 重构）
- `frontend/src/pages/DataUpload.tsx`（多文件）
- `frontend/src/pages/SiteList.tsx`（概览列）
- `frontend/src/pages/TraceDetail.tsx`（下载按钮）
- `frontend/src/api/client.ts`（eda/importBatch/downloadAttachment）
- `frontend/vite.config.ts`（后端地址环境变量）

**报告**：
- `reporting/templates/traceability_report.html`（嵌图）

**打包**：
- `packaging/launcher.py`（run_preflight + 自检菜单 + 阻断提示）

**文档**：
- `docs/audit/system_acceptance_20260615_v2.md`（本文件）

---

## 五、与 v1（代码工具）的差异

- v1 验的是"主干能跑通"（接口 200、闭环 true）。
- v2 补齐项目组指出的"能用、好看、完整"层：EDA 多图、批量导入、附件下载、报告地图真图、打包自检、RAG 容错，并逐项 API/产物级复验。
- 测试数：47 → 68 passed。
- **未改变**任何 v1 已验证的核心闭环（数据真实性、阈值可追溯、降级链）。

---

## 六、地图离线方案（新增，解决桌面打包分发 + 内网场景）

### 背景
v1 地图依赖地图服务在线瓦片，受 key 白名单（IP/Referer）限制，桌面打包（exe/dmg）分发 + 内网场景下走不通（IP 不固定、key 会泄露、需外网）。本轮重构为**三层离线地图架构**。

### 三层架构
| 层级 | 内容 | 体积 | 外网 | 用途 |
|------|------|------|------|------|
| **L1 矢量底图（默认）** | 全国 35 省/475 地市/2728 县行政区边界 | 27MB | ❌ 完全离线 | 开箱即用，行政区轮廓+采样点 |
| **L2 MBTiles（可选）** | 指定区域卫星影像 | 按区域 | 仅下载时 | 桌面版按需导入 |
| **L2 在线（可选）** | 地图服务实时影像 | 0 | ✅ | 服务器+固定IP |

### 实现
- **数据**：`data/geo/`（27MB，阿里 DataV 开放数据），`scripts/download_admin_boundaries.py` 全量下载 + 建索引。
- **后端**：`/map/geo/index` + `/map/geo/boundaries?level=province|prefecture|county&adcode=xxx` 三级返回；`/map/tile` 改为**优先读本地 MBTiles，无则走在线**。
- **前端**：`SiteMap.tsx` 改三级金字塔懒加载（缩放 1-5 省/6-8 地市/9+ 县），缩放平移自动下钻；右下角显示当前层级；采样点+图例保留。
- **L2 下载**：`scripts/download_tianditu_mbtiles.py`（按 adcode/bbox 下载地图服务影像到 MBTiles，支持断点续传、体积预估）。
- **打包**：`packaging/srs.spec` 加 `data/geo/` 自动随 exe 分发；`matplotlib` 加入 hidden_imports（之前被误排除，报告图件依赖它）；MBTiles 存在则打包。

### 验收
- API：`/map/geo/index` 返回 35 省/475 地市/2728 县；`/map/geo/boundaries` 三级返回正常，个旧市（532501）定位精准。
- 测试：`test_map_api.py` 新增 2 个 geo 测试，**地图测试 5 passed**。
- 后端全量：**70 passed, 2 skipped**（比上轮 +2）。
- 前端：build + tsc EXIT=0。
- 桌面打包：L1 离线底图随 exe 分发，**开箱即用，无 key/无外网**。

### 桌面打包分发结论
- ✅ **exe/dmg 发出去默认能用**：L1 行政区底图 + 采样点 + 报告图件，零配置。
- ✅ **需要卫星影像**：用户/甲方跑 `download_tianditu_mbtiles.py`（提供 key）下载工作区影像，放入 `data/geo/tiles/` 即启用。
- ✅ **地图服务白名单问题彻底解决**：L1 不依赖地图服务；L2 在线仅服务器固定 IP 场景用。
- ⚠️ 乡镇级边界：DataV 开放数据最细到县级，乡镇级无免费开放数据源；县级粒度匹配土壤修复业务（按市县监管审批）。

详细配置见 `docs/地图离线方案与地图服务配置.md`。

## 七、最终残留风险（如实标注）

1. **地图服务 L2 在线**：仅服务器固定 IP 场景适用；桌面打包走 L1/L2-MBTiles。
2. **真实 deploy/.env** 仍 SiliconFlow/Qwen（代码默认已 GLM）。
3. **模型 AUC≈1.0**：阈值派生虚高风险，须持续标注。
4. **前端主包 2.5MB**：后续路由级懒加载。
5. **RAG**：关键词检索，本轮加同义词容错，无向量库。
6. **`.app` onefile 不稳**：已加首启自检过渡，onedir+签名公证后续。
7. **乡镇级地图数据**：无免费开放源，县级为离线极限（匹配业务粒度）。
