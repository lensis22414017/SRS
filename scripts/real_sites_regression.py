"""v1.2.1(R07): 三个原始场地(甲方/子课题提供, 未公开分发)在最终版本上的回归。

经 HTTP API(进程内 TestClient, 独立库)逐场地执行: 导入 → 课题一 KOS(按污染类型选子集; 生产轨 其他 / 生态轨 第一类用地)
→ 修复前情景判断 → 报告 PDF/DOCX → 评价快照 + 跨渠道一致性断言。
输出只写入 --out(应位于 owner_private), 不进入公开包; 不修改原始文件。

用法: python scripts/real_sites_regression.py --out <owner_private>/D12_real_site_regression --db <dir>/srs_demo_real.db
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
SITES = [("1.20250731_复合污染场地数据表(乡村建设用地)_完整版.xlsx", "hm_op"),
         ("2.20250731_有机污染场地数据表(南京栖霞)_完整版.xlsx", "op"),
         ("3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx", "hm")]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def main(out: str, db: str):
    p = os.path.abspath(db)
    if not os.path.basename(p).startswith("srs_demo"):
        raise SystemExit("独立库文件名须以 srs_demo 开头")
    os.environ["DATABASE_URL"] = "sqlite:///" + p
    os.environ.setdefault("SECRET_KEY", "regression_only_" + "x" * 40)
    for q in (os.path.join(ROOT, "backend"), os.path.join(ROOT, "packaging", "ci")):
        sys.path.insert(0, q)
    from fastapi.testclient import TestClient
    from app.main import app
    import demo_runner as DR
    import report_invariants as RI
    os.makedirs(out, exist_ok=True)
    res = {"generated_by": "scripts/real_sites_regression.py", "sites": []}
    with TestClient(app) as c:
        H = DR.Http(c, ""); DR.ensure_admin(H, ("admin", "Demo@Run2026x"))
        before = set()
        for fn, subset in SITES:
            path = os.path.join(RAW, fn)
            row = {"file": fn, "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(), "subset": subset, "checks": []}
            r = H.post("/api/v1/import", data={"mapping_id": "auto", "on_conflict": "skip"},
                       files={"file": (fn, open(path, "rb").read(), XLSX)})
            row["import_status"] = r.status_code
            items = H.get("/api/v1/sites", params={"page_size": 100}).json().get("items", [])
            new = [s for s in items if s["id"] not in before]
            if r.status_code != 200 or not new:
                row["error"] = r.text[:300]; res["sites"].append(row); continue
            site = new[0]; before |= {s["id"] for s in items}; sid = site["id"]
            row.update({"site_id": sid, "site_code": site["site_code"], "name": site["name"]})
            kos = {}
            for track, extra in (("prod", "&farmland_type=其他"), ("eco", "&eco_land_class=第一类用地")):
                kj = H.post(f"/api/v1/sites/{sid}/kos-diagnosis?track={track}&subset={subset}&top_n=10{extra}").json()
                kos[track] = {"status": kj.get("official_ranking_status"),
                              "official": [(k["factor"], k.get("value"), k.get("threshold_value"), k.get("threshold_unit"),
                                            k.get("threshold_standard"), k.get("exceedance_ratio")) for k in kj.get("key_obstacles", [])],
                              "exploratory": [(k["factor"], k.get("value"), k.get("threshold_value"), k.get("threshold_type"),
                                               k.get("threshold_resolution_status")) for k in kj.get("exploratory_obstacles", [])],
                              "unit_unresolved": kj.get("unit_unresolved"), "n_rejected_note": kj.get("data_quality_flags", [])[:8]}
                off = {k[0] for k in kos[track]["official"]}
                row["checks"].append({"check": f"{track} 正式 Top-N 不含肥力下限指标", "passed": not off & RI.FERTILITY,
                                      "detail": sorted(off)})
            row["kos"] = kos
            dp = H.post(f"/api/v1/sites/{sid}/utilization", params={"stage": "pre_remediation", "farmland_type": "其他"}).json()
            row["decision_pre"] = {"state": dp.get("decision_state"),
                                   "gates": {t: (dp.get(t) or {}).get("gate", {}).get("state") for t in ("production", "ecology")},
                                   "missing_evidence": (dp.get("missing_evidence") or [])[:6]}
            files_b, snaps = {}, []
            for fmt in ("pdf", "docx"):
                rr = H.post(f"/api/v1/sites/{sid}/report?format={fmt}")
                rid = rr.json().get("report_id")
                files_b[fmt] = H.get(f"/api/v1/reports/{rid}/download").content
                open(os.path.join(out, f"site{sid}_{site['site_code']}_report.{fmt}"), "wb").write(files_b[fmt])
                snaps.append({**{k: v for k, v in H.get(f"/api/v1/reports/{rid}/snapshot").json().items() if k != "snapshot"}, "format": fmt})
            sj = H.get(f"/api/v1/sites/{sid}/evaluation-snapshot").json()
            xb = H.get(f"/api/v1/sites/{sid}/evaluation-snapshot.xlsx").content
            open(os.path.join(out, f"site{sid}_{site['site_code']}_evaluation_snapshot.xlsx"), "wb").write(xb)
            json.dump(sj["snapshot"], open(os.path.join(out, f"site{sid}_{site['site_code']}_evaluation_snapshot.json"), "w",
                                           encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
            row["headline"] = sj["headline"]
            row["checks"] += RI.check_channels(sj["headline"], snaps, xb, files_b["pdf"], files_b["docx"])
            row["passed"] = all(x["passed"] for x in row["checks"])
            res["sites"].append(row)
            print(site["site_code"], "passed" if row["passed"] else "FAILED", [x["check"] for x in row["checks"] if not x["passed"]])
    res["all_passed"] = all(s.get("passed") for s in res["sites"])
    json.dump(res, open(os.path.join(out, "real_sites_regression.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--db", required=True)
    a = ap.parse_args()
    r = main(a.out, a.db)
    print(json.dumps({"all_passed": r["all_passed"], "n": len(r["sites"])}, ensure_ascii=False))
