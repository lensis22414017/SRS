// scripts/screenshot_p0_round4.js — P0 PATCH 截图(指定round4文件名)
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const BASE = "http://127.0.0.1:5173";
const OUT = "docs/audit/screenshots_20260703_round4";
fs.mkdirSync(OUT, { recursive: true });

async function login(page) {
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const inp = await page.$$('input');
  if (inp.length >= 2) { await inp[0].fill("admin"); await inp[1].fill("Demo@2026"); }
  const b = await page.$('button[type="submit"]'); if (b) await b.click();
  await page.waitForTimeout(3000);
}

async function selectFirstSite(page, url) {
  await page.goto(BASE + url, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const picker = await page.$('.ant-select-selector');
  if (picker) { await picker.click(); await page.waitForTimeout(800);
    const o = await page.$('.ant-select-item-option');
    if (o) { await o.click(); await page.waitForTimeout(2000); return true; } }
  return false;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  await login(page);

  // ── P0-1: KOS 诊断截图 ──
  await selectFirstSite(page, "/obstacle");
  // 生产轨
  let kosResp = page.waitForResponse(r => r.url().includes('kos-diagnosis') && r.status()===200, {timeout:30000}).catch(()=>null);
  const btns1 = await page.$$('button');
  for (const b of btns1) { const t=(await b.textContent())||''; if(t.includes('生产')&&t.includes('KOS')){await b.click();break;} }
  const r1 = await kosResp;
  await page.waitForTimeout(4000);
  await page.evaluate(()=>{ const cs=document.querySelectorAll('.ant-card'); for(const c of cs){if(c.textContent.includes('关键障碍因子 Top-N')){c.scrollIntoView({block:'start'});break;}} });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "diagnosis_prod_result_top5_round4.png"), fullPage: true });
  console.log("✅ diagnosis_prod_result_top5_round4.png");

  // 四层面板单独截
  await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
  await page.waitForTimeout(500);
  await page.evaluate(()=>{ const cs=document.querySelectorAll('.ant-card'); for(const c of cs){if(c.textContent.includes('关键障碍因子')){c.scrollIntoView({block:'center'});break;}} });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "kos_four_layer_panel_round4.png") });
  console.log("✅ kos_four_layer_panel_round4.png");

  // 生态轨
  let kosResp2 = page.waitForResponse(r => r.url().includes('kos-diagnosis') && r.status()===200, {timeout:30000}).catch(()=>null);
  const btns2 = await page.$$('button');
  for (const b of btns2) { const t=(await b.textContent())||''; if(t.includes('生态')&&t.includes('KOS')){await b.click();break;} }
  await kosResp2;
  await page.waitForTimeout(4000);
  await page.evaluate(()=>{ const cs=document.querySelectorAll('.ant-card'); for(const c of cs){if(c.textContent.includes('关键障碍因子 Top-N')){c.scrollIntoView({block:'start'});break;}} });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "diagnosis_eco_result_top5_round4.png"), fullPage: true });
  console.log("✅ diagnosis_eco_result_top5_round4.png");

  // ── P0-2: Recommendation ──
  await selectFirstSite(page, "/recommendation");
  const btns3 = await page.$$('button');
  for (const b of btns3) { const t=(await b.textContent())||''; if(t.includes('运行')||t.includes('推荐')){await b.click();await page.waitForTimeout(4000);break;} }
  await page.screenshot({ path: path.join(OUT, "recommendation_reads_kos_round4.png"), fullPage: true });
  const htmlRec = await page.content();
  console.log(`✅ recommendation_reads_kos_round4.png (based_on_factors: ${htmlRec.includes('based_on')||htmlRec.includes('因子')})`);

  // ── P0-3: Reconstruction ──
  await selectFirstSite(page, "/reconstruction");
  const btns4 = await page.$$('button');
  for (const b of btns4) { const t=(await b.textContent())||''; if(t.includes('运行')||t.includes('评价')||t.includes('重构')){await b.click();await page.waitForTimeout(5000);break;} }
  await page.screenshot({ path: path.join(OUT, "reconstruction_reads_kos_round4.png"), fullPage: true });
  const htmlRec2 = await page.content();
  console.log(`✅ reconstruction_reads_kos_round4.png (limiting: ${htmlRec2.includes('限制因子')}, KOS因子: ${htmlRec2.includes('Pb')||htmlRec2.includes('Cu')||htmlRec2.includes('As')})`);

  await browser.close();
  console.log("\nP0 截图完成");
})();
