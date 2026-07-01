import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    desktop = os.path.expanduser("~\\Desktop\\SRS_Screenshots")
    os.makedirs(desktop, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        # 2K Resolution, 16:9
        context = await browser.new_context(viewport={'width': 2560, 'height': 1440})
        page = await context.new_page()

        print("Navigating to Login...")
        await page.goto("http://localhost:5173/login")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(desktop, "01_系统登录页.png"), full_page=True)

        print("Logging in...")
        await page.fill('input[type="text"]', 'admin')
        await page.fill('input[type="password"]', 'Demo@2026')
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(3000)
        
        print("Taking Dashboard screenshot...")
        await page.screenshot(path=os.path.join(desktop, "02_数据概览.png"), full_page=True)
        
        print("Navigating to Site Management...")
        await page.click('text=场地管理')
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(desktop, "03_场地管理列表.png"), full_page=True)

        print("Navigating to Data Import...")
        await page.click('text=批量导入')
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(desktop, "04_数据导入页.png"), full_page=True)
        
        # Navigate back and select a site to view details
        await page.go_back()
        await page.wait_for_timeout(2000)
        # Click the first '详情' link
        detail_links = await page.query_selector_all('text=详情')
        if detail_links:
            await detail_links[0].click()
            await page.wait_for_timeout(3000)
            await page.screenshot(path=os.path.join(desktop, "05_场地详情页.png"), full_page=True)
        
        print("Navigating to Obstacle Analysis...")
        await page.click('text=障碍因子分析')
        await page.wait_for_timeout(3000)
        
        # Select site from dropdown if needed, or click Run
        run_btn = await page.query_selector('text=障碍因子智能诊断')
        if run_btn:
            try:
                await run_btn.click()
                await page.wait_for_timeout(8000) # Wait for diagnosis to complete
            except:
                pass
        await page.screenshot(path=os.path.join(desktop, "06_障碍因子智能诊断.png"), full_page=True)

        print("Navigating to Reconstruction Analysis...")
        await page.click('text=功能重构分析')
        await page.wait_for_timeout(3000)
        eval_btn = await page.query_selector('text=运行功能重构潜力评价')
        if eval_btn:
            try:
                await eval_btn.click()
                await page.wait_for_timeout(5000)
            except:
                pass
        await page.screenshot(path=os.path.join(desktop, "07_功能重构潜力评价.png"), full_page=True)

        print("Navigating to SSUI Analysis...")
        await page.click('text=SSUI评价')
        await page.wait_for_timeout(3000)
        ssui_btn = await page.query_selector('text=运行 SSUI 可持续利用评价')
        if ssui_btn:
            try:
                await ssui_btn.click()
                await page.wait_for_timeout(5000)
            except:
                pass
        await page.screenshot(path=os.path.join(desktop, "08_SSUI可持续利用评价.png"), full_page=True)
        
        print("Navigating to Recommendation...")
        await page.click('text=方案推荐')
        await page.wait_for_timeout(3000)
        rec_btn = await page.query_selector('text=生成推荐方案')
        if rec_btn:
            try:
                await rec_btn.click()
                await page.wait_for_timeout(5000)
            except:
                pass
        await page.screenshot(path=os.path.join(desktop, "09_修复方案智能推荐.png"), full_page=True)
        
        print("Navigating to Trace...")
        await page.click('text=全流程追溯')
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(desktop, "10_全流程追溯列表.png"), full_page=True)
        
        trace_links = await page.query_selector_all('text=查看报告')
        if trace_links:
            await trace_links[0].click()
            await page.wait_for_timeout(3000)
            await page.screenshot(path=os.path.join(desktop, "11_溯源报告详情.png"), full_page=True)
            
        print("Navigating to System Management...")
        await page.click('text=系统管理')
        await page.wait_for_timeout(2000)
        await page.screenshot(path=os.path.join(desktop, "12_系统管理权限设置.png"), full_page=True)
        
        print("Screenshots saved to Desktop/SRS_Screenshots.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
