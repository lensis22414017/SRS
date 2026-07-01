# [MODE: PLAN]

> 项目组每日开发巡检 — 2026-06-15（周一）
> 项目组，以下是今日计划。

---

## 昨日情况

- **最后提交**：`0dccc9a` 2026-06-13 23:29 `feat: 新增地图模块 (地图服务瓦片代理 + map router)`
- **2026-06-14/15 无新提交**
- **未提交变更**：18 个 modified 文件 + 2 个 untracked 目录（`000/`、`data/synthetic/`），持续累积中

---

## 当前仓库状态扫描

### docs/
✅ 完整：SRS.md、system_architecture.md、database_schema.md、算法文档×4、acceptance_criteria.md、用户操作手册、运维交接手册、系统设计文档、软著申请材料均已生成。
⚠️ 2026-06-12 审计报告（6 份）已在 `docs/audit/`，但产出的问题尚未全部回填修复。

### backend/
✅ 核心 API 全部实现：auth、data、diagnosis、evaluation、map、workflow、ai、system。
✅ 服务层：import、validation、diagnosis（RF+SHAP）、evaluation（重构+SSUI）、recommend、report（15章+版本号）、workflow（五阶段）、audit。
✅ 41 tests passed（最近已知状态）。
⚠️ `diagnosis_service.py`、`report_service.py`、`ai_service.py` 有未提交修改，真实状态与 HEAD 不一致。

### frontend/
✅ 页面齐全：Login、Dashboard、SiteList、SiteDetail、DataUpload、ObstacleAnalysis、ReconstructionAnalysis、SSUIAnalysis、RecommendationPage、TraceList、TraceDetail、SystemManagement。
⚠️ `SiteDetail.tsx`、`SiteMap.tsx`、`client.ts` 有未提交修改。
⚠️ 主包 ~2.5MB 未做路由懒加载拆分。
❌ 本机前端冒烟测试（loading/empty/error态、窄屏布局）**尚未执行**。

### ml/
✅ RF 模型：4 个版本快照（0610-0613），feature_mapping.json，SHAP 服务，group_split 指标。
⚠️ **关键风险**：`rf_group_split_metrics.json` 自身附带警告：
  > "若 row/group 指标都接近 1, 优先解释为阈值派生标签与污染物特征强绑定, **不能当作独立真实性能证据**"
  行级随机 AUC 0.9999，分组 AUC 1.0——这说明当前标签（label_risk）是直接从污染物特征阈值推导的，模型"学"的是规则本身，不是真正的数据泛化能力。若甲方追问，无法辩护。

### reporting/
✅ 报告模板 `traceability_report.html` 已更新为连续章节编号（一到十六），重复编号缺陷已修复（在未提交修改中）。
⚠️ 报告内无静态图表（无箱线图、SHAP 瀑布图内嵌图片），纯文字+表格。
⚠️ 无"人工复核意见/复核人/复核时间"区块。

### deploy/
✅ `docker-compose.yml` + `.env.example` 存在。
❌ Docker 端到端构建验证**尚未在本机执行**，全链路是否能 `docker compose up` 跑通未知。

### data/
✅ `data/knowledge_base/`：统一障碍因子知识库、技术库、案例库。
✅ `data/model_ready/`：8 个模型就绪 CSV + manifest。
✅ `data/splits/`：零泄漏分组切分已重建。
⚠️ `data/synthetic/` 未追踪，尚未 `.gitignore` 或提交。

---

## MVP 闭环进度评估

| 闭环节点 | 代码 | 测试 | 本机验证 | 甲方可演示 |
|----------|------|------|----------|-----------|
| 数据导入 | ✅ | ✅ | ⚠️ 未截图 | 基本可 |
| 数据校验 | ✅ | ✅ | ⚠️ 未截图 | 基本可 |
| 场地详情 | ✅ | ✅ | ⚠️ 未截图 | 基本可 |
| 障碍因子识别 | ✅ | ✅ | ⚠️ 未截图 | ⚠️ 指标需诚实标注 |
| RF/SHAP 解释 | ✅ | ✅ | ⚠️ 未截图 | ⚠️ 同上 |
| 功能重构评价 | ✅ | ✅ | ⚠️ 未截图 | 基本可 |
| SSUI 评价 | ✅ | ✅ | ⚠️ 未截图 | 基本可 |
| 方案推荐 | ✅ | ✅ | ⚠️ 未截图 | 基本可 |
| 全流程追溯 | ✅ | ✅ | ⚠️ 未截图 | 基本可 |
| PDF 报告 | ✅ | ✅ | ⚠️ 未截图 | ⚠️ 缺图件/复核区 |
| 操作日志 | ✅ | ✅ | ⚠️ 未截图 | 基本可 |
| 地图 | ✅ | ✅ | ❌ 地图服务 key 未配 | ⚠️ 需配 key |

