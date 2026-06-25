"""修复案例库入库。"""
from __future__ import annotations

import csv
import os

from app.db.init_db import create_all
from app.db.session import SessionLocal
from app.models import RemediationCase

from app.core.config import resource_root

ROOT = resource_root()
CSV = os.path.join(ROOT, "data", "knowledge_base", "remediation_case_library_seed.csv")


def load(db, csv_path: str = CSV) -> int:
    db.query(RemediationCase).delete()
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        db.add(RemediationCase(**{k: (v if v != "" else None) for k, v in row.items()}))
    db.commit()
    return len(rows)


def main():
    create_all()
    db = SessionLocal()
    try:
        n = load(db)
        print(f"修复案例库入库完成: {n} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main()
