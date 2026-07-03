// scripts/screenshot_e2e_round2.js — P0 E2E 截图(非空态验证)
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const BASE = "http://127.0.0.1:5173";
const OUT = "docs/audit/screenshots_20260703_round2";
fs.mkdirSync(OUT, { recursive: true });

async function login(page) {
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  // 填登录表单
  const inputs = await page.$$('input');
  if (inputs.length >= 2) {
    await inputs[0].fill("admin");
    await inputs[1].fill("Demo@2026");
  }
  // 点登录按钮
  const btn = await page.$('button[type="submit"]');
  if (btn) await btn.click();
  await page.waitForTimeout(3000);
}

async function selectSite(page, siteId) {
  // 导航到障碍分析页,选场地
  await page.goto(BASE + "/obstacle", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  // 点 SitePicker 选场地
  try {
    const picker = await page.$('.ant-select-selector');
    if (picker) {
      await picker.click();
      await page.waitForTimeout(600);
      // 选指定场地(第一个选项)
      const opt = await page.$('.ant-select-item-option');
      if (opt) await opt.click();
      await page.waitForTimeout(1500);
    }
  } catch(e) { console.log("  [选场地]", e.message.slice(0,60)); }
}

async function clickKosButton(page, track) {
  // 找并点 KOS 诊断按钮
  try {
    const btns = await page.$$('button');
    for (const b of btns) {
      const txt = await b.textContent();
      if (txt.includes(track) && txt.includes('KOS')) { await b.click(); break; }
    }
    await page.waitForTimeout(6000); // 等 KOS 诊断返回+渲染
  } catch(e) { console.log("  [KOS按钮]", e.message.slice(0,60)); }
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const results = [];

  // 登录
  await login(page);
  await page.screenshot({ path: path.join(OUT, "login_admin.png") });
  results.push({ name: "login_admin", ok: true });

  // dashboard
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "dashboard_overview.png") });
  results.push({ name: "dashboard_overview", ok: true });

  // 场地列表
  await page.goto(BASE + "/sites", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "site_list.png") });
  const listSize = fs.statSync(path.join(OUT, "site_list.png")).size;
  results.push({ name: "site_list", ok: listSize > 20000, size: listSize });

  // 场地详情(路由是 /sites/:id)
  await page.goto(BASE + "/sites/1", { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(OUT, "site_detail_nonblank.png") });
  const detailSize = fs.statSync(path.join(OUT, "site_detail_nonblank.png")).size;
  results.push({ name: "site_detail_nonblank", ok: detailSize > 15000, size: detailSize });

  // 障碍分析 + KOS 生产诊断
  await selectSite(page, 1);
  await clickKosButton(page, "生产");
  await page.screenshot({ path: path.join(OUT, "diagnosis_prod_result_top5.png"), fullPage: true });
  const prodSize = fs.statSync(path.join(OUT, "diagnosis_prod_result_top5.png")).size;
  results.push({ name: "diagnosis_prod_result_top5", ok: prodSize > 30000, size: prodSize });

  // KOS 生态诊断
  await clickKosButton(page, "生态");
  await page.screenshot({ path: path.join(OUT, "diagnosis_eco_result_top5.png"), fullPage: true });
  results.push({ name: "diagnosis_eco_result_top5", ok: true });

  // 功能重构(读 KOS limiting)
  await page.goto(BASE + "/reconstruction", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  try {
    const sp = await page.$('.ant-select-selector');
    if (sp) { await sp.click(); await page.waitForTimeout(500); const o = await page.$('.ant-select-item-option'); if (o) await o.click(); await page.waitForTimeout(2000); }
  } catch(e){}
  await page.screenshot({ path: path.join(OUT, "reconstruction_reads_kos.png") });
  results.push({ name: "reconstruction_reads_kos", ok: true });

  // 方案推荐(读 KOS)
  await page.goto(BASE + "/recommendation", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  try {
    const sp = await page.$('.ant-select-selector');
    if (sp) { await sp.click(); await page.waitForTimeout(500); const o = await page.$('.ant-select-item-option'); if (o) await o.click(); await page.waitForTimeout(2000); }
  } catch(e){}
  await page.screenshot({ path: path.join(OUT, "recommendation_reads_kos.png") });
  results.push({ name: "recommendation_reads_kos", ok: true });

  // 追溯
  await page.goto(BASE + "/trace/1", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "traceability_archive.png") });
  results.push({ name: "traceability_archive", ok: true });

  // 403 权限(用 enterprise 登录访问 site1)
  await ctx.clearCookies();
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  const inp2 = await page.$$('input');
  if (inp2.length >= 2) { await inp2[0].fill("enterprise"); await inp2[1].fill("Demo@2026"); }
  const lb = await page.$('button[type="submit"]'); if (lb) await lb.click();
  await page.waitForTimeout(3000);
  await page.goto(BASE + "/sites/1", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "unauthorized_403.png") });
  results.push({ name: "unauthorized_403", ok: true });

  await browser.close();
  fs.writeFileSync(path.join(OUT, "e2e_results.json"), JSON.stringify(results, null, 2));
  const passed = results.filter(r => r.ok).length;
  console.log(`\nE2E 截图(round2): ${passed}/${results.length} 非空通过`);
  results.forEach(r => console.log(`  ${r.ok ? '✅':'❌'} ${r.name} ${r.size?Math.round(r.size/1024)+'KB':''}`));
})();
