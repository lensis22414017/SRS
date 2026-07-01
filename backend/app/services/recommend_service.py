"""方案推荐入库服务: 障碍因子 + 技术库 -> recommendations。需 DB。

推荐绑定障碍因子(diagnosis_factor_details 的全局 Top 因子)。
"""
from __future__ import annotations

import os
import sys

from sqlalchemy.orm import Session

from app.models import (
    DiagnosisFactorDetail, DiagnosisResult, FactorDictionary, Measurement,
    Recommendation, Site, TechnologyLibrary,
)

from app.core.config import resource_root

ROOT = resource_root()
for p in (os.path.join(ROOT, "ml", "recommend"),):
    if p not in sys.path:
        sys.path.insert(0, p)

LAND_MAP = {"生产用地": "生产用地", "production": "生产用地",
            "生态用地": "生态用地", "ecology": "生态用地"}


def _organic_factors_of(db: Session, site_id: int) -> list[str]:
    """场地实测有机污染物因子名(环境指标 - 重金属), 用于 OP 降级推荐匹配。"""
    return [name for (name,) in (db.query(FactorDictionary.factor_name)
            .join(Measurement, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id,
                    FactorDictionary.level1_category == "环境指标",
                    ~FactorDictionary.factor_name.in_(
                        ["砷", "铅", "铜", "锌", "镉", "铬", "汞", "镍"]))
            .distinct().all())]


def run_recommendation(db: Session, site_id: int, top_k: int = 5) -> dict:
    import engine as E

    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"场地不存在: {site_id}")
    diag = (db.query(DiagnosisResult).filter_by(site_id=site_id)
            .order_by(DiagnosisResult.id.desc()).first())

    organic_fallback = False
    factor_detail_id: dict = {}
    if diag is None:
        # 有机场地无 SHAP 诊断 → 走 OP 技术候选降级, 不抛错
        if site.pollution_type == "organic":
            organic_fallback = True
            factor_names = _organic_factors_of(db, site_id) or ["有机污染物"]
        else:
            raise ValueError("请先运行障碍因子诊断")
    else:
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
    rule_ver = E.RULE_VERSION + ("(organic_fallback)" if organic_fallback else "")
    saved = []
    for r in recs:
        tech = tech_by_name.get(r["tech_name"])
        if tech is None:
            continue
        bind_factor = next((f for f in r["matched_factors"] if f in factor_detail_id), None)
        reason_text = r["reason"]
        if organic_fallback:
            reason_text = (reason_text or "") + "(基于有机污染因子的候选技术, 未跑 SHAP 诊断)"
        # brief 4.6: 入库保存结构化字段(engine 已生成 reason_struct/matched_factors/source)
        db.add(Recommendation(
            site_id=site_id, technology_id=tech.id,
            diagnosis_factor_id=factor_detail_id.get(bind_factor),
            rule_version=rule_ver, match_score=r["match_score"],
            reason=reason_text, rank=r["rank"],
            reason_struct=r.get("reason_struct"),
            matched_factors=r.get("matched_factors"),
            source=r.get("source")))
        saved.append({"rank": r["rank"], "tech_name": r["tech_name"],
                      "matched_factors": r.get("matched_factors"),
                      "match_score": r["match_score"],
                      "reason_struct": r.get("reason_struct"),
                      "source": r.get("source"),
                      "cost_level": tech.cost_level,
                      "duration_level": tech.duration_level})
    db.commit()
    return {"site_id": site_id, "diagnosis_id": (diag.id if diag else None),
            "based_on_factors": factor_names,
            "organic_fallback": organic_fallback,
            "recommendations": saved}
