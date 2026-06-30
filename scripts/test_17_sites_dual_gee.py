"""17 真实场地双轨回归(_barrier_gee 防泄漏+GEE协变量模型)。

验证裴总 goal:
  1. prod>eco 系统性(生产严阈值→正样本率更高)
  2. 个旧砷场地 top1 含砷/gee_soil_pH(砷活性与pH强相关)
  3. 双轨 model_version 不同(prod/eco)
直接 DB session(不经API), run_diagnosis 内 _enrich_gee_if_needed 自动 GEE 补入。
"""
import sys
import os

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)
os.environ.setdefault("GEE_PROJECT_ID", "project-1bc9db36-ce72-4e39-b2b")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.db.session import SessionLocal  # noqa: E402
from app.models import Site, Measurement  # noqa: E402
from app.services.diagnosis_service import run_diagnosis  # noqa: E402

db = SessionLocal()
sites = [s for s in db.query(Site).order_by(Site.id).all()
         if db.query(Measurement).filter_by(site_id=s.id).count() > 0]
print(f"=== {len(sites)} 场地双轨回归(_barrier_gee + GEE协变量补入) ===\n")

results = []
for s in sites:
    orig = s.land_use_type
    row = {"id": s.id, "name": s.name[:22], "type": s.pollution_type}
    for lut in ["生产", "生态"]:
        s.land_use_type = lut
        db.commit()
        try:
            r = run_diagnosis(db, s.id, top_n=5)
            row[f"{lut}_proba"] = r["risk_proba_mean"]
            row[f"{lut}_top1"] = (r["top_factors"][0]["factor"]
                                  if r["top_factors"] else "—")
            row[f"{lut}_model"] = r["model_version"]
        except Exception as e:
            row[f"{lut}_proba"] = None
            row[f"{lut}_err"] = str(e)[:50]
    s.land_use_type = orig
    db.commit()
    results.append(row)
    pp, ep = row.get("生产_proba"), row.get("生态_proba")
    print(f"  {row['id']:2d} {row['name']:22s} {row['type']:12s} "
          f"prod={pp} eco={ep} | prod_top1={row.get('生产_top1')}")

print("\n=== 系统性验证 ===")
ok = [r for r in results if r.get("生产_proba") is not None
      and r.get("生态_proba") is not None]
if ok:
    gt = sum(1 for r in ok if r["生产_proba"] > r["生态_proba"])
    print(f"  prod>eco: {gt}/{len(ok)} ({gt/len(ok)*100:.0f}%)")
# 个旧砷场地(云南个旧 heavy_metal)
gj = [r for r in results if "个旧" in r["name"] or "云南" in r["name"]]
if gj:
    print(f"  个旧场地: prod_top1={gj[0].get('生产_top1')} (期望含砷/gee_soil_pH)")
# 双轨 model_version
diff = sum(1 for r in ok if r.get("生产_model") != r.get("生态_model"))
print(f"  双轨model不同: {diff}/{len(ok)}")
db.close()
