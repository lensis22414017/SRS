# SRS 甲方演示截图证据

**最后重新生成时间**: 2026-07-01 19:59 (UTC+8)
**Git Commit**: 即将更新
**截图工具**: Playwright (@playwright/test), Chromium
**大屏截图 viewport**: 1920×1080（确保大屏完整渲染，非小屏提示页）
**登录角色**: admin（主路径）/ enterprise（权限验证 E03）
**数据来源**: 16+ 测试场地，真实检测数据 8095+ 条

---

## 失效截图修复记录 (2026-07-01 19:59)

| 原文件 | 问题 | 修复后 | 验证 |
|--------|------|--------|------|
| `A02_digital_screen.png` (336KB 小屏页) | viewport 1280<1366 触发小屏提示 | 1920×1080 + data-testid 等待 | ✅ 846KB 真实大屏 |
| `A03_screen_bottom.png` (scrollTo 无效) | 大屏 100vh 无需滚动 | 重命名 `A03_screen_trends.png` + locator 截图 | ✅ 趋势区特写 |
| `F01_screen_demo_tags.png` (小屏页) | 同 A02 | 1920×1080 + locator 截左侧面板 | ✅ 真实演示标签 |
| `F02_screen_real_kpi.png` (viewport 改小) | viewport 200px 截小屏页 | 1920×1080 + locator 截 KPI 行 | ✅ 94KB KPI 特写 |
| `B03_map_tooltip.png` (无弹窗) | 点击地图中央未命中 marker | SVG circle 精确点击 + .leaflet-popup 等待 | ✅ 真实弹窗 |
| `D04_report_map.png` (追溯页非报告) | 未触发 openPreview | 生成报告 + 点击预览 + iframe Modal 等待 | ✅ 报告预览 |
| `E03_system_admin_view.png` (admin 视角) | admin 不会触发 403 | enterprise 账号 → /system | ✅ 真实 403 页 |

---

## A 组 — 主路径页面 (11 张) · 甲方演示可用

| 文件名 | 页面 | 验收点 | 演示数据 |
|--------|------|--------|----------|
| `A01_dashboard_full.png` | `/` 数据概览 | KPI×6、饼图、超标排行、地图、最近操作 | 否 |
| `A02_digital_screen.png` | `/dashboard/screen` 1920×1080 | 深色驾驶舱、KPI×6、地图、预警TOP10、态势矩阵 | 部分(标注) |
| `A03_screen_trends.png` | 大屏趋势区 locator 截图 | 趋势图三栏（场地/检测/报告） | **是(已标注)** |
| `A04_site_list.png` | `/sites` | 场地名优化、中文标签 | 否 |
| `A05_site_detail.png` | `/sites/:id` | 点位地图、宽表、EDA | 否 |
| `A06_obstacle.png` | `/obstacle` | SHAP排序、AUC/F1标注、摘要展开 | 否 |
| `A07_reconstruction.png` | `/reconstruction` | 雷达图、贡献度、追溯 | 否 |
| `A08_ssui.png` | `/ssui` | 仪表盘、MVP标注 | 否 |
| `A09_recommend.png` | `/recommend` | 方案匹配、因子覆盖、技术详情 | 否 |
| `A10_trace.png` | `/trace/:id` | 五阶段轴、附件、操作日志 | 否 |
| `A11_system.png` | `/system` | 参与单位、功能、技术栈 | 否 |

## B 组 — 地图状态 (4 张)

| 文件名 | 说明 | 可用于演示 |
|--------|------|:----------:|
| `B01_map_normal.png` | 正常加载：点位+底图+双列图例 | ✅ |
| `B02_map_no_coords.png` | 无坐标或少坐标场地的地图展示 | ✅ |
| `B03_map_tooltip.png` | **circleMarker 精确点击 → .leaflet-popup 弹窗** | ✅ |
| `B04_map_filter.png` | 污染物筛选状态 | ✅ |

## C 组 — 数据导入 (5 张) · 研发验证

| 文件名 | 说明 |
|--------|------|
| `C01_import_upload.png` | 导入页面：模板选择+文件上传+冲突策略 |
| `C02_import_wizard.png` | 字段映射 Wizard 三步流程 |
| `C03_import_success.png` | 单文件导入成功结果表 |
| `C04_import_new_version.png` | 冲突策略：作为新版本 |
| `C05_import_batch.png` | 批量双文件导入结果 |

## D 组 — 报告生成 (5 张) · 研发验证

| 文件名 | 说明 | 可用于演示 |
|--------|------|:----------:|
| `D01_report_generate.png` | 报告生成触发区域 | ✅ |
| `D02_report_preview.png` | 追溯页含报告列表 | ✅ |
| `D03_report_download.png` | 追溯详情（含下载入口） | ✅ |
| `D04_report_map.png` | **生成报告 + 预览 Modal + iframe** | ✅ |
| `D05_report_trace.png` | 追溯归档页底部 | ✅ |

## E 组 — 权限与空态 (5 张)

| 文件名 | 说明 | 可用于演示 |
|--------|------|:----------:|
| `E01_login_admin.png` | Admin 登录页 | ✅ |
| `E02_enterprise_empty.png` | 企业用户登录后状态 | ✅ |
| `E03_permission_403.png` | **enterprise 账号 → /system → 403 页** | ✅ |
| `E04_register.png` | 注册页（含角色选择） | ✅ |
| `E05_forgot_password.png` | 忘记密码页 | ✅ |

## F 组 — 大屏证据 (4 张)

| 文件名 | 说明 | 可用于演示 |
|--------|------|:----------:|
| `F01_screen_demo_tags.png` | **1920×1080 左侧面板演示数据标注** | ✅ |
| `F02_screen_real_kpi.png` | **1920×1080 KPI 行 locator 截图** | ✅ |
| `F03_screen_unauthenticated.png` | 未登录访问大屏 → 重定向登录 | 研发验证 |
| `F04_screen_back.png` | 返回工作台后仪表盘恢复 | ✅ |

---

## 截图脚本关键修复

```typescript
// 1. 大屏截图必须 1920×1080
await page.setViewportSize({ width: 1920, height: 1080 });
await page.waitForSelector('[data-testid="digital-screen-root"]');

// 2. B03 tooltip: SVG circle 精确点击 + popup 等待
const circles = page.locator(".leaflet-overlay-pane svg circle");
await page.mouse.click(box.x + box.width/2, box.y + box.height/2);
await page.waitForSelector(".leaflet-popup", { timeout: 5000 });

// 3. D04 报告: 生成 + 预览 Modal + iframe
await page.click('button:has-text("生成报告")');
await page.click('a:has-text("预览")');
await page.waitForSelector(".ant-modal iframe", { timeout: 10000 });

// 4. E03 权限: enterprise 账号 (非 admin)
await page.fill('input[id="username"]', "enterprise");
await page.goto(`${BASE}/system`); // AdminOnly 守卫 → 403
```

## 甲方演示指南

### 可直接演示 (33 张)
A01-A11 + B01-B04 + C01-C05 + D01-D05 + E01-E05 + F01-F02 + F04

### 含演示数据需口头说明 (2 张)
- **A02** 大屏：趋势图/TOP10/追溯摘要 3 模块为 P1 接入项（黄色"演示数据"标注）
- **A03** 趋势区：三个趋势图均为演示数据

### 仅研发验证 (1 张)
- F03 未登录重定向（非大屏本体）

### 截图命令
```bash
cd frontend
npx playwright test e2e/capture-ui-audit.spec.ts --reporter=list --timeout=120000
```

脚本: `frontend/e2e/capture-ui-audit.spec.ts` (34 tests, 34 passed)