---

## 今日三大目标

---

### 目标一：清理未提交变更并打 v0.1.0 release tag

**文件路径**：
- `backend/app/services/report_service.py`（修改中）
- `backend/app/services/diagnosis_service.py`（修改中）
- `backend/app/services/ai_service.py`（修改中）
- `frontend/src/pages/SiteDetail.tsx`（修改中）
- `frontend/src/components/SiteMap.tsx`（修改中）
- `frontend/src/api/client.ts`（修改中）
- `reporting/templates/traceability_report.html`（修改中，含章节编号修复）
- `backend/tests/test_map_api.py`（新文件，未追踪）
- `data/synthetic/`（未追踪，需决定是否 .gitignore）
- 其余 9 个 modified 文件

**具体任务**：
1. `cd /path/to/SRS && git diff --stat` 确认 18 个修改全貌。
2. 确认 `backend/.env`、`frontend/.env.local`、`*.db`、`storage/` 在 `.gitignore`（避免提交机密）。
3. `data/synthetic/` 确认为合成数据，加入 `.gitignore` 或一并提交（大文件检查 `du -sh`）。
4. `git add -A && git commit -m "chore: 提交 v0.1 PR 审计修复集 — 报告模板/地图/诊断/前端细节"`
5. `git tag -a v0.1.0 -m "SRS MVP v0.1.0 — 全链路闭环交付"`

**验证方式**：
- `git log --oneline -5` 确认提交。
- `git tag -l` 确认 tag 存在。
- `git status` 输出 `nothing to commit, working tree clean`。

**风险**：
- 18 个修改中可能有冲突或半成品代码，提交前必须先 `git diff` 逐一确认。
- 若 `report_service.py` 修改未完成，应先 `git stash` 隔离。

---

### 目标二：在文档与代码中诚实标注 RF 模型"AUC=1.0"的来源与边界

**文件路径**：
- `docs/algorithms/rf_shap.md`（主要更新目标）
- `ml/artifacts/MODEL_README.md`（补充说明）
- `backend/app/services/diagnosis_service.py`（结论解释文本中已有"imputed_features"机制，需补"标签来源说明"）

**具体任务**：

1. 在 `docs/algorithms/rf_shap.md` 新增"性能指标解读"章节，明确写明：
   - 当前 `label_risk` 标签来自「检测值 vs 国标阈值比较规则」，属于阈值派生标签，非独立真实风险评估。
   - 行级 AUC=0.9999、分组 AUC=1.0 是**规则拟合程度**，不是模型泛化能力的独立证据。
   - 真实泛化评估需要：独立领域专家标注的风险标签 OR 修复效果回访数据（MVP 阶段暂不具备）。
   - 当前模型的正当用途：**从 128 个特征中快速排序障碍因子重要性（SHAP 全局排序）**，辅助专家决策，非替代专家判断。

2. 在 `ml/artifacts/MODEL_README.md` 补充同等内容的摘要版本。

3. 在 `backend/app/services/diagnosis_service.py` 的结论生成逻辑中，在 `explanation` 字段追加一行固定说明文字，例如：
   ```
   「注：当前模型标签来源于阈值规则推导，AUC 反映规则拟合程度，SHAP 因子排序具参考价值，最终结论需专家复核。」
   ```

**验证方式**：
- `grep -n "标签来源\|阈值派生\|规则拟合" docs/algorithms/rf_shap.md` 能命中。
- 调用一次 `/sites/{id}/diagnosis` 接口，确认 explanation 字段含上述说明。

**风险**：
- 这是**诚实标注**，不是降低系统价值，而是保护甲方演示时不被专家追问穿帮。
- 不改核心算法逻辑，风险极低，但改 diagnosis_service.py 需同步运行 `pytest tests/test_diagnosis.py`。

---

### 目标三：本机端到端冒烟测试并截图存档

