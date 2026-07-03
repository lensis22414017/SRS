# EDA 组件验证报告

> 生成时间: 2026-07-03 | 组件: `frontend/src/components/EdaPanel.tsx` (React + ECharts)
> 后端: `backend/app/api/data.py` `/sites/{id}/eda` (含节五新增 5 项统计)

## 一、验证目标

裴总要求 EDA 图表必须是 CSS/React/ECharts 交互组件, **不能只是离线图片**。
逐项核对 10 类 EDA 图件是否已实现为前端组件, 并配普通用户可读图注(看什么/发现什么/影响/下一步)。

## 二、EDA 组件清单(EdaPanel.tsx 的 Tab)

| # | 图件 | 实现类型 | 数据源 | 图注四要素 | 状态 |
|---|---|---|---|---|---|
| 1 | 缺失率(统计体检表) | Table + Tag | `/eda` factors.stats.missing_pct | ✅(数据来源说明) | ✅ 已实现 |
| 2 | 因子覆盖率(对比柱状) | ECharts bar(均值+CV) | `/eda` factors.stats | ✅ | ✅ 已实现 |
| 3 | 污染物分布(云雨图) | ECharts boxplot+scatter+KDE | `/eda` factors.distribution | ✅(箱体/中线/须线说明) | ✅ 已实现 |
| 4 | 异常值检测明细 | Table(IQR+Z-score) | `/eda` outlier_detail(**节五新增**) | ✅(看什么/发现/影响/下一步) | ✅ **节五新增** |
| 5 | 正态性检验(Q-Q 图) | ECharts scatter+参考线 | `/eda` factors.qq | ✅(y=x 线说明) | ✅ 已实现 |
| 6 | Mann-Whitney U 检验 | ECharts bar(p值+0.05阈值线) | `/eda` hypothesis_test(**节五新增**) | ✅ | ✅ **节五新增** |
| 6b | Kruskal-Wallis 检验 | Table(H/p/显著) | `/eda` hypothesis_test(**节五新增**) | ✅ | ✅ **节五新增** |
| 7 | 效应量 Cohen's d/Cliff's δ | ECharts bar(量级色阶) | `/eda` effect_size(**节五新增**) | ✅ | ✅ **节五新增** |
| 8 | 相关性热力图 | ECharts heatmap(Pearson) | `/eda` correlation | ✅(蓝正红负) | ✅ 已实现 |
| 9 | PCA 主成分载荷 | ECharts scatter(载荷+采样点) | `/eda` pca(**节五新增**) | ✅ | ✅ **节五新增** |
| 10 | 直方图+KDE | ECharts bar+line | `/eda` factors.histogram | ✅ | ✅ 已实现 |
| 11 | 分组对比 | ECharts bar(区域/深度/因子) | `/eda` grouped | ✅ | ✅ 已实现 |
| 12 | 类别分布 | ECharts pie(环形) | `/eda` factors.category | ✅ | ✅ 已实现 |

## 三、节五新增统计(后端 data.py `/sites/{id}/eda`)

| 统计项 | 方法 | 依赖 | 降级策略 |
|---|---|---|---|
| Mann-Whitney U | scipy.stats.mannwhitneyu (两组对比) | scipy | 分组<2 或样本<3 → 返回空 |
| Kruskal-Wallis | scipy.stats.kruskal (≥3 组) | scipy | 组数<3 → 不返回 |
| Cohen's d | 均值差/合并标准差 | numpy | std=0 → d=0 |
| Cliff's delta | 非参, 两两比较计数 | numpy | 样本<2 → 跳过 |
| PCA | sklearn.decomposition.PCA + StandardScaler | sklearn | 样本<3 或因子<2 → 不返回 |
| 异常值明细 | IQR(Q1-1.5IQR~Q3+1.5IQR) + Z-score(\|Z\|>3) | pandas | 样本<4 → 跳过 |

## 四、图注规范核对(节五要求)

每个新增 Tab 的 Card 内 `<Text type="secondary">` 均含:
- **看什么**: 该图的核心判读维度(如 p 值、Cohen's d 绝对值)
- **发现了什么**: 显著/大效应意味着什么(空间分异、污染热点)
- **对诊断的影响**: 是否需分区治理、是否重点因子
- **下一步**: 复测、溯源、分区精查等行动建议

## 五、交互性核对

- ✅ 所有图件为 ECharts/React 组件, 非静态图片
- ✅ 支持因子下拉切换(直方图/Q-Q)
- ✅ 支持分组维度切换(区域/深度/因子)
- ✅ tooltip 悬浮显示数值
- ✅ 数据来自后端真实计算, 不写死

## 六、已知限制

1. **假设检验分组依赖 region/depth**: 若场地无区位信息或仅单一区域, 分组不足时返回空(诚实, 不伪造)。
2. **PCA 需宽表 pivot**: 采样点需有≥2 因子实测且无缺失, 否则 dropna 后样本不足。
3. **小样本警告**: 分组样本<3 自动跳过, 避免小样本检验失真。
