# 第二阶段最终验收口径 (Round 6)

> 生成时间: 2026-07-03 | 基线 commit: 待收尾提交
> 口径: 按 AGENTS.md "不写全部完成" 原则, 分四类如实标注。

## 一、已真实完成(代码+验证均已落地, 可复查)

| # | 项 | 证据 |
|---|---|---|
| 1 | 术语清理: "KOS Top-N" → "污染场地关键障碍因子 Top-N" | `ObstacleAnalysis.tsx:316` + 3 脚本 |
| 2 | 旧 SHAP 关键障碍因子表下线 | `ObstacleAnalysis.tsx`(删除 Card 块, 改由 KOS 承载) |
| 3 | 诊断方法说明卡片(KaTeX 公式 + 五要素 + 免责声明) | `components/MethodExplainCard.tsx` + 接入 |
| 4 | 大屏接入真实 API(TOP10/趋势/追溯三处去写死) | `data.py` 3 聚合端点 + `DashboardScreen.tsx` |
| 5 | EDA 后端补 5 项统计(Mann-Whitney/Kruskal/Cohen/PCA/异常值) | `data.py` `/eda` 端点 + scipy/sklearn |
| 6 | EDA 前端 4 新 Tab(假设检验/效应量/PCA/异常值明细) | `EdaPanel.tsx` + 3 build 函数 |
| 7 | 核心问题闭环页(四问 + 双轨障碍 + 下载) | `components/SiteConclusion.tsx` + SiteDetail Tab |
| 8 | 前端 typecheck 全通过 | `npx tsc --noEmit` 无错误 |
| 9 | 后端 data.py 语法校验 | `ast.parse` 通过 |

## 二、Alpha 可演示(功能可用, 但有限制需说明)

| # | 项 | 限制 |
|---|---|---|
| 1 | 6 PDF + 6 DOCX 带地图报告 | 地图为离线 matplotlib 散点(无真实瓦片底图), 水印诚实标注。需运行 `generate_reports_with_maps.py`(依赖后端+DB) |
| 2 | 15+3 批量验证 | 脚本 `run_round6_batch_validation.py` 已建, 需后端启动运行填数字。内部场地仅 KOS 链路 |
| 3 | Round6 截图(15 张) | 脚本 `screenshot_round6.js` 已建, 需前后端启动后运行 |
| 4 | 演示包 v2 zip | 脚本 `pack_demo_v2.py` 已建, 需前述产物先生成再打包 |

## 三、仍需完善(不影响演示, 但甲方深度追问会暴露)

| # | 项 | 说明 |
|---|---|---|
| 1 | 报告地图无真实底图 | 天地图 MBTiles 未落地(`data/geo/tiles/` 不存在), 地图无卫星影像。需下载瓦片或接入行政区 GeoJSON 边界 |
| 2 | 场地级 boundary 缺失 | DB 仅存场地中心点经纬度, 无场地轮廓多边形, 地图无场地边界线 |
| 3 | 大屏障碍因子 TOP10 依赖诊断历史 | 各场地需先跑过诊断才有聚合数据, 无诊断的场地不参与(诚实, 不伪造) |
| 4 | OP 有机污染模型探索性 | 相关 KOS/报告结论标注"探索性", 需人工复核 |
| 5 | weasyprint 依赖系统库 | 若环境无 pango/cairo, PDF 降级为 xhtml2pdf, CSS 排版质量略降 |

## 四、不建议甲方触碰(已知脆弱或易误读)

| # | 项 | 原因 |
|---|---|---|
| 1 | OP 生产轨 KOS Top-N | OP 模型探索性, 排名可能不稳定, 展示时需口头说明 |
| 2 | 内部 15 场地的重构/SSUI | 内部合成场地无完整阈值上下文, 不展示这些环节(标注 N/A) |
| 3 | EDA 的 PCA/假设检验小样本 | 采样点 < 3 或分组 < 2 时返回空, 强行解读会误导 |
| 4 | 大屏底部趋势线(无历史数据时) | 新系统无 12 个月历史, 趋势线为 0, 标"待接入"而非伪造增长 |

## 五、与 Alpha 版对比

| 维度 | Alpha (commit 4883deb) | v2 (本批) |
|---|---|---|
| 关键障碍术语 | "KOS Top-N" | "污染场地关键障碍因子 Top-N" |
| 旧 SHAP 表 | 条件隐藏(仍可触达) | 彻底下线 |
| 方法说明 | 无 | KaTeX 卡片 + 免责声明 |
| 报告地图 | ❌ 零图片 | ✅ matplotlib 嵌入(脚本就绪) |
| 大屏数据 | 写死占位 | 真实 API 聚合(3 新端点) |
| EDA 图件 | 9 项 | 13 项(+假设检验/效应量/PCA/异常值) |
| 闭环页 | 无 | SiteDetail 综合结论 Tab |
| 验收口径 | "全部通过" | 四分类诚实标注 |

## 六、运行清单(收尾验证用)

```bash
# 1. 后端测试
cd backend && pytest -q

# 2. 前端构建
cd frontend && npm run build

# 3. 生成带地图报告(需后端启动)
python scripts/generate_reports_with_maps.py

# 4. 批量验证(需后端启动)
python scripts/run_round6_batch_validation.py

# 5. 截图(需前后端启动)
node scripts/screenshot_round6.js

# 6. 打包
python scripts/pack_demo_v2.py
```

---

**结论**: 本批改动(节一至节十)代码已全部落地并通过类型/语法校验。
报告地图/批量验证/截图/打包为"脚本就绪待运行"状态(依赖运行时环境),
不声明"全部完成"。建议裴总在本机 venv 启动后端后执行上述运行清单, 我再据实更新验收数字。
