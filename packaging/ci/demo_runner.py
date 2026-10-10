"""SRS v1.2 演示包执行器: 按 metadata.json 的导入顺序经 HTTP API 执行全部场景与夹具, 与 expected.json 比对。

同一份代码用于:
  * 本机: scripts/mc_demo_v12.py run (FastAPI TestClient, 独立演示库)
  * Windows 安装包验收: packaging/ci/windows_acceptance.py (requests → 已安装的 SRS.exe)
"""
from __future__ import annotations

import io
import json
import os

try:
    import report_invariants as RI
except ImportError:  # pragma: no cover
    from packaging.ci import report_invariants as RI  # type: ignore

LABEL = "模拟数据——仅供测试/演示"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Http:
    """requests.Session 或 TestClient 的薄封装。"""

    def __init__(self, client, base: str = ""):
        self.c, self.base, self.h = client, base.rstrip("/"), {}

    def get(self, url, **kw):
        return self.c.get(self.base + url, headers={**self.h, **kw.pop("headers", {})}, **kw)

    def post(self, url, **kw):
        return self.c.post(self.base + url, headers={**self.h, **kw.pop("headers", {})}, **kw)


def _set_code(path: str, sheet: str, cell: str, code: str) -> bytes:
    from openpyxl import load_workbook
    wb = load_workbook(path)
    wb[sheet][cell] = code
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()


def ensure_admin(http: Http, admin: tuple[str, str]) -> dict:
    st = http.get("/api/v1/setup/status").json()
    out = {"first_launch_needs_setup": st.get("needs_setup"), "has_users_before": st.get("has_users")}
    if st.get("needs_setup"):
        r = http.post("/api/v1/setup/complete", json={"username": admin[0], "password": admin[1], "confirm_password": admin[1]})
        out["setup_status"] = r.status_code
    r = http.post("/api/v1/auth/login", json={"username": admin[0], "password": admin[1]})
    r.raise_for_status()
    http.h = {"Authorization": "Bearer " + r.json()["access_token"]}
    return out


