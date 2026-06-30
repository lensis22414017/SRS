"""EDA 重新截图脚本(裴总反馈: EDA 分析结果在系统中看不到)。

根因: 打包 exe 首启空库无场地数据 → EDA 接口 404。
修复: 已导入广东_HM_200点真实场地(site_id=1, 200采样点/2000检测/10因子)。
本脚本: Playwright 登录 → 进场地详情 EDA Tab → 逐个子 Tab 等足加载 → 截图。
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "audit", "screenshots_20260630"))
os.makedirs(OUT, exist_ok=True)
SITE_ID = 1  # 广东_HM_200点(已导入, 10因子/200采样点)

# EDA 子 Tab 中文名 → 文件名后缀(对应 EdaPanel.tsx 的 Tabs items label)
EDA_SUBTABS = [
    ("统计体检", "overview"),
    ("直方图", "hist"),
    ("云雨图", "box"),
    ("散点图", "scatter"),
    ("相关热力图", "heatmap"),
    ("Q-Q 图", "qq"),
    ("因子对比", "compare"),
    ("分组对比", "grouped"),
    ("类别分布", "pie"),
]


def shot(page, name, full=True):
    path = os.path.join(OUT, f"{name}.png")
    page.screenshot(path=path, full_page=full)
    print(f"  [OK] {name}.png")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()

        # 1. 登录
        print("[1] 登录")
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.fill('input[id="username"], input[type="text"]', "admin")
        page.fill('input[id="password"], input[type="password"]', "Demo@2026")
        page.keyboard.press("Enter")
        page.wait_for_url("**/", timeout=15000)
        page.wait_for_timeout(2000)

        # 2. 进场地详情
        print(f"[2] 进场地详情 site_id={SITE_ID}")
        page.goto(f"{BASE}/sites/{SITE_ID}", wait_until="networkidle")
        page.wait_for_timeout(3000)

        # 3. 点 EDA Tab(整体截图, 覆盖旧的空图)
        print("[3] EDA 主 Tab 整体截图(覆盖 06_site_detail_eda)")
        try:
            page.click('text=EDA', timeout=5000)
        except Exception:
            try:
                page.click('.ant-tabs-tab:has-text("EDA"), [role=tab]:has-text("EDA")', timeout=5000)
            except Exception as e:
                print(f"  [WARN] 未找到 EDA tab: {e}")
        page.wait_for_timeout(4000)  # 等 EDA 数据加载(9 Tab 一次拉全量)
        shot(page, "06_site_detail_eda")

        # 4. 逐个子 Tab 截图
        for label, suffix in EDA_SUBTABS:
            print(f"[4] EDA 子 Tab: {label}")
            try:
                # EDA 内部 Tabs 的 tab label
                page.click(f'.ant-tabs-tab:has-text("{label}")', timeout=4000)
                page.wait_for_timeout(2500)  # 等图表渲染
                shot(page, f"06_eda_{suffix}")
            except Exception as e:
                print(f"  [WARN] 子 Tab {label} 截图失败: {e}")
                shot(page, f"06_eda_{suffix}_alt")

        browser.close()
    print(f"\n✅ EDA 截图完成, 共存 {OUT}")


if __name__ == "__main__":
    main()
