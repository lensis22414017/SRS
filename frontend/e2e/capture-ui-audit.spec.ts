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
  // Scroll to map area
  await page.evaluate(() => { const el = document.querySelector(".leaflet-container"); if (el) el.scrollIntoView(); });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "B01_map_normal.png"), fullPage: false });
});
