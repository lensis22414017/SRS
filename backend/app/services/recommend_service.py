"""方案推荐入库服务: 障碍因子 + 技术库 -> recommendations。需 DB。

推荐绑定障碍因子(diagnosis_factor_details 的全局 Top 因子)。
"""
from __future__ import annotations

import os
import sys

from sqlalchemy.orm import Session

from app.models import (
    DiagnosisFactorDetail, DiagnosisResult, FactorDictionary, Recommendation,
    Site, TechnologyLibrary,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
for p in (os.path.join(ROOT, "ml", "recommend"),):
    if p not in sys.path:
        sys.path.insert(0, p)

LAND_MAP = {"生产用地": "生产用地", "production": "生产用地",
            "生态用地": "生态用地", "ecology": "生态用地"}


def run_recommendation(db: Session, site_id: int, top_k: int = 5) -> dict:
    import engine as E

    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"场地不存在: {site_id}")
    diag = (db.query(DiagnosisResult).filter_by(site_id=site_id)
            .order_by(DiagnosisResult.id.desc()).first())
    if diag is None:
        raise ValueError("请先运行障碍因子诊断")

    # 全局 Top 因子(sampling_point_id 为空)
    details = (db.query(DiagnosisFactorDetail, FactorDictionary)
               .join(FactorDictionary, DiagnosisFactorDetail.factor_id == FactorDictionary.id)
               .filter(DiagnosisFactorDetail.diagnosis_id == diag.id,
                       DiagnosisFactorDetail.sampling_point_id.is_(None))
               .order_by(DiagnosisFactorDetail.rank).all())
    factor_names = [fd.factor_name for _, fd in details]
    factor_detail_id = {fd.factor_name: d.id for d, fd in details}

    land_cn = LAND_MAP.get(site.land_use_type or "生产用地", "生产用地")
    recs = E.recommend(factor_names, land_use_cn=land_cn,
                       pollution_type=site.pollution_type or "heavy_metal", top_k=top_k)

    # 清除旧推荐(同站重算)
    db.query(Recommendation).filter_by(site_id=site_id).delete()
    tech_by_name = {t.tech_name: t for t in db.query(TechnologyLibrary).all()}
    saved = []
    for r in recs:
        tech = tech_by_name.get(r["tech_name"])
        if tech is None:
            continue
        bind_factor = next((f for f in r["matched_factors"] if f in factor_detail_id), None)
        db.add(Recommendation(
            site_id=site_id, technology_id=tech.id,
            diagnosis_factor_id=factor_detail_id.get(bind_factor),
            rule_version=E.RULE_VERSION, match_score=r["match_score"],
            reason=r["reason"], rank=r["rank"]))
        saved.append({"rank": r["rank"], "tech_name": r["tech_name"],
                      "matched_factors": r["matched_factors"],
                      "match_score": r["match_score"]})
    db.commit()
    return {"site_id": site_id, "diagnosis_id": diag.id,
            "based_on_factors": factor_names, "recommendations": saved}
