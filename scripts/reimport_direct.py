"""直接用 pipeline.run_import 导入(确保事务提交)。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
os.environ.setdefault("DATABASE_URL", "sqlite:///./srs_dev.db")
os.environ.setdefault("SECRET_KEY", "dev_secret_change_me")

from app.db.session import SessionLocal
from app.db.bootstrap import main as bootstrap
from app.services.import_service import smart_detect_and_map, parse
from app.services.ingest_service import ingest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES = [
    ("data/raw/3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx", "01.云南-个旧-HM-134点"),
    ("data/raw/2.20250731_有机污染场地数据表(南京栖霞)_完整版.xlsx", "02.江苏-栖霞-OP-49点"),
    ("data/raw/1.20250731_复合污染场地数据表(乡村建设用地)_完整版.xlsx", "03.农村-HMOP-8点"),
]

def main():
    bootstrap()
    for relpath, site_code in FILES:
        fpath = os.path.join(ROOT, relpath.replace("/", os.sep))
        if not os.path.exists(fpath):
            print(f"❌ 文件不存在: {fpath}")
            continue
        print(f"\n{'='*60}")
        print(f"导入: {os.path.basename(fpath)} → {site_code}")

        mid, mapping, factor_cols = smart_detect_and_map(fpath)
        # 覆盖 site_code 为我们指定的
        mapping["site"] = mapping.get("site", {})
        mapping["site"]["site_code"] = site_code
        mapping["site"]["name"] = site_code

        parsed = parse(fpath, mapping)
        print(f"解析: {parsed.n_points}点, {parsed.n_measurements}测量")

        # 每次用独立 session 确保提交
        db = SessionLocal()
        try:
            result = ingest(db, parsed, mapping=mapping, on_conflict="overwrite",
                            imported_by=1, source_path=fpath)
            db.commit()
            print(f"✅ 导入: site_id={result['site_id']}, action={result['action']}, "
                  f"points={result['n_points']}, measurements={result['n_measurements']}")
        except Exception as e:
            db.rollback()
            print(f"❌ 导入失败: {e}")
        finally:
            db.close()

    # 验证
    print(f"\n{'='*60}\n验证\n{'='*60}")
    import sqlite3
    conn = sqlite3.connect("backend/srs_dev.db")
    rows = conn.execute("""
        SELECT s.id, s.name, s.site_code, s.pollution_type,
               COUNT(DISTINCT sp.id) as n_pts,
               COUNT(m.id) as n_meas,
               s.longitude, s.latitude
        FROM sites s
        LEFT JOIN sampling_points sp ON sp.site_id=s.id
        LEFT JOIN measurements m ON m.site_id=s.id
        WHERE s.site_code LIKE '01.%' OR s.site_code LIKE '02.%' OR s.site_code LIKE '03.%'
        GROUP BY s.id
    """).fetchall()
    for r in rows:
        print(f"  id={r[0]} {r[1][:30]:30s} | {r[3]:12s} | pts={r[4]} meas={r[5]} | lng={r[6]} lat={r[7]}")
    conn.close()

if __name__ == "__main__":
    main()
