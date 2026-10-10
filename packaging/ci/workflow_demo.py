"""SRS v1.2.2 场地 H: 方案推荐 + 五阶段业务追溯 —— 全部经 HTTP API 执行(本机 TestClient / Windows 已安装 SRS.exe 共用)。

身份全部为模拟账户: 企业填报员(enterprise, 自注册+管理员批准)、模拟审核员(admin 角色)、模拟监管查看员(regulator)、
另一家无关企业(enterprise)。每一步记录 HTTP 状态与关键返回值, 供 comparison.json / 证据包使用。
"""
from __future__ import annotations

import hashlib
import io
import json
import os

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _child(http, token: str | None):
    h = type(http)(http.c, http.base)
    h.h = {"Authorization": "Bearer " + token} if token else {}
    return h


def _req(http, method: str, url: str, **kw):
    return getattr(http.c, method)(http.base + url, headers={**http.h, **kw.pop("headers", {})}, **kw)


def _ensure_users(admin, case) -> dict:
    """创建/批准模拟账户(可重复执行: 已存在则跳过)。返回 {key: Http}。"""
    pw, out, info = case["password"], {}, {}
    for key, u in case["users"].items():
        if u["via"] == "register+approve":
            r = admin.post("/api/v1/auth/register", json={"username": u["username"], "password": pw, "display_name": u["display_name"],
                                                         "organization_name": u["organization_name"], "role_code": u["role"]})
            if r.status_code == 200:
                admin.post(f"/api/v1/auth/approve/{r.json()['user_id']}")
            info[key] = {"create_status": r.status_code}
        else:
            r = admin.post("/api/v1/system/users", json={"username": u["username"], "password": pw, "display_name": u["display_name"],
                                                         "role_codes": [u["role"]]})
            info[key] = {"create_status": r.status_code}
        lg = admin.c.post(admin.base + "/api/v1/auth/login", json={"username": u["username"], "password": pw})
        info[key]["login_status"] = lg.status_code
        tok = lg.json().get("access_token") if lg.status_code == 200 else None
        out[key] = _child(admin, tok)
        if tok:
            me = out[key].get("/api/v1/auth/me")
            info[key]["user_id"] = me.json().get("id") if me.status_code == 200 else None
    return out, info


def _docx_text(b: bytes) -> str:
    import zipfile
    import re
    x = zipfile.ZipFile(io.BytesIO(b)).read("word/document.xml").decode("utf-8")
    return re.sub(r"<[^>]+>", "", x)


