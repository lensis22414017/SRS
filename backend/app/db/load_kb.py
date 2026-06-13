"""把统一障碍因子知识库 V1.0 入库 (factor_dictionary + threshold_rules)。"""
import os
import sys

from app.db.init_db import create_all
from app.db.session import SessionLocal

# 引入 ml/etl 的解析+入库逻辑
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "etl"))
from load_knowledge_base import load  # noqa: E402

CSV = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")


def main(csv_path: str = CSV):
    create_all()
    db = SessionLocal()
    try:
        nf, nr = load(db, csv_path)
        print(f"知识库入库完成: 因子 {nf} 种, 阈值规则 {nr} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else CSV)