**文件路径**：
- 测试记录写入 `docs/audit/smoke_test_20260615.md`（新建）
- 截图存入 `docs/audit/screenshots/`（新建目录）

**具体任务**：

按以下顺序在本机执行并截图（每步截图存档）：

```
1. cd backend && python -m pytest --tb=short -q
   → 期望：41+ passed，0 error
   → 若失败：记录哪个 test，不继续下一步

2. cd frontend && npm run build
   → 期望：构建成功，dist/ 2.x MB
   → 若报 TS 错误：记录文件行号

3. cd .. && docker compose -f deploy/docker-compose.yml up -d
   → 访问 http://localhost:8000/api/v1/health
   → 期望：{"status": "ok"}

4. 访问 http://localhost:3000（或 Vite 端口）
   → 截图：登录页
   → 登录 admin/admin123
   → 截图：数据概览首页

5. 进入场地列表 → 选择 GJ-2025-001
   → 截图：场地详情（基本信息 + 采样点）

6. 触发障碍因子诊断
   → 截图：Top-N 因子列表 + SHAP 图

7. 触发功能重构评价 + SSUI 评价
   → 截图：评价得分页

8. 进入全流程追溯 → 录入调查评估阶段记录
   → 截图：追溯阶段卡片

9. 点击"生成 PDF 报告"
   → 截图：报告下载成功提示
   → 打开 PDF 验证章节完整（一到十六）

10. 测试不同角色登录（enterprise_user / regulator）
    → 确认数据隔离生效
    → 截图：权限不足提示页
```

**验证方式**：
- `docs/audit/smoke_test_20260615.md` 记录每步 PASS/FAIL + 截图路径。
- 所有 10 步 PASS → MVP 验收标准 15 项基本覆盖。

**风险**：
- Docker 首次构建可能因网络或依赖问题失败，先备用方案：直接 `uvicorn app.main:app` + `npm run dev`。
- 地图服务瓦片需配置 `TIANDITU_KEY`（`.env` 中补充），否则地图降级 OSM，截图时注明。
- PDF 生成依赖 `xhtml2pdf` / `weasyprint`，Docker 镜像内应已包含，本机裸跑需确认 `pip install`。

---

## 新发现问题汇总

| # | 问题 | 严重度 | 建议处理时间 |
|---|------|--------|------------|
| 1 | 18 个未提交文件，0 个 release tag | 高 | 今日目标一 |
| 2 | ML 模型 AUC=1.0 来源未在代码/文档中诚实说明 | 高 | 今日目标二 |
| 3 | 本机端到端验证从未执行 | 高 | 今日目标三 |
| 4 | 报告无静态图表（SHAP/箱线图） | 中 | 本周内 |
| 5 | 报告无"人工复核区" | 中 | 本周内 |
| 6 | 前端主包 2.5MB，未做路由懒加载 | 低 | 后续优化 |
| 7 | desktop/ 目录为空，无桌面打包程序 | 视合同 | 与甲方确认 |

---

## 阻塞项

- 目标三全部需要**本机执行**，无法在 Cowork 沙箱中完成。
- 地图服务 key 需项目组提供/配置，否则地图瓦片代理无法验证。

---

## 建议不要动的文件（今日）

- `data/raw/`（原始检测数据，永远不动）
- `ml/models/dataset_splits.py`（刚完成零泄漏修复，稳定）
- `backend/alembic/versions/0001_baseline.py`（基线迁移，已是稳定基线）

---

项目组确认后，可另开 Cowork 任务发送 `ENTER EXECUTE MODE` 执行。

---

# [MODE: EXECUTE] 项目组执行记录 — 2026-06-15（晚间）

> 承 代码工具 v1 验收（`system_acceptance_20260615.md` 主干闭环已通），本轮针对项目组指出的"能用/好看/完整"层缺口做补齐 + 系统级复验。详见 `system_acceptance_20260615_v2.md`。

## 本轮完成（6 缺口 + 系统级验收）

