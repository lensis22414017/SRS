"""系统级极端验收: 10 组随机场地 -> 全流程闭环。

验证内容:
- 上传/导入解析/校验/入库;
- RF+SHAP 障碍因子、重构评价、SSUI、推荐;
- 五阶段工作流、附件上传/下载、PDF/DOCX 报告;
- AI/RAG 降级或模型回复;
- 质量评分: 诊断合理性、评价合理性、图表/报告覆盖、追溯闭环。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND = os.path.join(ROOT, "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

os.environ.setdefault("DATABASE_URL", "sqlite:///./srs_extreme_validation.db")
os.environ.setdefault("SECRET_KEY", "extreme_validation_secret")
os.environ.setdefault("DEMO_PASSWORD", "Demo@2026")
os.environ.setdefault("FILE_STORAGE_DIR", "./storage_extreme")

from fastapi.testclient import TestClient  # noqa: E402

from app.db.bootstrap import main as bootstrap  # noqa: E402
from app.db.load_kb import main as load_kb  # noqa: E402
from app.db.load_remediation_cases import main as load_cases  # noqa: E402
from app.db.load_standard_thresholds import main as load_standards  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import report_service, workflow_service  # noqa: E402
from app.services.ai_service import chat, retrieve  # noqa: E402
from app.services.diagnosis_service import run_diagnosis  # noqa: E402
from app.services.evaluation_service import run_evaluation  # noqa: E402
from app.services.pipeline import run_import  # noqa: E402
from app.services.recommend_service import run_recommendation  # noqa: E402


OUTDIR = os.path.join(ROOT, "validation_outputs", "extreme")
FACTOR_COLS = [
    "pH", "有机质(g/kg)", "全氮(g/kg)", "全磷(g/kg)", "全钾(g/kg)",
    "碱解氮(mg/kg)", "速效磷(mg/kg)", "速效钾(mg/kg)", "铜_Cu(mg/kg)",
    "铅_Pb(mg/kg)", "锌_Zn(mg/kg)", "铁_Fe(mg/kg)", "锰_Mn(mg/kg)", "砷_As(mg/kg)",
]
REQUIRED_FACTOR_COLS = {"pH", "铜_Cu(mg/kg)", "铅_Pb(mg/kg)", "锌_Zn(mg/kg)", "砷_As(mg/kg)"}
POLLUTANT_EXPECT = {
    "铜_Cu(mg/kg)": "铜",
    "铅_Pb(mg/kg)": "铅",
    "锌_Zn(mg/kg)": "锌",
    "砷_As(mg/kg)": "砷",
}


def _scenario(seed: int, i: int) -> dict:
    rng = np.random.default_rng(seed + i)
    patterns = [
        ("As_hotspot", "砷_As(mg/kg)", 180, "重金属砷热点"),
        ("CuZn_hotspot", "铜_Cu(mg/kg)", 900, "铜锌冶炼扰动"),
        ("Pb_hotspot", "铅_Pb(mg/kg)", 650, "铅污染建设用地"),
        ("Zn_high", "锌_Zn(mg/kg)", 1200, "锌污染矿区"),
        ("multi_hm", "砷_As(mg/kg)", 120, "多重金属复合"),
        ("acid_low_ph", "pH", 4.2, "酸化障碍"),
        ("alkaline_high_ph", "pH", 9.0, "碱化障碍"),
        ("low_fertility", "有机质(g/kg)", 3.0, "肥力短板"),
        ("sparse_missing", "砷_As(mg/kg)", 90, "高缺失稀疏场景"),
        ("mixed_extreme", "铜_Cu(mg/kg)", 1200, "复合极端场景"),
    ]
    key, driver, value, label = patterns[i % len(patterns)]
    return {"key": key, "driver_col": driver, "driver_value": value,
            "label": label, "rng": rng}


def make_dataset(path: str, site_idx: int, seed: int = 20260612) -> dict:
    s = _scenario(seed, site_idx)
    rng = s["rng"]
    n = int(rng.integers(24, 55))
    rows = []
    for j in range(n):
        row = {
            "采样点编号": f"EXT-{site_idx + 1:02d}-{j + 1:03d}",
            "经度": round(102.0 + rng.normal(0, 0.03), 6),
            "纬度": round(24.0 + rng.normal(0, 0.03), 6),
            "区域": rng.choice(["核心区", "缓冲区", "对照区"]),
            "深度_上限(cm)": 0,
            "深度_下限(cm)": int(rng.choice([20, 40, 60])),
            "土壤类型": rng.choice(["红壤", "黄壤", "砂壤土", "黏壤土"]),
            "备注": s["label"],
            "pH": round(float(rng.normal(6.8, 0.7)), 2),
            "有机质(g/kg)": round(max(float(rng.normal(22, 6)), 1), 2),
            "全氮(g/kg)": round(max(float(rng.normal(1.2, 0.4)), 0.05), 3),
            "全磷(g/kg)": round(max(float(rng.normal(0.8, 0.25)), 0.05), 3),
            "全钾(g/kg)": round(max(float(rng.normal(16, 4)), 1), 2),
            "碱解氮(mg/kg)": round(max(float(rng.normal(85, 25)), 3), 2),
            "速效磷(mg/kg)": round(max(float(rng.normal(18, 8)), 0.5), 2),
            "速效钾(mg/kg)": round(max(float(rng.normal(110, 35)), 2), 2),
            "铜_Cu(mg/kg)": round(max(float(rng.lognormal(np.log(80), 0.45)), 1), 2),
            "铅_Pb(mg/kg)": round(max(float(rng.lognormal(np.log(90), 0.5)), 1), 2),
            "锌_Zn(mg/kg)": round(max(float(rng.lognormal(np.log(250), 0.45)), 1), 2),
            "铁_Fe(mg/kg)": round(max(float(rng.normal(22000, 5000)), 1000), 2),
            "锰_Mn(mg/kg)": round(max(float(rng.normal(600, 180)), 20), 2),
            "砷_As(mg/kg)": round(max(float(rng.lognormal(np.log(30), 0.55)), 0.5), 2),
        }
        if j < max(6, n // 4):
            row[s["driver_col"]] = round(float(s["driver_value"] * rng.uniform(0.8, 1.35)), 2)
        if s["key"] == "multi_hm" and j < n // 3:
            row["铜_Cu(mg/kg)"] = round(float(700 * rng.uniform(0.7, 1.2)), 2)
            row["铅_Pb(mg/kg)"] = round(float(500 * rng.uniform(0.7, 1.2)), 2)
            row["锌_Zn(mg/kg)"] = round(float(1000 * rng.uniform(0.7, 1.2)), 2)
        if s["key"] == "mixed_extreme" and j < n // 3:
            row["砷_As(mg/kg)"] = round(float(160 * rng.uniform(0.8, 1.4)), 2)
            row["铅_Pb(mg/kg)"] = round(float(800 * rng.uniform(0.7, 1.2)), 2)
        if s["key"] == "sparse_missing":
            for c in FACTOR_COLS:
                if c != s["driver_col"] and c not in REQUIRED_FACTOR_COLS and rng.random() < 0.35:
                    row[c] = np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False)
    return {"scenario": s["key"], "driver_col": s["driver_col"],
            "expected_factor": POLLUTANT_EXPECT.get(s["driver_col"], s["driver_col"]),
            "rows": n}


def make_mapping(path: str, site_idx: int) -> str:
    import json as _json

    base = os.path.join(BACKEND, "app", "services", "mappings", "yunnan_gejiu.json")
    with open(base, encoding="utf-8") as f:
        mapping = _json.load(f)
    mapping["site"]["site_code"] = f"EXTREME-{site_idx + 1:02d}"
    mapping["site"]["name"] = f"极端验证场地 {site_idx + 1:02d}"
    mapping["site"]["province"] = "云南省"
    mapping["site"]["city"] = "个旧市"
    mapping["mapping_id"] = f"extreme_{site_idx + 1:02d}"
    with open(path, "w", encoding="utf-8") as f:
        _json.dump(mapping, f, ensure_ascii=False, indent=2)
    return path


def _score_case(meta: dict, diag: dict, ev: dict, rec: dict, report_pdf: dict,
                report_docx: dict, ctx: dict, workflow: list[dict],
                upload_download_ok: bool, ai_ok: bool) -> dict:
    top_names = [t["factor"] for t in diag.get("top_factors", [])[:5]]
    expected = meta["expected_factor"]
    keyword_hit = expected in top_names or (expected == "pH" and "pH" in top_names)
    if expected == "有机质(g/kg)":
        keyword_hit = "有机质" in top_names
    eval_ok = all(k in ev for k in ("reconstruction_prod", "reconstruction_eco", "ssui"))
    ssui_ok = 0 <= ev["ssui"]["ssui"] <= 1
    rec_ok = len(rec.get("recommendations", [])) >= 3
    report_ok = report_pdf["format"] in ("pdf", "html") and report_docx["format"] == "docx"
    coverage_sections = {"coverage": bool(ctx.get("coverage")),
                         "standards": bool(ctx.get("standard_versions")),
                         "cases": bool(ctx.get("remediation_cases"))}
    workflow_ok = len(workflow) == 5 and any(s["status"] == "completed" for s in workflow)
    score = sum([
        keyword_hit, eval_ok, ssui_ok, rec_ok, report_ok,
        all(coverage_sections.values()), workflow_ok, upload_download_ok, ai_ok,
    ])
    return {
        "expected_factor": expected,
        "top5": top_names,
        "keyword_hit": bool(keyword_hit),
        "ssui_in_range": bool(ssui_ok),
        "recommendation_ok": bool(rec_ok),
        "report_ok": bool(report_ok),
        "coverage_sections": coverage_sections,
        "workflow_ok": bool(workflow_ok),
        "upload_download_ok": bool(upload_download_ok),
        "ai_ok": bool(ai_ok),
        "quality_score": round(score / 9 * 100, 2),
    }


def run() -> dict:
    os.makedirs(OUTDIR, exist_ok=True)
    bootstrap(); load_kb(); load_standards(); load_cases()
    client = TestClient(app)
    login = client.post("/api/v1/auth/login",
                        json={"username": "admin", "password": os.environ.get("DEMO_PASSWORD", "Demo@2026")})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    cases = []
    db = SessionLocal()
    try:
        for i in range(10):
            xlsx = os.path.join(OUTDIR, f"extreme_dataset_{i + 1:02d}.xlsx")
            mapping = os.path.join(OUTDIR, f"extreme_mapping_{i + 1:02d}.json")
            meta = make_dataset(xlsx, i)
            make_mapping(mapping, i)

            with open(xlsx, "rb") as f:
                upload_resp = client.post(
                    "/api/v1/import",
                    data={"mapping_id": mapping},
                    files={"file": (os.path.basename(xlsx), f,
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    headers=headers,
                )
            if upload_resp.status_code != 200:
                raise RuntimeError(f"API 上传导入失败 case {i + 1}: {upload_resp.status_code} {upload_resp.text}")
            imp = upload_resp.json()
            sid = imp["site_id"]

            diag = run_diagnosis(db, sid, top_n=10)
            ev = run_evaluation(db, sid)
            rec = run_recommendation(db, sid, top_k=5)
            workflow_service.init_stages(db, sid)
            workflow_service.update_stage(db, sid, "survey", status="completed",
                                          review_comment="极端测试数据已导入并诊断",
                                          is_completed=True, advance=True)
            workflow = workflow_service.get_stages(db, sid)

            report_pdf = report_service.generate(db, sid, generated_by=1, report_format="pdf")
            report_docx = report_service.generate(db, sid, generated_by=1, report_format="docx")
            report_download = client.get(f"/api/v1/reports/{report_pdf['report_id']}/download",
                                         headers=headers)

            upload_resp = client.post(
                f"/api/v1/sites/{sid}/workflow/survey/attachment",
                data={"file_role": "极端测试附件"},
                files={"file": (f"extreme_attachment_{i + 1}.txt",
                                f"case {i + 1} attachment".encode("utf-8"),
                                "text/plain")},
                headers=headers,
            )
            workflow_after_upload = workflow_service.get_stages(db, sid)
            attachment_uploaded = upload_resp.status_code == 200 and any(
                s["stage"] == "survey" and s["n_attachments"] >= 1
                for s in workflow_after_upload)
            upload_download_ok = attachment_uploaded and report_download.status_code == 200
            ctx = report_service.collect(db, sid, "quality-check")

            rag = retrieve(db, "砷超标可以用什么修复技术", site_id=sid)
            ai_res = chat(db, "请基于知识库用两句话解释该场地修复建议", site_id=sid)
            ai_ok = bool(rag.get("technologies")) and bool(ai_res.get("reply"))

            quality = _score_case(meta, diag, ev, rec, report_pdf, report_docx, ctx,
                                  workflow, upload_download_ok, ai_ok)
            cases.append({
                "case_id": i + 1,
                "site_id": sid,
                "scenario": meta["scenario"],
                "import": imp,
                "diagnosis": {
                    "risk_proba_mean": diag["risk_proba_mean"],
                    "top_factors": diag["top_factors"][:5],
                    "imputed_count": len(diag["imputed_features"]),
                },
                "evaluation": {
                    "prod": ev["reconstruction_prod"],
                    "eco": ev["reconstruction_eco"],
                    "ssui": ev["ssui"],
                },
                "recommendation_count": len(rec.get("recommendations", [])),
                "report": {"pdf": report_pdf, "docx": report_docx},
                "quality": quality,
            })
    finally:
        db.close()

    keyword_accuracy = sum(c["quality"]["keyword_hit"] for c in cases) / len(cases)
    avg_quality = sum(c["quality"]["quality_score"] for c in cases) / len(cases)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_url": os.environ["DATABASE_URL"],
        "n_cases": len(cases),
        "keyword_hit_accuracy": round(keyword_accuracy, 4),
        "avg_quality_score": round(avg_quality, 2),
        "cases": cases,
        "closed_loop": {
            "import": all(c["import"]["validation"]["passed"] for c in cases),
            "diagnosis": all(c["diagnosis"]["top_factors"] for c in cases),
            "evaluation": all(c["quality"]["ssui_in_range"] for c in cases),
            "recommendation": all(c["quality"]["recommendation_ok"] for c in cases),
            "report": all(c["quality"]["report_ok"] for c in cases),
            "workflow_traceability": all(c["quality"]["workflow_ok"] for c in cases),
            "file_upload_download": all(c["quality"]["upload_download_ok"] for c in cases),
            "ai_rag": all(c["quality"]["ai_ok"] for c in cases),
        },
    }
    out_json = os.path.join(OUTDIR, "extreme_validation_report.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    summary = pd.DataFrame([{
        "case_id": c["case_id"], "scenario": c["scenario"],
        "site_id": c["site_id"], "keyword_hit": c["quality"]["keyword_hit"],
        "quality_score": c["quality"]["quality_score"],
        "top5": ";".join(c["quality"]["top5"]),
        "prod_grade": c["evaluation"]["prod"]["grade"],
        "eco_grade": c["evaluation"]["eco"]["grade"],
        "ssui": c["evaluation"]["ssui"]["ssui"],
        "ssui_grade": c["evaluation"]["ssui"]["grade"],
    } for c in cases])
    out_csv = os.path.join(OUTDIR, "extreme_validation_summary.csv")
    summary.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"已生成: {out_json}")
    print(f"已生成: {out_csv}")
    print(json.dumps({
        "n_cases": report["n_cases"],
        "keyword_hit_accuracy": report["keyword_hit_accuracy"],
        "avg_quality_score": report["avg_quality_score"],
        "closed_loop": report["closed_loop"],
    }, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    run()