def run_all(http: Http, demo: str, out: str, admin: tuple[str, str], report: bool = True) -> dict:
    os.makedirs(out, exist_ok=True)
    meta = json.load(open(os.path.join(demo, "metadata.json"), encoding="utf-8"))
    exp = json.load(open(os.path.join(demo, "expected.json"), encoding="utf-8"))
    import hashlib
    checks: list[dict] = []

    def check(name, cond, detail=None):
        checks.append({"check": name, "passed": bool(cond), "detail": detail})
        print(("[PASS] " if cond else "[FAIL] ") + name + (f" — {detail}" if detail is not None else ""))
        return cond

    for rel, sha in meta["files"].items():
        got = hashlib.sha256(open(os.path.join(demo, rel), "rb").read()).hexdigest()
        if got != sha:
            check(f"demo file unchanged {rel}", False, got[:12])
    setup = ensure_admin(http, admin)
    actual: dict = {"setup": setup, "scenarios": {}, "fixtures": {}}
    sites0 = {s["id"] for s in http.get("/api/v1/sites", params={"page_size": 100}).json().get("items", [])}
    for code, ex in exp["scenarios"].items():
        d = os.path.join(demo, f"site_{code}")
        files = sorted(os.listdir(d))
        f1 = [f for f in files if f.startswith("01_")][0]
        a: dict = {"title": ex["title"]}
        r = http.post("/api/v1/import", data={"mapping_id": "auto", "on_conflict": "skip"},
                      files={"file": (f1, open(os.path.join(d, f1), "rb").read(), XLSX)})
        check(f"[{code}] 修复前检测数据导入", r.status_code == 200, r.status_code if r.status_code == 200 else r.text[:200])
        items = http.get("/api/v1/sites", params={"page_size": 100}).json().get("items", [])
        new = [s for s in items if s["id"] not in sites0]
        if not new:
            check(f"[{code}] 场地已创建", False); continue
        site = new[0]; sites0.add(site["id"]); sid, scode = site["id"], site["site_code"]
        a.update({"site_id": sid, "site_code": scode})
        check(f"[{code}] 场地编号为纯字母约定", all(ch.isalpha() or ch == "-" for ch in scode), scode)
        # v1.2.1: KOS 与利用方向门禁使用同一 GB 15618 农用地类型(水田)
        r = http.post(f"/api/v1/sites/{sid}/kos-diagnosis?track=prod&subset=hm&top_n=10&farmland_type=水田")
        kj = r.json() if r.status_code == 200 else {}
        a["S1_kos_top"] = [k.get("factor") for k in kj.get("key_obstacles", [])][:6] if r.status_code == 200 else None
        a["S1_kos_status"] = kj.get("official_ranking_status")
        a["S1_kos_exploratory"] = [k.get("factor") for k in kj.get("exploratory_obstacles", [])]
        check(f"[{code}] 课题一 KOS 诊断(正式/探索性分层)", r.status_code == 200 and a["S1_kos_status"] in
              ("available", "partial", "insufficient_evidence"), {"status": a["S1_kos_status"], "top": a["S1_kos_top"]})
        check(f"[{code}] 课题一 正式 Top-N 仅含官方证据(无肥力下限指标)",
              not (set(a["S1_kos_top"] or []) & RI.FERTILITY)
              and all(k.get("evidence") in ("A", "B") for k in kj.get("key_obstacles", [])), a["S1_kos_top"])
        f2 = [f for f in files if f.startswith("02_")][0]
        content = open(os.path.join(d, f2), "rb").read()  # 演示文件原样导入(B2 留空 = 所选场地)
        pv = http.post(f"/api/v1/sites/{sid}/recon/preview", files={"file": (f2, content, XLSX)}).json()
        check(f"[{code}] 课题二 指标预览通过", pv.get("can_confirm") is True, (pv.get("errors") or [])[:3])
        cf = http.post(f"/api/v1/recon/batches/{pv.get('batch_id')}/confirm").json()
        ev = cf.get("evaluation") or {}
        a["S2"] = {t: {k: (ev.get(t) or {}).get(k) for k in ("score", "grade", "path", "point_grade_distribution")}
                   for t in ("production", "ecology")}
        a["S2"]["data_origin_label"] = pv.get("data_origin_label")
        check(f"[{code}] 课题二 确认并计算", cf.get("status") == "confirmed" and ev.get("production", {}).get("score") is not None,
              a["S2"]["production"])
        check(f"[{code}] 课题二 模拟数据标签", pv.get("data_origin_label") == LABEL, pv.get("data_origin_label"))
        x = http.get(f"/api/v1/recon/batches/{pv.get('batch_id')}/export")
        open(os.path.join(out, f"{code}_S2_export_batch{pv.get('batch_id')}.xlsx"), "wb").write(x.content)
        check(f"[{code}] 课题二 导出", x.status_code == 200 and x.content[:2] == b"PK", len(x.content))
        r = http.post(f"/api/v1/sites/{sid}/evaluation", json={"scope": "production"})
        check(f"[{code}] 综合评价(重构+SSUI参考)", r.status_code == 200, r.status_code)
        dp = http.post(f"/api/v1/sites/{sid}/utilization", params={"stage": "pre_remediation", "farmland_type": "水田", "eco_land_class": "第一类用地"}).json()
        a["decision_pre"] = {"state": dp.get("decision_state"), "gates": {t: dp.get(t, {}).get("gate", {}).get("state")
                                                                         for t in ("production", "ecology")}}
        check(f"[{code}] 修复前情景判断(非修复后结论)", dp.get("is_post_remediation_conclusion") is False, a["decision_pre"])
        a["S3"] = {}
        for track, prefix in (("production", "03_"), ("ecology", "04_")):
            fn = [f for f in files if f.startswith(prefix)][0]
            content = open(os.path.join(d, fn), "rb").read()
            pv3 = http.post(f"/api/v1/sites/{sid}/ssui-post/preview", data={"track": track},
                            files={"file": (fn, content, XLSX)}).json()
            ok = pv3.get("can_confirm") is True
            check(f"[{code}] 课题三 {track} 预览", ok, pv3.get("n_errors"))
            if not ok:
                continue
            cf3 = http.post(f"/api/v1/ssui-post/batches/{pv3['batch_id']}/confirm").json()
            calc = cf3.get("calc", {})
            a["S3"][track] = {"ssui": calc.get("ssui"), "grade": calc.get("grade"), "feasible": calc.get("feasible")}
            e_s = ex["ssui"][track]["ssui"]
            check(f"[{code}] 课题三 {track} SSUI = 独立期望值", calc.get("ssui") is not None and abs(calc["ssui"] - e_s) < 1e-5,
                  f"actual {calc.get('ssui')} expected {e_s}")
            xx = http.get(f"/api/v1/ssui-post/batches/{pv3['batch_id']}/export")
            open(os.path.join(out, f"{code}_S3_{track}_export_batch{pv3['batch_id']}.xlsx"), "wb").write(xx.content)
        dq = http.post(f"/api/v1/sites/{sid}/utilization", params={"stage": "post_remediation", "farmland_type": "水田", "eco_land_class": "第一类用地"}).json()
        a["decision_post"] = {"state": dq.get("decision_state"),
                              "gates": {t: dq.get(t, {}).get("gate", {}).get("state") for t in ("production", "ecology")},
                              "conclusion_text": dq.get("conclusion_text"), "missing_evidence": dq.get("missing_evidence"),
                              "data_origin": dq.get("data_origin")}
        check(f"[{code}] 修复后门禁 = 独立期望值", a["decision_post"]["gates"] == ex["post_gates"],
              f"actual {a['decision_post']['gates']} expected {ex['post_gates']}")
        check(f"[{code}] 修复后利用结论 = 期望分支 {ex['post_decision']}", dq.get("decision_state") == ex["post_decision"],
              dq.get("decision_state"))
        check(f"[{code}] 结论带模拟数据标签", dq.get("data_origin") == "monte_carlo_demo", dq.get("data_origin"))
        if report:
            # v1.2.1(R03): 每个场景都出 PDF/DOCX/快照 Excel, 并做跨渠道一致性断言
            files_b, rsnaps = {}, []
            for fmt in ("pdf", "docx"):
                rr = http.post(f"/api/v1/sites/{sid}/report?format={fmt}")
                ok = rr.status_code == 200
                if ok:
                    rid = rr.json().get("report_id") or rr.json().get("id")
                    dl = http.get(f"/api/v1/reports/{rid}/download")
                    open(os.path.join(out, f"{code}_report.{fmt}"), "wb").write(dl.content)
                    files_b[fmt] = dl.content
                    ok = dl.status_code == 200 and len(dl.content) > 1000
                    rsnaps.append({**http.get(f"/api/v1/reports/{rid}/snapshot").json(), "format": fmt})
                check(f"[{code}] 报告 {fmt} 生成与下载", ok, rr.status_code)
            sj = http.get(f"/api/v1/sites/{sid}/evaluation-snapshot").json()
            a["snapshot_headline"] = sj.get("headline")
            json.dump(sj.get("snapshot"), open(os.path.join(out, f"{code}_evaluation_snapshot.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1, default=str)
            xb = http.get(f"/api/v1/sites/{sid}/evaluation-snapshot.xlsx").content
            open(os.path.join(out, f"{code}_evaluation_snapshot.xlsx"), "wb").write(xb)
            for c_ in RI.check_channels(sj.get("headline") or {}, [{k: v for k, v in r_.items() if k != "snapshot"} for r_ in rsnaps],
                                        xb, files_b.get("pdf"), files_b.get("docx")):
                check(f"[{code}] 跨渠道 {c_['check']}", c_["passed"], c_["detail"])
            hl = sj.get("headline") or {}
            check(f"[{code}] 报告修复后结论 = 利用方向结论", hl.get("decision_post") == dq.get("decision_state"),
                  hl.get("decision_post"))
            pg = http.get(f"/api/v1/sites/{sid}/trace/progress").json()
            a["trace_progress"] = {"software_milestones": f"{pg.get('completed')}/{pg.get('total')}",
                                   "business_stages_completed": f"{pg.get('business_completed')}/{pg.get('business_total')}",
                                   "milestone_kind": pg.get("milestone_kind")}
            check(f"[{code}] 七项软件操作里程碑与五阶段业务记录分开报告",
                  pg.get("milestone_kind") == "software_operation" and pg.get("business_total") == 5, a["trace_progress"])
        actual["scenarios"][code] = a
    # ───── v1.2.1 补充场景 F/G(课题一 正式/探索性分层, 有机物单位对齐) ─────
    for code, cs in ((meta.get("cases_v121") or {}).get("cases") or {}).items():
        path = os.path.join(demo, cs["file"])
        got = hashlib.sha256(open(path, "rb").read()).hexdigest()
        check(f"[{code}] 补充场景文件未改动", got == meta["cases_v121"]["files"][cs["file"]], got[:12])
        r = http.post("/api/v1/import", data={"mapping_id": "auto", "on_conflict": "skip"},
                      files={"file": (os.path.basename(path), open(path, "rb").read(), XLSX)})
        check(f"[{code}] 修复前检测数据导入", r.status_code == 200, r.status_code)
        items = http.get("/api/v1/sites", params={"page_size": 100}).json().get("items", [])
        new = [x for x in items if x["id"] not in sites0]
        if not new:
            check(f"[{code}] 场地已创建", False); continue
        sid = new[0]["id"]; sites0.add(sid)
        k = cs["kos"]
        q = f"track={k['track']}&subset={k['subset']}&top_n=10"
        q += f"&eco_land_class={k['eco_land_class']}" if k.get("eco_land_class") else ""
        q += f"&farmland_type={k['farmland_type']}" if k.get("farmland_type") else ""
        kj = http.post(f"/api/v1/sites/{sid}/kos-diagnosis?{q}").json()
        ex = cs["expected"]
        off = {o["factor"]: o for o in kj.get("key_obstacles", [])}
        exp_ = {o["factor"]: o for o in kj.get("exploratory_obstacles", [])}
        a = {"site_id": sid, "official": sorted(off), "exploratory": sorted(exp_), "status": kj.get("official_ranking_status")}
        check(f"[{code}] 正式 Top-N 因子 = 独立期望", sorted(off) == sorted(ex.get("official_factors", [])),
              f"actual {sorted(off)} expected {ex.get('official_factors')}")
        if ex.get("official_ranking_status"):
            check(f"[{code}] 正式排名状态 = {ex['official_ranking_status']}", kj.get("official_ranking_status") == ex["official_ranking_status"],
                  kj.get("official_ranking_status"))
        for f, d_ in (ex.get("official_detail") or {}).items():
            o = off.get(f, {})
            check(f"[{code}] {f} 超标倍数 = 独立期望 {d_['ratio']}", abs((o.get("exceedance_ratio") or 0) - d_["ratio"]) < 1e-3,
                  {"value": o.get("value"), "threshold": o.get("threshold_value"), "unit": o.get("threshold_unit")})
        for f in ex.get("exploratory_must_include", []):
            check(f"[{code}] {f} 仅在探索性列表", f in exp_ and f not in off, sorted(exp_))
            if ex.get("exploratory_direction"):
                check(f"[{code}] {f} 方向 = {ex['exploratory_direction']}", (exp_.get(f) or {}).get("threshold_type") == ex["exploratory_direction"],
                      (exp_.get(f) or {}).get("threshold_type"))
        for f in ex.get("official_must_exclude", []):
            check(f"[{code}] {f} 不进入正式 Top-N", f not in off)
        actual["scenarios"][code] = a
    # ───── v1.2.2 场地 H: 方案推荐 + 五阶段业务追溯(角色/退回/下载/报告) ─────
    if meta.get("cases_v122"):
        try:
            import workflow_demo as WD
        except ImportError:  # pragma: no cover
            from packaging.ci import workflow_demo as WD  # type: ignore
        actual["scenarios"]["H"] = WD.run_site_h(http, demo, meta, check, out, report=report)
        actual["phthalate_case_P"] = WD.run_case_p(http, demo, meta, check)
    # ───── 夹具 ─────
    sA = actual["scenarios"].get("A", {})
    sidA, codeA = sA.get("site_id"), sA.get("site_code")
    for k, fx in meta["fixtures"].items():
        path = os.path.join(demo, fx["file"])
        name = os.path.basename(path)
        if k.startswith("F07"):
            pv = http.post(f"/api/v1/sites/{sidA}/ssui-post/preview", data={"track": "production"},
                           files={"file": (name, _set_code(path, "批次信息", "B2", codeA), XLSX)}).json()
            msgs = " ".join(str(e.get("message")) for e in pv.get("errors", []))
            ok = pv.get("can_confirm") is False and fx["message_contains"] in msgs
        else:
            content = _set_code(path, "批次信息", "B2", codeA) if not k.startswith("F08") else _set_code(path, "批次信息", "B2", codeA)
            pv = http.post(f"/api/v1/sites/{sidA}/recon/preview", files={"file": (name, content, XLSX)}).json()
            errs = " ".join(e["message"] for e in pv.get("errors", []))
            warns = " ".join(w["message"] for w in pv.get("warnings", []))
            if fx["expect"] == "warning":
                ok = pv.get("can_confirm") is True and fx["message_contains"] in warns
                if ok:
                    http.post(f"/api/v1/recon/batches/{pv['batch_id']}/reject")
            else:
                ok = pv.get("can_confirm") is False and fx["message_contains"] in errs
        actual["fixtures"][k] = {"expect": fx["expect"], "passed": ok,
                                 "messages": [e.get("message") for e in pv.get("errors", [])][:5]}
        check(f"夹具 {k} ({fx['expect']})", ok, actual["fixtures"][k]["messages"][:2])
    # ───── v1.2.2(T01): v1.2.1 旧 S3 得分(SSUI>1, 域外)经真实 API 回放 → 不分级、不给支持; 再恢复域内输入 ─────
    fxA = (exp.get("ssui_out_of_domain_fixtures") or {}).get("A_production")
    if fxA and sidA:
        uq = {"stage": "post_remediation", "farmland_type": "水田", "eco_land_class": "第一类用地"}

        def _s3(path):
            nm = os.path.basename(path)
            pv = http.post(f"/api/v1/sites/{sidA}/ssui-post/preview", data={"track": "production"},
                           files={"file": (nm, open(path, "rb").read(), XLSX)}).json()
            if not pv.get("can_confirm"):
                return pv, {}
            return pv, http.post(f"/api/v1/ssui-post/batches/{pv['batch_id']}/confirm").json().get("calc", {})
        pv, calc = _s3(os.path.join(demo, fxA["file"]))
        check("[A·域外夹具] v1.2.1 旧得分可导入预览", pv.get("can_confirm") is True, pv.get("n_errors"))
        check(f"[A·域外夹具] SSUI 原值保留 {fxA['ssui']} 且 status=out_of_domain", abs((calc.get("ssui") or 0) - fxA["ssui"]) < 1e-5
              and calc.get("status") == "out_of_domain", {"ssui": calc.get("ssui"), "status": calc.get("status")})
        check("[A·域外夹具] 不分级、可行性不判定", calc.get("grade") is None and calc.get("feasible") is None,
              {"grade": calc.get("grade"), "feasible": calc.get("feasible")})
        dq = http.post(f"/api/v1/sites/{sidA}/utilization", params=uq).json()
        check("[A·域外夹具] 利用结论不给生产正向支持", dq.get("decision_state") not in ("both_supported", "production_supported")
              and (dq.get("production") or {}).get("track_status") != "supported",
              {"decision": dq.get("decision_state"), "production": (dq.get("production") or {}).get("track_status")})
        fx_rep = {"ssui": calc.get("ssui"), "status": calc.get("status"), "grade": calc.get("grade"),
                  "decision_with_fixture": dq.get("decision_state"), "production_track": (dq.get("production") or {}).get("track_status")}
        dA = os.path.join(demo, "site_A"); f03 = [f for f in sorted(os.listdir(dA)) if f.startswith("03_")][0]
        pv, calc = _s3(os.path.join(dA, f03))
        dq = http.post(f"/api/v1/sites/{sidA}/utilization", params=uq).json()
        check("[A·域外夹具] 恢复域内输入后结论回到期望分支", dq.get("decision_state") == exp["scenarios"]["A"]["post_decision"],
              dq.get("decision_state"))
        fx_rep["decision_after_restore"] = dq.get("decision_state")
        actual["ssui_out_of_domain_replay"] = fx_rep
    passed = sum(c["passed"] for c in checks)
    actual["summary"] = {"checks": len(checks), "passed": passed, "failed": len(checks) - passed,
                         "decisions": {c: s.get("decision_post", {}).get("state") for c, s in actual["scenarios"].items()},
                         "expected": {c: e["post_decision"] for c, e in exp["scenarios"].items()}}
    actual["checks"] = checks
    json.dump(actual, open(os.path.join(out, "comparison.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return actual
