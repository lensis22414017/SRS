"""SRS v1.1 安装包验收脚本(G8) — 在 Windows 已安装程序上执行关键流程。

只使用合成的蒙特卡洛演示数据(demo/mc_v11), 不使用甲方真实数据。
用法: python windows_acceptance.py --base http://127.0.0.1:18080 --demo demo/mc_v11 --out acceptance_out [--phase full|restart]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

import requests

ADMIN = ("admin", "Accept@2026Srs")
RESULTS: list[dict] = []


def check(name, cond, detail=None):
    RESULTS.append({"check": name, "passed": bool(cond), "detail": detail})
    print(("[PASS] " if cond else "[FAIL] ") + name + (f" — {detail}" if detail is not None else ""))
    return cond


def login(base):
    r = requests.post(f"{base}/api/v1/auth/login", json={"username": ADMIN[0], "password": ADMIN[1]})
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def phase_full(base, demo, out):
    h = requests.get(f"{base}/health").json()
    check("health ok", h.get("status") == "ok", h.get("status"))
    check("version 1.1.0", h.get("version") == "1.1.0", h.get("version"))
    check("models healthy", (h.get("model_health") or {}).get("ok") is True)
    st = requests.get(f"{base}/api/v1/setup/status").json()
    check("empty first launch requires setup", st.get("needs_setup") is True and st.get("has_users") is False, st)
    r = requests.post(f"{base}/api/v1/setup/complete",
                      json={"username": ADMIN[0], "password": ADMIN[1], "confirm_password": ADMIN[1]})
    check("first-run admin setup", r.status_code == 200, r.status_code)
    H = login(base)
    sites = requests.get(f"{base}/api/v1/sites", headers=H).json()
    check("no business data on first launch", len(sites.get("items", [])) == 0, len(sites.get("items", [])))
    for url in ("/api/v1/templates/pre-remediation", "/api/v1/templates/ssui-post?track=production",
                "/api/v1/trace/guide"):
        rr = requests.get(base + url, headers=H)
        check(f"GET {url}", rr.status_code == 200, rr.status_code)
    meta = json.load(open(os.path.join(demo, "metadata.json"), encoding="utf-8"))
    pre = [n for n in meta["files"] if "修复前" in n][0]
    with open(os.path.join(demo, pre), "rb") as fh:
        r = requests.post(f"{base}/api/v1/import", headers=H, data={"mapping_id": "auto", "on_conflict": "skip"},
                          files={"file": (pre, fh.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    check("pre-remediation demo import", r.status_code == 200, r.status_code if r.status_code == 200 else r.text[:300])
    items = requests.get(f"{base}/api/v1/sites", headers=H).json()["items"]
    site = items[0]; sid = site["id"]; code = site["site_code"]
    check("site created with points", (site.get("n_points") or 0) > 0, site.get("n_points"))
    r = requests.post(f"{base}/api/v1/sites/{sid}/kos-diagnosis?track=prod&subset=hm&top_n=10", headers=H)
    ok = r.status_code == 200 and len(r.json().get("key_obstacles", [])) > 0
    check("S1 KOS diagnosis", ok, [k.get("factor") for k in r.json().get("key_obstacles", [])][:5] if r.status_code == 200 else r.text[:200])
    r = requests.post(f"{base}/api/v1/sites/{sid}/evaluation", headers=H, json={"scope": "production"})
    check("S2 reconstruction evaluation", r.status_code == 200, r.status_code)
    d_pre = requests.post(f"{base}/api/v1/sites/{sid}/utilization?stage=pre_remediation&farmland_type=水田", headers=H).json()
    check("pre-remediation decision labelled as scenario", d_pre.get("is_post_remediation_conclusion") is False
          and d_pre.get("conclusion_text", "").startswith("【修复前情景判断"), d_pre.get("decision_state"))
    check("pre-remediation demo data labelled simulated", d_pre.get("data_origin") == "monte_carlo_demo", d_pre.get("data_origin"))
    from openpyxl import load_workbook
    ssui = {}
    for track, cn in (("production", "生产"), ("ecology", "生态")):
        name = [n for n in meta["files"] if "课题三" in n and cn in n][0]
        wb = load_workbook(os.path.join(demo, name)); wb["批次信息"]["B2"] = code  # 演示表场地编号对齐到安装后生成的编号
        buf = io.BytesIO(); wb.save(buf)
        pv = requests.post(f"{base}/api/v1/sites/{sid}/ssui-post/preview", headers=H, data={"track": track},
                           files={"file": (name, buf.getvalue(), "application/octet-stream")}).json()
        check(f"S3 {track} preview valid", pv.get("can_confirm") is True, pv.get("n_errors"))
        cf = requests.post(f"{base}/api/v1/ssui-post/batches/{pv['batch_id']}/confirm", headers=H).json()
        ssui[track] = cf.get("calc", {}).get("ssui")
        check(f"S3 {track} confirmed", cf.get("status") == "confirmed", ssui[track])
        ex = requests.get(f"{base}/api/v1/ssui-post/batches/{pv['batch_id']}/export", headers=H)
        open(os.path.join(out, f"ssui_{track}_export.xlsx"), "wb").write(ex.content)
        check(f"S3 {track} export", ex.status_code == 200 and ex.content[:2] == b"PK", len(ex.content))
    d_post = requests.post(f"{base}/api/v1/sites/{sid}/utilization?stage=post_remediation&farmland_type=水田", headers=H).json()
    check("post-remediation decision", d_post.get("is_post_remediation_conclusion") is True, d_post.get("decision_state"))
    check("simulation label propagated", d_post.get("data_origin") == "monte_carlo_demo", d_post.get("data_origin"))
    for fmt in ("pdf", "docx"):
        r = requests.post(f"{base}/api/v1/sites/{sid}/report?format={fmt}", headers=H)
        check(f"report {fmt}", r.status_code == 200, r.status_code if r.status_code == 200 else r.text[:200])
        if r.status_code == 200:
            rid = r.json().get("report_id") or r.json().get("id")
            dl = requests.get(f"{base}/api/v1/reports/{rid}/download", headers=H)
            open(os.path.join(out, f"report.{fmt}"), "wb").write(dl.content)
            check(f"report {fmt} download", dl.status_code == 200 and len(dl.content) > 1000, len(dl.content))
    pg = requests.get(f"{base}/api/v1/sites/{sid}/trace/progress", headers=H).json()
    check("trace progress reflects real work", pg.get("completed", 0) >= 6, f"{pg.get('completed')}/{pg.get('total')}")
    state = {"site_id": sid, "decision_post": requests.get(
        f"{base}/api/v1/sites/{sid}/utilization?stage=post_remediation", headers=H).json()["decision"], "ssui": ssui}
    json.dump(state, open(os.path.join(out, "state_before_restart.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def phase_restart(base, demo, out):
    state = json.load(open(os.path.join(out, "state_before_restart.json"), encoding="utf-8"))
    st = requests.get(f"{base}/api/v1/setup/status").json()
    check("restart: setup not requested again", st.get("needs_setup") is False, st)
    H = login(base)
    d = requests.get(f"{base}/api/v1/sites/{state['site_id']}/utilization?stage=post_remediation", headers=H).json()["decision"]
    check("restart: decision identical", d == state["decision_post"], d.get("decision_id") if d else None)
    b = requests.get(f"{base}/api/v1/sites/{state['site_id']}/ssui-post/batches", headers=H).json()["batches"]
    got = {x["track"]: x["ssui"] for x in b if x["status"] == "confirmed"}
    check("restart: SSUI identical", got == state["ssui"], got)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18080")
    ap.add_argument("--demo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--phase", default="full", choices=["full", "restart"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for _ in range(90):
        try:
            if requests.get(f"{a.base}/health", timeout=3).status_code == 200:
                break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    try:
        (phase_full if a.phase == "full" else phase_restart)(a.base, a.demo, a.out)
    except Exception as e:  # noqa: BLE001
        check(f"{a.phase} phase raised", False, repr(e)[:300])
    json.dump(RESULTS, open(os.path.join(a.out, f"acceptance_{a.phase}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    failed = [r for r in RESULTS if not r["passed"]]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    sys.exit(1 if failed else 0)
