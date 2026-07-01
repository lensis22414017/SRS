import asyncio
from playwright.async_api import async_playwright
import os

async def run():
    desktop = "C:\\Users\\曾鸿\\Desktop\\SRS_UI_Details"
    os.makedirs(desktop, exist_ok=True)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 2K 16:9
        page = await browser.new_page(viewport={"width": 2560, "height": 1440})
        
        try:
            print("Starting comprehensive test...")
            # ================= 1. 登录页模块 =================
            await page.goto("http://localhost:5173/login")
            await page.wait_for_load_state('networkidle')
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\01_登录页_默认全貌.png")
            
            await page.click('input[type="text"]')
            await page.wait_for_timeout(500)
            await page.screenshot(path=f"{desktop}\\02_登录页_输入框聚焦态.png")

            await page.fill('input[type="text"]', "admin")
            await page.fill('input[type="password"]', "Demo@2026")
            # 捕获点击瞬间
            await page.mouse.move(1280, 720) # Move away
            await page.screenshot(path=f"{desktop}\\03_登录页_信息填入态.png")
            await page.click('button[type="submit"]')
            
            # ================= 2. 首页数据概览 =================
            await page.wait_for_url("http://localhost:5173/")
            # capture skeleton if possible (might be too fast)
            await page.screenshot(path=f"{desktop}\\04_数据概览_加载骨架屏.png")
            
            await page.wait_for_timeout(3000) # Wait for charts
            await page.screenshot(path=f"{desktop}\\05_数据概览_完整呈现.png")
            
            # 鼠标悬浮到环形图上
            await page.mouse.move(500, 600)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\06_数据概览_图表交互悬浮(Tooltip).png")
            
            # ================= 3. 场地管理 =================
            await page.click("text=场地管理")
            await page.wait_for_timeout(1500)
            await page.screenshot(path=f"{desktop}\\07_场地管理_列表页全貌.png")
            
            # 搜索测试
            await page.fill('input[placeholder="按名称/编号搜索"]', "测试")
            await page.click('button:has-text("刷新")')
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\08_场地管理_搜索过滤状态.png")
            await page.fill('input[placeholder="按名称/编号搜索"]', "")
            await page.click('button:has-text("刷新")')
            await page.wait_for_timeout(1000)
            
            # 详情页
            try:
                await page.click("text=查看详情")
                await page.wait_for_timeout(1500)
                await page.screenshot(path=f"{desktop}\\09_场地详情_基础信息区块.png")
                await page.mouse.wheel(0, 800)
                await page.wait_for_timeout(500)
                await page.screenshot(path=f"{desktop}\\10_场地详情_检测数据表格.png")
                await page.go_back()
                await page.wait_for_timeout(1000)
            except Exception as e:
                print(f"Skipped details: {e}")

            # 导入页
            try:
                await page.click("text=批量导入")
                await page.wait_for_timeout(1000)
                await page.screenshot(path=f"{desktop}\\11_场地管理_批量导入界面.png")
                await page.go_back()
                await page.wait_for_timeout(1000)
            except Exception as e:
                print(f"Skipped import: {e}")
            
            # ================= 4. 障碍因子分析 =================
            await page.click("text=障碍因子分析")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\12_障碍因子分析_空状态与引导.png")
            
            await page.click('.ant-select-selector')
            await page.wait_for_timeout(500)
            await page.screenshot(path=f"{desktop}\\13_障碍因子分析_下拉选择框展开.png")
            
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            await page.click("button:has-text('运行')")
            await page.wait_for_timeout(3000)
            
            await page.screenshot(path=f"{desktop}\\14_障碍因子分析_图表渲染全貌.png")
            await page.mouse.move(500, 600)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\15_障碍因子分析_SHAP归因悬浮交互.png")
            
            await page.mouse.wheel(0, 1000)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\16_障碍因子分析_双轨概率对比图.png")
            
            # ================= 5. SSUI评价 =================
            await page.click("text=SSUI评价")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\17_SSUI评价_空状态及公式科普区.png")
            
            await page.click('.ant-select-selector')
            await page.wait_for_timeout(500)
            await page.keyboard.press("ArrowDown")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            await page.click("button:has-text('运行 SSUI 可持续利用评价')")
            await page.wait_for_timeout(3000)
            
            await page.screenshot(path=f"{desktop}\\18_SSUI评价_执行后仪表盘与指数.png")
            
            await page.mouse.wheel(0, 800)
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\19_SSUI评价_双轴条形图详解.png")
            
            # ================= 6. 功能重构分析 =================
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
            await page.screenshot(path=f"{desktop}\\20_功能重构分析_方案空间展示.png")
            
            # ================= 7. 方案推荐 =================
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
            await page.screenshot(path=f"{desktop}\\21_方案推荐_智能推荐列表.png")
            
            # ================= 8. 全流程追溯 =================
            await page.click("text=全流程追溯")
            await page.wait_for_timeout(2000)
            await page.screenshot(path=f"{desktop}\\22_全流程追溯_时间轴展示.png")
            
            # ================= 9. 全局框架细节 =================
            # 侧边栏折叠
            await page.click('.ant-layout-sider-trigger')
            await page.wait_for_timeout(1000)
            await page.screenshot(path=f"{desktop}\\23_全局_侧边栏折叠收起状态.png")
            await page.click('.ant-layout-sider-trigger')
            await page.wait_for_timeout(1000)
            
            # 右上角用户菜单
            await page.click('.ant-dropdown-trigger')
            await page.wait_for_timeout(500)
            await page.screenshot(path=f"{desktop}\\24_全局_右上角用户菜单展开.png")

        except Exception as e:
            print(f"Error occurred: {e}")
            await page.screenshot(path=f"{desktop}\\Error_State.png")
        
        finally:
            await browser.close()
            print("Comprehensive testing complete.")

if __name__ == "__main__":
    asyncio.run(run())
