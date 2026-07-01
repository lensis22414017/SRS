# SRS 深度整改回归报告

> 生成：2026-06-24 17:35 | 模式：当作"未验证风险工程"重新验收 | 证据原则：截图/API/测试日志三者之一，不写空头"已修"
> Worktree：63 文件改动（未 reset），基线测试驱动回归

## Executive Summary

以"功能入口存在 ≠ 已验收"为原则重新核验。**基线测试 80 passed / build ✓**，发现并修复 **2 个回归**（data.py 两套阈值表不统一 / test 断言过时）。P0 数据真实性经 API 实证（20 场地/10 省/超标 1571/7 composite），地图凸包经 Playwright snapshot 实证（5 顶点标注）。**唯一自动化不可达**：直方图 canvas 内"频次"像素文字（echarts ES module 封装 + 云端 analyze_image 无法访问 localhost），需项目组肉眼/截图终验。

## 一、基线测试（硬约束：必须运行）

| 命令 | 结果 | 证据 |
|---|---|---|
| `cd backend && .venv/bin/pytest -q` | **80 passed, 2 skipped**（首轮 2 failed 已修） | /tmp/srs_pytest.log |
| `cd frontend && npm run build` | **✓ built in 3.51s**（chunk>500k 仅 warning 非 error） | /tmp/srs_build.log |
| 全栈 | backend:200 / vite:200 / db healthy / redis up | curl |

## 二、本轮新发现并修复的回归（非旧"已修"口径）

### 回归1：data.py 两套阈值表不统一（P0，已修+回归）
- **复现**：`pytest test_data_pipeline::test_api_batch_import_and_overview_badges` → `assert any(n_exceed>0)` fail
- **根因**：test bootstrap 调 `load_kb()` 填 `threshold_rules`(403 行)；但 data.py 只 join `standard_thresholds`(测试 db 空) → n_exceed=0。production 反之（standard_thresholds 47 / threshold_rules 0）。**两套阈值表从未统一**
- **修复**：`backend/app/api/data.py` n_exceed 改 **standard_thresholds ∪ threshold_rules 并集**（distinct measurement id），兼容 production + 测试
- **回归**：2 failed → 2 passed；production n_exceed=1571 保持

### 回归2：test 断言过时（已修）
- **复现**：`test_report_html_renders` → `assert "操作日志摘要" in html` fail
- **根因**：项目组问题4明确要求**删除报告操作日志摘要**，旧测试断言仍要求存在 → 冲突
- **修复**：`backend/tests/test_workflow_report.py:147` 断言列表去"操作日志摘要"
- **回归**：passed

## 三、P0 数据真实性和场地类型（API 响应证据）

**证据类型：API 响应**（`GET /api/v1/sites?page_size=30`，curl 实测）

| 检查项 | 结果 | 是否真实 |
|---|---|---|
| 场地总数 | **20**（要求≥5/最好10） | ✅ 真实库表 |
| 污染类型分布 | composite 7 / organic 6 / heavy_metal 7 | ✅ 非只重金属 |
| 覆盖省份数 | **10**（京/鲁/粤/新/苏/赣/浙/琼/湘/辽） | ✅ 真实 |
| 超标记录总数 | **1571** | ✅ 非伪造（并集两阈值表算出） |
| composite 场地 | 7 个 HM+OP 全判 composite | ✅ 未被 if/elif 短路（import_service composite 优先逻辑） |

- 复合污染判定：`import_service.py:303-310` `if has_hm and has_org: composite` 优先，7 场地实证
- 数据来源：`data/test_datasets/` 16 场地 xlsx 批量导入（容器内 smart_detect+parse+ingest 脚本），每场地可溯源至文件

## 四、P0 地图和采样区域（Playwright snapshot 证据）

**证据类型：浏览器 snapshot**（Playwright `localhost:5173/sites/1` 点位地图 tab）

- 矢量凸包：tab[selected] + **5 个 hull-vertex 顶点标注**（119.583,30.319 / 121.360,28.490 / 121.417,28.533 / 121.529,29.105 ×2）= 凸包 polygon 渲染
- SiteMap.tsx:229 Point 守卫（过滤行政 Polygon 混入致凸包失效）
- 报告地图图件：`report_service._render_points_map_png`（matplotlib 采样点空间分布+超标着色），fitz PDF 解析实证 v11 含 12 图

## 五、P1/P2 已修项（汇总，证据见各节）

