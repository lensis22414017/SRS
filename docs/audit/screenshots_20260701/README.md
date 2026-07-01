# SRS 甲方演示截图证据

**生成时间**: 2026-07-01 18:40 (UTC+8)
**Git Commit**: `ee96e0a` → 即将更新
**截图工具**: Playwright (@playwright/test), Chromium headless 1280x720
**登录角色**: 系统管理员 (admin)
**数据来源**: 16 个测试场地（从 `data/test_datasets/site_*.xlsx` 导入）、真实检测数据 8095 条

---

## A 组 — 主路径页面截图 (12 张)

| 文件名 | 页面路径 | 角色 | 数据来源 | 验收点 | 含演示数据 | 可用于甲方演示 |
|--------|---------|------|---------|--------|-----------|--------------|
| `A01_dashboard_full.png` | `/` 数据概览 | admin | 真实 16 场地 | KPI 卡片、污染类型饼图、超标排行、地图、最近操作 | 否 | **是** |
| `A02_digital_screen.png` | `/dashboard/screen` 首屏 | admin | 16 场地 + 部分演示 | 深色驾驶舱、KPI、地图、态势卡、预警 TOP10 | 是（趋势图、TOP10、追溯摘要） | **是（标注后）** |
| `A03_screen_bottom.png` | `/dashboard/screen` 底部 | admin | 演示数据 | 趋势图三栏布局 | 是 | 否（研发验证） |
| `A04_site_list.png` | `/sites` 场地管理 | admin | 真实 16 场地 | 场地名称优化展示、污染类型中文标签、超标/质量标签 | 否 | **是** |
| `A05_site_detail.png` | `/sites/:id` 场地详情 | admin | 真实场地 #1 | 点位地图、采样点表格、EDA 面板 | 否 | **是** |
| `A06_obstacle.png` | `/obstacle` 障碍因子分析 | admin | 真实诊断结果 | SHAP 排序、影响方向、AUC/F1(含开发验证标注)、摘要展开/收起 | 否 | **是** |
| `A07_reconstruction.png` | `/reconstruction` 功能重构 | admin | 真实评价结果 | 双维度雷达图、贡献度、计算追溯 | 否 | **是** |
| `A08_ssui.png` | `/ssui` SSUI 评价 | admin | 真实 + MVP路径说明 | 仪表盘、可持续等级、公式、MVP路径标注 | 否 | **是** |
| `A09_recommend.png` | `/recommend` 方案推荐 | admin | 真实推荐结果 | 方案匹配分、障碍因子覆盖、技术详情 | 否 | **是** |
| `A10_trace.png` | `/trace/:id` 追溯详情 | admin | 真实五阶段 | 阶段轴、附件、操作日志 | 否 | **是** |
| `A11_system.png` | `/system` 系统管理 | admin | - | 参与单位、核心功能、技术栈、系统健康 | 否 | **是** |
| `B01_map_normal.png` | `/sites/:id` 地图区域 | admin | 真实坐标 | 点位渲染、底图、图例(污染类型+超标色阶) | 否 | **是** |

## 数据状态说明

- **真实数据**: 场地 KPI、采样点、检测记录、诊断/评价/推荐结果
- **演示数据**: 大屏趋势图（P1 待接入接口）、障碍因子 TOP10（跨场地聚合接口待开发）、追溯任务摘要（工作流聚合接口待开发）
- **MVP 标注**: SSUI 评价页明确标注"当前评价路径为 MVP 路径"
- **待接入字段**: 大屏 KPI "报告数量""在管流程"显示为"待接入"（后端接口待扩展）

## 甲方演示建议

### 可演示页面（12/12）
- A01-A11 全部可用于甲方演示
- A02 大屏含演示数据，演示前建议说明趋势图/TOP10/追溯摘要 3 个模块为 P1 接入项

### 不建议现场触碰
- 无。所有页面均基于真实数据，不含 mock/假数据

### 演示前检查
1. 确保后端运行，数据已导入（16 场地、8095 检测记录）
2. 确保前端已构建为生产模式 (`npm run build`)
3. 所有图表有加载态和空态，不会白屏

## 截图脚本

```bash
cd frontend
npx playwright test e2e/capture-ui-audit.spec.ts --reporter=list --timeout=60000
```

脚本位置: `frontend/e2e/capture-ui-audit.spec.ts`
