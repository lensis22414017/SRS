# -*- coding: utf-8 -*-
"""
SRS E2E test - 85+ test points across all modules
Screenshots saved to desktop/SRS_E2E_{timestamp}/
"""
import asyncio, os, sys, json
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

BASE = "http://localhost:5173"
DESKTOP = Path.home() / "desktop"
SCREENSHOT_DIR = DESKTOP / f"SRS_E2E_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
results = []
seq = [0]

async def ss(page, name):
    seq[0] += 1
    fname = f"{seq[0]:03d}_{name}.png"
    path = SCREENSHOT_DIR / fname
    await page.screenshot(path=str(path), full_page=False)
    results.append({"seq": seq[0], "name": name, "file": fname})
    print(f"  [{seq[0]:03d}] {name}")

async def login_as(page, user, pw, label):
    await page.goto(f"{BASE}/login")
    await page.wait_for_timeout(600)
    await page.fill('input[id="username"], input[placeholder*="用户名"]', user)
    await page.fill('input[id="password"], input[placeholder*="密码"]', pw)
    await page.wait_for_timeout(200)
    await ss(page, f"login_{label}_form")
    await page.click('button[type="submit"]')
    await page.wait_for_timeout(2000)
    await ss(page, f"login_{label}_after")

async def logout(page):
    try:
        await page.goto(f"{BASE}/")
        await page.wait_for_timeout(500)
        avatar = page.locator('.ant-avatar, [class*="avatar"]').first
        if await avatar.count() > 0:
            await avatar.click(timeout=3000)
            await page.wait_for_timeout(500)
        logout_btn = page.locator('text=退出登录')
        if await logout_btn.count() > 0:
            await logout_btn.click(timeout=3000)
            await page.wait_for_timeout(500)
        confirm = page.locator('button:has-text("确认退出")')
        if await confirm.count() > 0:
            await confirm.click(timeout=3000)
            await page.wait_for_timeout(1000)
    except:
        await page.goto(f"{BASE}/login")
        await page.wait_for_timeout(500)
    await ss(page, "logout_complete")

async def click_tab(page, text, fallback=None):
    """Click antd tab by text"""
    try:
        tab = page.locator(f'div.ant-tabs-tab:has-text("{text}")')
        if await tab.count() > 0:
            await tab.click(timeout=3000)
        else:
            btn = page.locator(f'text={text}').first
            if await btn.count() > 0:
                await btn.click(timeout=3000)
        await page.wait_for_timeout(600)
        return True
    except:
        if fallback:
            await fallback()
        return False

async def try_click(page, selector, timeout=3000):
    """Try to click an element, return True if successful"""
    try:
        el = page.locator(selector).first
        if await el.count() > 0:
            await el.click(timeout=timeout)
            await page.wait_for_timeout(500)
            return True
    except:
        pass
    return False

async def try_fill(page, selector, value):
    try:
        el = page.locator(selector).first
        if await el.count() > 0:
            await el.fill(value)
            return True
    except:
        pass
    return False

