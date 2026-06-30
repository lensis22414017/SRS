"""Wave F: 导入test_datasets代表场地 + 多场地双用途双轨测试(裴总goal)。

本地SQLite仅1场地有数据 → 导入test_datasets(HM/OP/composite代表)补齐,
然后跑多场地双轨诊断矩阵(生产/生态×多场地)。
"""
import sys
import os
import glob
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import SessionLocal  # noqa: E402
from app.services.import_service import smart_detect_and_map  # noqa: E402
from app.services.pipeline import run_import_with_mapping  # noqa: E402
from app.models import Site, Measurement  # noqa: E402
from app.services.diagnosis_service import run_diagnosis  # noqa: E402

TD = os.path.join(ROOT, "data", "test_datasets")
# 代表场地: HM / OP / composite(HM+OP) 各覆盖
PICKS = ["site_广东_HM_200点.xlsx", "site_北京_OP_200点.xlsx",
         "site_山东_HM+OP_24点.xlsx", "site_新疆_HM_200点.xlsx", "site_浙江_OP_175点.xlsx"]

db = SessionLocal()
print("=== 第1步: 导入 test_datasets 代表场地 ===")
imported = []
for name in PICKS:
    fp = os.path.join(TD, name)
    if not os.path.exists(fp):
        print(f"  ✗ {name} 不存在")
        continue
    try:
        source, mapping, rows = smart_detect_and_map(fp)
        res = run_import_with_mapping(db, fp, mapping, on_conflict="skip")
        v = res["validation"]
        sid = res.get("site_id")
        print(f"  ✓ {name}: site_id={sid} type={mapping.get('site',{}).get('pollution_type')} "
              f"points={v['n_points']} meas={v['n_measurements']} exceed={v['n_exceed']}")
        imported.append(sid)
    except Exception as e:
        print(f"  ✗ {name}: {type(e).__name__}: {str(e)[:90]}")
db.commit()

print(f"\n=== 第2步: Wave F 多场地双用途双轨矩阵 (full双轨模型) ===")
sites = [(s, db.query(Measurement).filter_by(site_id=s.id).count())
         for s in db.query(Site).order_by(Site.id).all()]
sites = [(s, n) for s, n in sites if n > 0]
print(f"有数据场地: {len(sites)}")
print(f"{'场地':<26}{'类型':<13}{'生产proba':<11}{'生态proba':<11}{'模型异':<7}{'结论异'}")
ok = 0
for s, n in sites:
    orig = s.land_use_type
    row = {"name": s.name[:24], "type": str(s.pollution_type), "prod": None, "eco": None, "mp": False}
    for lut in ["生产", "生态"]:
        s.land_use_type = lut
        db.commit()
        try:
            r = run_diagnosis(db, s.id, top_n=5)
            row[lut == "生产" and "prod" or "eco"] = r["risk_proba_mean"]
            if lut == "生产":
                row["prod_m"] = r["model_version"]
            else:
                row["eco_m"] = r["model_version"]
        except Exception as e:
            print(f"  id={s.id} {lut}: ✗ {type(e).__name__}: {str(e)[:60]}")
    s.land_use_type = orig
    db.commit()
    if row["prod"] is not None and row["eco"] is not None:
        dm = row.get("prod_m") != row.get("eco_m")
        dp = abs(row["prod"] - row["eco"]) > 0.001
        if dm:
            ok += 1
        print(f"{row['name']:<26}{row['type']:<13}{row['prod']:<11}{row['eco']:<11}"
              f"{'✓' if dm else '✗':<7}{'✓' if dp else '='}")
print(f"\n双轨打通场地: {ok}/{len(sites)}")
db.close()
