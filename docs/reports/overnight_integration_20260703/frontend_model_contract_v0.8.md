# 前端模型契约 v0.8 (Frontend Model Contract)

> 用于前端页面接入 KOS 诊断的接口规范。

## 1. 诊断接口

### 触发 KOS 诊断
```
POST /api/v1/sites/{site_id}/kos-diagnosis?track=prod&subset=all&top_n=10
Header: Authorization: Bearer {token}
```

### 响应字段(前端展示用)

| 字段 | 前端展示名 | 展示位置 | 说明 |
|---|---|---|---|
| key_obstacles | **关键障碍因子 Top-N** | 障碍分析页主表格 | 排序展示,含 KOS 分数 |
| key_obstacles[].factor | 因子名称 | 表格列 | 如 "砷(As)" |
| key_obstacles[].KOS | 综合评分 | 表格列(进度条) | 0-1,越高越关键 |
| key_obstacles[].components | 评分构成 | Tooltip | R/W/M/S/E 五分量 |
| key_obstacles[].value | 实测值 | 表格列 | 该因子实测浓度 |
| key_obstacles[].evidence | 证据等级 | Badge | A/B/C/D |
| recommended_tests | **建议补测** | 独立卡片 | 未实测重要因子 |
| model_contribution | **模型贡献度** | 横向条形图 | 不写"SHAP" |
| model_contribution[].factor | 因子 | 图表标签 | |
| model_contribution[].contribution | 贡献份额 | 条形长度 | 0-1 |
| data_quality_flags | 数据质量提示 | 黄色警告条 | 缺失/proxy/OP |
| review_required | 需人工复核 | 红色标记 | true 时高亮 |
| model_status | 模型状态 | 模型信息卡 | approved_alpha/exploratory |
| interpretation_note | 解释声明 | 页脚 | 固定文案 |

### 模型注册表
```
GET /api/v1/models/registry
```
展示:模型版本、状态(approved/exploratory)、Spearman 指标。

## 2. 前端展示文案规范(禁止项)

| ❌ 禁止 | ✅ 应写 |
|---|---|
| SHAP 值 | 模型贡献度 |
| 障碍高度 | 关键障碍评分(KOS) |
| 因果影响 | 模型解释贡献 |
| x_missing_* | (不展示) |
| GEE proxy | (不展示为障碍) |
| site-level 泛化 | (不宣称) |

## 3. OP 场景提示文案
> "当前有机污染模型为探索性模型,建议结合规则筛查和人工复核。"

## 4. 甲方话术(报告/演示用)
> "系统采用规则诊断与模型解释结合。规则层负责判断是否构成障碍,模型层负责辅助识别对当前用途障碍指数贡献较大的因子,最终通过关键障碍综合评分输出排序。未检测但重要的指标不会被系统伪装成结论,而是列为补测建议。"

## 5. 现有前端页面接入状态(本轮)

| 页面 | 现状 | P4 接入需求 |
|---|---|---|
| ObstacleAnalysis.tsx | 调旧 diagnosis API(SHAP 二分类) | 改调 kos-diagnosis,展示三层输出 |
| SiteDetail.tsx | 不调诊断 API | 加"运行诊断"按钮 |
| ReconstructionAnalysis.tsx | 假 Top 因子 | 读 KOS Top 作限制因子 |
| RecommendationPage.tsx | — | 按 KOS 因子匹配技术库 |

**本轮未改前端 TSX(留下一轮),后端 API 已就绪可供前端调用。**