def run_site_h(admin, demo: str, meta: dict, check, out: str, report: bool = True) -> dict:
    cs_all = (meta.get("cases_v122") or {})
    case = (cs_all.get("cases") or {}).get("H")
    if not case:
        return {}
    a: dict = {"steps": []}
    for rel, sha in cs_all["files"].items():
        got = _sha(open(os.path.join(demo, rel), "rb").read())
        check(f"[v1.2.2 案例] 演示文件未改动 {os.path.basename(rel)}", got == sha, got[:12])
    U, info = _ensure_users(admin, case)
    a["users"] = info
    check("[H] 模拟账户创建/登录(企业·审核员·监管·无关企业)", all(v.get("login_status") == 200 for v in info.values()), info)
    ent, rev, reg, oth = U["enterprise"], U["reviewer"], U["regulator"], U["other_enterprise"]
    ent_id, rev_id = info["enterprise"].get("user_id"), info["reviewer"].get("user_id")

    # ── 企业用户导入修复前数据 → 场地归属本企业 ──
    path = os.path.join(demo, case["file"])
    r = ent.post("/api/v1/import", data={"mapping_id": "auto", "on_conflict": "skip"},
                 files={"file": (os.path.basename(path), open(path, "rb").read(), XLSX)})
    check("[H] 企业用户导入修复前检测数据", r.status_code == 200, r.status_code if r.status_code == 200 else r.text[:200])
    sid = r.json().get("site_id") if r.status_code == 200 else None
    if not sid:
        return a
    a["site_id"] = sid
    lst = ent.get("/api/v1/sites", params={"page_size": 100}).json().get("items", [])
    a["site_code"] = next((x["site_code"] for x in lst if x["id"] == sid), None)
    check("[H] 企业用户可在场地列表看到自己导入的场地(归属本企业)", a["site_code"] is not None, [x["id"] for x in lst])

    # ── 课题一 KOS(生产轨) ──
    k = case["kos"]
    kj = ent.post(f"/api/v1/sites/{sid}/kos-diagnosis?track={k['track']}&subset={k['subset']}&top_n=10&farmland_type={k['farmland_type']}").json()
    off = {o["factor"]: o for o in kj.get("key_obstacles", [])}
    ex = case["expected"]
    check("[H] 正式 Top-N 因子 = 独立期望", sorted(off) == ex["official_factors"], f"actual {sorted(off)} expected {ex['official_factors']}")
    for f, d_ in ex["official_detail"].items():
        o = off.get(f, {})
        check(f"[H] {f} 超标倍数 = 独立期望 {d_['ratio']}", abs((o.get("exceedance_ratio") or 0) - d_["ratio"]) < 1e-3,
              {"value": o.get("value"), "threshold": o.get("threshold_value")})
    a["kos_official"] = sorted(off)

    # ── 方案推荐: 生成 → 比选 → 选择记录 ──
    rr = ent.post(f"/api/v1/sites/{sid}/recommendation")
    rj = rr.json() if rr.status_code == 200 else {}
    recs = rj.get("recommendations") or []
    check("[H] 生成方案推荐(规则推荐, 基于正式障碍因子)", rr.status_code == 200 and len(recs) >= ex["recommendation"]["min_candidates"],
          rr.status_code)
    top = recs[0] if recs else {}
    check("[H] 第 1 名候选命中正式障碍因子", bool(set(top.get("matched_factors") or []) & set(ex["recommendation"]["top_must_match_any"])
                                       or set(rj.get("based_on_factors") or []) & set(ex["recommendation"]["top_must_match_any"])),
          {"matched": top.get("matched_factors"), "based_on": rj.get("based_on_factors")})
    comp = [{"rank": x["rank"], "technology": x["tech_name"], "match_score": x["match_score"], "matched_factors": x.get("matched_factors"),
             "cost_level": x.get("cost_level"), "duration_level": x.get("duration_level"), "source": x.get("source"),
             "applicability": (x.get("reason_struct") or {}).get("applicability") if isinstance(x.get("reason_struct"), dict) else None}
            for x in recs]
    check("[H] 每个候选含匹配分/来源(可比选)", all(c["match_score"] is not None and c["source"] for c in comp), comp[:2])
    g = ent.get(f"/api/v1/sites/{sid}/recommendation").json()
    check("[H] 推荐结果已持久化(GET 与生成一致)", [i["rank"] for i in g.get("items", [])] == [c["rank"] for c in comp],
          [i.get("rank") for i in g.get("items", [])])
    a["recommendation"] = {"type": rj.get("recommendation_type"), "based_on_factors": rj.get("based_on_factors"),
                           "upstream_status": rj.get("upstream_status"), "candidates": comp,
                           "rule_version": (g.get("items") or [{}])[0].get("rule_version")}

    # ── 五阶段 ──
    ri = ent.post(f"/api/v1/sites/{sid}/workflow/init")
    check("[H] 企业用户初始化五阶段", ri.status_code == 200, ri.status_code)
    stage_url = f"/api/v1/sites/{sid}/workflow"
    rc = {}
    r = rev.post(f"{stage_url}/survey", json={"status": "completed", "is_completed": True, "review_comment": "x"})
    rc["complete_from_not_started"] = r.status_code
    uploaded = {}

    def upload(who, stage, rel, role):
        b = open(os.path.join(demo, rel), "rb").read()
        r = who.post(f"{stage_url}/{stage}/attachment", data={"file_role": role},
                     files={"file": (os.path.basename(rel), b, "application/pdf")})
        if r.status_code == 200:
            st = next(s for s in r.json()["stages"] if s["stage"] == stage)
            att = next(x for x in st["attachments"] if x["file_object_id"] == r.json()["file_object_id"])
            uploaded[os.path.basename(rel)] = {"stage": stage, "attachment_id": att["id"], "sha256": _sha(b),
                                               "server_sha256": att.get("sha256"), "uploaded_by": att.get("uploaded_by_name")}
        return r

    for i, st in enumerate(case["stages"]):
        code = st["stage"]
        body = {"status": "in_progress", "data_source": st["data_source"]}
        if i == 0:
            body["operator_id"] = rev_id  # 冒用他人 operator_id: 服务端应忽略, 以登录用户留痕
        r = ent.post(f"{stage_url}/{code}", json=body)
        s = next((x for x in r.json().get("stages", []) if x["stage"] == code), {}) if r.status_code == 200 else {}
        check(f"[H] {st['name']} 企业提交(进行中)", r.status_code == 200 and s.get("status") == "in_progress", r.status_code)
        if i == 0:
            rc["spoof_operator_id"] = {"sent": rev_id, "recorded": s.get("operator_id"), "enterprise_id": ent_id}
            check("[H] 请求体自报 operator_id 被忽略(按登录用户留痕)", s.get("operator_id") == ent_id, rc["spoof_operator_id"])
        r = upload(ent, code, st["file"], st["file_role"])
        check(f"[H] {st['name']} 企业上传模拟材料", r.status_code == 200, r.status_code if r.status_code == 200 else r.text[:150])
        if code == "survey":
            rc["regulator_upload"] = reg.post(f"{stage_url}/survey/attachment", data={"file_role": "x"},
                                              files={"file": ("x.pdf", b"%PDF-1.4 synthetic", "application/pdf")}).status_code
            rc["regulator_update"] = reg.post(f"{stage_url}/survey", json={"status": "completed", "is_completed": True,
                                                                           "review_comment": "x"}).status_code
        if code == "approval" and comp:
            sel = {"rank": comp[0]["rank"], "technology": comp[0]["technology"], "match_score": comp[0]["match_score"],
                   "rule_version": a["recommendation"]["rule_version"],
                   "basis": "模拟比选: 匹配分最高且命中正式障碍因子; 成本/周期等级可接受(演示)",
                   "candidates_compared": len(comp)}
            r = ent.post(f"{stage_url}/approval", json={"payload": {"selected_recommendation": sel}})
            check("[H] 方案审批阶段记录选定方案", r.status_code == 200, r.status_code)
            a["selection"] = sel
        if code == RETURN_STAGE(case):
            rcy = case["return_cycle"]
            r = rev.post(f"{stage_url}/{code}", json={"status": "returned", "is_returned": True})
            rc["return_without_reason"] = r.status_code
            r = rev.post(f"{stage_url}/{code}", json={"status": "returned", "is_returned": True, "review_comment": rcy["reason"]})
            s = next((x for x in r.json().get("stages", []) if x["stage"] == code), {}) if r.status_code == 200 else {}
            check(f"[H] {st['name']} 模拟审核员退回(含原因)", r.status_code == 200 and s.get("status") == "returned"
                  and s.get("operator_id") == rev_id, r.status_code)
            r = ent.post(f"{stage_url}/{code}", json={"status": "in_progress", "is_returned": False})
            check(f"[H] {st['name']} 企业重新提交", r.status_code == 200, r.status_code)
            r = upload(ent, code, rcy["revision_file"], st["file_role"] + "(修订稿)")
            check(f"[H] {st['name']} 企业上传修订稿", r.status_code == 200, r.status_code)
        r = rev.post(f"{stage_url}/{code}", json={"status": "completed", "is_completed": True, "review_comment": st["review_comment"]})
        s = next((x for x in r.json().get("stages", []) if x["stage"] == code), {}) if r.status_code == 200 else {}
        check(f"[H] {st['name']} 模拟审核员审核通过(意见留痕)", r.status_code == 200 and s.get("status") == "completed"
              and s.get("review_comment") == st["review_comment"] and s.get("operator_id") == rev_id,
              {"status": r.status_code, "operator": s.get("operator_id")})

    # ── 角色检查 ──
    att0 = next(iter(uploaded.values()), {})
    dl = f"{stage_url}/{att0.get('stage')}/attachments/{att0.get('attachment_id')}/download"
    rd = _req(reg, "get", dl)
    rc["regulator_view"] = reg.get(stage_url).status_code
    rc["regulator_download"] = rd.status_code
    rc["other_enterprise_view"] = oth.get(stage_url).status_code
    rc["other_enterprise_download"] = _req(oth, "get", dl).status_code
    expect = {"complete_from_not_started": 400, "regulator_update": 403, "regulator_upload": 403, "regulator_view": 200,
              "regulator_download": 200, "other_enterprise_view": 403, "other_enterprise_download": 403, "return_without_reason": 400}
    for kk, v in expect.items():
        check(f"[H] 角色/规则检查 {kk} = {v}", rc.get(kk) == v, rc.get(kk))
    a["role_checks"] = rc

    # ── 附件下载: 内容指纹一致 ──
    ok_dl = []
    for name, u in uploaded.items():
        r = _req(ent, "get", f"{stage_url}/{u['stage']}/attachments/{u['attachment_id']}/download")
        ok_dl.append(r.status_code == 200 and _sha(r.content) == u["sha256"] and (u["server_sha256"] in (None, "", u["sha256"])))
    check(f"[H] {len(uploaded)} 份附件下载内容 SHA-256 与原件一致", all(ok_dl) and len(uploaded) == ex["n_attachments"], ok_dl)
    a["attachments"] = uploaded

    # ── 追溯进度/快照/报告 ──
    pg = ent.get(f"/api/v1/sites/{sid}/trace/progress").json()
    check("[H] 五阶段业务记录 5/5 完成且均有材料", pg.get("business_completed") == ex["business_completed"]
          and pg.get("business_with_documents") == ex["business_with_documents"],
          {"completed": pg.get("business_completed"), "with_docs": pg.get("business_with_documents")})
    snap = ent.get(f"/api/v1/sites/{sid}/evaluation-snapshot").json().get("snapshot", {})
    bs = (snap.get("workflow") or {}).get("business_stages") or []
    ev12 = {e["sha256_12"] for s in bs for e in (s.get("evidence") or [])}
    check("[H] 快照逐阶段列出材料指纹(=上传文件)", ev12 == {u["sha256"][:12] for u in uploaded.values()}, sorted(ev12))
    check("[H] 快照记录选定方案", any(s.get("selected_recommendation") for s in bs))
    a["business_stages"] = [{k_: s.get(k_) for k_ in ("stage", "name", "status_cn", "n_attachments", "operator_name", "review_comment")}
                            for s in bs]
    x = ent.get(f"/api/v1/sites/{sid}/evaluation-snapshot.xlsx")
    check("[H] 评价快照 Excel 导出", x.status_code == 200 and x.content[:2] == b"PK", x.status_code)
    if report:
        for fmt in ("docx", "pdf"):
            r = ent.post(f"/api/v1/sites/{sid}/report?format={fmt}")
            rid = (r.json() or {}).get("report_id") if r.status_code == 200 else None
            d = _req(ent, "get", f"/api/v1/reports/{rid}/download") if rid else None
            ok = bool(d is not None and d.status_code == 200 and len(d.content) > 1000)
            check(f"[H] 追溯报告 {fmt} 生成与下载", ok, r.status_code)
            if ok:
                fn = os.path.join(out, f"H_{a['site_code']}_trace_report.{fmt}")
                open(fn, "wb").write(d.content)
                a[f"report_{fmt}"] = os.path.basename(fn)
                if fmt == "docx":
                    t = _docx_text(d.content)
                    miss = [u["sha256"][:12] for u in uploaded.values() if u["sha256"][:12] not in t]
                    check("[H] 报告“阶段→证据追溯”表含全部材料指纹", not miss, miss)
                    check("[H] 报告含方案选择记录与模拟审核员", "方案选择记录" in t and "模拟审核员" in t)
    a["persist_probe"] = {"site_id": sid, "stage_status": {s["stage"]: s["status"] for s in ent.get(stage_url).json().get("stages", [])},
                          "attachments": {n: {"stage": u["stage"], "attachment_id": u["attachment_id"], "sha256": u["sha256"]}
                                          for n, u in uploaded.items()},
                          "selection": a.get("selection")}
    json.dump(a["persist_probe"], open(os.path.join(out, "H_persist_probe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return a


def run_case_p(admin, demo: str, meta: dict, check) -> dict:
    """T02 已安装程序回放: 邻苯二甲酸酯单体/总量/未登记单体经真实导入 + KOS(生态轨, 第一/二类用地)。"""
    case = ((meta.get("cases_v122") or {}).get("cases") or {}).get("P")
    if not case:
        return {}
    path = os.path.join(demo, case["file"])
    r = admin.post("/api/v1/import", data={"mapping_id": "auto", "on_conflict": "skip"},
                   files={"file": (os.path.basename(path), open(path, "rb").read(), XLSX)})
    check("[P] 邻苯二甲酸酯数据导入", r.status_code == 200, r.status_code)
    sid = r.json().get("site_id") if r.status_code == 200 else None
    if not sid:
        return {}
    out = {"site_id": sid}
    for land, ex in case["expected"].items():
        k = admin.post(f"/api/v1/sites/{sid}/kos-diagnosis?track=eco&subset=all&top_n=10&eco_land_class={land}").json()
        offi = {o["factor"]: o for o in k.get("key_obstacles", [])}
        allf = {o["factor"] for o in k.get("key_obstacles", []) + k.get("exploratory_obstacles", [])}
        check(f"[P·{land}] 正式障碍因子 = 独立期望 {ex['official_factors']}", sorted(offi) == ex["official_factors"], sorted(offi))
        for f, d_ in ex["official_detail"].items():
            o = offi.get(f, {})
            check(f"[P·{land}] {f} 超标倍数 = {d_['ratio']} (阈值 {d_['screening_mgkg']} mg/kg)",
                  abs((o.get("exceedance_ratio") or 0) - d_["ratio"]) < 1e-3, {"value": o.get("value"), "thr": o.get("threshold_value")})
        st = (k.get("per_point_stats") or {}).get("邻苯二甲酸二正辛酯") or {}
        thr = {p.get("threshold") for p in st.get("point_details", [])}
        check(f"[P·{land}] DnOP μg/kg→mg/kg 后与自身官方值 {ex['dnop_threshold_mgkg']} 比较且未超标",
              st.get("n_exceed_points") == 0 and abs((st.get("max_value") or 0) - ex["dnop_value_mgkg"]) < 1e-6
              and thr == {ex["dnop_threshold_mgkg"]}, {"max": st.get("max_value"), "thr": sorted(thr)})
        check(f"[P·{land}] 邻苯二甲酸酯总量不判定(无官方总量值)", not set(case["must_not_judge"]) & allf, sorted(allf))
        md = {m["original_name"]: m for m in k.get("mapping_details", [])}
        check(f"[P·{land}] 标识: 总量=family_total, DEHP/DnOP 按 CAS 绑定",
              md.get("邻苯二甲酸酯总量", {}).get("identity") == "family_total"
              and md.get("邻苯二甲酸二(2-乙基己基)酯", {}).get("cas") == "117-81-7"
              and md.get("邻苯二甲酸二正辛酯", {}).get("cas") == "117-84-0",
              {n: (m.get("identity"), m.get("cas")) for n, m in md.items() if "邻苯" in n})
        fam = {x["original_name"]: x for x in k.get("family_alerts", [])}
        check(f"[P·{land}] 未登记单体(邻苯二甲酸二甲酯)不赋阈值、要求人工复核",
              all(n in (k.get("unmapped") or []) and (fam.get(n) or {}).get("review_required") for n in case["must_be_unmapped_with_review"]),
              {"unmapped": k.get("unmapped"), "alerts": list(fam)})
        out[land] = {"official": sorted(offi), "dnop": {"max": st.get("max_value"), "thr": sorted(thr)}}
    return out


def RETURN_STAGE(case) -> str:
    return case["return_cycle"]["stage"]


def verify_persisted(http, probe: dict, check, label: str = "重启后") -> dict:
    """服务重启(或新进程)后: 阶段状态、附件内容、方案选择记录不丢失。http 需已登录(管理员或企业用户)。"""
    sid = probe["site_id"]
    st = http.get(f"/api/v1/sites/{sid}/workflow").json().get("stages", [])
    now = {s["stage"]: s["status"] for s in st}
    check(f"[H] {label} 五阶段状态保持", now == probe["stage_status"], now)
    ok = []
    for n, u in probe["attachments"].items():
        r = _req(http, "get", f"/api/v1/sites/{sid}/workflow/{u['stage']}/attachments/{u['attachment_id']}/download")
        ok.append(r.status_code == 200 and _sha(r.content) == u["sha256"])
    check(f"[H] {label} {len(ok)} 份附件可下载且指纹一致", all(ok) and bool(ok), ok)
    sel = next((s.get("payload", {}).get("selected_recommendation") for s in st if s["stage"] == "approval"), None)
    check(f"[H] {label} 方案选择记录保持", sel == probe.get("selection"), sel)
    return {"stage_status": now, "downloads_ok": ok, "selection_kept": sel == probe.get("selection")}
