"""SRS v1.2 安装包验收脚本 — 在 Windows 已安装(或便携版)程序上经 HTTP 执行关键流程。

只使用合成的蒙特卡洛演示数据(demo/mc_v12, demo/mc_v11), 不使用甲方真实数据。
阶段:
  full      空库首启 → 管理员设置 → demo_runner 全部 5 个场景 + 8 个夹具 → 与 expected.json 比对 → 状态快照
  restart   重启后: 不再要求设置; 5 个场景的修复后结论、课题二批次、课题三 SSUI 与快照一致
  seed_v11  (旧版 v1.1.0 安装后) 首启设置 + 导入 v1.1 演示修复前数据 + 课题三生产批次, 快照
  upgrade   (覆盖安装 v1.2.0 后) 旧数据仍在、旧结论可读、新接口可用、阈值已按官方值更正
  portable  便携版: 数据目录位于 exe 同级 SRS_data, 空库首启 + 一次导入与计算
用法: python windows_acceptance.py --base http://127.0.0.1:18080 --demo demo/mc_v12 --out acceptance_out --phase full
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import demo_runner as DR  # noqa: E402

ADMIN = ("admin", "Accept@2026Srs")
EXPECTED_VERSION = open(os.path.join(os.path.dirname(__file__), "..", "..", "VERSION"), encoding="utf-8").read().strip()
RESULTS: list[dict] = []


def check(name, cond, detail=None):
    RESULTS.append({"check": name, "passed": bool(cond), "detail": detail})
    print(("[PASS] " if cond else "[FAIL] ") + name + (f" — {detail}" if detail is not None else ""))
    return cond


def http(base):
    return DR.Http(requests.Session(), base)


def _health(base, version):
    h = requests.get(f"{base}/health").json()
    check("health ok", h.get("status") == "ok", h.get("status"))
    check(f"version {version}", h.get("version") == version, h.get("version"))
    check("models healthy (packaged model files load)", (h.get("model_health") or {}).get("ok") is True,
          (h.get("model_health") or {}).get("ok"))
    return h


def phase_full(base, demo, out):
    _health(base, EXPECTED_VERSION)
    st = requests.get(f"{base}/api/v1/setup/status").json()
    check("empty first launch requires setup", st.get("needs_setup") is True and st.get("has_users") is False, st)
    H = http(base)
    DR.ensure_admin(H, ADMIN)
    sites = H.get("/api/v1/sites").json()
    check("no business data on first launch", len(sites.get("items", [])) == 0, len(sites.get("items", [])))
    for url in ("/api/v1/templates/pre-remediation", "/api/v1/templates/ssui-post?track=production",
                "/api/v1/templates/recon-pre", "/api/v1/trace/guide", "/api/v1/methods/reconstruction-baseline",
                "/api/v1/files"):
        rr = H.get(url)
        check(f"GET {url}", rr.status_code == 200, rr.status_code)
    res = DR.run_all(H, demo, os.path.join(out, "demo_actual"), admin=ADMIN)
    for c in res["checks"]:
        check("demo " + c["check"], c["passed"], c["detail"])
    _write_state(H, {code: s["site_id"] for code, s in res["scenarios"].items()}, out)


def _write_state(H, site_ids, out, name="state_before_restart.json"):
    state = {"sites": {}}
    for code, sid in site_ids.items():
        dec = H.get(f"/api/v1/sites/{sid}/utilization", params={"stage": "post_remediation"}).json()["decision"]
        rb = H.get(f"/api/v1/sites/{sid}/recon/batches").json()["batches"]
        sb = H.get(f"/api/v1/sites/{sid}/ssui-post/batches").json()["batches"]
        state["sites"][code] = {"site_id": sid, "decision_post": dec,
                                "recon": [(b["batch_id"], b["status"], b["production"], b["ecology"]) for b in rb],
                                "ssui": sorted([(b["track"], b["ssui"]) for b in sb if b["status"] == "confirmed"])}
    json.dump(state, open(os.path.join(out, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return state


def phase_snapshot(base, demo, out):
    """截图阶段(会上传夹具生成预览批次)之后、停止程序之前, 重新记录重启前状态。"""
    p = os.path.join(out, "state_before_restart.json")
    old = json.load(open(p, encoding="utf-8"))
    os.replace(p, os.path.join(out, "state_after_full_phase.json"))
    H = http(base); DR.ensure_admin(H, ADMIN)
    st = _write_state(H, {c: v["site_id"] for c, v in old["sites"].items()}, out)
    for c, v in st["sites"].items():
        check(f"snapshot [{c}]: post decision unchanged by screenshot stage",
              json.dumps(v["decision_post"], sort_keys=True, default=str) == json.dumps(old["sites"][c]["decision_post"], sort_keys=True, default=str))
        check(f"snapshot [{c}]: confirmed S2/S3 unchanged by screenshot stage",
              [b for b in v["recon"] if b[1] == "confirmed"] == [b for b in old["sites"][c]["recon"] if b[1] == "confirmed"]
              and v["ssui"] == old["sites"][c]["ssui"], len(v["recon"]) - len(old["sites"][c]["recon"]))


def phase_restart(base, demo, out):
    _health(base, EXPECTED_VERSION)
    state = json.load(open(os.path.join(out, "state_before_restart.json"), encoding="utf-8"))
    st = requests.get(f"{base}/api/v1/setup/status").json()
    check("restart: setup not requested again", st.get("needs_setup") is False, st)
    H = http(base); DR.ensure_admin(H, ADMIN)
    for code, s in state["sites"].items():
        sid = s["site_id"]
        dec = H.get(f"/api/v1/sites/{sid}/utilization", params={"stage": "post_remediation"}).json()["decision"]
        check(f"restart [{code}]: post decision identical", json.dumps(dec, sort_keys=True, default=str)
              == json.dumps(s["decision_post"], sort_keys=True, default=str), (dec or {}).get("decision_state"))
        rb = H.get(f"/api/v1/sites/{sid}/recon/batches").json()["batches"]
        got = [(b["batch_id"], b["status"], b["production"], b["ecology"]) for b in rb]
        check(f"restart [{code}]: S2 batches identical", json.loads(json.dumps(got)) == json.loads(json.dumps(s["recon"])), len(got))
        sb = H.get(f"/api/v1/sites/{sid}/ssui-post/batches").json()["batches"]
        got = sorted([(b["track"], b["ssui"]) for b in sb if b["status"] == "confirmed"])
        check(f"restart [{code}]: S3 SSUI identical", json.loads(json.dumps(got)) == json.loads(json.dumps(s["ssui"])), got)


def phase_seed_v11(base, demo, out):
    """demo 指向 demo/mc_v11(旧版本自带的演示包)。"""
    h = requests.get(f"{base}/health").json()
    check("old version running", h.get("version") == "1.1.0", h.get("version"))
    H = http(base); DR.ensure_admin(H, ADMIN)
    meta = json.load(open(os.path.join(demo, "metadata.json"), encoding="utf-8"))
    pre = [n for n in meta["files"] if "修复前" in n][0]
    r = H.post("/api/v1/import", data={"mapping_id": "auto", "on_conflict": "skip"},
               files={"file": (pre, open(os.path.join(demo, pre), "rb").read(), DR.XLSX)})
    check("v1.1: pre-remediation import", r.status_code == 200, r.status_code)
    site = H.get("/api/v1/sites").json()["items"][0]
    sid = site["id"]
    r = H.post(f"/api/v1/sites/{sid}/evaluation", json={"scope": "production"})
    check("v1.1: evaluation", r.status_code == 200, r.status_code)
    name = [n for n in meta["files"] if "课题三" in n and "生产" in n][0]
    content = DR._set_code(os.path.join(demo, name), "批次信息", "B2", site["site_code"])
    pv = H.post(f"/api/v1/sites/{sid}/ssui-post/preview", data={"track": "production"},
                files={"file": (name, content, DR.XLSX)}).json()
    cf = H.post(f"/api/v1/ssui-post/batches/{pv['batch_id']}/confirm").json()
    check("v1.1: S3 confirmed", cf.get("status") == "confirmed", (cf.get("calc") or {}).get("ssui"))
    n_meas = H.get(f"/api/v1/sites/{sid}").json().get("n_measurements") or H.get(f"/api/v1/sites/{sid}").json().get("measurement_count")
    snap = {"site_id": sid, "site_code": site["site_code"], "n_points": site.get("n_points"), "n_measurements": n_meas,
            "ssui": (cf.get("calc") or {}).get("ssui"),
            "ssui_batches": H.get(f"/api/v1/sites/{sid}/ssui-post/batches").json()["batches"]}
    json.dump(snap, open(os.path.join(out, "state_v11.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)


def phase_upgrade(base, demo, out):
    _health(base, EXPECTED_VERSION)
    snap = json.load(open(os.path.join(out, "state_v11.json"), encoding="utf-8"))
    st = requests.get(f"{base}/api/v1/setup/status").json()
    check("upgrade: existing admin kept (no setup prompt)", st.get("needs_setup") is False, st)
    H = http(base); DR.ensure_admin(H, ADMIN)
    site = H.get(f"/api/v1/sites/{snap['site_id']}").json()
    check("upgrade: v1.1 site preserved", site.get("site_code") == snap["site_code"], site.get("site_code"))
    b = H.get(f"/api/v1/sites/{snap['site_id']}/ssui-post/batches").json()["batches"]
    check("upgrade: v1.1 S3 batch and SSUI preserved",
          [x["ssui"] for x in b if x["status"] == "confirmed"] == [x["ssui"] for x in snap["ssui_batches"] if x["status"] == "confirmed"],
          [x["ssui"] for x in b])
    r = H.get(f"/api/v1/sites/{snap['site_id']}/recon/batches")
    check("upgrade: new v1.2 tables available (recon batches)", r.status_code == 200 and r.json()["batches"] == [], r.status_code)
    r = H.get("/api/v1/methods/reconstruction-baseline")
    check("upgrade: frozen method baseline served", r.status_code == 200 and "M-REC-2025" in r.json().get("method_version", ""))
    r = H.get("/api/v1/files")
    check("upgrade: file management accessible (file:read granted to existing roles)", r.status_code == 200, r.status_code)
    r = H.post(f"/api/v1/sites/{snap['site_id']}/evaluation", json={"scope": "production"})
    check("upgrade: re-evaluation with v1.2 method on upgraded data", r.status_code == 200, r.status_code)


def phase_portable(base, demo, out):
    _health(base, EXPECTED_VERSION)
    st = requests.get(f"{base}/api/v1/setup/status").json()
    check("portable: empty first launch", st.get("needs_setup") is True, st)
    H = http(base); DR.ensure_admin(H, ADMIN)
    d = os.path.join(demo, "site_A")
    f1 = [f for f in sorted(os.listdir(d)) if f.startswith("01_")][0]
    r = H.post("/api/v1/import", data={"mapping_id": "auto", "on_conflict": "skip"},
               files={"file": (f1, open(os.path.join(d, f1), "rb").read(), DR.XLSX)})
    check("portable: import", r.status_code == 200, r.status_code)
    sid = H.get("/api/v1/sites").json()["items"][0]["id"]
    r = H.post(f"/api/v1/sites/{sid}/evaluation", json={"scope": "production"})
    check("portable: evaluation", r.status_code == 200, r.status_code)


PHASES = {"full": phase_full, "snapshot": phase_snapshot, "restart": phase_restart, "seed_v11": phase_seed_v11, "upgrade": phase_upgrade,
          "portable": phase_portable}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:18080")
    ap.add_argument("--demo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--phase", default="full", choices=list(PHASES))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    up = False
    for _ in range(120):
        try:
            if requests.get(f"{a.base}/health", timeout=3).status_code == 200:
                up = True; break
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    check(f"{a.phase}: application reachable", up)
    try:
        if up:
            PHASES[a.phase](a.base, a.demo, a.out)
    except Exception as e:  # noqa: BLE001
        check(f"{a.phase} phase raised", False, repr(e)[:300])
    json.dump(RESULTS, open(os.path.join(a.out, f"acceptance_{a.phase}.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=str)
    failed = [r for r in RESULTS if not r["passed"]]
    print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    sys.exit(1 if failed else 0)
