#!/usr/bin/env bash
# 一键演示: 导入个旧场地 -> 诊断 -> 打印 Top-N 障碍因子 (假定已 setup)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"
# shellcheck disable=SC1091
source .venv/bin/activate
export DATABASE_URL="${DATABASE_URL:-sqlite:///./srs_dev.db}"
export SECRET_KEY="${SECRET_KEY:-dev_secret_change_me}"

python - <<'PY'
import os, sys
from app.db.bootstrap import main as bootstrap
from app.db.load_kb import main as load_kb
from app.db.load_remediation_cases import main as load_remediation_cases
from app.db.load_standard_thresholds import main as load_standard_thresholds
from app.db.session import SessionLocal
from app.services.pipeline import run_import
from app.services.diagnosis_service import run_diagnosis
from app.services.evaluation_service import run_evaluation
from app.services.recommend_service import run_recommendation
from app.services import workflow_service as W
from app.services import report_service

GEJIU = os.path.join("..", "data", "raw", "3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx")

bootstrap(); load_kb(); load_standard_thresholds(); load_remediation_cases()
db = SessionLocal()
try:
    imp = run_import(db, GEJIU, "yunnan_gejiu")
    print(f"\n[导入] 场地#{imp['site_id']} 点{imp['n_points']} 检测{imp['n_measurements']} "
          f"校验: 错误{imp['validation']['n_errors']} 超标提示{imp['validation']['n_exceed']}")
    sid = imp["site_id"]

    res = run_diagnosis(db, sid, top_n=10)
    print(f"\n[诊断] 模型 {res['model_version']} 指标 {res['model_metrics']}")
    print(f"风险概率均值 {res['risk_proba_mean']}  最高风险点 {res['worst_point']}")
    print("Top 障碍因子:")
    for t in res["top_factors"]:
        print(f"  #{t['rank']} {t['factor']}({t['category']}) |SHAP|={t['importance']} {t['direction']}")
    print(f"填充特征(未参与排名): {len(res['imputed_features'])} 项")

    ev = run_evaluation(db, sid)
    print(f"\n[评价] 生产重构: {ev['reconstruction_prod']['score']} {ev['reconstruction_prod']['grade']}"
          f" | 生态重构: {ev['reconstruction_eco']['score']} {ev['reconstruction_eco']['grade']}"
          f" | SSUI: {ev['ssui']['ssui']} {ev['ssui']['grade']}")

    rec = run_recommendation(db, sid, top_k=5)
    print("\n[推荐] 基于因子", rec["based_on_factors"][:5])
    for r in rec["recommendations"]:
        print(f"  #{r['rank']} {r['tech_name']} 匹配{r['matched_factors']} 分{r['match_score']}")

    W.init_stages(db, sid)
    W.update_stage(db, sid, "survey", status="completed",
                   review_comment="场地调查报告、检测数据、障碍因子识别结果齐全",
                   is_completed=True, advance=True)
    W.update_stage(db, sid, "approval", status="in_progress",
                   review_comment="重构方案待审批")
    stages = W.get_stages(db, sid)
    print("\n[追溯] 五阶段:")
    for s in stages:
        print(f"  {s['stage_name']}: {s['status']} (附件{s['n_attachments']})")

    rep = report_service.generate(db, sid)
    print(f"\n[报告] {rep['format'].upper()} 已生成: {rep['file_name']} (版本{rep['version']})")
    print(f"  存储: backend/storage/{rep['storage_key']}")
    rep_docx = report_service.generate(db, sid, report_format="docx")
    print(f"[报告] DOCX 已生成: {rep_docx['file_name']} (版本{rep_docx['version']})")
finally:
    db.close()

# 认证/RBAC/企业隔离 演示
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
print("\n[权限] 登录与 RBAC 演示:")
for u in ["admin", "enterprise", "agency", "regulator"]:
    r = c.post("/api/v1/auth/login", json={"username": u, "password": "Demo@2026"})
    tok = r.json()["access_token"]; h = {"Authorization": f"Bearer {tok}"}
    me = c.get("/api/v1/auth/me", headers=h).json()
    rep_code = c.post("/api/v1/sites/1/report", headers=h).status_code
    print(f"  {u:11} 角色{me['roles']} 报告生成权限={'通过' if rep_code in (200,404) else '拒绝(403)'}")
print("  无令牌访问 /sites:", c.get("/api/v1/sites").status_code, "(401 即拦截生效)")
PY
echo ""
echo "✅ 演示完成。查看 API: uvicorn app.main:app --reload 后访问"
echo "   GET /api/v1/sites/1/diagnosis"
