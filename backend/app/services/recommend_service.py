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
    """v1.0.2(GPT 第七节): 方案推荐 — 区分类型 + 接收上游 + 不吞异常。

    推荐类型(GPT 7.1):
      - rule_based: 规则推荐(因子→技术库匹配, 当前主路径)
      - case_based: 案例相似推荐(RemediationCase 匹配, 如有数据)
      - collaborative: 协同过滤(需足够案例数据, 当前数据不足不启用)

    上游依赖(GPT 7.3):
      - KOS key_obstacles(同数据版本)
      - 重构/SSUI 结果(如已计算)
      任一上游过期/不可用 → 标降级原因(GPT 7.3), 不吞异常(GPT 7.4)
    """
    import engine as E

    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"场地不存在: {site_id}")
    diag = (db.query(DiagnosisResult).filter_by(site_id=site_id)
            .order_by(DiagnosisResult.id.desc()).first())

    # v1.0.2: 上游状态追踪(GPT 7.3)
    upstream_status = {
        "kos": "available",       # KOS 诊断
        "reconstruction": "not_computed",  # 重构评价
        "ssui": "not_computed",   # SSUI
    }
    degradation_reasons = []

    # P4: 优先读 KOS key_obstacles 作为障碍因子输入
    kos_factor_names = []
    kos_review_required = False
    try:
        from app.services.kos_service import run_kos_diagnosis
        track = "eco" if (site.land_use_type or "").startswith("生态") else "prod"
        subset = {"heavy_metal": "hm", "organic": "op"}.get(site.pollution_type or "", "all")
        # 从 DB 读场地因子值
        from app.models import Measurement
        rows = (db.query(Measurement.value, FactorDictionary.factor_name, FactorDictionary.factor_code)
                .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id, isouter=True)
                .filter(Measurement.site_id == site_id, Measurement.value.isnot(None)).all())
        sv = {}
        for v, fn, fc in rows:
            n = fn or fc
            if n:
                try:
                    vv = float(v)
                    if n not in sv or vv > sv[n]:
                        sv[n] = vv
                except (TypeError, ValueError):
                    pass
        if sv:
            kos_r = run_kos_diagnosis(sv, track=track, subset=subset, db_session=db)
            kos_factor_names = [k["factor"] for k in kos_r.get("key_obstacles", [])][:5]
            kos_review_required = kos_r.get("review_required", False)
    except Exception as e:
        # v1.0.2(GPT 7.4): 不吞 KOS 异常, 标注降级原因
        upstream_status["kos"] = f"failed: {str(e)[:80]}"
        degradation_reasons.append(f"KOS诊断失败({e}), 降级到SHAP路径")

    # KOS 因子英文名 → 中文名(推荐引擎用中文 METAL 集合匹配)
    _EN2CN = {"Cd_mgkg": "镉", "Pb_mgkg": "铅", "As_mgkg": "砷", "Cr_mgkg": "铬",
              "Hg_mgkg": "汞", "Cu_mgkg": "铜", "Zn_mgkg": "锌", "Ni_mgkg": "镍",
              "BaP_ngg": "苯并芘", "SumHCHs_ngg": "有机氯", "SumDDTs_ngg": "有机氯",
              "pH": "pH"}
    if kos_factor_names:
        kos_factor_names = [_EN2CN.get(f, f) for f in kos_factor_names]

    organic_fallback = False
    factor_detail_id: dict = {}
    if kos_factor_names:
        # KOS 因子优先
        factor_names = kos_factor_names
    elif diag is None:
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

    # v1.0.2(GPT 7.1): 推荐类型区分
    # 当前系统主要是规则推荐(因子→技术库匹配), 案例数据不足不启用协同过滤
    recommendation_type = "rule_based"
    if organic_fallback:
        recommendation_type = "rule_based_organic_degraded"

    # v1.0.2(GPT 7.3): 检查重构/SSUI 上游状态
    try:
        from app.models import EvaluationResult
        eval_r = (db.query(EvaluationResult).filter_by(site_id=site_id)
                  .order_by(EvaluationResult.id.desc()).first())
        if eval_r:
            upstream_status["reconstruction"] = "available"
            if eval_r.results and "ssui" in (eval_r.results or {}):
                upstream_status["ssui"] = "available"
    except Exception:
        pass

    return {"site_id": site_id, "diagnosis_id": (diag.id if diag else None),
            "based_on_factors": factor_names,
            "organic_fallback": organic_fallback,
            # v1.0.2(GPT 7.1-7.5)
            "recommendation_type": recommendation_type,
            "upstream_status": upstream_status,
            "degradation_reasons": degradation_reasons,
            "collaborative_filtering_available": False,  # GPT 7.2: 案例数据不足
            "kos_review_required": kos_review_required,
            "recommendations": saved}
