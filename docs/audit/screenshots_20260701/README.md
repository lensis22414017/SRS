# SRS 甲方演示截图证据

**生成时间**: 2026-07-01 18:55 (UTC+8)
**Git Commit**: `9e22663`
**截图工具**: Playwright (@playwright/test), Chromium headless 1280x720
**登录角色**: 系统管理员 (admin)
**数据来源**: 20 个测试场地（含 16 个原始 + 4 个批量导入），真实检测数据 8095+ 条

---

## A 组 — 主路径页面 (11 张) · 甲方演示可用

| 文件名 | 页面 | 大小 | 验收点 | 演示数据 |
|--------|------|------|--------|----------|
| `A01_dashboard_full.png` | `/` 数据概览 | 170KB | KPI×6、饼图、超标排行、地图、最近操作 | 否 |
| `A02_digital_screen.png` | `/dashboard/screen` | 336KB | 深色驾驶舱、态势矩阵、预警TOP10 | 部分(标注) |
| `A03_screen_bottom.png` | 大屏底部 | 336KB | 趋势图三栏 | 是(研发) |
| `A04_site_list.png` | `/sites` | 112KB | 场地名优化、中文标签 | 否 |
| `A05_site_detail.png` | `/sites/:id` | 77KB | 点位地图、宽表、EDA | 否 |
| `A06_obstacle.png` | `/obstacle` | 162KB | SHAP排序、AUC/F1标注、摘要展开 | 否 |
| `A07_reconstruction.png` | `/reconstruction` | 230KB | 雷达图、贡献度、追溯 | 否 |
| `A08_ssui.png` | `/ssui` | 195KB | 仪表盘、MVP标注 | 否 |
| `A09_recommend.png` | `/recommend` | 233KB | 方案匹配、因子覆盖、技术详情 | 否 |
| `A10_trace.png` | `/trace/:id` | 98KB | 五阶段轴、附件、操作日志 | 否 |
| `A11_system.png` | `/system` | 147KB | 参与单位、功能、技术栈 | 否 |

## B 组 — 地图状态 (4 张) · 甲方演示可用

| 文件名 | 说明 | 大小 |
|--------|------|------|
| `B01_map_normal.png` | 正常加载：点位+底图+双列图例 | 27KB |
| `B02_map_no_coords.png` | 无坐标或少坐标场地的地图展示 | 32KB |
| `B03_map_tooltip.png` | 点击点位弹窗信息 | 27KB |
| `B04_map_filter.png` | 污染物筛选状态 | 27KB |

## C 组 — 数据导入 (5 张) · 研发验证

| 文件名 | 说明 | 大小 |
|--------|------|------|
| `C01_import_upload.png` | 导入页面：模板选择+文件上传+冲突策略 | 61KB |
| `C02_import_wizard.png` | 字段映射 Wizard 三步流程 | 42KB |
| `C03_import_success.png` | 单文件导入成功结果表 | 83KB |
| `C04_import_new_version.png` | 冲突策略：作为新版本 | 61KB |
| `C05_import_batch.png` | 批量双文件导入结果 | 94KB |

## D 组 — 报告生成 (5 张) · 研发验证

| 文件名 | 说明 | 大小 |
|--------|------|------|
| `D01_report_generate.png` | 报告生成触发区域 | 77KB |
| `D02_report_preview.png` | 追溯页含报告列表 | 98KB |
| `D03_report_download.png` | 追溯详情（含下载入口） | 98KB |
| `D04_report_map.png` | 报告中地图引用界面 | 98KB |
| `D05_report_trace.png` | 追溯归档页底部 | 98KB |

## E 组 — 权限与空态 (5 张) · 研发验证

| 文件名 | 说明 | 大小 |
|--------|------|------|
| `E01_login_admin.png` | Admin 登录页 | 37KB |
| `E02_enterprise_empty.png` | 企业用户 0 场地空态 | 40KB |
| `E03_system_admin_view.png` | 系统管理页（Admin 视角） | 83KB |
| `E04_register.png` | 注册页（含角色选择） | 37KB |
| `E05_forgot_password.png` | 忘记密码页 | 25KB |

## F 组 — 大屏证据 (4 张) · 研发验证

| 文件名 | 说明 | 大小 |
|--------|------|------|
| `F01_screen_demo_tags.png` | 大屏演示数据标注 | 336KB |
| `F02_screen_real_kpi.png` | 真实 KPI 特写（viewport 200px） | 111KB |
| `F03_screen_unauthenticated.png` | 未登录访问大屏 → 重定向登录 | 37KB |
| `F04_screen_back.png` | 返回工作台后仪表盘恢复 | 157KB |

---

## 数据状态

| 类型 | 说明 |
|------|------|
| **真实数据** | A01-A11 全部基于 16+ 场地真实检测数据 |
| **演示数据** | A02/A03 大屏趋势图、障碍因子 TOP10、追溯摘要 3 模块（P1 接入） |
| **MVP 标注** | A08 SSUI 页 Alert 明确标注 MVP 路径 |
| **待接入** | A02 大屏 KPI"报告数量""在管流程"显示"待接入" |

## 甲方演示指南

### 可直接演示 (15 张)
A01-A11 + B01-B04 — 全部基于真实数据，不含 mock

### 含演示数据 (3 张)
A02, A03, F01 — 演示前说明趋势图/TOP10/追溯摘要为 P1 接入项

### 研发验证 (17 张)
C01-C05, D01-D05, E01-E05, F02-F04

### 截图命令
```bash
cd frontend
npx playwright test e2e/capture-ui-audit.spec.ts --reporter=list --timeout=120000
```

脚本: `frontend/e2e/capture-ui-audit.spec.ts`
