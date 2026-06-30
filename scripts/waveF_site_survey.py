"""Wave F 场地数据调查: 本地SQLite场地全貌 + test_datasets可用文件。"""
import sys
import os
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, BACKEND)
from app.db.session import SessionLocal  # noqa: E402
from app.models import Site, Measurement  # noqa: E402

db = SessionLocal()
print("=== 本地 SQLite 所有场地 ===")
sites = db.query(Site).order_by(Site.id).all()
print(f"总数: {len(sites)}")
for s in sites:
    n = db.query(Measurement).filter_by(site_id=s.id).count()
    flag = " ★有数据" if n > 0 else ""
    print(f"  id={s.id} {s.name[:24]:<26} type={str(s.pollution_type):<14} "
          f"lut={str(s.land_use_type):<12} n={n}{flag}")
db.close()

print("\n=== data/test_datasets/ 场地文件 ===")
td = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "test_datasets"))
if os.path.isdir(td):
    for f in sorted(os.listdir(td)):
        fp = os.path.join(td, f)
        sz = os.path.getsize(fp) // 1024
        print(f"  {f} ({sz}KB)")
else:
    print(f"  ✗ {td} 不存在")

print("\n=== data/raw/ 场地文件 ===")
raw = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
if os.path.isdir(raw):
    for f in sorted(os.listdir(raw))[:15]:
        if f.endswith((".xlsx", ".csv")):
            fp = os.path.join(raw, f)
            sz = os.path.getsize(fp) // 1024
            print(f"  {f} ({sz}KB)")