### 缺口补齐（全部完成并测试）
1. **EDA 科研级可视化**：后端 `profile.py` +5 函数、`data.py` EDA 接口加 `include/group_by/factor/max_points` query 参数；前端 `EdaPanel.tsx` 重构为 8 Tab（体检/直方图/**箱线+小提琴**/**散点+拟合**/**相关热力图**/**Q-Q**/**因子对比**/**分组对比**）。新增 `test_eda.py`（7 纯算法 + 6 API 测试）。
2. **批量导入 + 场地概览**：后端 `/import/batch`（串行避免竞态）+ `list_sites` 补 n_factors/n_exceed/data_quality；前端 `DataUpload` 多文件 + 逐文件结果表、`SiteList` 补概览列。
3. **阶段附件下载**：后端 `GET /workflow/{stage}/attachments/{id}/download`（三层越权校验）；前端 `TraceDetail` 加下载按钮。测试覆盖 200/404/401。
4. **报告地图图件**：`report_service.py` 用 matplotlib 离线画采样点散点（按超标倍数着色，不依赖地图服务 key），注入 `map_summary.map_image`；HTML 模板 + DOCX 均嵌入图。`requirements.txt` 加 matplotlib。
5. **打包首启自检**：`launcher.py` 加 `run_preflight`（端口/DB/Redis/AI key/地图服务 key 只读探测）+ 托盘"环境自检"项 + 阻断提示框。两场景验收通过。
6. **RAG 同义词容错**：`ai_service.py` 让因子/阈值检索也用 `_expand_terms`（中英符号互查 + 错字），扩充别名表（11→20 金属 + 有机物）。+5 测试。

### 系统级验收（本机 venv）
- 后端测试：**68 passed, 2 skipped, 7 warnings**（比 v1 多 21 个新测试，全过）。
- 极端 10 场地：`n=10, accuracy=1.0, quality=100`，8 闭环全 true。
- 数据闭环：split `all_passed=True`，13 项 overlap=0，synthetic 未混入 real。
- API 复验：EDA 新字段、批量导入（2/2）、附件下载（200+越权 404/401）、报告（PDF `%PDF-1.4` + 2 Image 对象；DOCX 含 `word/media/image1.png` 52KB）全通过。
- 前端：build + tsc EXIT=0，产物含 boxplot/heatmap/QQ/小提琴 逻辑。
- 打包自检：空闲→✅、占用→❌ 阻断提示，两场景正确。

## 残留风险（如实标注，未回避）
- 地图服务底图仍受 key 白名单限制（报告内静态图件已不依赖，解决报告层）。
- 真实 `deploy/.env` 仍 SiliconFlow/Qwen（代码默认已 GLM，需人工改 .env）。
- 模型 AUC≈1.0 须持续标注为阈值派生虚高风险。
- RAG 实质为关键词检索（无向量库），本轮只加同义词容错。
- `.app/.pkg` onefile 不稳，本轮加首启自检过渡，onedir+签名公证列为后续。

## 交付物
- `docs/audit/system_acceptance_20260615_v2.md`（完整验收记录）。
- 代码改动覆盖后端/前端/报告/打包/测试，全部经测试验证。

**下一步建议**：项目组若要提交，可发指令让我 `git add -A && commit`（当前未提交，遵循"不主动 commit"）。

---

## 追加：地图离线方案（2026-06-15 夜间）

项目组指出最终交付是 exe/dmg 安装包 + 内网环境，地图服务在线方案（IP 白名单）桌面分发走不通。重构为三层离线地图：

- **L1 矢量底图（默认，27MB）**：全国 35 省/475 地市/2728 县行政区边界，DataV 开放数据，**完全离线，无 key/无外网**，开箱即用。`SiteMap.tsx` 三级金字塔懒加载（省→地市→县随缩放下钻）。
- **L2 MBTiles（可选）**：`scripts/download_tianditu_mbtiles.py` 按区域下载地图服务影像，桌面版按需导入。
- **L2 在线（可选）**：仅服务器固定 IP 场景，配 TIANDITU_KEY + IP 白名单。

数据：`data/geo/` 27MB 已下载齐全。后端 `/map/geo/index`+`/map/geo/boundaries` 三级 + `/map/tile` 优先 MBTiles。打包 spec 加 data/geo + matplotlib（修复误排除）。详细见 `docs/地图离线方案与地图服务配置.md`。

验收：地图测试 5 passed（含个旧市定位），后端全量 70 passed，前端 build EXIT=0。乡镇级无免费开放数据源，县级匹配业务粒度。

**地图服务白名单结论**：桌面打包版用 L1 不需要白名单；服务器固定 IP 才用 L2 在线 + IP 白名单（填服务器出口公网 IP）。
