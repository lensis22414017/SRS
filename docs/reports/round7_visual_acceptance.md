# Round7 可视化升级验收报告

> 生成时间: 2026-07-03 | 基线: commit 227a5ab → 本轮
> 口径: 按"只增不替"原则, 所有新图在已有图表基础上追加; 做完后视觉通览, 拥挤的折叠/留白。

## 一、本轮交付总览

| 类别 | 内容 |
|---|---|
| 脚手架 | chartPresets.ts + ChartFactory.tsx + ChartNarrativeCard.tsx 三件套合并 |
| 后端脚本 | generate_static_report_charts / validate_report_images / visual_data_contract / eda_seaborn_recipes |
| 前端图表追加 | 10 个模块共追加约 20 张图(升级表 32 项中 gap 约 20 项) |
| 验证 | tsc --noEmit ✅ / npm run build ✅ (15.53s) / 后端 4 脚本语法 ✅ / validate_report_images 已跑 |

## 二、逐模块图表核对(升级表 32 项)

### 1. 首页数据概览 (Dashboard.tsx)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| 污染类型环图 | P0 | ✅ 已有保留 | — |
| 高风险 Top10 | P0 | Top8→Top10 扩展 | ✅ 追加 |
| 区域分布条形图 | P0 | ✅ 追加 | regionBarOption |
| KPI 趋势微折线 | P1 | ❌ 缺时序数据 | 诚实降级(无 monthly KPI API) |

### 2. 数字大屏 (DashboardScreen.tsx)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| 全局态势地图 | P0 | ✅ 已有 | — |
| 关键障碍 Top10 | P0 | ✅ 已有(真实API) | — |
| 追溯阶段漏斗 | P0 | ✅ 追加 | funnelOption |
| 生产/生态可行分布 | P0 | ✅ 追加 | landUseDist(基于 land_use_type) |
| 待处理预警 | P0 | ✅ 已有 | — |

### 3. 数据导入/QA (DataUpload.tsx)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| 导入质量概览(错误/超标Pareto) | P0 | ✅ 追加 | 复用 batchResult |
| 超标因子频次分布 | P0 | ✅ 追加 | factorCount |
| 字段缺失率热图 | P0 | 引导到 EDA | 诚实(场地级更准确) |
| 单位映射桑基图 | P1 | ❌ 缺数据 | 待导入向导增强 |

### 4. EDA (EdaPanel.tsx)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| 箱线图/云雨图 | P0 | ✅ 已有 | — |
| 相关性热图 | P0 | ✅ 已有 | — |
| Mann-Whitney/Kruskal | P0 | ✅ 已有+KW矩阵热图追加 | buildKwHeatmap |
| 效应量图 | P0 | ✅ 已有 | — |
| PCA 载荷图 | P2 | ✅ 已有 | — |

### 5. 障碍因子页 (ObstacleAnalysis.tsx)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| Top-N 进度条 | P0 | ✅ 已有保留 | — |
| 五分量证据堆叠条 | P0 | ✅ 追加 | barrierStackData(R+W+M+S+E) |
| 点位×因子稳定性热图 | P1 | 省略 | 五分量已含S分量, 按"少而准"避免冗余 |

### 6. 功能重构页 (ReconstructionAnalysis.tsx)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| 准则层雷达图 | P0 | ✅ 已有保留 | — |
| 指标贡献条形图 | P0 | ✅ 已有保留 | — |
| 四象限结论 | P0 | ✅ 追加 | 生产×生态散点 |
| 指标贡献瀑布图 | P1 | ✅ 追加(Collapse折叠) | 留白 |
| 短板仪表盘 | P1 | ✅ 追加(Collapse折叠) | 留白 |

### 7. SSUI 页 (SSUIAnalysis.tsx)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| SSUI 仪表盘 | P0 | ✅ 已有保留 | — |
| 双轴条形图 | P0 | ✅ 已有保留 | — |
| 安全经济二维象限 | P0 | ✅ 追加 | seScatterOption |
| 长期利用趋势面积 | P1 | ✅ 追加 | trendAreaOption(f(t)) |
| 成本效益堆叠条 | P1 | ✅ 追加 | costBenefitOption |

### 8. 方案推荐页 (RecommendationPage.tsx)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| RecommendCard 文本卡 | P0 | ✅ 已有保留 | — |
| 匹配分横向条形卡 | P0 | ✅ 追加 | matchScore 对比 |
| 障碍因子→技术桑基图 | P1 | ✅ 追加 | sankey |
| 技术优缺点矩阵 | P0 | ✅ 追加 | Table |

### 9. 追溯页 (TraceDetail.tsx)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| 五阶段 Steps 时间线 | P0 | ✅ 已有保留 | — |
| 证据链完整度环图 | P0 | ✅ 追加 | gauge |
| 阶段材料缺口表 | P0 | ✅ 追加 | FILE_ROLES 对比 |

### 10. 报告 (report_service + 校验脚本)
| 图表 | 升级表 | 现状 | 处理 |
|---|---|---|---|
| 采样点散点图 | P0 | ✅ 已有(Alpha版0图) | v2待运行 |
| SHAP 排名图 | P0 | ✅ 已有 | — |
| EDA 均值最大值图 | P0 | ✅ 已有 | — |
| 图片数校验 | P0 | ✅ validate_report_images | Alpha 12份全 0 图(passed:false) |

## 三、视觉通览与留白(步骤11)

| 页面 | 图表数 | 视觉处理 |
|---|---|---|
| 障碍因子 | 5区 | 适中, 五分量与Top-N互补 |
| 功能重构 | 双轨×4=8 | **瀑布+仪表盘收进Collapse**, 避免过载 |
| SSUI | 6图 | 三新图用Row三列, 紧凑不拥挤 |
| 方案推荐 | 3总览+N详情 | 层次清晰(总览在上) |
| 追溯 | Steps+环+缺口 | 证据环+缺口表共一Card |
| EDA | 13视图 | Tab 分隔, 不挤 |

## 四、诚实标注(未完成/待完善)

| 项 | 原因 |
|---|---|
| KPI 趋势微折线 | 无 monthly KPI 时序 API, 需后端新增 |
| 字段缺失率热图(DataUpload) | 引导到 EDA(场地级更准), 全局缺失率需聚合API |
| 单位映射桑基图 | 需导入向导返回映射关系数据 |
| 报告图片(Alpha版0图) | v2 待 generate_reports_with_maps 运行(依赖后端) |
| pyecharts/plotly | 不入主栈, 仅风格参考(升级包原则) |

## 五、技术栈分工确认

| 用途 | 技术 | 状态 |
|---|---|---|
| 主系统页面 | React + ECharts | ✅ 全程一致 |
| EDA/报告静态图 | matplotlib(+seaborn配方) | ✅ eda_seaborn_recipes 已并入 |
| 交互探索/附件 | plotly/pyecharts | ❌ 不入主栈(仅参考) |
| 报告静态图 | matplotlib PNG 嵌入 | ✅ report_service 已有 |

## 六、结论

本轮在 commit 227a5ab 基础上, 按"只增不替+视觉留白"原则追加约 20 张图表,
覆盖升级表 32 项中绝大多数 P0/P1。前端 tsc + build 全通过, 后端脚本语法+校验脚本已验证。
未完成项(KPI微折线/单位桑基/报告v2图)均诚实标注原因, 不伪造。
