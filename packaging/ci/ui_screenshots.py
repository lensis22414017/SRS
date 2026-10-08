"""从已安装并完成验收流程的 SRS 实例采集真实界面截图(供用户手册/PPT 使用)。

前置: windows_acceptance.py --phase full 已完成(已有管理员、演示场地与结果)。
用法: python ui_screenshots.py --base http://127.0.0.1:18080 --out screenshots
"""
from __future__ import annotations

import argparse
import json
import os

import requests
from playwright.sync_api import sync_playwright

from windows_acceptance import ADMIN

PAGES = [
    ("01_login", "/login", None),
    ("02_dashboard", "/", None),
    ("03_sites", "/sites", None),
    ("04_import", "/sites/import", None),
    ("05_obstacle_S1", "/obstacle", None),
    ("06_reconstruction_S2_pre_decision", "/reconstruction", None),
    ("07_ssui_post_S3", "/ssui-post", None),
    ("08_ssui_legacy_reference", "/ssui", None),
    ("09_trace_guide", "/trace", None),
    ("10_trace_detail", "/trace/{sid}", None),
    ("11_files", "/files", None),
    ("12_system", "/system", None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18080")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    r = requests.post(f"{a.base}/api/v1/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]}).json()
    tok, user = r["access_token"], r["user"]
    sid = requests.get(f"{a.base}/api/v1/sites", headers={"Authorization": f"Bearer {tok}"}).json()["items"][0]["id"]
    shots = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN", device_scale_factor=1)
        page = ctx.new_page()
        page.goto(a.base + "/login"); page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(a.out, "01_login.png")); shots.append("01_login.png")
        page.evaluate("""([t,u,s]) => { localStorage.setItem('srs_token', t); localStorage.setItem('srs_user', u);
                         sessionStorage.setItem('srs_current_site_id', String(s)); }""", [tok, json.dumps(user), sid])
        for name, path, _ in PAGES[1:]:
            page.goto(a.base + path.format(sid=sid))
            page.wait_for_load_state("networkidle"); page.wait_for_timeout(2500)
            fn = f"{name}.png"
            page.screenshot(path=os.path.join(a.out, fn), full_page=True); shots.append(fn)
        # 课题三页 + 修复后利用结论(滚动到底部)
        page.goto(a.base + "/ssui-post"); page.wait_for_load_state("networkidle"); page.wait_for_timeout(2500)
        page.mouse.wheel(0, 4000); page.wait_for_timeout(800)
        page.screenshot(path=os.path.join(a.out, "13_post_decision.png")); shots.append("13_post_decision.png")
        b.close()
    json.dump({"base": a.base, "site_id": sid, "screenshots": shots}, open(os.path.join(a.out, "index.json"), "w"), indent=1)
    print(len(shots), "screenshots")


if __name__ == "__main__":
    main()
