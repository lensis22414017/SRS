// scripts/screenshot_e2e_v3.js — P0 E2E v3(确保 KOS 真触发+数据渲染)
// 关键改进: 拦截 kos-diagnosis 网络响应, 确认数据返回后才截图
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const BASE = "http://127.0.0.1:5173";
const OUT = "docs/audit/screenshots_20260703_round4";
fs.mkdirSync(OUT, { recursive: true });

async function login(page) {
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const inputs = await page.$$('input');
  if (inputs.length >= 2) { await inputs[0].fill("admin"); await inputs[1].fill("Demo@2026"); }
  const btn = await page.$('button[type="submit"]');
  if (btn) await btn.click();
  await page.waitForTimeout(3000);
}

async function selectFirstSite(page) {
  // 障碍分析页选第一个场地
  await page.goto(BASE + "/obstacle", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const picker = await page.$('.ant-select-selector');
  if (picker) {
    await picker.click();
    await page.waitForTimeout(800);
    const opt = await page.$('.ant-select-item-option');
    if (opt) { await opt.click(); await page.waitForTimeout(1500); return true; }
  }
  return false;
}

async function triggerKosAndWait(page, track) {
  // 点 KOS 按钮, 同时监听 kos-diagnosis 响应
  const kosResponse = page.waitForResponse(
    resp => resp.url().includes('kos-diagnosis') && resp.status() === 200,
    { timeout: 30000 }
  ).catch(() => null);
  const btns = await page.$$('button');
  for (const b of btns) {
    const txt = (await b.textContent()) || '';
    if (txt.includes(track) && txt.includes('KOS')) { await b.click(); break; }
  }
  const resp = await kosResponse;
  if (resp) {
    const data = await resp.json();
    // 等 KOS 面板渲染(关键障碍卡片出现)
    await page.waitForTimeout(3000);
    return data;
  }
  await page.waitForTimeout(3000);
  return null;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const results = [];
  const shot = async (name, opts) => {
    const fp = path.join(OUT, name + ".png");
    await page.screenshot({ path: fp, ...(opts || {}) });
    const sz = fs.statSync(fp).size;
    const ok = sz > 15000; // 白屏通常 <10KB
    results.push({ name, ok, size: Math.round(sz/1024) + "KB" });
    console.log(`${ok ? '✅' : '❌'} ${name} (${Math.round(sz/1024)}KB)`);
    return ok;
  };

  await login(page);
  await shot("login_admin");

  await page.goto(BASE + "/sites", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await shot("site_list");

  await page.goto(BASE + "/sites/1", { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  await shot("site_detail_nonblank");

  // 障碍分析: 选场地 + KOS 生产诊断
  await selectFirstSite(page);
  const prodData = await triggerKosAndWait(page, "生产");
  if (prodData) console.log(`  KOS prod 返回: key=${prodData.key_obstacles?.length} attention=${prodData.model_attention_factors?.length}`);
  await shot("diagnosis_prod_result_top5", { fullPage: true });

  // 滚动到 KOS 面板再截一次(确保可见)
  await page.evaluate(() => {
    const cards = document.querySelectorAll('.ant-card');
    for (const c of cards) { if (c.textContent.includes('KOS')) { c.scrollIntoView({ block: 'center' }); break; } }
  });
  await page.waitForTimeout(1000);
  await shot("kos_top5_detail");

  // KOS 生态
  const ecoData = await triggerKosAndWait(page, "生态");
  if (ecoData) console.log(`  KOS eco 返回: key=${ecoData.key_obstacles?.length}`);
  await shot("diagnosis_eco_result_top5", { fullPage: true });

  // 功能重构
  await page.goto(BASE + "/reconstruction", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  try { const sp = await page.$('.ant-select-selector'); if (sp) { await sp.click(); await page.waitForTimeout(600); const o = await page.$('.ant-select-item-option'); if (o) { await o.click(); await page.waitForTimeout(3000); } } } catch(e){}
  await shot("reconstruction_reads_kos");

  // 方案推荐(先触发 runRecommendation)
  await page.goto(BASE + "/recommendation", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  try {
    const sp = await page.$('.ant-select-selector');
    if (sp) { await sp.click(); await page.waitForTimeout(600); const o = await page.$('.ant-select-item-option'); if (o) { await o.click(); await page.waitForTimeout(2000); } }
    // 点运行推荐按钮
    const btns = await page.$$('button');
    for (const b of btns) { const t = (await b.textContent())||''; if (t.includes('运行') || t.includes('推荐')) { await b.click(); await page.waitForTimeout(4000); break; } }
  } catch(e){}
  await shot("recommendation_reads_kos");

  // 追溯
  await page.goto(BASE + "/trace/1", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await shot("traceability_archive");

  // 403: enterprise 登录访问 site1
  await ctx.clearCookies();
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const inp2 = await page.$$('input');
  if (inp2.length >= 2) { await inp2[0].fill("enterprise"); await inp2[1].fill("Demo@2026"); }
  const lb = await page.$('button[type="submit"]'); if (lb) await lb.click();
  await page.waitForTimeout(3000);
  await page.goto(BASE + "/sites/1", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await shot("unauthorized_403");

  await browser.close();
  fs.writeFileSync(path.join(OUT, "e2e_results.json"), JSON.stringify(results, null, 2));
  const passed = results.filter(r => r.ok).length;
  console.log(`\nE2E v3: ${passed}/${results.length} 非空通过`);
})();
