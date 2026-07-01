/**
 * UI Audit 截图脚本 — 甲方演示质量截图
 * 用法: npx playwright test e2e/capture-ui-audit.spec.ts --project=chromium
 */
import { test, expect } from "@playwright/test";
import path from "path";

const OUT = "C:\\Users\\曾鸿\\desktop\\SRS_test_screenshots";
const BASE = "http://localhost:5173";

async function login(page: any) {
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle" });
  await page.fill('input[id="username"]', "admin");
  await page.fill('input[id="password"]', "Demo@2026");
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);
  // Verify we're on a page after login (not still on /login)
  const url = page.url();
  if (url.includes("/login")) {
    // Retry once
    await page.fill('input[id="username"]', "admin");
    await page.fill('input[id="password"]', "Demo@2026");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
  }
}

test("A01 — Dashboard full", async ({ page }) => {
  await login(page);
  // CSS Module 会改变类名, 使用文本内容等待
  await page.waitForSelector('text=场地总数', { timeout: 15000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, "A01_dashboard_full.png"), fullPage: true });
});

test("A02 — Digital Screen", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/dashboard/screen`);
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(OUT, "A02_digital_screen.png"), fullPage: false });
});

test("A03 — Screen Bottom", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/dashboard/screen`);
  await page.waitForTimeout(2000);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, "A03_screen_bottom.png"), fullPage: false });
});

test("A04 — Site List", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites`);
  await page.waitForSelector("table", { timeout: 5000 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, "A04_site_list.png"), fullPage: true });
});

test("A05 — Site Detail", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites/1`);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "A05_site_detail.png"), fullPage: true });
});

test("A06 — Obstacle Analysis", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/obstacle`);
  await page.waitForTimeout(1000);
  // Click site picker and run
  await page.click(".ant-select"); await page.waitForTimeout(500);
  await page.click(".ant-select-item-option:first-child"); await page.waitForTimeout(500);
  await page.click('button:has-text("运行障碍因子诊断")');
  await page.waitForTimeout(8000);
  await page.screenshot({ path: path.join(OUT, "A06_obstacle.png"), fullPage: true });
});

test("A07 — Reconstruction", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/reconstruction`);
  await page.waitForTimeout(1000);
  await page.click(".ant-select"); await page.waitForTimeout(500);
  await page.click(".ant-select-item-option:first-child"); await page.waitForTimeout(500);
  await page.click('button:has-text("运行功能重构")');
  await page.waitForTimeout(8000);
  await page.screenshot({ path: path.join(OUT, "A07_reconstruction.png"), fullPage: true });
});

test("A08 — SSUI", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/ssui`);
  await page.waitForTimeout(1000);
  await page.click(".ant-select"); await page.waitForTimeout(500);
  await page.click(".ant-select-item-option:first-child"); await page.waitForTimeout(500);
  await page.click('button:has-text("运行 SSUI")');
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(OUT, "A08_ssui.png"), fullPage: true });
});

test("A09 — Recommend", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/recommend`);
  await page.waitForTimeout(1000);
  await page.click(".ant-select"); await page.waitForTimeout(500);
  await page.click(".ant-select-item-option:first-child"); await page.waitForTimeout(500);
  await page.click('button:has-text("运行方案推荐")');
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(OUT, "A09_recommend.png"), fullPage: true });
});

test("A10 — Trace Detail", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/trace`);
  await page.waitForSelector("table", { timeout: 5000 });
  await page.waitForTimeout(500);
  // Click first site's detail link
  await page.click("table a:first-child");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "A10_trace.png"), fullPage: true });
});

test("A11 — System", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/system`);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "A11_system.png"), fullPage: true });
});

test("B01 — Map Normal", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites/1`);
  await page.waitForTimeout(3000);
  await page.evaluate(() => { const el = document.querySelector(".leaflet-container"); if (el) el.scrollIntoView(); });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "B01_map_normal.png"), fullPage: false });
});

// ══════════════════════════════════════════════════════════
// C 组 — 数据导入 (6 张)
// ══════════════════════════════════════════════════════════

test("B02 — Map No Coordinates", async ({ page }) => {
  await login(page);
  // Site #16 (辽宁_HM+OP_16) likely has few coordinates
  await page.goto(`${BASE}/sites/18`);
  await page.waitForTimeout(3000);
  await page.evaluate(() => { const el = document.querySelector(".leaflet-container"); if (el) el.scrollIntoView(); });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "B02_map_no_coords.png"), fullPage: false });
});

test("B03 — Map Tooltip", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites/1`);
  await page.waitForTimeout(3000);
  await page.evaluate(() => { const el = document.querySelector(".leaflet-container"); if (el) el.scrollIntoView(); });
  await page.waitForTimeout(1000);
  // Click center of map where marker likely is
  const mapBox = await page.locator(".leaflet-container").boundingBox();
  if (mapBox) {
    await page.mouse.click(mapBox.x + mapBox.width / 3, mapBox.y + mapBox.height / 2);
    await page.waitForTimeout(1500);
  }
  await page.screenshot({ path: path.join(OUT, "B03_map_tooltip.png"), fullPage: false });
});

test("B04 — Map Risk Filter", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites/1`);
  await page.waitForTimeout(3000);
  await page.evaluate(() => { const el = document.querySelector(".leaflet-container"); if (el) el.scrollIntoView(); });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, "B04_map_filter.png"), fullPage: false });
});

test("C01 — Import Upload", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites/import`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, "C01_import_upload.png"), fullPage: true });
});

