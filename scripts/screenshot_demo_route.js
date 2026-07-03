// scripts/screenshot_demo_route.js — 第二阶段演示路线最终截图(8页)
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");
const BASE = "http://127.0.0.1:5173";
const OUT = "docs/audit/screenshots_demo_final";
fs.mkdirSync(OUT, { recursive: true });

async function login(page) {
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const inp = await page.$$('input');
  if (inp.length >= 2) { await inp[0].fill("admin"); await inp[1].fill("Demo@2026"); }
  const b = await page.$('button[type="submit"]'); if (b) await b.click();
  await page.waitForTimeout(3000);
}

async function pickSite(page, url) {
  await page.goto(BASE + url, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const sp = await page.$('.ant-select-selector');
  if (sp) { await sp.click(); await page.waitForTimeout(800);
    const o = await page.$('.ant-select-item-option');
    if (o) { await o.click(); await page.waitForTimeout(2000); } }
}

async function clickBtn(page, kw) {
  const btns = await page.$$('button');
  for (const b of btns) { const t = (await b.textContent())||'';
    if (t.includes(kw) && t.length < 20) { await b.click(); return true; } }
  return false;
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const shots = [];

  await login(page);

  // 1. 登录后概览
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "01_dashboard.png") });
  shots.push("01_dashboard");

  // 2. 场地列表
  await page.goto(BASE + "/sites", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "02_site_list.png") });
  shots.push("02_site_list");

  // 3. 场地详情(个旧)
  await page.goto(BASE + "/sites/1", { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(OUT, "03_site_detail.png") });
  shots.push("03_site_detail");

  // 4-5. 障碍分析 + KOS 生产诊断
  await pickSite(page, "/obstacle");
  let r = page.waitForResponse(x => x.url().includes('kos-diagnosis') && x.status()===200, {timeout:30000}).catch(()=>null);
  await clickBtn(page, "生产");
  await r;
  await page.waitForTimeout(4000);
  await page.evaluate(()=>{ const cs=document.querySelectorAll('.ant-card'); for(const c of cs){if(c.textContent.includes('关键障碍因子 Top-N')){c.scrollIntoView({block:'start'});break;}} });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "04_kos_prod_top5.png"), fullPage: true });
  shots.push("04_kos_prod_top5");

  // 6. KOS 生态
  r = page.waitForResponse(x => x.url().includes('kos-diagnosis') && x.status()===200, {timeout:30000}).catch(()=>null);
  await clickBtn(page, "生态");
  await r;
  await page.waitForTimeout(4000);
  await page.evaluate(()=>{ const cs=document.querySelectorAll('.ant-card'); for(const c of cs){if(c.textContent.includes('关键障碍因子 Top-N')){c.scrollIntoView({block:'start'});break;}} });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(OUT, "05_kos_eco_top5.png"), fullPage: true });
  shots.push("05_kos_eco_top5");

  // 7. 功能重构
  await pickSite(page, "/reconstruction");
  await clickBtn(page, "运行") || await clickBtn(page, "评价") || await clickBtn(page, "重构");
  await page.waitForTimeout(5000);
  await page.screenshot({ path: path.join(OUT, "06_reconstruction.png"), fullPage: true });
  shots.push("06_reconstruction");

  // 8. 方案推荐
  await pickSite(page, "/recommend");
  await clickBtn(page, "运行") || await clickBtn(page, "推荐");
  await page.waitForTimeout(6000);
  await page.screenshot({ path: path.join(OUT, "07_recommendation.png"), fullPage: true });
  shots.push("07_recommendation");

  // 9. 追溯
  await page.goto(BASE + "/trace/1", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "08_traceability.png") });
  shots.push("08_traceability");

  // 10. 权限隔离(enterprise 403)
  await ctx.clearCookies();
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const inp2 = await page.$$('input');
  if (inp2.length >= 2) { await inp2[0].fill("enterprise"); await inp2[1].fill("Demo@2026"); }
  const lb = await page.$('button[type="submit"]'); if (lb) await lb.click();
  await page.waitForTimeout(3000);
  await page.goto(BASE + "/sites/2", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(OUT, "09_permission_403.png") });
  shots.push("09_permission_403");

  await browser.close();

  // 校验大小
  const results = shots.map(s => {
    const fp = path.join(OUT, s + ".png");
    const sz = fs.existsSync(fp) ? fs.statSync(fp).size : 0;
    return { name: s, size: Math.round(sz/1024) + "KB", ok: sz > 15000 };
  });
  fs.writeFileSync(path.join(OUT, "manifest.json"), JSON.stringify(results, null, 2));
  const passed = results.filter(r => r.ok).length;
  console.log(`\n演示路线截图: ${passed}/${results.length} 非空通过`);
  results.forEach(r => console.log(`  ${r.ok?'✅':'❌'} ${r.name} (${r.size})`));
})();
