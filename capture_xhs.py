import asyncio
from playwright.async_api import async_playwright
import os

async def run():
    desktop = "C:\\Users\\曾鸿\\Desktop\\Xiaohongshu_UI_References"
    os.makedirs(desktop, exist_ok=True)
    
    # 针对国内审美的关键词（B端设计、数据大屏、后台管理系统）
    targets = [
        {"name": "01_小红书_B端UI设计案例", "url": "https://www.xiaohongshu.com/search_result?keyword=B%E7%AB%AFUI%E8%AE%BE%E8%AE%A1&source=web_search_result_notes"},
        {"name": "02_小红书_数据大屏设计案例", "url": "https://www.xiaohongshu.com/search_result?keyword=%E6%95%B0%E6%8D%AE%E5%A4%A7%E5%B1%8F%E8%AE%BE%E8%AE%A1&source=web_search_result_notes"},
        {"name": "03_站酷_中国顶级数据大屏UI", "url": "https://www.zcool.com.cn/search/content?word=%E6%95%B0%E6%8D%AE%E5%A4%A7%E5%B1%8F"},
        {"name": "04_站酷_中国顶级后台UI", "url": "https://www.zcool.com.cn/search/content?word=B%E7%AB%AF%E5%90%8E%E5%8F%B0"}
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 16:9 2K
        page = await browser.new_page(viewport={"width": 2560, "height": 1440}, device_scale_factor=2)
        
        for t in targets:
            print(f"Capturing {t['name']}...")
            try:
                # Set a user agent to pretend to be a normal browser
                await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"})
                await page.goto(t["url"], wait_until="networkidle", timeout=20000)
                await page.wait_for_timeout(4000) # Wait for masonry grid to load images
                
                # Close any login popups on Xiaohongshu if they appear
                try:
                    await page.evaluate("""
                        () => {
                            const closeBtn = document.querySelector('.close-box');
                            if (closeBtn) closeBtn.click();
                            
                            // remove login modal if it's there
                            const loginModal = document.querySelector('.login-container');
                            if (loginModal) loginModal.remove();
                            
                            const mask = document.querySelector('.mask');
                            if (mask) mask.remove();
                        }
                    """)
                except:
                    pass
                
                await page.wait_for_timeout(1000)
                await page.screenshot(path=f"{desktop}\\{t['name']}.png", full_page=False)
            except Exception as e:
                print(f"Failed to capture {t['name']}: {e}")
                
        await browser.close()
        print("All Xiaohongshu/Zcool references captured successfully.")

if __name__ == "__main__":
    asyncio.run(run())
