import asyncio
from playwright.async_api import async_playwright
import os

async def run():
    # 强制创建保存目录
    desktop = "C:\\Users\\曾鸿\\Desktop\\TDesign_UI_Details"
    os.makedirs(desktop, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # device_scale_factor=2 gives 5120x2880 physical resolution
        page = await browser.new_page(viewport={"width": 2560, "height": 1440}, device_scale_factor=2)
        
        try:
            print("Starting ultra high-res test...")
            # 1. 登录页
            await page.goto("http://localhost:5173/login")
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\01_登录页_高级光感全貌.png")
            
            await page.fill('input[type="text"]', "admin")
            await page.fill('input[type="password"]', "Demo@2026")
            await page.click('button[type="submit"]')
            
            # 2. 首页数据概览
            await page.wait_for_url("http://localhost:5173/")
            await page.screenshot(path=f"{desktop}\\02_数据概览_骨架屏过渡.png")
            await page.wait_for_timeout(3000)
            await page.screenshot(path=f"{desktop}\\03_数据概览_尊享明亮完整版.png")
            
            # 鼠标悬浮
            await page.mouse.move(500, 600)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\04_数据概览_图表高清交互(Tooltip).png")
            
            # 3. 场地管理
            await page.click("text=场地管理")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=f"{desktop}\\05_场地管理_列表页全貌.png")
            
            await page.fill('input[placeholder="按名称/编号搜索"]', "测试")
            await page.click('button:has-text("刷新")')
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\06_场地管理_搜索高亮状态.png")
            
            try:
                await page.click("text=查看详情")
                await page.wait_for_timeout(1500)
                await page.screenshot(path=f"{desktop}\\07_场地详情_基础信息沉浸式区块.png")
                await page.go_back()
                await page.wait_for_timeout(1000)
            except: pass
            
            # 4. 障碍因子分析
            await page.click("text=障碍因子分析")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\08_障碍因子分析_高级缺省页.png")
            
            await page.click('.ant-select-selector')
            await page.wait_for_timeout(500)
            await page.screenshot(path=f"{desktop}\\09_障碍因子分析_下拉选择框展开.png")
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            await page.click("button:has-text('运行')")
            await page.wait_for_timeout(3000)
            
            await page.screenshot(path=f"{desktop}\\10_障碍因子分析_图表渲染全貌.png")
            await page.mouse.move(500, 600)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\11_障碍因子分析_SHAP归因悬浮交互.png")
            
            await page.mouse.wheel(0, 1000)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\12_障碍因子分析_双轨概率对比图.png")
            
            # 5. SSUI评价
            await page.click("text=SSUI评价")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\13_SSUI评价_空状态及公式科普区.png")
            
            await page.click('.ant-select-selector')
            await page.wait_for_timeout(500)
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            await page.click("button:has-text('运行 SSUI 可持续利用评价')")
            await page.wait_for_timeout(3000)
            
            await page.screenshot(path=f"{desktop}\\14_SSUI评价_执行后仪表盘与指数.png")
            await page.mouse.wheel(0, 800)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\15_SSUI评价_双轴条形图详解.png")
            
            # 6. 功能重构分析
            await page.click("text=功能重构分析")
            await page.wait_for_timeout(2000)
            await page.screenshot(path=f"{desktop}\\16_功能重构分析_方案空间展示.png")
            
            # 7. 方案推荐
            await page.click("text=方案推荐")
            await page.wait_for_timeout(2000)
            await page.screenshot(path=f"{desktop}\\17_方案推荐_智能推荐列表.png")
            
            # 8. 全流程追溯
            await page.click("text=全流程追溯")
            await page.wait_for_timeout(2000)
            await page.screenshot(path=f"{desktop}\\18_全流程追溯_时间轴展示.png")
            
            # 9. 框架与细节
            try:
                await page.click('.ant-layout-sider-trigger', timeout=2000)
                await page.wait_for_timeout(1000)
                await page.screenshot(path=f"{desktop}\\19_全局_侧边栏折叠收起状态.png")
                await page.click('.ant-layout-sider-trigger', timeout=2000)
                await page.wait_for_timeout(1000)
            except: pass
            
            try:
                await page.click('.ant-dropdown-trigger', timeout=2000)
                await page.wait_for_timeout(500)
                await page.screenshot(path=f"{desktop}\\20_全局_右上角用户菜单展开.png")
            except: pass
            
        except Exception as e:
            print(f"Error occurred: {e}")
        finally:
            await browser.close()
            print("Ultra tests complete.")

if __name__ == "__main__":
    asyncio.run(run())