test("C02 — Import Wizard", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites/import/wizard`);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, "C02_import_wizard.png"), fullPage: true });
});

test("C03 — Import Success", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites/import`);
  await page.waitForTimeout(1000);
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles("C:\\Users\\曾鸿\\desktop\\SRS\\data\\test_datasets\\site_广东_HM_200点.xlsx");
  await page.waitForTimeout(1500);
  // Click import button (text varies by file count)
  const importBtn = page.locator('button:has-text("并校验")');
  if (await importBtn.count() > 0) {
    await importBtn.click();
    await page.waitForTimeout(15000);
  }
  await page.screenshot({ path: path.join(OUT, "C03_import_success.png"), fullPage: true });
});

test("C04 — Import Conflict New Version", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites/import`);
  await page.waitForTimeout(1000);
  // Select "作为新版本" radio for conflict strategy
  await page.click('text=作为新版本');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, "C04_import_new_version.png"), fullPage: true });
});

test("C05 — Import Batch", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/sites/import`);
  await page.waitForTimeout(1000);
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles([
    "C:\\Users\\曾鸿\\desktop\\SRS\\data\\test_datasets\\site_江西_HM_200点.xlsx",
    "C:\\Users\\曾鸿\\desktop\\SRS\\data\\test_datasets\\site_湖南_HM_200点.xlsx",
  ]);
  await page.waitForTimeout(2000);
  // Button text changes to "批量导入 2 个文件并校验"
  const btn = page.locator('button:has-text("批量导入")');
  if (await btn.count() > 0) {
    await btn.click();
    await page.waitForTimeout(20000);
  }
  await page.screenshot({ path: path.join(OUT, "C05_import_batch.png"), fullPage: true });
});

// ══════════════════════════════════════════════════════════
// D 组 — 报告生成 (5 张)
// ══════════════════════════════════════════════════════════

test("D01 — Report Generate Dialog", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/trace/1`);
  await page.waitForTimeout(2000);
  // Find and click report generate button
  const btn = page.locator('button:has-text("生成报告")');
  if (await btn.count() > 0) {
    await btn.first().click();
    await page.waitForTimeout(2000);
  }
  await page.screenshot({ path: path.join(OUT, "D01_report_generate.png"), fullPage: false });
});

test("D02 — Report Preview PDF", async ({ page }) => {
  await login(page);
  // Generate a report first via the reports list
  await page.goto(`${BASE}/trace/1`);
  await page.waitForTimeout(2000);
  // Look for report list or download link
  await page.screenshot({ path: path.join(OUT, "D02_report_preview.png"), fullPage: true });
});

test("D03 — Report Download", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/trace`);
  await page.waitForTimeout(1000);
  await page.click("table a:first-child");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "D03_report_download.png"), fullPage: true });
});

test("D04 — Report Map in Report", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/trace/1`);
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(OUT, "D04_report_map.png"), fullPage: true });
});

test("D05 — Report Traceability Archive", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/trace/1`);
  await page.waitForTimeout(2000);
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, "D05_report_trace.png"), fullPage: true });
});

// ══════════════════════════════════════════════════════════
// E 组 — 权限与空态 (5 张)
// ══════════════════════════════════════════════════════════

test("E01 — Login Admin", async ({ page }) => {
  await page.goto(`${BASE}/login`);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "E01_login_admin.png"), fullPage: false });
});

test("E02 — Enterprise Empty Site", async ({ page }) => {
  // Login as enterprise user
  await page.goto(`${BASE}/login`);
  await page.fill('input[id="username"]', "demo_enterprise");
  await page.fill('input[id="password"]', "Demo@2026");
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(OUT, "E02_enterprise_empty.png"), fullPage: true });
});

test("E03 — Permission 403", async ({ page }) => {
  await login(page);
  // Try to access admin-only page as enterprise... actually try as a non-admin
  await page.goto(`${BASE}/system`);
  await page.waitForTimeout(1500);
  // If we get a 403-like message, capture it
  await page.screenshot({ path: path.join(OUT, "E03_system_admin_view.png"), fullPage: false });
});

test("E04 — Register Page", async ({ page }) => {
  await page.goto(`${BASE}/register`);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "E04_register.png"), fullPage: false });
});

test("E05 — Forgot Password", async ({ page }) => {
  await page.goto(`${BASE}/forgot-password`);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "E05_forgot_password.png"), fullPage: false });
});

// ══════════════════════════════════════════════════════════
// F 组 — 大屏证据 (4 张)
// ══════════════════════════════════════════════════════════

test("F01 — Screen Demo Tags", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/dashboard/screen`);
  await page.waitForTimeout(2000);
  // Zoom to highlight the demo data tags on left panel
  await page.screenshot({ path: path.join(OUT, "F01_screen_demo_tags.png"), fullPage: false });
});

test("F02 — Screen Real KPI", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/dashboard/screen`);
  await page.waitForTimeout(2000);
  // Crop to KPI area by setting viewport small
  await page.setViewportSize({ width: 1280, height: 200 });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(OUT, "F02_screen_real_kpi.png"), fullPage: false });
  await page.setViewportSize({ width: 1280, height: 720 });
});

test("F03 — Screen Empty State", async ({ page }) => {
  // Access screen without login should show error or redirect
  await page.goto(`${BASE}/dashboard/screen`);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "F03_screen_unauthenticated.png"), fullPage: false });
});

test("F04 — Screen Back to Workspace", async ({ page }) => {
  await login(page);
  await page.goto(`${BASE}/dashboard/screen`);
  await page.waitForTimeout(2000);
  // Click back button
  await page.click('button:has-text("返回工作台")');
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(OUT, "F04_screen_back.png"), fullPage: true });
});
