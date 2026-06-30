"""端到端页面截图脚本(裴总: 每页每功能点截图存专用文件夹)。

Playwright headless Chromium 登录 → 遍历每页/每功能点 → 截图存 docs/audit/screenshots_20260630/。
覆盖: 登录/Dashboard/场地列表/场地详情/地图/EDA/障碍因子诊断(双轨+SHAP)/功能重构/SSUI/推荐/追溯/报告/系统管理/AI浮窗。
"""
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "audit", "screenshots_20260630"))
os.makedirs(OUT, exist_ok=True)
SITE_ID = 1  # 个旧(有砷诊断+GEE)


def shot(page, name, full=True):
    path = os.path.join(OUT, f"{name}.png")
    page.screenshot(path=path, full_page=full)
    print(f"  [OK] {name}.png")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        page = ctx.new_page()

        # 1. 登录页
        print("[1] 登录页")
        page.goto(f"{BASE}/login", wait_until="networkidle")
        shot(page, "01_login")
        page.fill('input[id="username"], input[type="text"]', "admin")
        page.fill('input[id="password"], input[type="password"]', "Demo@2026")
        page.keyboard.press("Enter")
        page.wait_for_url("**/", timeout=15000)
        page.wait_for_timeout(2500)
        shot(page, "02_dashboard_after_login")

        # 2. Dashboard
        print("[2] Dashboard 数据概览")
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.wait_for_timeout(2000)
        shot(page, "03_dashboard")

        # 3. 场地列表
        print("[3] 场地列表")
        page.goto(f"{BASE}/sites", wait_until="networkidle")
        page.wait_for_timeout(2000)
        shot(page, "04_site_list")

        # 4. 场地详情(个旧) + 地图 + EDA
        print("[4] 场地详情(个旧)")
        page.goto(f"{BASE}/sites/{SITE_ID}", wait_until="networkidle")
        page.wait_for_timeout(3000)
        shot(page, "05_site_detail_map")
        # EDA tab(如有)
        try:
            page.click('text=EDA', timeout=3000)
            page.wait_for_timeout(2000)
            shot(page, "06_site_detail_eda")
        except Exception:
            shot(page, "06_site_detail_eda_alt")

        # 5. 障碍因子诊断(双轨+SHAP)
        print("[5] 障碍因子诊断")
        page.goto(f"{BASE}/obstacle", wait_until="networkidle")
        page.wait_for_timeout(2000)
        # 选个旧场地
        try:
            page.click('text=个旧', timeout=3000)
            page.wait_for_timeout(1000)
        except Exception:
            pass
        # 运行诊断按钮
        try:
            page.click('text=运行 RF+SHAP', timeout=5000)
            page.wait_for_timeout(90000)  # 诊断SHAP慢
        except Exception:
            pass
        shot(page, "07_obstacle_diagnosis")
        # 双轨对比 + 局部SHAP 截图
        page.wait_for_timeout(2000)
        shot(page, "08_obstacle_dual_track_shap")

        # 6. 功能重构评价
        print("[6] 功能重构评价")
        page.goto(f"{BASE}/reconstruction", wait_until="networkidle")
        page.wait_for_timeout(2000)
        try:
            page.click('text=个旧', timeout=3000)
            page.wait_for_timeout(1000)
            page.click('text=运行评价', timeout=5000)
            page.wait_for_timeout(30000)
        except Exception:
            pass
        shot(page, "09_reconstruction")

        # 7. SSUI 评价
        print("[7] SSUI 评价")
        page.goto(f"{BASE}/ssui", wait_until="networkidle")
        page.wait_for_timeout(2000)
        try:
            page.click('text=个旧', timeout=3000)
            page.wait_for_timeout(1000)
            page.click('text=运行', timeout=5000)
            page.wait_for_timeout(30000)
        except Exception:
            pass
        shot(page, "10_ssui")

        # 8. 方案推荐
        print("[8] 方案推荐")
        page.goto(f"{BASE}/recommend", wait_until="networkidle")
        page.wait_for_timeout(2000)
        try:
            page.click('text=个旧', timeout=3000)
            page.wait_for_timeout(1000)
            page.click('text=推荐', timeout=5000)
            page.wait_for_timeout(20000)
        except Exception:
            pass
        shot(page, "11_recommendation")

        # 9. 追溯列表 + 详情
        print("[9] 追溯")
        page.goto(f"{BASE}/trace", wait_until="networkidle")
        page.wait_for_timeout(2000)
        shot(page, "12_trace_list")
        page.goto(f"{BASE}/trace/{SITE_ID}", wait_until="networkidle")
        page.wait_for_timeout(2000)
        shot(page, "13_trace_detail")

        # 10. 系统管理
        print("[10] 系统管理")
        page.goto(f"{BASE}/system", wait_until="networkidle")
        page.wait_for_timeout(2000)
        shot(page, "14_system_management")

        # 11. AI 浮窗实测
        print("[11] AI 浮窗实测")
        page.goto(f"{BASE}/", wait_until="networkidle")
        page.wait_for_timeout(2000)
        try:
            page.click('[class*="ai"], [aria-label*="AI"], button:has-text("AI"), button:has-text("助手")', timeout=5000)
            page.wait_for_timeout(1500)
        except Exception:
            try:
                page.click('button:has-text("问")', timeout=3000)
                page.wait_for_timeout(1500)
            except Exception:
                pass
        # 输入问题
        try:
            page.fill('textarea, input[type="text"]', "镉污染场地用什么修复技术?")
            page.wait_for_timeout(500)
            page.keyboard.press("Enter")
            page.wait_for_timeout(30000)  # GLM-5.2 RAG 响应
        except Exception:
            pass
        shot(page, "15_ai_assistant_chat")

        # 12. 报告生成页(追溯详情内)
        print("[12] 报告生成")
        page.goto(f"{BASE}/trace/{SITE_ID}", wait_until="networkidle")
        page.wait_for_timeout(2000)
        try:
            page.click('text=生成报告', timeout=5000)
            page.wait_for_timeout(30000)
        except Exception:
            pass
        shot(page, "16_report_generation")

        browser.close()
    print(f"\n✅ 截图完成, 共存 {OUT}")


if __name__ == "__main__":
    main()
