// scripts/screenshot_e2e.js — 一夜冲刺 E2E 截图(Playwright)
// 用法: node scripts/screenshot_e2e.js
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const BASE = "http://127.0.0.1:5173";
const OUT = "docs/audit/screenshots_20260703";
fs.mkdirSync(OUT, { recursive: true });

const SHOTS = [
  { name: "login_admin", url: "/", desc: "登录页", action: async (page) => {
    await page.waitForSelector('input', { timeout: 10000 });
    await page.fill('input[type="text"], input[id*="user"], input[placeholder*="账号"]', "admin");
    await page.fill('input[type="password"]', "Demo@2026");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
  }},
  { name: "dashboard_overview", url: "/", desc: "数据概览" },
  { name: "site_list", url: "/sites", desc: "场地管理" },
  { name: "site_detail", url: "/site/1", desc: "场地详情" },
  { name: "obstacle_analysis", url: "/obstacle", desc: "障碍因子分析", action: async (page) => {
    await page.waitForTimeout(2000);
    // 选场地(如果有 SitePicker)
    try {
      await page.click('.ant-select-selector', { timeout: 5000 });
      await page.waitForTimeout(500);
      await page.click('.ant-select-item-option:first-child', { timeout: 3000 });
      await page.waitForTimeout(1000);
    } catch(e) {}
    // 点 KOS 生产诊断按钮
    try {
      const btns = await page.$$('button');
      for (const b of btns) {
        const txt = await b.textContent();
        if (txt.includes('生产用途诊断') && txt.includes('KOS')) {
          await b.click();
          break;
        }
      }
      await page.waitForTimeout(5000);
    } catch(e) {}
  }},
  { name: "kos_top5", url: "/obstacle", desc: "KOS关键障碍Top5" },
  { name: "recommended_tests", url: "/obstacle", desc: "建议补测" },
  { name: "reconstruction_eval", url: "/reconstruction", desc: "功能重构分析" },
  { name: "ssui_eval", url: "/ssui", desc: "SSUI评价" },
  { name: "recommendation_result", url: "/recommendation", desc: "方案推荐" },
  { name: "traceability_list", url: "/trace", desc: "追溯列表" },
  { name: "model_health", url: "/system", desc: "系统管理/模型" },
  { name: "client_demo_route", url: "/", desc: "甲方演示入口" },
];

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const results = [];

  for (const s of SHOTS) {
    try {
      await page.goto(BASE + s.url, { waitUntil: "networkidle", timeout: 20000 });
      await page.waitForTimeout(1500);
      if (s.action) { try { await s.action(page); } catch(e) { console.log(`  [action err ${s.name}] ${e.message.slice(0,80)}`); } }
      const fp = path.join(OUT, s.name + ".png");
      await page.screenshot({ path: fp, fullPage: false });
      const sz = fs.statSync(fp).size;
      results.push({ name: s.name, status: "✅", size: Math.round(sz/1024) + "KB" });
      console.log(`✅ ${s.name} (${Math.round(sz/1024)}KB)`);
    } catch (e) {
      results.push({ name: s.name, status: "❌", error: e.message.slice(0, 100) });
      console.log(`❌ ${s.name}: ${e.message.slice(0, 100)}`);
    }
  }

  await browser.close();
  // 写结果
  fs.writeFileSync(path.join(OUT, "e2e_results.json"), JSON.stringify(results, null, 2));
  const passed = results.filter(r => r.status === "✅").length;
  console.log(`\nE2E 截图: ${passed}/${results.length} 成功`);
})();
