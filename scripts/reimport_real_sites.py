"""重新导入三份真实场地数据：个旧HM(134点)、栖霞OP、农村HM+OP。
用系统自带的 smart_detect_and_map + parse + ingest 链路。
"""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

os.environ.setdefault("DATABASE_URL", "sqlite:///./srs_dev.db")
os.environ.setdefault("SECRET_KEY", "dev_secret_change_me")

from app.db.session import SessionLocal, engine
from app.db.bootstrap import main as bootstrap
from app.services.import_service import smart_detect_and_map, parse
from app.services.ingest_service import ingest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES = [
    ("data/raw/3.20250731_重金属污染场地数据表(云南个旧)_最终版.xlsx", "yunnan_gejiu_real"),
    ("data/raw/2.20250731_有机污染场地数据表(南京栖霞)_完整版.xlsx", "nanjing_xixia_real"),
    ("data/raw/1.20250731_复合污染场地数据表(乡村建设用地)_完整版.xlsx", "rural_composite_real"),
]

def main():
    bootstrap()
    db = SessionLocal()
    try:
        for relpath, mapping_id in FILES:
            fpath = os.path.join(ROOT, relpath.replace("/", os.sep))
            if not os.path.exists(fpath):
                print(f"❌ 文件不存在: {fpath}")
                continue
            print(f"\n{'='*60}")
            print(f"导入: {os.path.basename(fpath)}")
            print(f"{'='*60}")

            # 智能识别 mapping
            mid, mapping, factor_cols = smart_detect_and_map(fpath)
            print(f"mapping_id={mid}, 因子列数={len(factor_cols)}")
            print(f"point_columns: {json.dumps(mapping.get('point_columns',{}), ensure_ascii=False)[:200]}")

            if not mapping.get("point_columns", {}).get("point_code"):
                print("❌ 未识别到采样点编号列，跳过")
                continue

            # 解析
            parsed = parse(fpath, mapping)
            print(f"解析: {parsed.n_points} 采样点, {parsed.n_measurements} 测量记录")

            # 检查坐标
            coords = [(p.longitude, p.latitude) for p in parsed.points if p.longitude and p.latitude]
            print(f"有坐标的采样点: {len(coords)}/{parsed.n_points}")
            if coords:
                print(f"坐标范围: lng[{min(c[0] for c in coords):.4f}, {max(c[0] for c in coords):.4f}] lat[{min(c[1] for c in coords):.4f}, {max(c[1] for c in coords):.4f}]")

            # 导入(传 source_path 让判重工作, site_id=1已手动清空)
            result = ingest(db, parsed, mapping=mapping, on_conflict="overwrite",
                            imported_by=1, source_path=fpath)
            print(f"导入结果: action={result['action']}, site_id={result['site_id']}, points={result['n_points']}, measurements={result['n_measurements']}")
    finally:
        db.close()

    # 验证
    print(f"\n{'='*60}")
    print("验证数据库")
    print(f"{'='*60}")
    import sqlite3
    conn = sqlite3.connect("backend/srs_dev.db")
    rows = conn.execute("""
        SELECT s.id, s.name, s.pollution_type, s.longitude, s.latitude,
               COUNT(DISTINCT sp.id) as n_points
        FROM sites s
        LEFT JOIN sampling_points sp ON sp.site_id=s.id
        WHERE s.name LIKE '%个旧%' OR s.name LIKE '%栖霞%' OR s.name LIKE '%农村%'
            OR s.site_code LIKE '%gejiu_real%' OR s.site_code LIKE '%xixia_real%' OR s.site_code LIKE '%rural%'
        GROUP BY s.id
    """).fetchall()
    for r in rows:
        print(f"  id={r[0]} {r[1][:30]:30s} | {r[2]:12s} | lng={r[3]} lat={r[4]} | 点={r[5]}")
    conn.close()

if __name__ == "__main__":
    main()
