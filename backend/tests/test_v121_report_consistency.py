"""v1.2.1 审计 R03/R04 回归: 评价快照驱动的报告 — 阶段/批次分离、修复后 SSUI、法规门禁、五阶段真实状态,
以及 API 快照 = 报告记录 = Excel = PDF 文本 = DOCX 文本 的跨渠道一致性; 快照不随后续数据变化。

数据: demo/mc_v12/site_A(模拟数据, 种子 20261009) 与一个按 GB 15618 管制值构造的“修复前不可行”夹具。
"""
from __future__ import annotations

import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "packaging", "ci"))
import report_invariants as RI  # noqa: E402

DEMO_A = os.path.join(ROOT, "demo", "mc_v12", "site_A")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
needs_demo = pytest.mark.skipif(not os.path.isdir(DEMO_A), reason="demo/mc_v12 不在工作树")


def _login(c):
    tok = c.post("/api/v1/auth/login", json={"username": "admin", "password": "Demo@2026"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _f(prefix):
    return [os.path.join(DEMO_A, f) for f in sorted(os.listdir(DEMO_A)) if f.startswith(prefix)][0]


def _import_pre(c, h, path=None, content=None, name=None):
    before = {s["id"] for s in c.get("/api/v1/sites", params={"page_size": 100}, headers=h).json()["items"]}
    data = content if content is not None else open(path, "rb").read()
    r = c.post("/api/v1/import", headers=h, data={"mapping_id": "auto", "on_conflict": "skip"},
               files={"file": (name or os.path.basename(path), data, XLSX)})
    assert r.status_code == 200, r.text[:300]
    new = [s for s in c.get("/api/v1/sites", params={"page_size": 100}, headers=h).json()["items"] if s["id"] not in before]
    return new[0]["id"], new[0]["site_code"]


def _reports(c, h, sid):
    files, snaps = {}, []
    for fmt in ("pdf", "docx"):
        rr = c.post(f"/api/v1/sites/{sid}/report?format={fmt}", headers=h)
        assert rr.status_code == 200, rr.text[:300]
        rid = rr.json().get("report_id") or rr.json().get("id")
        files[fmt] = c.get(f"/api/v1/reports/{rid}/download", headers=h).content
        snaps.append({**{k: v for k, v in c.get(f"/api/v1/reports/{rid}/snapshot", headers=h).json().items()
                         if k != "snapshot"}, "format": fmt, "report_id": rid})
    return files, snaps


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c, _login(c)


@needs_demo
def test_site_a_cross_channel_and_stage_separation(client):
    c, h = client
    sid, code = _import_pre(c, h, _f("01_"))
    assert c.post(f"/api/v1/sites/{sid}/kos-diagnosis?track=prod&subset=hm&top_n=10&farmland_type=水田",
                  headers=h).status_code == 200
    pv = c.post(f"/api/v1/sites/{sid}/recon/preview", headers=h,
                files={"file": ("s2.xlsx", open(_f("02_"), "rb").read(), XLSX)}).json()
    assert c.post(f"/api/v1/recon/batches/{pv['batch_id']}/confirm", headers=h).json()["status"] == "confirmed"
    c.post(f"/api/v1/sites/{sid}/utilization", headers=h, params={"stage": "pre_remediation", "farmland_type": "水田", "eco_land_class": "第一类用地"})
    for track, pre in (("production", "03_"), ("ecology", "04_")):
        p3 = c.post(f"/api/v1/sites/{sid}/ssui-post/preview", headers=h, data={"track": track},
                    files={"file": ("s3.xlsx", open(_f(pre), "rb").read(), XLSX)}).json()
        assert p3["can_confirm"], p3.get("errors")
        c.post(f"/api/v1/ssui-post/batches/{p3['batch_id']}/confirm", headers=h)
    dq = c.post(f"/api/v1/sites/{sid}/utilization", headers=h,
                params={"stage": "post_remediation", "farmland_type": "水田", "eco_land_class": "第一类用地"}).json()

    files, snaps = _reports(c, h, sid)
    sj = c.get(f"/api/v1/sites/{sid}/evaluation-snapshot", headers=h).json()
    hl, snap = sj["headline"], sj["snapshot"]
    xb = c.get(f"/api/v1/sites/{sid}/evaluation-snapshot.xlsx", headers=h).content

    # 阶段/批次分离: 修复前 20 点; 修复后两轨重复导入 40 条点位记录 = 20 个独立样品
    assert hl["pre_n_samples"] == 20 and hl["pre_n_measurements"] == 260
    assert hl["post_n_batches"] == 2 and hl["post_n_point_records"] == 40 and hl["post_n_samples"] == 20
    inv = snap["inventory"]["post_remediation"]
    assert inv["duplicate_groups"] and inv["duplicate_groups"][0]["n_shared_samples"] == 20
    assert inv["n_unique_measurements"] * 2 == inv["n_measurement_records"]
    # 修复后 SSUI 来自课题三批次, 与独立期望值一致; 修复前旧口径只作参考
    # v1.2.2: 期望值读自 demo/mc_v12/expected.json(生成器独立计算, 均在等级定义域 [0, 1] 内);
    # v1.2.1 的 1.019189(域外) 已降为 fixtures/ssui_out_of_domain 回归夹具
    _exA = json.load(open(os.path.join(ROOT, "demo", "mc_v12", "expected.json"), encoding="utf-8"))["scenarios"]["A"]["ssui"]
    assert hl["ssui_post_production"] == pytest.approx(_exA["production"]["ssui"], abs=1e-6)
    assert hl["ssui_post_ecology"] == pytest.approx(_exA["ecology"]["ssui"], abs=1e-6)
    assert 0 <= hl["ssui_post_production"] <= 1 and 0 <= hl["ssui_post_ecology"] <= 1
    assert snap["ssui"]["pre_reference"] is None or "参考" in snap["ssui"]["pre_reference"]["label"]
    # 场地级门禁按阶段: 修复前超筛选值, 修复后通过; 与利用方向结论一致
    assert hl["pre_gate_production"] == "conditional" and set(hl["pre_exceed_production"]) >= {"Cd", "Pb"}
    assert hl["post_gate_production"] == "pass" and hl["post_gate_ecology"] == "pass"
    assert hl["decision_post"] == dq["decision_state"] == "both_supported"
    # 修复前门禁: 课题二批次同编号同值点位按同一样品合并, 不重复计数
    cd = [f for f in snap["gates"]["pre_remediation"]["production"]["factors"] if f["factor"] == "Cd"][0]
    assert cd["n_obs"] == 20
    # 五阶段业务记录与七项软件里程碑分开
    assert hl["business_stages_completed"] == 0 and hl["business_stages_total"] == 5
    assert all(s["status_cn"].startswith("未开展") for s in snap["workflow"]["business_stages"])
    # KOS: 正式 Top-N 只含 GB 15618 证据; 肥力指标仅在探索性列表
    assert hl["kos_official_status"] == "available" and not set(hl["kos_official"]) & RI.FERTILITY
    assert snap["kos"]["farmland_type"] == "水田"
    # 课题一 KOS 与修复前生产门禁对同一最不利点使用同一筛选值(水田口径)
    g = {f["factor"]: f for f in snap["gates"]["pre_remediation"]["production"]["factors"]}
    for k in snap["kos"]["official"]:
        sym = k["factor"].split("_")[0]
        if sym in g and g[sym]["worst_point"] == k["decision_point_code"]:
            assert k["threshold_value"] == pytest.approx(g[sym]["worst_screening"]), (k, g[sym])
    # 六价铬单位不再显示为 VI
    pre_fs = {x["factor"]: x for x in snap["factor_summary"]["pre_remediation"]}
    assert pre_fs["六价铬"]["unit"] == "mg/kg"

    checks = RI.check_channels(hl, snaps, xb, files["pdf"], files["docx"])
    failed = [x for x in checks if not x["passed"]]
    assert not failed, failed
    txt = RI.pdf_text(files["pdf"])
    assert "模拟采样点" in txt and "真实采样点" not in txt

    # 界面地图图层与法规门禁同一口径: 修复前点位按 GB 15618 筛选值(水田, 点位 pH)着色, 不再全部“无阈值”
    ml = c.get(f"/api/v1/sites/{sid}/map/layers", headers=h).json()
    feats = {f["properties"]["point_code"]: f["properties"] for f in ml["geojson"]["features"]}
    worst_cd = g["Cd"]["worst_point"]
    sel = feats[worst_cd]["selected"]
    assert sel and sel["exceedance"] == pytest.approx(g["Cd"]["worst_value"] / g["Cd"]["worst_screening"], rel=1e-3)
    n_colored = sum(1 for pc, p in feats.items() if p["selected"] and not pc.startswith("POST"))
    assert n_colored == 20 and "GB 15618" in ml["color_basis"]
    cd_layer = c.get(f"/api/v1/sites/{sid}/map/layers", headers=h, params={"factor": "镉"}).json()
    cdp = [f["properties"] for f in cd_layer["geojson"]["features"] if f["properties"]["point_code"] == worst_cd][0]
    assert cdp["selected"]["threshold"] == pytest.approx(g["Cd"]["worst_screening"])
    # 场地详情分阶段计数与快照一致
    sd = c.get(f"/api/v1/sites/{sid}", headers=h).json()["stage_counts"]
    assert sd["pre_remediation"]["n_unique_samples"] == hl["pre_n_samples"] == 20
    assert sd["post_remediation"]["n_unique_samples"] == hl["post_n_samples"] == 20


@needs_demo
def test_report_snapshot_is_immutable_after_new_data(client):
    c, h = client
    sid, _ = _import_pre(c, h, _f("01_"))
    c.post(f"/api/v1/sites/{sid}/kos-diagnosis?track=prod&subset=hm&top_n=10&farmland_type=水田", headers=h)
    files, snaps = _reports(c, h, sid)
    before = snaps[0]
    # 新增修复后批次 → 当前快照改变; 已生成报告的快照不变且仍可校验
    p3 = c.post(f"/api/v1/sites/{sid}/ssui-post/preview", headers=h, data={"track": "production"},
                files={"file": ("s3.xlsx", open(_f("03_"), "rb").read(), XLSX)}).json()
    c.post(f"/api/v1/ssui-post/batches/{p3['batch_id']}/confirm", headers=h)
    live = c.get(f"/api/v1/sites/{sid}/evaluation-snapshot", headers=h).json()["headline"]
    again = c.get(f"/api/v1/reports/{before['report_id']}/snapshot", headers=h).json()
    assert live["snapshot_id"] != before["snapshot_id"]
    assert again["snapshot_id"] == before["snapshot_id"] and again["verified"] is True
    assert again["headline"]["post_n_batches"] == 0 and live["post_n_batches"] == 1


def test_infeasible_pre_remediation_case_reports_control_exceedance(client):
    """不可行夹具: Cd 超 GB 15618 管制值 → 生产门禁 fail; 报告首页与正文均写明, 不出现“支持利用”。"""
    c, h = client
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active
    hdr = ["采样点编号", "经度", "纬度", "深度_上限(cm)", "深度_下限(cm)", "土壤类型", "pH", "镉_Cd(mg/kg)", "汞_Hg(mg/kg)",
           "砷_As(mg/kg)", "铅_Pb(mg/kg)", "铬_Cr(mg/kg)", "铜_Cu(mg/kg)", "镍_Ni(mg/kg)", "锌_Zn(mg/kg)",
           "六价铬_Cr(VI)(mg/kg)", "有机质(g/kg)", "全氮(g/kg)", "阳离子交换量(cmol/kg)"]
    ws.append(hdr)
    for i in range(1, 6):
        ws.append([f"X{i:02d}", 120.1 + i * 0.001, 30.1, 0, 20, "水稻土", 6.0, 6.5 + i, 0.2, 20, 60, 80, 30, 30, 120,
                   0.3, 25, 1.5, 15])
    buf = io.BytesIO(); wb.save(buf)
    sid, _ = _import_pre(c, h, content=buf.getvalue(), name="【模拟数据——仅供测试/演示】不可行夹具_修复前检测.xlsx")
    c.post(f"/api/v1/sites/{sid}/kos-diagnosis?track=prod&subset=hm&top_n=10&farmland_type=水田", headers=h)
    dp = c.post(f"/api/v1/sites/{sid}/utilization", headers=h,
                params={"stage": "pre_remediation", "farmland_type": "水田", "eco_land_class": "第一类用地"}).json()
    files, snaps = _reports(c, h, sid)
    sj = c.get(f"/api/v1/sites/{sid}/evaluation-snapshot", headers=h).json()
    hl = sj["headline"]
    assert hl["pre_gate_production"] == "fail" and "Cd" in hl["pre_exceed_production"]
    assert dp["decision_state"] in ("neither_supported", "insufficient_evidence")
    assert hl["decision_pre"] == dp["decision_state"] and hl["post_n_batches"] == 0
    assert hl["kos_official"] and hl["kos_official"][0] == "Cd_mgkg"
    checks = RI.check_channels(hl, snaps, None, files["pdf"], files["docx"])
    assert not [x for x in checks if not x["passed"]], checks
    txt = RI.pdf_text(files["pdf"])
    assert "超管制值" in txt and "尚无修复后数据" in txt
