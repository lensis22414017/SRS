"""SSUI Demo 经济数据预填充脚本。

为所有 demo_sites 自动填入 2023 年全国平均参照经济数据(D18-D25)。
source_type="official_national_reference", is_proxy=True。
用户可在前端随时替换为场地真实数据。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)

from app.db.session import SessionLocal
from app.models import Site, EconomicIndicator

# 2023 年 D18-D25 全国平均参照值(来源: 全国农产品成本收益资料汇编 + 国家统计局)
ECONOMIC_SEED = [
    {
        "indicator_code": "D18", "indicator_name": "劳动力成本",
        "raw_value": 452.78, "unit": "元/亩·年", "direction": "negative",
    },
    {
        "indicator_code": "D19", "indicator_name": "机械化成本",
        "raw_value": 278.11, "unit": "元/亩·年", "direction": "negative",
    },
    {
        "indicator_code": "D20", "indicator_name": "土地成本",
        "raw_value": 268.44, "unit": "元/亩·年", "direction": "negative",
    },
    {
        "indicator_code": "D21", "indicator_name": "非机械化成本",
        "raw_value": 386.17, "unit": "元/亩·年", "direction": "negative",
    },
    {
        "indicator_code": "D22", "indicator_name": "单位面积总产值",
        "raw_value": 19687.23, "unit": "元/公顷·年", "direction": "positive",
    },
    {
        "indicator_code": "D23", "indicator_name": "效益费用比",
        "raw_value": 0.993476, "unit": "无量纲", "direction": "positive",
    },
    {
        "indicator_code": "D24", "indicator_name": "人均可支配收入",
        "raw_value": 21691.0, "unit": "元/人·年", "direction": "positive",
    },
    {
        "indicator_code": "D25", "indicator_name": "单位面积实物产量",
        "raw_value": 7134.21, "unit": "kg/公顷·年", "direction": "positive",
    },
]

SOURCE_NAME = "全国农产品成本收益资料汇编2024(推算)+国家统计局2024年鉴"
SOURCE_URL = "https://www.stats.gov.cn/sj/ndsj/2024/indexch.htm"


def seed():
    db = SessionLocal()
    try:
        sites = db.query(Site).all()
        print(f"共 {len(sites)} 个场地")

        created = 0
        skipped = 0

        for site in sites:
            for item in ECONOMIC_SEED:
                # 幂等: 已存在则跳过
                existing = (
                    db.query(EconomicIndicator)
                    .filter_by(
                        site_id=site.id,
                        evaluation_year=2023,
                        scenario="production",
                        indicator_code=item["indicator_code"],
                    )
                    .first()
                )
                if existing is not None:
                    skipped += 1
                    continue

                record = EconomicIndicator(
                    site_id=site.id,
                    evaluation_year=2023,
                    scenario="production",
                    indicator_code=item["indicator_code"],
                    indicator_name=item["indicator_name"],
                    raw_value=item["raw_value"],
                    unit=item["unit"],
                    direction=item["direction"],
                    source_type="official_national_reference",
                    source_name=SOURCE_NAME,
                    source_url=SOURCE_URL,
                    source_geography="CN",
                    source_year=2023,
                    is_proxy=True,
                    confidence=0.6,
                    note="自动填充: 全国平均参照数据(2023年)。请根据场地实际情况替换。",
                    version="v1.2",
                )
                db.add(record)
                created += 1

        db.commit()
        print(f"新增 {created} 条经济记录, 跳过 {skipped} 条(已存在)")
        print(f"预计每个场地 8 条 (D18-D25), {len(sites)} 个场地")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
