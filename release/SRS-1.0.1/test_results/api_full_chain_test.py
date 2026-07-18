"""
SRS v1.0.1 全链路 API 测试
对 18 个演示 xlsx 执行: 导入 → KOS诊断 → 重构评价(含SSUI) → 推荐推荐
"""
import sys, os, json, traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
os.environ.setdefault('DATABASE_URL', f"sqlite:///./srs_api_test_{os.getpid()}.db")
os.environ['SRS_DEMO_SEED'] = '1'

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal, engine
from app.db.base import Base

# 重建测试库
Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

# 种子数据(角色/权限/参考数据/demo账号)
from app.db.seed_db import seed_if_empty
seed_if_empty()

c = TestClient(app)
DEMO_DIR = os.path.join(os.path.dirname(__file__), '..', 'samples', 'demo_data')

results = {"sites": [], "summary": {}}

# 1. 登录
login = c.post("/api/v1/auth/login", json={"username": "admin", "password": "Demo@2026"})
token = login.json().get("access_token", "") if login.status_code == 200 else ""
headers = {"Authorization": f"Bearer {token}"}
print(f"登录: {login.status_code}, token={'有' if token else '无'}")
if not token:
    print(f"登录失败: {login.text[:200]}")
    sys.exit(1)

# 2. 批量导入 18 个 xlsx
xlsx_files = sorted([f for f in os.listdir(DEMO_DIR) if f.endswith('.xlsx')])
print(f"\n开始导入 {len(xlsx_files)} 个 xlsx...")

for idx, fname in enumerate(xlsx_files):
    site_result = {"file": fname, "import": None, "kos_prod": None, "kos_eco": None,
                   "reconstruction": None, "errors": []}
    fpath = os.path.join(DEMO_DIR, fname)
    try:
        with open(fpath, "rb") as f:
            r = c.post("/api/v1/import", headers=headers,
                       data={"mapping_id": "auto", "on_conflict": "skip"},
                       files={"file": (fname, f, "application/octet-stream")})
        site_result["import"] = {"status": r.status_code, "ok": r.status_code == 200}
        if r.status_code != 200:
            site_result["errors"].append(f"import: {r.text[:200]}")
            results["sites"].append(site_result)
            continue

        site_id = r.json().get("site_id")
        if not site_id:
            site_result["errors"].append("import: no site_id returned")
            results["sites"].append(site_result)
            continue

        # KOS 诊断 prod
        r_kos = c.post(f"/api/v1/sites/{site_id}/kos-diagnosis?track=prod", headers=headers)
        site_result["kos_prod"] = {"status": r_kos.status_code,
                                    "n_obstacles": len(r_kos.json().get("key_obstacles", [])) if r_kos.status_code == 200 else 0}
        if r_kos.status_code != 200:
            site_result["errors"].append(f"kos_prod: {r_kos.text[:200]}")

        # KOS 诊断 eco
        r_kos_eco = c.post(f"/api/v1/sites/{site_id}/kos-diagnosis?track=eco", headers=headers)
        site_result["kos_eco"] = {"status": r_kos_eco.status_code,
                                   "n_obstacles": len(r_kos_eco.json().get("key_obstacles", [])) if r_kos_eco.status_code == 200 else 0}
        if r_kos_eco.status_code != 200:
            site_result["errors"].append(f"kos_eco: {r_kos_eco.text[:200]}")

        # 重构评价(含 SSUI)
        r_recon = c.post(f"/api/v1/sites/{site_id}/evaluation", headers=headers,
                         json={"t": 5, "intensity": "medium"})
        site_result["reconstruction"] = {"status": r_recon.status_code,
                                          "grade": r_recon.json().get("grade") if r_recon.status_code == 200 else None,
                                          "has_ssui": "ssui" in r_recon.json() if r_recon.status_code == 200 else False}
        if r_recon.status_code != 200:
            site_result["errors"].append(f"reconstruction: {r_recon.text[:200]}")

    except Exception as e:
        site_result["errors"].append(f"exception: {str(e)[:200]}\n{traceback.format_exc()[:300]}")

    results["sites"].append(site_result)
    status_icon = "✅" if not site_result["errors"] else "❌"
    kos_p = site_result['kos_prod']['status'] if site_result['kos_prod'] else 'N/A'
    recon_s = site_result['reconstruction']['status'] if site_result['reconstruction'] else 'N/A'
    print(f"  [{idx+1:2d}/{len(xlsx_files)}] {status_icon} {fname[:35]:35s} "
          f"import={site_result['import']['status']} kos={kos_p} recon={recon_s}")

# 3. 汇总
total = len(results["sites"])
ok = sum(1 for s in results["sites"] if not s["errors"])
results["summary"] = {"total": total, "succeeded": ok, "failed": total - ok,
                       "success_rate": f"{ok}/{total} = {ok/total*100:.1f}%"}

# 4. 输出报告
output_path = os.path.join(os.path.dirname(__file__), "api_test_report.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n{'='*60}")
print(f"全链路测试完成: {results['summary']['success_rate']}")
print(f"报告: {output_path}")

# 清理(SessionLocal 持有连接, 需先关闭)
db_path = f"./srs_api_test_{os.getpid()}.db"
try:
    db2 = SessionLocal()
    db2.close()
    engine.dispose()
    if os.path.exists(db_path):
        os.remove(db_path)
except: pass
