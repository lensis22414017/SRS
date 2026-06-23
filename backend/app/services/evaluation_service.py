"""评价入库服务: 重构可行性(生产/生态) + SSUI -> evaluation_results。需 DB。"""
from __future__ import annotations

import os
import statistics
import sys
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import EvaluationResult, FactorDictionary, Measurement, SamplingPoint, Site
from app.services.threshold_resolver import build_pollutant_limits, resolve_limit

from app.core.config import resource_root
from app.services.versioning import current_site_data_version

ROOT = resource_root()
for p in (os.path.join(ROOT, "ml", "evaluation"),):
    if p not in sys.path:
        sys.path.insert(0, p)
KB_CSV = os.path.join(ROOT, "data", "knowledge_base", "统一障碍因子知识库_V1.0.csv")
PARAM_VERSION = "evaluation_params_v0.1"

_LIM = None


def _limits():
    global _LIM
    if _LIM is None:
        _LIM = build_pollutant_limits(KB_CSV)
    return _LIM


def _series_and_means(db: Session, site_id: int):
    rows = (db.query(SamplingPoint.point_code, FactorDictionary.factor_code, Measurement.value)
            .join(Measurement, Measurement.sampling_point_id == SamplingPoint.id)
            .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id).all())
    series = defaultdict(list)
    for _, fc, v in rows:
        if v is not None:
            series[fc].append(v)
    means = {k: statistics.mean(v) for k, v in series.items() if v}
    return dict(series), means


def run_evaluation(db: Session, site_id: int, t: float = 2.0,
                   intensity: str = "medium") -> dict:
    import reconstruction as R
    import ssui as S

    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"场地不存在: {site_id}")
    series, means = _series_and_means(db, site_id)
    if not means:
        raise ValueError("该场地无检测数据")
    ph = means.get("pH")
    data_version = current_site_data_version(db, site_id)

    # brief 4.5 / D1: 追加式保留历史(旧实现 delete 全部旧评价 → 无历史)。
    # 若三类 latest 的 data_version 都等于当前版本 → 数据未变(幂等), 直接返回不重算,
    # 避免冗余累积; 数据变化时新增, 旧结果因 data_version 不同自动被 GET 判为 stale。
    existing_latest: dict[str, EvaluationResult] = {}
    for r in (db.query(EvaluationResult).filter_by(site_id=site_id)
              .order_by(EvaluationResult.id.desc()).all()):
        existing_latest.setdefault(r.eval_type, r)
    if all(et in existing_latest and existing_latest[et].data_version == data_version
           for et in ("reconstruction_prod", "reconstruction_eco", "ssui")):
        return {
            "site_id": site_id, "data_version": data_version,
            "param_version": PARAM_VERSION, "reused": True,
            "reconstruction_prod": {"score": existing_latest["reconstruction_prod"].score,
                                    "grade": existing_latest["reconstruction_prod"].grade},
            "reconstruction_eco": {"score": existing_latest["reconstruction_eco"].score,
                                   "grade": existing_latest["reconstruction_eco"].grade},
            "ssui": {"ssui": existing_latest["ssui"].score,
                     "grade": existing_latest["ssui"].grade},
            "details": {et: {"score": existing_latest[et].score,
                             "grade": existing_latest[et].grade,
                             "data_version": existing_latest[et].data_version}
                        for et in existing_latest},
        }

    results = {}
    for scope in ("production", "ecology"):
        screen = {f: (resolve_limit(_limits(), f, ph, scope=scope,
                                    land_subtype="其他用地") or {}).get("limit")
                  for f in ("砷", "铅", "铜", "锌", "镉", "铬", "汞", "镍")}
        r = R.evaluate(means, scope, ph=ph, screen_limits=screen)
        et = "reconstruction_prod" if scope == "production" else "reconstruction_eco"
        _save(db, site_id, et, data_version, r.get("score"), r.get("grade"),
              dimensions={"dimensions": r["dimensions"],
                          "missing_indicators": r.get("missing_indicators", []),
                          "calculation_trace": r.get("calculation_trace", [])},
              weights=r.get("weights"), limiting=r.get("limiting_factors"),
              explanation=r.get("explanation"))
        results[et] = r

    s = S.evaluate(series, scope="production", t=t, intensity=intensity)
    ssui_dimensions = dict(s.get("dimensions") or {})
    ssui_dimensions["calculation_trace"] = s.get("calculation_trace", [])
    _save(db, site_id, "ssui", data_version, s.get("ssui"), s.get("grade"),
          dimensions=ssui_dimensions, weights=s.get("weights"),
          limiting=s.get("limiting_factors"), risk=s.get("risk_factors"),
          explanation=s.get("explanation"))
    results["ssui"] = s

    db.commit()
    return {
        "site_id": site_id, "data_version": data_version,
        "param_version": PARAM_VERSION,
        "reconstruction_prod": {"score": results["reconstruction_prod"]["score"],
                                "grade": results["reconstruction_prod"]["grade"]},
        "reconstruction_eco": {"score": results["reconstruction_eco"]["score"],
                               "grade": results["reconstruction_eco"]["grade"]},
        "ssui": {"ssui": results["ssui"]["ssui"], "grade": results["ssui"]["grade"]},
        "details": results,
    }


def _save(db, site_id, eval_type, data_version, score, grade,
          dimensions=None, weights=None, limiting=None, risk=None, explanation=None):
    db.add(EvaluationResult(
        site_id=site_id, eval_type=eval_type, data_version=data_version,
        param_version=PARAM_VERSION, score=score, grade=grade,
        dimensions=dimensions, weights=weights,
        limiting_factors=limiting, risk_factors=risk, explanation=explanation))
