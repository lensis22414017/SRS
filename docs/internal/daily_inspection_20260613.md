# 每日巡检 — 2026-06-13

## [MODE: REVIEW] 今日盘点(基于真实仓库状态)

### 已收敛
- 报告模板编号缺陷修复:一~十七连续,含地图图件/修复案例/人工复核区。
- 企业数据隔离:diagnosis/evaluation/recommendation/workflow/reports/map.layers/ai.chat 全过 `assert_site_access`,回归测试覆盖。
- 切分零泄漏(DOI+Source 连通分量)、地图瓦片代理 + 失败态、AI(GLM 默认)RAG 降级、DOCX/PDF 报告、基线迁移、EDA 科研图件(箱线/小提琴/QQ/热力/散点)。

### 今日修复(本轮)
1. **甲方三类真实场地仅 1 类可导入** → 新增南京栖霞(有机)、乡村建设用地(复合)字段映射 `nanjing_qixia.json`/`xiangcun_fuhe.json`。沙箱用真实原始表验证:栖霞 49 点/18 因子/366 值,乡村 8 点/14 因子/107 值,解析正确。
2. **前端下拉 mapping_id 与文件名不符 bug**:codex 下拉用 `nanjing_qixia_organic_v1` 等内部 id,而 `load_mapping` 按文件名加载会 404 → 已改为文件 stem `nanjing_qixia`/`xiangcun_fuhe`,三类均可加载。
3. **阻断性测试 bug**:`test_data_pipeline.py` 第119行用 `@needs_data` 但未定义 → 模块导入 NameError 会拖垮整套 pytest。已补 `needs_data` skipif 定义。

### 未收敛(需甲方确认或后续)
- **栖霞/乡村原始表尚未入 data/raw**:项目组遵守红线未写 data/raw,需项目组将两份原始 xlsx 放入 `data/raw/`(或前端上传),三类才能在系统内端到端跑通。
- 生产/生态两套指标体系权重口径与方法文件的细粒度对齐(两团队课题),待甲方定稿。
- 报告静态图表(箱线/超标热图/SHAP)仍以 EDA 页呈现,尚未内嵌进 PDF/DOCX 报告图件。
- 分组切分指标若≈1.0 须标注"标签/阈值派生虚高",不得当真实泛化。

## [MODE: PLAN] 收敛路线
1. **三类真实场地入库(P0)**:项目组放置两原始表→ `python -m app.db.bootstrap` 后用对应 mapping 导入→ 跑诊断/评价/推荐/报告,验证有机与复合场地闭环(有机场地无坐标,地图应显示无坐标态)。
2. **指标口径对齐(P1,需甲方)**:核对功能重构生产/生态权重与 SSUI 参数是否采用方法文件第2/3章定稿;差异点列清单提交甲方。
3. **报告图件内嵌(P1)**:report_service 用 matplotlib 生成箱线/超标热图/SHAP PNG 内嵌 PDF/DOCX,带测试,不破坏现有套件。
4. **泛化诚实性(P1)**:分组切分重训指标与行级随机对照并表,显式标注虚高风险。
5. **PR 收口(P2)**:独立仓库 git init + 干净提交;Docker 由 codex 最终跑。

## 验收口径
三类真实场地各跑通"导入→校验→诊断→评价→推荐→追溯→报告";原始数据零改动;模拟不进真实验证;不夸大模拟为真实泛化。
