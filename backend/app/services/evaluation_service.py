"""评价入库服务: 重构可行性(生产/生态) + SSUI -> evaluation_results。需 DB。"""
from __future__ import annotations

import os
import statistics
import sys
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import (EvaluationResult, FactorDictionary, Measurement, SamplingPoint,
                        Site, StandardThreshold, ThresholdRule)
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


# 裴总 P0-3 / CLAUDE.md §3.1 木桶短板: 有机场地缺重金属评价元指标时, 不裸露 null, 走可解释降级。
# 重金属评价因子(与 run_evaluation screen 名单一致; factor_code==factor_name 中文)
HM_EVAL_FACTORS = {"砷", "铅", "铜", "锌", "镉", "铬", "汞", "镍"}
# 理化/肥力类 category(定位有机污染物 = 环境指标 - 重金属)
PROPERTY_CATEGORIES = {"化学性质", "肥力指标", "物理性质", "生物指标"}


def _organic_risk(db: Session, site_id: int, series: dict, means: dict) -> dict:
    """有机污染物超标风险诊断(规则型, 非 ML)。

    裴总 P0-3 + 数据真实性: 查 threshold_rules ∪ standard_thresholds 两表最严档阈值,
    区分三类: 超标(有阈值且>阈值)/ 未超标(有阈值且≤阈值)/ 无阈值无法判定。
    不把"无阈值"默认当"未超标"——诚实报告数据缺口, 避免给假的"达标"结论。
    """
    rows = (db.query(FactorDictionary.factor_code, FactorDictionary.factor_name,
                     FactorDictionary.level1_category)
            .join(Measurement, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id).distinct().all())
    info = {fc: (name, cat) for fc, name, cat in rows}
    organic = {fc: name for fc, (name, cat) in info.items()
               if cat == "环境指标" and name not in HM_EVAL_FACTORS and fc != "pH"}
    if not organic:
        return {"n_organic_factors": 0, "detected_factors": {}, "exceed_factors": [],
                "max_ratios": {}, "no_threshold_factors": {}, "overall": "未检出有机污染物",
                "note": "该场地未检测到有机污染物因子(环境指标中无非重金属有机物)。"}
    organic_names = list(organic.values())
    # 阈值并集: threshold_rules(threshold_max) ∪ standard_thresholds(screening_value), 取最严档(min)
    tr_rows = (db.query(FactorDictionary.factor_name, ThresholdRule.threshold_max)
               .join(ThresholdRule, ThresholdRule.factor_id == FactorDictionary.id)
               .filter(FactorDictionary.factor_name.in_(organic_names),
                       ThresholdRule.threshold_max != None,
                       ThresholdRule.threshold_max > 0).all())
    st_rows = (db.query(FactorDictionary.factor_name, StandardThreshold.screening_value)
               .join(StandardThreshold, StandardThreshold.factor_id == FactorDictionary.id)
               .filter(FactorDictionary.factor_name.in_(organic_names),
                       StandardThreshold.screening_value != None,
                       StandardThreshold.screening_value > 0).all())
    min_thr: dict[str, float] = {}
    for name, v in list(tr_rows) + list(st_rows):
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv > 0 and (name not in min_thr or fv < min_thr[name]):
            min_thr[name] = fv
    exceed_factors: list[str] = []
    max_ratios: dict[str, float] = {}
    detected: dict[str, int] = {}
    no_threshold: dict[str, float] = {}  # 无阈值因子(诚实标注) → 最大值供人工核对
    for fc, name in organic.items():
        vals = [v for v in series.get(fc, []) if v is not None]
        if not vals:
            continue
        mx = max(float(v) for v in vals)
        detected[name] = len(vals)
        thr = min_thr.get(name)
        if thr and thr > 0:
            ratio = mx / thr
            if ratio > 1:
                exceed_factors.append(name)
                max_ratios[name] = round(ratio, 2)
        else:
            no_threshold[name] = round(mx, 3)
    n_exceed = len(exceed_factors)
    n_with_thr = len([n for n in detected if n in min_thr])
    n_no_thr = len(no_threshold)
    if n_exceed > 0:
        overall = f"有机物超标({n_exceed} 个因子; 另 {n_no_thr} 个无阈值无法判定)"
    elif n_with_thr > 0:
        overall = f"有阈值因子未超标({n_with_thr}); 无阈值无法判定({n_no_thr})"
    elif n_no_thr > 0:
        overall = f"全部 {n_no_thr} 个有机因子无 GB36600 筛选值, 无法定量判定(需补权威阈值)"
    else:
        overall = "未检出有机物"
    return {
        "n_organic_factors": len(organic),
        "detected_factors": detected,
        "exceed_factors": exceed_factors,
        "max_ratios": max_ratios,
        "no_threshold_factors": no_threshold,
        "n_with_threshold": n_with_thr,
        "n_no_threshold": n_no_thr,
        "overall": overall,
        "threshold_source": "GB36600-2018 / GB15618-2018 (threshold_rules ∪ standard_thresholds 最严档)",
        "note": ("无 GB36600 单项筛选值的有机因子单独列出(不默认判'未超标'); "
                 "需补权威阈值方可定量判定(遵守不凭记忆补阈值原则)。"),
    }


