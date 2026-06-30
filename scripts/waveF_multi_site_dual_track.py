"""Wave F 多场地双用途功能测试(裴总goal: 用full双轨模型)。

扩展单场地e2e到多场地: HM/OP/composite各类型场地标生产/生态,跑run_diagnosis,
验双轨不同模型(lake_prod_full/lake_eco_full)+不同结论。用full双轨模型(过渡)。
"""
import sys
import os
from collections import defaultdict
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)

from app.db.session import SessionLocal  # noqa: E402
from app.models import Site, Measurement  # noqa: E402
from app.services.diagnosis_service import run_diagnosis  # noqa: E402

db = SessionLocal()
sites_with_data = []
for s in db.query(Site).order_by(Site.id).all():
    n = db.query(Measurement).filter_by(site_id=s.id).count()
    if n > 0:
        sites_with_data.append((s, n))

by_type = defaultdict(list)
for s, n in sites_with_data:
    by_type[s.pollution_type or "unknown"].append((s, n))
print(f"=== Wave F 多场地双用途测试 (full双轨模型) ===")
print(f"有数据场地: {len(sites_with_data)}")
for t, lst in by_type.items():
    print(f"  {t}: {len(lst)} 场地 (id: {[s.id for s,_ in lst]})")

# 每类型取最多2场地
test_sites = []
for t, lst in by_type.items():
    test_sites.extend(lst[:2])
print(f"\n测试场地: {len(test_sites)} (每类型≤2)\n")

results = []
for s, n in test_sites:
    orig = s.land_use_type
    print(f"--- 场地 id={s.id} {s.name[:25]} type={s.pollution_type} n_meas={n} ---")
    for lut in ["生产", "生态"]:
        s.land_use_type = lut
        db.commit()
        try:
            res = run_diagnosis(db, s.id, top_n=5)
            top1 = res["top_factors"][0]["factor"] if res["top_factors"] else "—"
            mv = res["model_version"].split("_")[-2] + "_" + res["model_version"].split("_")[-1]
            print(f"  {lut}: model={mv} proba={res['risk_proba_mean']} top1={top1}")
            results.append({"site": s.id, "name": s.name[:18], "type": s.pollution_type,
                            "lut": lut, "model": mv, "proba": res["risk_proba_mean"], "top1": top1})
        except Exception as e:
            print(f"  {lut}: ✗ {type(e).__name__}: {str(e)[:70]}")
            results.append({"site": s.id, "lut": lut, "error": str(e)[:70]})
    s.land_use_type = orig
    db.commit()

# 双轨打通判定
print(f"\n=== Wave F 双轨打通矩阵 ===")
print(f"{'场地':<22}{'类型':<14}{'生产proba':<11}{'生态proba':<11}{'模型异':<7}{'结论异'}")
ok = 0
i = 0
while i < len(results) - 1:
    p, e = results[i], results[i + 1]
    if p.get("site") == e.get("site") and "error" not in p and "error" not in e:
        dm = p["model"] != e["model"]
        dp = abs(p["proba"] - e["proba"]) > 0.001
        if dm:
            ok += 1
        print(f"{p['name']:<22}{str(p['type']):<14}{p['proba']:<11}{e['proba']:<11}{'✓' if dm else '✗':<7}{'✓' if dp else '='}")
    i += 2
print(f"\n双轨打通场地: {ok}/{len(test_sites)}")
db.close()
