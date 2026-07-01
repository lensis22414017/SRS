# 报告专业质量审计 — 20260612

对象: `backend/app/services/report_service.py` + `reporting/templates/traceability_report.html`

## 1. 已具备章节(✅)
| 必需项 | 状态 |
|---|---|
| 场地基本信息 | ✅ 一 |
| 数据来源/证据等级 | ✅ 二(含 evidence_source) |
| 覆盖率/缺失率摘要 | ✅ 三(coverage_pct/missing_pct) |
| 采样点信息 | ✅ |
| 检测数据摘要 | ✅ 四 |
| 数据质量校验 | ✅ 五 |
| Top-N 障碍因子(RF+SHAP) | ✅ 六 |
| 功能重构(生产+生态) | ✅ 七 |
| SSUI 评价 | ✅ 八 |
| 推荐方案 + 修复矩阵 | ✅ 九 |
| 禁用条件 | ✅ (forbidden_conditions, 含于推荐矩阵) |
| 修复案例证据库 | ✅ 十 |
| 五阶段追溯时间线 | ✅ |
| 操作日志摘要 | ✅ 十二 |
| 模型/数据/标准/模板版本 | ✅ 十三 |

## 2. 发现缺陷(需修, 建议配测试)
1. **章节编号重复**: 模板出现两个"三"(覆盖率摘要 / 采样点)与两个"十"(推荐矩阵 / 五阶段)。属可见排版缺陷, 应重排为连续编号。
   - 修法: 调整 `<h2>` 序号; 新增/调整 `test_workflow_report`/`test_remediation_report` 对章节标题的断言, 防回归。
2. **缺独立"人工复核区"**: 报告未见显式签署/复核栏。建议在末尾增加"人工复核意见 / 复核人 / 复核时间"区块。
3. **缺静态图表**: 当前报告为表格+文字, 无箱线图、超标倍数热图、SHAP/Top 因子可视化的静态图件。
   - 建议: 后端用 matplotlib 生成 PNG 内嵌(base64)或 HTML 内联 SVG; 需新增依赖 matplotlib 并在 Docker/requirements 同步; 单独 PR 推进以免影响当前 38 测试。

## 3. 本轮处置
鉴于沙箱无法运行后端 pytest(无 sqlalchemy/weasyprint), 为不破坏现有 38 passed, **本轮不盲改模板**, 仅记录缺陷与带测试的修法。编号重排 + 人工复核区为低风险小修, 建议下一个聚焦 PR 落地并补断言。

## 4. 格式覆盖
后端 `generate(report_format=pdf|docx|html)` 三格式齐备; PDF 走 xhtml2pdf, 无 weasyprint 系统依赖; 前端本轮已补 PDF/DOCX 双按钮与按真实 `data_snapshot.format` 的下载扩展名(见 product_flow 审计 #4)。
