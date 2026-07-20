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
PARAM_VERSION = "evaluation_params_v0.2"

# v0.2 P1-9: SSUI 参数从 JSON 加载，不再硬编码
import json as _json
_EVAL_PARAMS = None

def _load_eval_params():
    """v1.0.1 final-audit: 配置文件缺失时明确报错(禁止静默退化为仅SSUI默认参数)。"""
    global _EVAL_PARAMS
    if _EVAL_PARAMS is None:
        cfg_path = os.path.join(ROOT, "ml", "evaluation", "evaluation_params.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding="utf-8") as f:
                _EVAL_PARAMS = _json.load(f)
        else:
            # v1.0.1 final-audit: 不静默退化, 明确报错
            raise FileNotFoundError(
                f"评价参数配置文件缺失: {cfg_path}。"
                f"功能重构评价和SSUI不可用, 请检查安装完整性。")
    return _EVAL_PARAMS

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


#  P0-3 / CLAUDE.md §3.1 木桶短板: 有机场地缺重金属评价元指标时, 不裸露 null, 走可解释降级。
# 重金属评价因子(与 run_evaluation screen 名单一致; factor_code==factor_name 中文)
HM_EVAL_FACTORS = {"砷", "铅", "铜", "锌", "镉", "铬", "汞", "镍"}
# 理化/肥力类 category(定位有机污染物 = 环境指标 - 重金属)
PROPERTY_CATEGORIES = {"化学性质", "肥力指标", "物理性质", "生物指标"}


def _organic_risk(db: Session, site_id: int, series: dict, means: dict) -> dict:
    """有机污染物超标风险诊断(规则型, 非 ML)。

     P0-3 + 数据真实性: 查 threshold_rules ∪ standard_thresholds 两表最严档阈值,
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

    评价口径基于重金属+农业肥力, 有机因子不在体系内 → 不评分, 但必须给出:
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


def _integrate_weighting_and_mice(means: dict, scope: str) -> dict:
    """v1.0.2(GPT P0-3): 集成 AHP 主观权重 + MICE 插补。

    单场地策略():
    - AHP 主观权重: 用 indicator_weights 作为主观权重(已归一化)
    - 客观权重(熵权/CRITIC): 单场地无跨场地数据, 退化为均匀权重
    - MICE: 单场地 1×n 退化为中位数兜底(已有逻辑)

    返回 evaluate() 的 custom_weights/imputed_values 参数。
    """
    import os as _os
    import json as _json
    import numpy as np
    # evaluation_service.py 在 backend/app/services/, 需上溯到 SRS 根(4级dirname)
    _PARAMS = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
        _os.path.dirname(_os.path.abspath(__file__))))), "ml", "params", "evaluation_params.json")
    with open(_PARAMS, encoding="utf-8") as f:
        params = _json.load(f)
    iw = params["reconstruction"][scope]["indicator_weights"]

    # AHP 主观权重(直接用 indicator_weights, 已归一化)
    n = len(iw)
    subjective = np.array(list(iw.values()))
    subjective = subjective / subjective.sum()

    # 客观权重: 单场地退化为均匀(诚实标注)
    objective = np.ones(n) / n

    # 组合权重(主观50% + 客观50%)
    try:
        from weighting import combined_weights
        combined = combined_weights(subjective, objective, alpha=0.5)
        custom_weights = {k: float(v) for k, v in zip(iw.keys(), combined)}
    except ImportError:
        custom_weights = None  # weighting.py 不可用时用静态权重

    # MICE 插补(单场地退化为中位数兜底)
    imputed_values = None
    try:
        from mice_imputer import apply_mice_to_values
        result = apply_mice_to_values(means, all_factors=list(iw.keys()))
        if result.get("imputed"):
            imputed_values = result["imputed"]
    except ImportError:
        pass

    return {"custom_weights": custom_weights, "imputed_values": imputed_values}


def run_evaluation(db: Session, site_id: int, t: float | None = None,
                   intensity: str | None = None, allow_proxy: bool = False,
                   evaluation_year: int | None = None, scenario: str = "production",
                   scope: str = "production") -> dict:
    """R3-P0-2/P0-4/Round8: 运行评价, 接收完整参数, 禁止跨年份拼数据。

    Round8 审计一类: 入参 scope 称为 requested_scope(用户请求的正式评价场景),
    内部双轨重构仍需同时跑 production+ecology, 用独立变量名 recon_scope 隔离,
    严禁把循环变量赋给入参导致 SSUI 串轨。
    """
    requested_scope = scope  # 用户显式请求的评价场景(production 或 ecology)
    # Round8 审计 1.4: scope/scenario 必须是合法枚举, 非法返回 ValueError(API 层转 422)
    if requested_scope not in ("production", "ecology"):
        raise ValueError(f"非法 scope: {requested_scope}, 只允许 production / ecology")
    if scenario not in ("production", "ecology"):
        raise ValueError(f"非法 scenario: {scenario}, 只允许 production / ecology")

    cfg = _load_eval_params().get("ssui", {})
    if t is None:
        t = cfg.get("t", 2.0)
    if intensity is None:
        intensity = cfg.get("intensity", "medium")
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

    # Round9 P0-1.2: 必须先解析 evaluation_year(自动选年), 再算指纹。
    # 旧 Round8 在 evaluation_year=None 时用 None 算指纹 → 指纹与实际计算输入不一致。
    # 自动选年: 取该 site+scenario 的最大 evaluation_year
    from app.models import EconomicIndicator
    if evaluation_year is None:
        latest_year_row = db.query(EconomicIndicator.evaluation_year).filter_by(
            site_id=site_id, scenario=scenario).order_by(
            EconomicIndicator.evaluation_year.desc()).first()
        if latest_year_row:
            evaluation_year = latest_year_row[0]
    # 若仍为 None(场地无任何经济数据) → 标 0 让指纹仍稳定(用户补录后指纹变)
    resolved_year = evaluation_year if evaluation_year is not None else 0

    # R3-P0-3 + Round9 P0-1: SSUI 用专用评价输入指纹(含经济数据+参数+CSV+阈值)
    from app.services.versioning import evaluation_input_fingerprint
    ssui_fingerprint = evaluation_input_fingerprint(
        db, site_id, evaluation_year=resolved_year, scenario=scenario,
        scope=requested_scope, t=t, intensity=intensity, allow_proxy=allow_proxy,
        param_version=PARAM_VERSION)

    # Round9 P0-1.3: 保存 run_config(供 GET 重算指纹, 不再依赖猜参数)
    ssui_run_config = {
        "evaluation_year": resolved_year,
        "scenario": scenario,
        "scope": requested_scope,
        "t": float(t),
        "intensity": intensity,
        "allow_proxy": bool(allow_proxy),
        "normalization_version": "v1",  # 由 ssui.py 实际填, 这里占位
        "param_version": PARAM_VERSION,
        "threshold_scope": requested_scope,
    }

    # 有机场地缺重金属评价元指标 → 走降级, 不算重构/SSUI 数值分(幂等检查前拦截)
    if site.pollution_type == "organic" and not any(n in means for n in HM_EVAL_FACTORS):
        return _evaluation_organic_degraded(db, site_id, site, series, means, data_version)

    # brief 4.5 / D1: 追加式保留历史。
    # R3-P0-3: reconstruction 用 data_version 判断; SSUI 用专用指纹判断
    existing_latest: dict[str, EvaluationResult] = {}
    for r in (db.query(EvaluationResult).filter_by(site_id=site_id)
              .order_by(EvaluationResult.id.desc()).all()):
        existing_latest.setdefault(r.eval_type, r)
    # reconstruction 复用判断(只看检测数据版本)
    recon_reusable = all(
        et in existing_latest and existing_latest[et].data_version == data_version
        for et in ("reconstruction_prod", "reconstruction_eco"))
    # SSUI 复用判断(看评价输入指纹, 存在 input_fingerprint 字段里)
    ssui_existing = existing_latest.get("ssui")
    ssui_reusable = (ssui_existing is not None
                     and ssui_existing.input_fingerprint == ssui_fingerprint)
    if recon_reusable and ssui_reusable:
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
    # Round8 审计一类: 双轨重构用独立循环变量 recon_scope, 严禁覆盖入参 requested_scope
    for recon_scope in ("production", "ecology"):
        # v1.0.2(GPT 5.4): 污染物阈值兜底 — resolve_limit 返回 None 时调 fallback
        from app.services.threshold_resolver import resolve_threshold_fallback
        _FACTOR_TO_CANON = {"砷": "As_mgkg", "铅": "Pb_mgkg", "铜": "Cu_mgkg",
                            "锌": "Zn_mgkg", "镉": "Cd_mgkg", "铬": "Cr_mgkg",
                            "汞": "Hg_mgkg", "镍": "Ni_mgkg"}
        _track = "prod" if recon_scope == "production" else "eco"
        screen = {}
        for f in ("砷", "铅", "铜", "锌", "镉", "铬", "汞", "镍"):
            lim = (resolve_limit(_limits(), f, ph, scope=recon_scope,
                                 land_subtype="其他用地") or {}).get("limit")
            # v1.0.2: resolve_limit 返回 None → 调 resolve_threshold_fallback 取最严档
            if lim is None and db is not None:
                canon = _FACTOR_TO_CANON.get(f, f)
                fb = resolve_threshold_fallback(db, canon, track=_track)
                if fb.get("threshold_resolution_status") == "fallback":
                    lim = fb.get("threshold_value")
            screen[f] = lim
        # v1.0.2(GPT P0-3): AHP主观权重 + MICE插补集成
        eval_kwargs = _integrate_weighting_and_mice(means, recon_scope)
        r = R.evaluate(means, recon_scope, ph=ph, screen_limits=screen, **eval_kwargs)
        et = "reconstruction_prod" if recon_scope == "production" else "reconstruction_eco"
        # P4: 合并 KOS key_obstacles 到 limiting_factors(功能重构读 KOS Top)
        # R3 审计第四类: 删除 except Exception: pass, 改为结构化错误处理
        kos_limiting = list(r.get("limiting_factors") or [])
        kos_error = None
        kos_factors = []
        try:
            from app.services.kos_service import run_kos_diagnosis
            from app.models import Measurement
            track = "prod" if recon_scope == "production" else "eco"
            mrows = (db.query(Measurement.value, FactorDictionary.factor_name)
                     .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id, isouter=True)
                     .filter(Measurement.site_id == site_id, Measurement.value.isnot(None)).all())
            sv = {}
            for v, fn in mrows:
                if fn:
                    try:
                        vv = float(v)
                        if fn not in sv or vv > sv[fn]: sv[fn] = vv
                    except (TypeError, ValueError): pass
            if sv:
                # R3 审计第四类 4.3: 传同一 db_session, 统一使用数据库动态阈值
                kos_r = run_kos_diagnosis(sv, track=track, subset="all", db_session=db)
                kos_factors = [k["factor"] for k in kos_r.get("key_obstacles", [])][:5]
                # KOS 因子优先,合并去重
                for kf in kos_factors:
                    if kf not in kos_limiting:
                        kos_limiting.insert(0, kf)
        except Exception as e:
            # R3 审计第四类 4.1-4.2: 不静默吞异常, 记录错误用于门禁降级
            kos_error = str(e)

        # R3 审计第四类 4.2: 门禁降级四字段同步(grade/score/explanation/limiting_factors)
        if kos_error:
            # KOS 调用失败 → 强制降级为"评价受阻", score=None
            r["grade"] = "评价受阻(KOS诊断失败)"
            r["score"] = None
            r["explanation"] = (r.get("explanation") or "") + \
                f" 结论门禁: KOS诊断执行失败({kos_error[:200]}), " \
                f"功能重构评价降级为'评价受阻', 请检查模型完整性后重试。"
            r.setdefault("data_quality_flags", []).append("kos_diagnosis_failed")
        elif kos_factors and r.get("grade") == "可行":
            # KOS 检出超标障碍且重构判"可行" → 强制降级, score 同步置 None
            r["grade"] = "不可行（存在超标障碍）"
            r["score"] = None
            r["explanation"] = (r.get("explanation") or "") + \
                f" 结论门禁: KOS诊断检出 {len(kos_factors)} 个超标障碍因子" \
                f"({', '.join(kos_factors[:3])}), 功能重构可行性强制降级为不可行。"
            r.setdefault("data_quality_flags", []).append("kos_obstacle_forced_downgrade")
        _save(db, site_id, et, data_version, r.get("score"), r.get("grade"),
              dimensions={"dimensions": r["dimensions"],
                          "missing_indicators": r.get("missing_indicators", []),
                          "calculation_trace": r.get("calculation_trace", [])},
              weights=r.get("weights"), limiting=kos_limiting,
              explanation=r.get("explanation"))
        results[et] = r

    # R3-P0-2/P0-4: 从 DB 查经济数据, 锁定 site_id+year+scenario(禁止跨年份拼数据)
    # Round9 P0-1.2: evaluation_year 已在前面的"自动选年"逻辑中解析完成, 这里直接用
    from app.models import EconomicIndicator
    econ_q = db.query(EconomicIndicator).filter_by(site_id=site_id, scenario=scenario)
    if resolved_year and resolved_year > 0:
        econ_q = econ_q.filter_by(evaluation_year=resolved_year)
    econ_rows = econ_q.all()
    economic_data = {}
    for er in econ_rows:
        code = er.indicator_code
        economic_data[code] = {
            "value": er.raw_value,
            "source_type": er.source_type,
            "is_proxy": er.is_proxy,
            "unit": er.unit,
        }

    # R3-P0-5 + Round8 审计三类: 用 resolve_threshold_from_db 按 scope/pH/land_use 解析
    # 不再用 production+ecology 无序覆盖, 严格按 requested_scope 解析
    from app.services.threshold_resolver import resolve_threshold_from_db
    from app.models import StandardThreshold
    safety_thresholds = {}
    threshold_resolution_status = {}
    land_use_type = getattr(site, "land_use_type", None)
    _HM_CANON_MAP = {"砷": "As_mgkg", "铅": "Pb_mgkg", "镉": "Cd_mgkg", "铬": "Cr_mgkg",
                     "汞": "Hg_mgkg", "铜": "Cu_mgkg", "锌": "Zn_mgkg", "镍": "Ni_mgkg"}
    _ORGANIC_FACTORS = ["苯并[a]芘", "六六六", "滴滴涕", "石油烃"]
    requested_track = "prod" if requested_scope == "production" else "eco"
    for cn_name, canon in _HM_CANON_MAP.items():
        resolved = resolve_threshold_from_db(
            db, canon, track=requested_track, site_pH=ph, land_use_type=land_use_type)
        if resolved.get("threshold_value") is not None:
            safety_thresholds[cn_name] = {
                "limit": float(resolved["threshold_value"]),
                "type": "upper",
                "standard": resolved.get("threshold_standard", ""),
                "version": resolved.get("threshold_version", ""),
                "pH_condition": resolved.get("pH_condition", ""),
                "land_use_type": resolved.get("land_use_type", ""),
                "resolution_status": resolved.get("threshold_resolution_status", "resolved"),
            }
        threshold_resolution_status[cn_name] = resolved.get(
            "threshold_resolution_status", "not_found")
    # D17 有机污染物阈值(原审计三类 3.4: 必须为每个有机物解析合法阈值)
    for org_name in _ORGANIC_FACTORS:
        resolved = resolve_threshold_from_db(
            db, org_name, track=requested_track, site_pH=ph, land_use_type=land_use_type)
        if resolved.get("threshold_value") is not None:
            safety_thresholds[org_name] = {
                "limit": float(resolved["threshold_value"]),
                "type": "upper",
                "standard": resolved.get("threshold_standard", ""),
                "version": resolved.get("threshold_version", ""),
                "pH_condition": resolved.get("pH_condition", ""),
                "land_use_type": resolved.get("land_use_type", ""),
                "resolution_status": resolved.get("threshold_resolution_status", "resolved"),
            }
        threshold_resolution_status[org_name] = resolved.get(
            "threshold_resolution_status", "not_found")

    # Round8 审计一类 1.3: SSUI 严格使用 requested_scope, 不再受双轨循环影响
    s = S.evaluate(series, scope=requested_scope, t=t, intensity=intensity,
                   economic_data=economic_data, allow_proxy=allow_proxy,
                   safety_thresholds=safety_thresholds,
                   threshold_resolution_status=threshold_resolution_status)
    ssui_dimensions = dict(s.get("dimensions") or {})
    ssui_dimensions["calculation_trace"] = s.get("calculation_trace", [])
    # R3: 把经济指标详情也存入 dimensions 供前端展示
    if s.get("economic_details"):
        ssui_dimensions["economic_details"] = s["economic_details"]
    if s.get("coverage"):
        ssui_dimensions["coverage"] = s["coverage"]
    ssui_dimensions["is_blocked"] = s.get("is_blocked", False)
    ssui_dimensions["is_reference"] = s.get("is_reference", False)
    # R3-P0-3 / Round9 P0-1: SSUI 指纹+run_config 写入专用字段(不再塞 param_version)
    # 用 ssui 实际返回的 normalization_version 覆盖占位
    ssui_run_config["normalization_version"] = s.get("normalization_version", "v1")
    _save(db, site_id, "ssui", data_version, s.get("ssui"), s.get("grade"),
          dimensions=ssui_dimensions, weights=s.get("weights"),
          limiting=s.get("limiting_factors"), risk=s.get("risk_factors"),
          explanation=s.get("explanation"), param_version=PARAM_VERSION,
          input_fingerprint=ssui_fingerprint, run_config=ssui_run_config)
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
        "scope": requested_scope,  # Round8 审计一类: 显式回传 scope, 便于审计追溯
        "scenario": scenario,
        "evaluation_year": resolved_year,  # Round9 P0-1: 永远是解析后的字面值, 不为 None
        "reconstruction_prod": {"score": results["reconstruction_prod"]["score"],
                                "grade": results["reconstruction_prod"]["grade"]},
        "reconstruction_eco": {"score": results["reconstruction_eco"]["score"],
                               "grade": results["reconstruction_eco"]["grade"]},
        "ssui": {"ssui": results["ssui"]["ssui"], "grade": results["ssui"]["grade"]},
        "details": results,
    }


def _save(db, site_id, eval_type, data_version, score, grade,
          dimensions=None, weights=None, limiting=None, risk=None, explanation=None,
          param_version=None, input_fingerprint=None, run_config=None):
    db.add(EvaluationResult(
        site_id=site_id, eval_type=eval_type, data_version=data_version,
        param_version=param_version or PARAM_VERSION,
        input_fingerprint=input_fingerprint,
        run_config=run_config,
        score=score, grade=grade,
        dimensions=dimensions, weights=weights,
        limiting_factors=limiting, risk_factors=risk, explanation=explanation))