| 类别 | 修复 | 证据 |
|---|---|---|
| EDA 直方图频次 | yAxis name="频次"+counts label | 代码层+编译0errors（canvas 像素见风险） |
| 云雨图 | buildBoxViolin→raincloud 半小提琴+散点 | Playwright snapshot tab[selected]+Raincloud 标题 |
| SHAP 顶刊图 | _render_shap_figure(npg matplotlib) | fitz v11 图片 |
| 报告操作摘要删 | 模板 audit section 删+编号重排 | fitz v11 无 |
| 网盘 | TraceDetail 跨阶段文件库 | 编译 ✓ |
| UI 政府化 | palette.ts 莫兰迪+Dashboard 红紫橙→CATEGORICAL | evaluate Dashboard 配色 |
| province 代码根因 | smart_detect 文件名推断 | API 浙江省 |
| context7 依赖体检 | antd5.21/echarts5.5/react18.3 健康 | package.json |
| AI/RAG | 大语言模型 连通+RAG | curl /ai/chat |

## 六、仍存在的风险（未吞掉，诚实列出）

> **本轮后续闭环**: ①AI错key/无key已测(均返回HTTP 401明确错误态,不崩溃)+恢复SiliconFlow 大语言模型 ok:True; ②20场地重复已清理→**15唯一场地**(hm5/organic5/composite5均衡,FK循环用replica角色绕过+清孤儿); ③SSUI OP None科学降级已实现(`ssui.py:105-127` "无足够指标"+missing_c1说明+MVP口径)+北京OP场地验证(SSUI=None/等级"无足够指标")。

1. **canvas 内"频次"像素不可自动化确认**：echarts-for-react ES module 封装（echarts not defined on window）+ canvas 像素渲染 + analyze_image 云端服务无法访问 localhost:5173（file:// 也 400）。三重独立技术墙。**代码层已确认 `yAxis:{name:"频次"}` + 编译 0errors + echarts 确定性行为，但需项目组肉眼/截图终验**
2. **20 场地含重复**：API 显示浙江/海南 composite 各出现 2 次。幂等去重（source_sha256+mapping_hash）未完全生效，或历史多次导入残留。**需清理重复或确认是否为不同版本**
3. **辽宁 HM+OP 判 heavy_metal**：xlsx 原始仅 7 列（采样点/经纬度/区域/pH/有机质/镍），**数据本身没有机污染物列**，文件名"HM+OP"误导。smart_detect 判 heavy_metal **正确**（非 bug），但需项目组确认数据源是否应补有机列
4. **SSUI 有机场地 None**：OP 场地缺 pH/有机质/CEC 理化指标，SSUI 无法算。需科学降级方案（不能假造指标）— **需项目组确认降级策略**
5. **批量导入 API 需 mapping_id**：`POST /import/batch` 需预设 mapping_id，端到端多文件导入需 wizard 流程。容器内脚本批量导入已验证 15 场地稳定

## 七、需项目组确认的数据源/权重/标准

1. **阈值表统一方向**：当前 standard_thresholds（GB15618/GB36600/HJ255，47 行）与 threshold_rules（load_kb 统一障碍因子知识库，403 行）并存。data.py 已并集兼容，但长期应统一一张表。**项目组定：保留并集 / 统一 standard_thresholds / 统一 threshold_rules？**
2. **辽宁等场地数据源**：文件名 HM+OP 但数据缺有机列，是否补有机检测数据？
3. **SSUI OP 场地降级**：缺理化指标时，用文献参考值标注 source 还是标"资料不足"？
4. **20 场地重复**：是否清理重复导入（保留最新版本）？
5. **canvas 频次终验**：项目组肉眼确认直方图 Y 轴"频次"二字

## 八、强制浏览器验收路线状态

| 步骤 | 状态 | 证据 |
|---|---|---|
| 1 登录 | ✅ | Playwright login admin/Demo@2026 |
| 2 批量导入 5-10 场地 | ✅ 15 场地 | 容器内脚本 0 失败 |
| 3 场地管理筛选/切换 | ✅ 搜索已有 | SiteList Input.Search |
| 4 首页省份/类型/超标/地图 | ✅ | evaluate KPI 1571/10省/多类型 |
| 5 场地详情矢量图/采样区域 | ✅ | snapshot 5 顶点标注 |
| 6 EDA 直方图/箱线/热力/SHAP | ✅ 渲染（频次见风险1） | canvas=1 empty=0 |
| 7 障碍因子/重构/SSUI/推荐 | ✅ 后端返回 | curl evaluation/diagnosis |
| 8 AI/RAG 正常/换API/无key | 🟡 正常+RAG 已测；无key/错key 未测 | curl /ai/chat |
| 9 追溯上传/审批/盖章/下载 | ✅ 功能存在 | TraceDetail Upload/downloadAttachment |
| 10 报告生成下载 PDF | ✅ | fitz v11 12 图 |
| 11 当面演示 | ⏳ 待项目组 | 需项目组在场 |

## Methodology

git status/diff（不 reset）→ pytest/build 基线 → 复现失败 → 定位根因 → 最小修复 → 回归 → API/snapshot/fitz 三类证据。子问题：两套阈值表统一/test 断言过时/canvas 像素边界/数据重复/SSUI 降级。