def _evaluation_organic_degraded(db: Session, site_id: int, site: Site,
                                 series: dict, means: dict, data_version: str) -> dict:
    """有机污染场地降级评价: 重构/SSUI 标"不适用(有机)" + organic_risk 风险诊断。

    裴总 P0-3: 评价口径基于重金属+农业肥力, 有机因子不在体系内 → 不评分, 但必须给出:
    (1) 为什么不能算 (2) 缺哪些指标 (3) 有机污染风险诊断 (4) OP 修复技术候选(见 recommend_service)。
    """
    # 幂等: 同 data_version 已降级过则复用, 不重复 _save(避免反复评价累积)
    existing_ssui = (db.query(EvaluationResult)
                     .filter_by(site_id=site_id, eval_type="ssui", data_version=data_version)
                     .first())
    if existing_ssui and existing_ssui.grade == "不适用(有机)":
        existing_or = (db.query(EvaluationResult)
                       .filter_by(site_id=site_id, eval_type="organic_risk")
                       .order_by(EvaluationResult.id.desc()).first())
        organic_risk = (existing_or.dimensions if existing_or
                        else _organic_risk(db, site_id, series, means))
        return {
            "site_id": site_id, "data_version": data_version, "param_version": PARAM_VERSION,
            "organic_degraded": True, "reused": True,
            "reconstruction_prod": {"score": None, "grade": "不适用(有机)"},
            "reconstruction_eco": {"score": None, "grade": "不适用(有机)"},
            "ssui": {"ssui": None, "grade": "不适用(有机)"},
            "organic_risk": organic_risk,
            "limiting_factors": existing_ssui.limiting_factors or [],
            "explanation": existing_ssui.explanation or "",
        }
    organic_risk = _organic_risk(db, site_id, series, means)
    limiting = ["缺重金属评价因子(砷/铅/镉/铬/汞/镍/铜/锌)",
                "缺农业肥力指标(有机质/速效钾/阳离子交换量等)"]
    explanation = (
        "本场地为有机污染场地, 功能重构可行性与 SSUI 评价口径基于重金属 + 农业肥力指标体系, "
        "有机污染物不在该评价体系内, 故不生成数值评分。下方'有机污染风险诊断'作为替代诊断依据。"
        "如需生成 SSUI/重构分数, 请补充: 砷、铅、镉等重金属指标, 以及有机质、速效钾等农业肥力指标。"
    )
    dims = {"applicable": False, "reason": "organic_site_no_heavy_metal_indicators",
            "organic_risk": organic_risk, "pollution_type": site.pollution_type}
    for et in ("reconstruction_prod", "reconstruction_eco", "ssui"):
        _save(db, site_id, et, data_version, score=None, grade="不适用(有机)",
              dimensions=dims, limiting=limiting, explanation=explanation)
    _save(db, site_id, "organic_risk", data_version,
          score=(max(organic_risk["max_ratios"].values()) if organic_risk["max_ratios"] else None),
          grade=organic_risk["overall"],
          dimensions=organic_risk, explanation=explanation)
    db.commit()
    return {
        "site_id": site_id, "data_version": data_version, "param_version": PARAM_VERSION,
        "organic_degraded": True,
        "reconstruction_prod": {"score": None, "grade": "不适用(有机)"},
        "reconstruction_eco": {"score": None, "grade": "不适用(有机)"},
        "ssui": {"ssui": None, "grade": "不适用(有机)"},
        "organic_risk": organic_risk,
        "limiting_factors": limiting,
        "explanation": explanation,
    }


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

    # 裴总 P0-3: 有机场地缺重金属评价元指标 → 走降级, 不算重构/SSUI 数值分(幂等检查前拦截)
    if site.pollution_type == "organic" and not any(n in means for n in HM_EVAL_FACTORS):
        return _evaluation_organic_degraded(db, site_id, site, series, means, data_version)

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

    # brief 4.5/M4: 追加式但限累积——每 eval_type 保留最近 10 个, 防止反复评价膨胀
    for et in ("reconstruction_prod", "reconstruction_eco", "ssui"):
        stale_rows = (db.query(EvaluationResult)
                      .filter_by(site_id=site_id, eval_type=et)
                      .order_by(EvaluationResult.id.desc()).offset(10).all())
        for row in stale_rows:
            db.delete(row)

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
