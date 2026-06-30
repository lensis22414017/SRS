"""Wave F 双用途端到端测试: 同场地标生产/生态 → 不同双轨模型诊断。

裴总要求: 两套阈值模型和诊断逻辑要打通(Wave F)。
验证: run_diagnosis 按 land_use_type 路由到 lake_prod_full / lake_eco_full,
      model_version 不同, 证双轨诊断打通。
"""
import sys
import os
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)

from app.db.session import SessionLocal  # noqa: E402
from app.models import Site, Measurement  # noqa: E402
from app.services.diagnosis_service import run_diagnosis  # noqa: E402

db = SessionLocal()
site = None
for s in db.query(Site).order_by(Site.id).limit(30).all():
    if db.query(Measurement).filter_by(site_id=s.id).count() > 0:
        site = s
        break
if site is None:
    print("✗ 无有检测数据的场地, 请先导入")
    sys.exit(1)
orig_lut = site.land_use_type
print(f"测试场地: id={site.id} name={site.name} pollution={site.pollution_type} "
      f"原land_use_type={orig_lut}\n")

results = {}
for lut in ["生产", "生态"]:
    site.land_use_type = lut
    db.commit()
    try:
        res = run_diagnosis(db, site.id, top_n=5)
        results[lut] = res
        top1 = res["top_factors"][0]["factor"] if res["top_factors"] else "—"
        print(f"land_use_type={lut}: ✓ model={res['model_version']} "
              f"risk_proba={res['risk_proba_mean']} top1={top1} "
              f"n_factors={len(res['top_factors'])}")
    except Exception as e:
        import traceback
        print(f"land_use_type={lut}: ✗ {type(e).__name__}: {e}")
        traceback.print_exc()

site.land_use_type = orig_lut
db.commit()

print("\n=== 打通判定 ===")
if "生产" in results and "生态" in results:
    vp = results["生产"]["model_version"]
    ve = results["生态"]["model_version"]
    rp = results["生产"]["risk_proba_mean"]
    re = results["生态"]["risk_proba_mean"]
    print(f"生产轨: {vp}  risk_proba={rp}")
    print(f"生态轨: {ve}  risk_proba={re}")
    if vp != ve and "prod" in vp and "eco" in ve:
        print("✓ 双轨诊断打通: 生产/生态选用不同 RF 模型(prod/eco)")
        if rp != re:
            print(f"  风险概率差异: 生产 {rp} vs 生态 {re} (双轨结论不同, 可演示)")
        else:
            print("  ⚠ 风险概率相同(可能该场地双轨结论一致, 或数据局限)")
    else:
        print("✗ 未打通: 模型相同或轨标记缺失")
else:
    print("✗ 双用途测试未完成(有轨报错)")

db.close()
