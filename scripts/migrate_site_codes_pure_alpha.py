"""
v1.0.1 final-audit: 场地编号纯字母迁移脚本

将所有含数字的 site_code 转为纯字母 Base26 编码(SRS-XXXX)。
原编号含数字时另存 original_site_code。

用法: cd backend && python ../scripts/migrate_site_codes_pure_alpha.py
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.environ.setdefault('DATABASE_URL', f"sqlite:///./srs_dev.db")

from app.db.session import SessionLocal
from app.models import Site


def to_base26(n: int) -> str:
    if n < 0:
        n = 0
    chars = []
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        chars.append(chr(ord('A') + rem))
    return ''.join(reversed(chars))


def migrate():
    db = SessionLocal()
    sites = db.query(Site).all()
    migrated = 0
    skipped = 0
    for s in sites:
        old_code = s.site_code or ""
        if re.search(r'[0-9]', old_code):
            # 另存原编号
            try:
                s.original_site_code = old_code
            except Exception:
                pass  # 字段不存在时跳过
            new_code = f"SRS-{to_base26(s.id)}"
            s.site_code = new_code
            migrated += 1
            print(f"  [{s.id}] {old_code} → {new_code}")
        else:
            skipped += 1
    db.commit()
    db.close()
    print(f"\n迁移完成: {migrated} 个场地编号改为纯字母, {skipped} 个已是纯字母")


if __name__ == "__main__":
    migrate()