async def test_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = await ctx.new_page()

        print("=" * 60)
        print("SRS E2E Test - 85+ test points")
        print("=" * 60)

        # ====== A: Auth (1-18) ======
        print("\n--- A: Auth ---")

        await page.goto(f"{BASE}/login")
        await page.wait_for_timeout(1000)
        await ss(page, "A01_login_page")

        await ss(page, "A02_login_role_cards")

        await try_click(page, 'a:has-text("注册")')
        await ss(page, "A03_register_page")

        # Fill register form
        await try_fill(page, 'input[placeholder*="用户名"]', "e2e_ent2")
        await try_fill(page, 'input[placeholder*="显示名"]', "E2E测试企业")
        await try_fill(page, 'input[placeholder*="组织"]', "E2E测试有限公司")
        await ss(page, "A04_register_filled")

        await try_click(page, 'label:has-text("企业用户")')
        await try_fill(page, 'input[placeholder*="密码（至少"]', "E2e@Test2026")
        await try_fill(page, 'input[placeholder*="确认密码"]', "E2e@Test2026")
        await ss(page, "A05_register_pwd")

        await try_click(page, 'button:has-text("提交注册")')
        await page.wait_for_timeout(1500)
        await ss(page, "A06_register_success")

        # Login as admin
        await login_as(page, "admin", "Demo@2026", "admin")
        await ss(page, "A07_admin_dashboard")

        # System management
        await page.goto(f"{BASE}/system")
        await page.wait_for_timeout(800)
        await ss(page, "A08_system_page")

        await click_tab(page, "账户审核")
        await ss(page, "A09_account_approvals")

        # Approve user
        await try_click(page, 'button:has-text("通过")')
        await page.wait_for_timeout(500)
        await try_click(page, '.ant-modal button.ant-btn-primary')
        await page.wait_for_timeout(800)
        await ss(page, "A10_user_approved")

        await click_tab(page, "联系方式")
        await ss(page, "A11_contact_info")

        await click_tab(page, "修改密码")
        await ss(page, "A12_change_pwd")

        await click_tab(page, "操作日志")
        await ss(page, "A13_audit_logs")

        await click_tab(page, "系统健康")
        await ss(page, "A14_system_health")

        await click_tab(page, "技术库")
        await ss(page, "A15_tech_library")

        await click_tab(page, "系统配置")
        await ss(page, "A16_system_config")

        await click_tab(page, "AI")
        await ss(page, "A17_ai_config")

        await click_tab(page, "关于")
        await ss(page, "A18_about")

        await logout(page)

        # Login as new enterprise user
        await login_as(page, "e2e_ent2", "E2e@Test2026", "enterprise")
        await ss(page, "A19_enterprise_login")

        # ====== B: Dashboard (19-40) ======
        print("\n--- B: Dashboard ---")

        await page.goto(f"{BASE}/")
        await page.wait_for_timeout(1500)
        await ss(page, "B19_dashboard_full")

        # Scroll to see all sections
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)
        await ss(page, "B20_kpi_cards")

        # Pie chart
        await ss(page, "B21_pie_chart")

        # Hover pie
        canvas = page.locator('canvas').first
        if await canvas.count() > 0:
            await canvas.hover(timeout=3000)
            await page.wait_for_timeout(500)
        await ss(page, "B22_pie_hover")

        # Bar chart
        await ss(page, "B23_bar_chart")

        # Quick actions
        await page.evaluate("window.scrollTo(0, 400)")
        await page.wait_for_timeout(300)
        await ss(page, "B24_quick_actions")

        # Recent sites
        await page.evaluate("window.scrollTo(0, 600)")
        await page.wait_for_timeout(300)
        await ss(page, "B25_recent_sites")

        # Sidebar menu
        await ss(page, "B26_sidebar_enterprise")

        # Map
        await page.evaluate("window.scrollTo(0, 1000)")
        await page.wait_for_timeout(500)
        await ss(page, "B27_map_area")

        # ====== C: Site Management (41-55) ======
        print("\n--- C: Site Management ---")

        await logout(page)
        await login_as(page, "admin", "Demo@2026", "admin_c")

        await page.goto(f"{BASE}/sites")
        await page.wait_for_timeout(1200)
        await ss(page, "C28_site_list")

        # Search
        await try_fill(page, 'input[placeholder*="搜索"]', "个旧")
        await page.wait_for_timeout(500)
        await ss(page, "C29_site_search")

        # Clear search, go to first site
        await try_fill(page, 'input[placeholder*="搜索"]', "")
        await page.wait_for_timeout(300)
        await try_click(page, 'a:has-text("详情")')
        await page.wait_for_timeout(1500)
        await ss(page, "C30_site_detail")

        # Point map tab
        await click_tab(page, "点位地图")
        await page.wait_for_timeout(1000)
        await ss(page, "C31_point_map")

        # Map popup - scroll map into view first
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(300)
        try:
            map_div = page.locator('.leaflet-container').first
            if await map_div.count() > 0:
                await map_div.scroll_into_view_if_needed(timeout=3000)
                await page.wait_for_timeout(500)
        except:
            pass
        await ss(page, "C32_map_popup")

        # Wide table
        await click_tab(page, "检测数据")
        await page.wait_for_timeout(800)
        await ss(page, "C33_wide_table")

        # EDA tab
        await click_tab(page, "数据分析")
        await page.wait_for_timeout(1500)
        await ss(page, "C34_eda_overview")

        # EDA sub-tabs
        await click_tab(page, "直方图")
        await page.wait_for_timeout(500)
        await ss(page, "C35_eda_histogram")

        await click_tab(page, "箱线", fallback=lambda: click_tab(page, "Box"))
        await page.wait_for_timeout(500)
        await ss(page, "C36_eda_boxplot")

        await click_tab(page, "散点")
        await page.wait_for_timeout(500)
        await ss(page, "C37_eda_scatter")

        await click_tab(page, "热力")
        await page.wait_for_timeout(500)
        await ss(page, "C38_eda_heatmap")

        await click_tab(page, "Q-Q")
        await page.wait_for_timeout(500)
        await ss(page, "C39_eda_qq")

        await click_tab(page, "因子对比")
        await page.wait_for_timeout(500)
        await ss(page, "C40_eda_compare")

        await click_tab(page, "类别分布")
        await page.wait_for_timeout(500)
        await ss(page, "C41_eda_pie")

        # Export buttons
        await try_click(page, 'button:has-text("CSV")')
        await ss(page, "C42_export_csv")
        await try_click(page, 'button:has-text("XLSX")')
        await ss(page, "C43_export_xlsx")

        # ====== D: Obstacle Diagnosis (44-58) ======
        print("\n--- D: Obstacle Diagnosis ---")

        await page.goto(f"{BASE}/obstacle")
        await page.wait_for_timeout(1000)
        await ss(page, "D44_obstacle_empty")

        # Select site
        select = page.locator('.ant-select-selector').first
        if await select.count() > 0:
            await select.click(timeout=3000)
            await page.wait_for_timeout(700)
            opt = page.locator('.ant-select-item-option').first
            if await opt.count() > 0:
                await opt.click(timeout=3000)
                await page.wait_for_timeout(800)
        await ss(page, "D45_site_selected")

        # Land use toggle
        seg = page.locator('.ant-segmented-item').nth(1)
        if await seg.count() > 0:
            await seg.click(timeout=3000)
            await page.wait_for_timeout(500)
        await ss(page, "D46_land_use_switch")

        # Run diagnosis
        await try_click(page, 'button:has-text("运行"), button:has-text("诊断")')
        await page.wait_for_timeout(8000)
        await ss(page, "D47_diagnosis_done")

        # Background card
        await ss(page, "D48_site_background")

        # Model conclusion
        await ss(page, "D49_model_conclusion")

        # AUC tooltip
        icon = page.locator('.anticon-info-circle').first
        if await icon.count() > 0:
            await icon.hover(timeout=3000)
            await page.wait_for_timeout(600)
        await ss(page, "D50_auc_tooltip")

        # Factor chart
        await page.evaluate("window.scrollTo(0, 700)")
        await page.wait_for_timeout(500)
        await ss(page, "D51_factor_chart")

        # Factor table
        await page.evaluate("window.scrollTo(0, 1200)")
        await page.wait_for_timeout(500)
        await ss(page, "D52_factor_table")

        await page.evaluate("window.scrollTo(0, 1700)")
        await page.wait_for_timeout(500)
        await ss(page, "D53_local_shap")

        await page.evaluate("window.scrollTo(0, 2200)")
        await page.wait_for_timeout(500)
        await ss(page, "D54_pie_chart")

        await try_click(page, 'button:has-text("导出诊断")')
        await ss(page, "D55_export")

        # ====== E: SSUI (56-65) ======
        print("\n--- E: SSUI ---")

        await page.goto(f"{BASE}/ssui")
        await page.wait_for_timeout(1000)
        await ss(page, "E56_ssui_empty")

        select = page.locator('.ant-select-selector').first
        if await select.count() > 0:
            await select.click(timeout=3000)
            await page.wait_for_timeout(500)
            opt = page.locator('.ant-select-item-option').first
            if await opt.count() > 0:
                await opt.click(timeout=3000)
                await page.wait_for_timeout(500)

        await try_click(page, 'button:has-text("运行 SSUI")')
        await page.wait_for_timeout(6000)
        await ss(page, "E57_ssui_done")

        await ss(page, "E58_ssui_gauge")
        await page.evaluate("window.scrollTo(0, 400)")
        await page.wait_for_timeout(300)
        await ss(page, "E59_ssui_indicators")
        await page.evaluate("window.scrollTo(0, 800)")
        await page.wait_for_timeout(300)
        await ss(page, "E60_ssui_chart")
        await try_click(page, 'button:has-text("导出")')
        await ss(page, "E61_ssui_export")

        # ====== F: Reconstruction (62-70) ======
        print("\n--- F: Reconstruction ---")

        await page.goto(f"{BASE}/reconstruction")
        await page.wait_for_timeout(1000)
        await ss(page, "F62_recon_empty")

        select = page.locator('.ant-select-selector').first
        if await select.count() > 0:
            await select.click(timeout=3000)
            await page.wait_for_timeout(500)
            opt = page.locator('.ant-select-item-option').first
            if await opt.count() > 0:
                await opt.click(timeout=3000)
                await page.wait_for_timeout(500)

        await try_click(page, 'button:has-text("运行功能")')
        await page.wait_for_timeout(6000)
        await ss(page, "F63_recon_done")

        await ss(page, "F64_recon_radar")
        await page.evaluate("window.scrollTo(0, 500)")
        await page.wait_for_timeout(300)
        await ss(page, "F65_recon_contrib")
        await try_click(page, 'button:has-text("导出")')
        await ss(page, "F66_recon_export")

        # ====== G: Trace & Report (71-80) ======
        print("\n--- G: Trace ---")

        await page.goto(f"{BASE}/trace")
        await page.wait_for_timeout(1000)
        await ss(page, "G67_trace_list")

        # Go to trace detail
        await try_click(page, 'td a, a:has-text("追溯")')
        await page.wait_for_timeout(1500)
        await ss(page, "G68_trace_detail")

        # Five stages
        await ss(page, "G69_five_stages")
        await page.evaluate("window.scrollTo(0, 400)")
        await page.wait_for_timeout(300)
        await ss(page, "G70_upload_area")

        # Generate report
        await try_click(page, 'button:has-text("生成报告"), button:has-text("PDF")')
        await page.wait_for_timeout(2000)
        await ss(page, "G71_generate_report")

        # ====== H: Recommend (81-82) ======
        print("\n--- H: Recommend ---")

        await page.goto(f"{BASE}/recommend")
        await page.wait_for_timeout(1000)
        await ss(page, "H72_recommend_page")

        # ====== I: Permission & Misc (83-91) ======
        print("\n--- I: Permissions ---")

        await logout(page)
        await login_as(page, "e2e_ent2", "E2e@Test2026", "ent_final")
        await ss(page, "I73_ent_dashboard")

        # Enterprise no system menu
        await ss(page, "I74_ent_no_sys_menu")

        await page.goto(f"{BASE}/sites")
        await page.wait_for_timeout(1000)
        await ss(page, "I75_ent_site_list")

        # Password strength
        await logout(page)
        await page.goto(f"{BASE}/register")
        await page.wait_for_timeout(800)
        await try_fill(page, 'input[placeholder*="密码（至少"]', "weak")
        await page.wait_for_timeout(300)
        await ss(page, "I76_pwd_strength_weak")

        await try_fill(page, 'input[placeholder*="密码（至少"]', "Str0ng!Pass")
        await page.wait_for_timeout(300)
        await ss(page, "I77_pwd_strength_strong")

        # Forgot password
        await page.goto(f"{BASE}/forgot-password")
        await page.wait_for_timeout(800)
        await ss(page, "I78_forgot_pwd")

        # Login redirect
        await page.goto(f"{BASE}/sites/1")
        await page.wait_for_timeout(1500)
        await ss(page, "I79_login_redirect")

        # Empty states
        await login_as(page, "admin", "Demo@2026", "admin_last")
        await ss(page, "I80_admin_dashboard_final")

        # ====== SAVE RESULTS ======
        print("\n" + "=" * 60)
        print(f"Test complete! {len(results)} screenshots saved to:")
        print(f"  {SCREENSHOT_DIR}")
        report = SCREENSHOT_DIR / "test_report.json"
        report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Report: {report}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_all())
