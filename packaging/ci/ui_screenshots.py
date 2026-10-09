"""从已安装并完成验收流程的 SRS 实例采集真实界面截图(用户手册/PPT/截图包使用)。

  --stage first_run   在管理员设置之前采集: 登录页 + 首启设置向导
  --stage main        在 windows_acceptance.py --phase full 完成后采集全部功能页面(含上传校验错误的真实界面)
截图索引 index.json 记录: 文件、标题、路由、场景/场地、版本、提交、环境、采集时间、视口。
"""
from __future__ import annotations

import argparse
import json
import os
import platform
from datetime import datetime, timezone

import requests
from playwright.sync_api import sync_playwright

from windows_acceptance import ADMIN, EXPECTED_VERSION

VIEW = {"width": 1440, "height": 900}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18080")
    ap.add_argument("--out", required=True)
    ap.add_argument("--demo", default="demo/mc_v12")
    ap.add_argument("--stage", choices=["first_run", "main"], default="main")
    ap.add_argument("--chrome", default=None)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    idx_path = os.path.join(a.out, "index.json")
    index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {"screenshots": []}
    env = {"os": platform.platform(), "python": platform.python_version(), "commit": os.environ.get("GITHUB_SHA"),
           "run_id": os.environ.get("GITHUB_RUN_ID"), "version": EXPECTED_VERSION, "browser": "Playwright Chromium (headless)",
           "base": a.base, "viewport": VIEW, "data": "合成蒙特卡洛演示数据 demo/mc_v12(模拟数据——仅供测试/演示)"}
    index["environment"] = env

    def rec(fn, title, route, scenario=None, note=None):
        index["screenshots"] = [s for s in index["screenshots"] if s["file"] != fn]
        index["screenshots"].append({"file": fn, "title": title, "route": route, "scenario": scenario, "note": note,
                                     "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=a.chrome) if a.chrome else p.chromium.launch()
        ctx = b.new_context(viewport=VIEW, locale="zh-CN", device_scale_factor=1)
        page = ctx.new_page()

        def shot(fn, title, route, scenario=None, full=True, note=None, wait=2500):
            page.wait_for_timeout(wait)
            page.screenshot(path=os.path.join(a.out, fn), full_page=full)
            rec(fn, title, route, scenario, note)

        if a.stage == "first_run":
            page.goto(a.base + "/setup"); page.wait_for_load_state("networkidle")
            shot("00_first_run_setup.png", "首次启动 · 管理员设置向导(空数据库)", "/setup", full=False)
            page.goto(a.base + "/login"); page.wait_for_load_state("networkidle")
            shot("01_login.png", "登录页", "/login", full=False)
        else:
            r = requests.post(f"{a.base}/api/v1/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]}).json()
            tok, user = r["access_token"], r["user"]
            H = {"Authorization": f"Bearer {tok}"}
            sites = requests.get(f"{a.base}/api/v1/sites", headers=H, params={"page_size": 100}).json()["items"]
            by = {}
            for s in sites:
                for code in "ABCDE":
                    if f"MCDEMO-{code}" in (s.get("name") or "") or f"MCDEMO-{code}" in (s.get("original_site_code") or ""):
                        by[code] = s["id"]
            sid = by.get("A", sites[0]["id"])
            page.goto(a.base + "/login"); page.wait_for_load_state("networkidle")
            page.evaluate("""([t,u,s]) => { localStorage.setItem('srs_token', t); localStorage.setItem('srs_user', u);
                             sessionStorage.setItem('srs_current_site_id', String(s)); }""", [tok, json.dumps(user), sid])

            def go(route, site=None):
                if site:
                    page.evaluate("s => sessionStorage.setItem('srs_current_site_id', String(s))", site)
                page.goto(a.base + route); page.wait_for_load_state("networkidle")

            go("/"); shot("02_dashboard.png", "数据概览", "/")
            go("/sites"); shot("03_sites.png", "场地管理(5 个合成演示场地, 纯字母编号)", "/sites")
            go(f"/sites/{sid}"); shot("04_site_detail.png", "场地详情", f"/sites/{sid}", "A")
            go("/sites/import"); shot("05_import.png", "修复前检测数据导入(课题一/二)", "/sites/import")
            go("/obstacle", sid); shot("06_obstacle_S1.png", "课题一 障碍因子识别(KOS)", "/obstacle", "A")
            go("/reconstruction", sid); shot("07_reconstruction_S2.png", "课题二 功能重构分析", "/reconstruction", "A")
            go("/recon-import", sid)
            try:
                page.get_by_text("查看", exact=True).first.click(); page.wait_for_timeout(1500)
            except Exception:  # noqa: BLE001
                pass
            shot("08_recon_import_S2_result.png", "课题二 28 项指标导入 · 已确认批次结果与计算过程", "/recon-import", "A")
            fx = os.path.join(a.demo, "fixtures")
            bad = [f for f in os.listdir(fx) if f.startswith("F02_")]
            if bad:
                go("/recon-import", sid)
                page.set_input_files("input[type=file]", os.path.join(fx, bad[0])); page.wait_for_timeout(3000)
                shot("09_recon_import_validation_error.png", "课题二 导入校验 · 非法类别逐格报错(不可确认)", "/recon-import",
                     "夹具 F02", note="上传后系统返回真实校验结果; 未写入业务数据")
            warn = [f for f in os.listdir(fx) if f.startswith("F05_")]
            if warn:
                go("/recon-import", sid)
                page.set_input_files("input[type=file]", os.path.join(fx, warn[0])); page.wait_for_timeout(3000)
                shot("10_recon_import_preview_ok.png", "课题二 导入预览 · 校验通过(含常数列告警)", "/recon-import", "夹具 F05")
            go("/ssui-post", sid); shot("11_ssui_post_S3.png", "课题三 修复后 SSUI 导入(批次与结果)", "/ssui-post", "A")
            bad3 = [f for f in os.listdir(fx) if f.startswith("F07_")]
            if bad3:
                go("/ssui-post", sid)
                page.set_input_files("input[type=file]", os.path.join(fx, bad3[0])); page.wait_for_timeout(3000)
                shot("12_ssui_post_validation_error.png", "课题三 导入校验 · 单位错误定位到工作表/行/列", "/ssui-post", "夹具 F07")
            for code, fn, title in (("A", "13_decision_A_both.png", "修复后利用结论 · 两轨均支持"),
                                    ("B", "14_decision_B_production.png", "修复后利用结论 · 仅生产支持"),
                                    ("C", "15_decision_C_ecology.png", "修复后利用结论 · 仅生态支持"),
                                    ("D", "16_decision_D_neither.png", "修复后利用结论 · 重度超标两轨均不支持"),
                                    ("E", "17_decision_E_insufficient.png", "修复后利用结论 · 缺测关键项目证据不足")):
                if code in by:
                    go("/ssui-post", by[code])
                    page.mouse.wheel(0, 6000); page.wait_for_timeout(1200)
                    shot(fn, title, "/ssui-post", code, full=False)
            go("/recon-import", sid); page.mouse.wheel(0, 8000); page.wait_for_timeout(1200)
            shot("18_decision_pre_A.png", "修复前情景判断(不作为修复后结论)", "/recon-import", "A", full=False)
            go("/ssui", sid); shot("19_ssui_reference.png", "SSUI 参考评价(修复前数据, 非课题三结论)", "/ssui", "A")
            go("/trace"); shot("20_trace_guide.png", "全流程追溯 · 进入即见五阶段引导", "/trace")
            go(f"/trace/{sid}"); shot("21_trace_detail.png", "全流程追溯 · 场地真实进度与报告", f"/trace/{sid}", "A")
            go("/recommend", sid); shot("22_recommend.png", "修复方案推荐", "/recommend", "A")
            go("/files"); shot("23_files.png", "文件管理", "/files")
            go("/system"); shot("24_system.png", "系统管理(用户/备份恢复/日志)", "/system")
        b.close()
    index["screenshots"].sort(key=lambda s: s["file"])
    json.dump(index, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(index["screenshots"]), "screenshots indexed")


if __name__ == "__main__":
    main()
