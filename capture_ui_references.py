import asyncio
from playwright.async_api import async_playwright
import os

async def run():
    desktop = "C:\\Users\\曾鸿\\Desktop\\Top_Tier_UI_References"
    os.makedirs(desktop, exist_ok=True)
    
    # 业界公认最牛 UI 标杆
    targets = [
        {"name": "01_Linear_App_极简主义与暗黑科幻的巅峰", "url": "https://linear.app/"},
        {"name": "02_Stripe_金融级明亮光感与网格排版标杆", "url": "https://stripe.com/"},
        {"name": "03_Vercel_性冷淡风与超高对比度排版", "url": "https://vercel.com/"},
        {"name": "04_Raycast_MacOS原生质感与极致毛玻璃", "url": "https://www.raycast.com/"},
        {"name": "05_Framer_动效与视觉表现力的天花板", "url": "https://www.framer.com/"}
    ]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 使用真 5K 超清比例，模拟超高配 Retina 屏幕
        page = await browser.new_page(viewport={"width": 2560, "height": 1440}, device_scale_factor=2)
        
        for t in targets:
            print(f"Capturing {t['name']}...")
            try:
                await page.goto(t["url"], wait_until="networkidle", timeout=20000)
                await page.wait_for_timeout(3000) # Wait for entry animations
                
                # 隐藏可能的 Cookie 弹窗，防止遮挡
                await page.evaluate("""
                    () => {
                        const selectors = ['#onetrust-banner-sdk', '.cookie-banner', '[id*="cookie"]', '[class*="cookie"]'];
                        selectors.forEach(s => {
                            document.querySelectorAll(s).forEach(el => el.remove());
                        });
                    }
                """)
                
                await page.screenshot(path=f"{desktop}\\{t['name']}.png", full_page=False)
            except Exception as e:
                print(f"Failed to capture {t['name']}: {e}")
                
        await browser.close()
        print("All references captured successfully.")

if __name__ == "__main__":
    asyncio.run(run())
