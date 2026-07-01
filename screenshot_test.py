import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 2K 16:9
        page = await browser.new_page(viewport={"width": 2560, "height": 1440})
        
        try:
            print("Starting test...")
            # 1. 登录页
            await page.goto("http://localhost:5173/login")
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(1000)
            await page.screenshot(path="C:\\Users\\曾鸿\\Desktop\\01_登录页.png")
            print("Captured: 登录页")

            # Login
            await page.fill('input[type="text"]', "admin")
            await page.fill('input[type="password"]', "Demo@2026")
            await page.click('button[type="submit"]')
            
            # 2. 数据概览
            await page.wait_for_url("http://localhost:5173/")
            await page.wait_for_timeout(3000) # Wait for charts
            await page.screenshot(path="C:\\Users\\曾鸿\\Desktop\\02_数据概览.png")
            print("Captured: 数据概览")
            
            # 3. 场地管理
            await page.click("text=场地管理")
            await page.wait_for_timeout(2000)
            await page.screenshot(path="C:\\Users\\曾鸿\\Desktop\\03_场地管理.png")
            print("Captured: 场地管理")
            
            # 4. 障碍因子分析
            await page.click("text=障碍因子分析")
            await page.wait_for_timeout(1000)
            await page.click('.ant-select-selector')
            await page.wait_for_timeout(500)
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            await page.click("button:has-text('运行')")
            await page.wait_for_timeout(3000) # Wait for execution and charts
            await page.screenshot(path="C:\\Users\\曾鸿\\Desktop\\04_障碍因子分析.png")
            print("Captured: 障碍因子分析")
            
            # 5. 功能重构分析
            await page.click("text=功能重构分析")
            await page.wait_for_timeout(1000)
            try:
                await page.click('.ant-select-selector', timeout=2000)
                await page.wait_for_timeout(500)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(500)
                await page.click("button:has-text('运行')")
                await page.wait_for_timeout(2000)
            except Exception:
                pass
            await page.screenshot(path="C:\\Users\\曾鸿\\Desktop\\05_功能重构分析.png")
            print("Captured: 功能重构分析")
            
            # 6. SSUI评价
            await page.click("text=SSUI评价")
            await page.wait_for_timeout(1000)
            await page.click('.ant-select-selector')
            await page.wait_for_timeout(500)
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            await page.click("button:has-text('运行 SSUI 可持续利用评价')")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="C:\\Users\\曾鸿\\Desktop\\06_SSUI评价.png")
            print("Captured: SSUI评价")
            
            # 7. 方案推荐
            await page.click("text=方案推荐")
            await page.wait_for_timeout(2000)
            try:
                await page.click('.ant-select-selector', timeout=2000)
                await page.wait_for_timeout(500)
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)
            except Exception:
                pass
            await page.screenshot(path="C:\\Users\\曾鸿\\Desktop\\07_方案推荐.png")
            print("Captured: 方案推荐")
            
            # 8. 全流程追溯
            await page.click("text=全流程追溯")
            await page.wait_for_timeout(2000)
            await page.screenshot(path="C:\\Users\\曾鸿\\Desktop\\08_全流程追溯.png")
            print("Captured: 全流程追溯")

        except Exception as e:
            print(f"Error occurred: {e}")
            await page.screenshot(path="C:\\Users\\曾鸿\\Desktop\\Error_State.png")
        
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
