"""障碍因子诊断: 取数 -> 特征对齐 -> RF 预测 -> SHAP -> 入库。

特征对齐策略(裴总已确认"重标化/诚实标注"原则):
  - 场地因子经 feature_mapping.json 映射到训练特征;
  - 训练特征在场地数据中缺失的, 用训练集中位数填充, 并记录 imputed_features;
  - 结论解释中明确标注哪些特征是填充值, 不冒充实测。
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
from sqlalchemy.orm import Session

from app.models import (
    DiagnosisFactorDetail, DiagnosisResult, FactorDictionary, MLModel,
    Measurement, SamplingPoint, Site,
)

from app.core.config import resource_root
from app.services.versioning import current_site_data_version

ROOT = resource_root()
ML_DIR = os.path.join(ROOT, "ml")
for p in (os.path.join(ML_DIR, "models"), os.path.join(ML_DIR, "explain")):
    if p not in sys.path:
        sys.path.insert(0, p)

MAPPING_PATH = os.path.join(ML_DIR, "models", "feature_mapping.json")


PRODUCTION_LIMIT_RULES = [
    {
        "factor": "有机质",
        "feature": "OrganicMatter(g/kg)",
        "lower": 10.0,
        "unit": "g/kg",
        "category": "肥力指标",
        "note": "生产/生态重构常用下限约 1% 有机质(10 g/kg); 极低值按木桶短板纳入障碍因子。",
    },
    {
        "factor": "pH",
        "feature": "SoilpH",
        "lower": 5.5,
        "upper": 8.5,
        "unit": "",
        "category": "化学性质",
        "note": "pH 超出生产用地常用适宜范围时作为化学限制因子。",
    },
]


def load_feature_mapping() -> dict:
    with open(MAPPING_PATH, encoding="utf-8") as f:
        return json.load(f)


def resolve_model_feature(factor: str, preferred_feature: str,
                          feature_list: list[str]) -> str | None:
    """兼容旧英文特征名与新 Fxx_中文特征名。"""
    if preferred_feature in feature_list:
        return preferred_feature
    suffix = f"_{factor}"
    for feature in feature_list:
        if feature == factor or feature.endswith(suffix):
            return feature
    return None


def feature_to_factor_mapping(mapping: dict, feature_list: list[str]) -> dict[str, str]:
    """训练特征 -> 场地因子中文名, 与 resolve_model_feature 保持一致。"""
    out = {}
    for factor, preferred_feature in mapping["factor_to_feature"].items():
        resolved = resolve_model_feature(factor, preferred_feature, feature_list)
        if resolved:
            out[resolved] = factor
    return out


def pivot_site_measurements(db: Session, site_id: int) -> pd.DataFrame:
    """长表 -> 行=采样点(point_code), 列=factor_code。"""
    rows = (db.query(SamplingPoint.point_code, FactorDictionary.factor_code,
                     Measurement.value)
            .join(Measurement, Measurement.sampling_point_id == SamplingPoint.id)
            .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id).all())
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["point_code", "factor_code", "value"])
    return df.pivot_table(index="point_code", columns="factor_code",
                          values="value", aggfunc="mean")


def align_features(pivot: pd.DataFrame, feature_list: list[str],
                   medians: dict, mapping: dict) -> tuple[pd.DataFrame, list[str]]:
    """场地因子矩阵 -> 模型特征矩阵; 返回 (X, imputed_features)。"""
    f2f = mapping["factor_to_feature"]
    conv = mapping.get("conversions", {})
    X = pd.DataFrame(index=pivot.index)
    measured: set[str] = set()
    for factor, preferred_feature in f2f.items():
        feature = resolve_model_feature(factor, preferred_feature, feature_list)
        if factor in pivot.columns and feature in feature_list:
            vals = pivot[factor]
            c = conv.get(factor)
            if c and c.get("to_feature_multiply") and feature == preferred_feature:
                vals = vals * c["to_feature_multiply"]
            X[feature] = vals
            measured.add(feature)
    imputed = []
    for feature in feature_list:
        if feature not in X.columns:
            X[feature] = medians.get(feature, 0.0)
            if not feature.endswith("__missing"):
                imputed.append(feature)
        else:
            med = medians.get(feature, 0.0)
            X[feature] = X[feature].fillna(med)
    # 缺失标记列: 实测=0, 填充=1
    for feature in feature_list:
        if feature.endswith("__missing"):
            base = feature[:-len("__missing")]
            X[feature] = 0 if base in measured else 1
    return X[feature_list], imputed


def production_limiting_factors(pivot: pd.DataFrame) -> list[dict]:
    """基于实测生产功能阈值补充识别肥力/化学短板。

    该结果是规则筛查, 不是 SHAP 解释; 用于避免污染风险模型漏掉
    低有机质等生产功能障碍。
    """
    factors: list[dict] = []
    for rule in PRODUCTION_LIMIT_RULES:
        factor = rule["factor"]
        if factor not in pivot.columns:
            continue
        vals = pd.to_numeric(pivot[factor], errors="coerce").dropna()
        if vals.empty:
            continue
        mean_v = float(vals.mean())
        p25 = float(vals.quantile(0.25))
        p75 = float(vals.quantile(0.75))
        lower = rule.get("lower")
        upper = rule.get("upper")
        severity = 0.0
        direction = "neutral"
        threshold_text = ""
        affected_fraction = 0.0
        if lower is not None and p25 < float(lower):
            affected_fraction = float((vals < float(lower)).mean())
            severity = ((float(lower) - p25) / max(abs(float(lower)), 1e-9)
                        + affected_fraction)
            direction = "negative"
            threshold_text = f"<{lower}{rule['unit']}"
        if upper is not None and p75 > float(upper):
            high_fraction = float((vals > float(upper)).mean())
            high_severity = ((p75 - float(upper)) / max(abs(float(upper)), 1e-9)
                             + high_fraction)
            if high_severity > severity:
                severity = high_severity
                affected_fraction = high_fraction
                direction = "positive"
                threshold_text = f">{upper}{rule['unit']}"
        if severity <= 0:
            continue
        factors.append({
            "feature": rule["feature"],
            "factor_code": factor,
            "mean_abs_shap": round(max(severity, 0.001), 6),
            "direction": direction,
            "source": "production_threshold_rule",
            "category": rule["category"],
            "mean_value": round(mean_v, 4),
            "diagnostic_value": round(p25 if direction == "negative" else p75, 4),
            "affected_fraction": round(affected_fraction, 4),
            "threshold": threshold_text,
            "note": rule["note"],
        })
    return sorted(factors, key=lambda x: x["mean_abs_shap"], reverse=True)


def pollutant_exceedance_factors(pivot: pd.DataFrame,
                                 scope: str = "production",
                                 land_subtype: str = "其他用地") -> list[dict]:
    """基于标准阈值识别污染物超标障碍因子。

    这是规则筛查, 不冒充 SHAP; 用于确保实测超标污染物不会被纯模型解释漏掉。
    """
    from app.services.pipeline import get_pollutant_limits
    from app.services.threshold_resolver import resolve_limit

    limits = get_pollutant_limits()
    ph_series = (pd.to_numeric(pivot["pH"], errors="coerce")
                 if "pH" in pivot.columns else None)
    factors: list[dict] = []
    for factor in limits:
        if factor not in pivot.columns:
            continue
        vals = pd.to_numeric(pivot[factor], errors="coerce").dropna()
        if vals.empty:
            continue
        exceed_ratios = []
        threshold_notes = []
        for idx, value in vals.items():
            ph = None
            if ph_series is not None and idx in ph_series.index and pd.notna(ph_series.loc[idx]):
                ph = float(ph_series.loc[idx])
            rule = resolve_limit(limits, factor, ph, scope=scope,
                                 land_subtype=land_subtype)
            if not rule:
                continue
            limit = rule.get("limit_max") or rule.get("limit")
            if not limit or limit <= 0:
                continue
            ratio = float(value) / float(limit)
            if ratio > 1:
                exceed_ratios.append(ratio)
                threshold_notes.append(rule.get("raw") or f"≤{limit}mg/kg")
        if not exceed_ratios:
            continue
        affected_fraction = len(exceed_ratios) / len(vals)
        max_exceedance = max(exceed_ratios)
        mean_exceedance = sum(exceed_ratios) / len(exceed_ratios)
        severity = (max_exceedance - 1.0) * 0.8 + affected_fraction * 0.2
        factors.append({
            "feature": factor,
            "factor_code": factor,
            "mean_abs_shap": round(max(severity, 0.001), 6),
            "direction": "positive",
            "source": "threshold_exceedance_rule",
            "category": "环境指标",
            "mean_value": round(float(vals.mean()), 4),
            "diagnostic_value": round(max_exceedance, 4),
            "affected_fraction": round(affected_fraction, 4),
            "threshold": threshold_notes[0] if threshold_notes else None,
            "note": (f"实测浓度超过标准阈值: 最大超标 {max_exceedance:.2f} 倍, "
                     f"超标点位占比 {affected_fraction:.1%}, "
                     f"超标点平均倍数 {mean_exceedance:.2f}。"),
        })
    return sorted(factors, key=lambda x: x["mean_abs_shap"], reverse=True)


def ensure_model_record(db: Session, bundle: dict) -> MLModel:
    m = (db.query(MLModel)
         .filter_by(model_name=bundle["model_name"], version=bundle["version"]).first())
    if m is None:
        m = MLModel(model_name=bundle["model_name"], version=bundle["version"],
                    algorithm=bundle["algorithm"], feature_list=bundle["feature_list"],
                    training_data_version=bundle["data_version"],
                    metrics=bundle["metrics"], artifact_path=bundle.get("artifact_path"))
        db.add(m)
        db.flush()
    return m


def run_diagnosis(db: Session, site_id: int, top_n: int = 10) -> dict:
    from rf_barrier import load_latest, train  # ml/models
    from shap_service import explain  # ml/explain

    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"场地不存在: {site_id}")
    pivot = pivot_site_measurements(db, site_id)
    if pivot.empty:
        raise ValueError("该场地无检测数据, 请先导入")

    # 双轨路由(2026-06-24 Wave): 按修复后用途选生产(严)/生态(宽)模型
    _track_map = {"生产": "prod", "生态": "eco"}
    track = _track_map.get(getattr(site, "land_use_type", None))
    bundle = load_latest(track=track)
    if bundle is None:
        train()  # 首次自动训练
        bundle = load_latest(track=track)
    model = bundle["model"]
    mapping = load_feature_mapping()
    X, imputed = align_features(pivot, bundle["feature_list"],
                                bundle["medians"], mapping)

    proba = model.predict_proba(X)[:, 1]
    shap_out = explain(model, X)

    # 反向映射: 训练特征 -> 因子中文名
    feat2factor = feature_to_factor_mapping(mapping, bundle["feature_list"])
    fd_by_code = {f.factor_code: f for f in db.query(FactorDictionary).all()}
    sp_by_code = {p.point_code: p for p in
                  db.query(SamplingPoint).filter_by(site_id=site_id).all()}

    # 仅对"有实测数据"的特征参与 Top-N 排名(填充特征不进结论, 诚实原则)
    measured_feats = {f for f in bundle["feature_list"]
                      if f not in imputed and not f.endswith("__missing")}
    shap_ranked = [dict(g, factor_code=feat2factor.get(g["feature"]),
                        source="rf_shap")
                   for g in shap_out["global"] if g["feature"] in measured_feats]
    exceedance_ranked = pollutant_exceedance_factors(pivot)
    rule_ranked = production_limiting_factors(pivot)
    ranked_all = sorted(shap_ranked + exceedance_ranked + rule_ranked,
                        key=lambda x: x["mean_abs_shap"], reverse=True)
    ranked = []
    seen_factors: set[str] = set()
    for item in ranked_all:
        fcode = item.get("factor_code") or feat2factor.get(item["feature"], item["feature"])
        if fcode in seen_factors:
            continue
        seen_factors.add(fcode)
        ranked.append(item)
        if len(ranked) >= top_n:
            break

    model_rec = ensure_model_record(db, bundle)
    summary = (
        f"基于 RF({bundle['version']}) + SHAP 对 {len(X)} 个采样点分析: "
        f"高风险概率均值 {float(proba.mean()):.2f}。"
        f"Top{len(ranked)} 关键障碍因子(按全局|SHAP|): "
        + ", ".join(g.get("factor_code") or feat2factor.get(g['feature'], g['feature'])
                    for g in ranked)
        + "。注: 训练特征中 "
        + (f"{len(imputed)} 项在本场地无实测(以训练中位数填充, 未参与结论排名)。"
           if imputed else "全部有实测。"))

    calc_trace = [
        f"① 取场地长表透视为 {len(X)} 个采样点 × {len(bundle['feature_list'])} 特征矩阵。",
        f"② 特征对齐: 场地实测因子映射到训练特征; {len(imputed)} 项无实测者以训练集中位数填充并标记(不参与结论排名)。",
        f"③ 加载 RF 模型 {bundle['version']}(训练集 {bundle.get('data_version')}, AUC={bundle['metrics'].get('auc')}, F1={bundle['metrics'].get('f1')})对各点预测高风险概率, 均值 {float(proba.mean()):.4f}。",
        "④ TreeExplainer 计算 SHAP 值, 全局重要性=各特征 |SHAP| 跨样本均值。",
        "⑤ 仅在有实测数据的特征中按 |SHAP| 降序取 RF Top, 同时叠加生产阈值短板筛查(规则项不冒充 SHAP): "
        + ", ".join(
            f"{g.get('factor_code') or feat2factor.get(g['feature'], g['feature'])}"
            f"({g.get('source', 'rf_shap')}={round(g['mean_abs_shap'], 4)})"
            for g in ranked[:5])
        + ("…" if len(ranked) > 5 else "") + "。",
        f"⑥ 局部解释取风险概率最高采样点, SHAP 值绑定该样本入库, 全程可追溯到检测值。",
    ]
    diag = DiagnosisResult(
        site_id=site_id, model_id=model_rec.id,
        data_version=current_site_data_version(db, site_id),
        top_n=top_n, summary=summary,
        shap_global={"global": shap_out["global"],
                     "imputed_features": imputed,
                     "risk_proba_mean": float(proba.mean()),
                     "calculation_trace": calc_trace},
        status="done")
    db.add(diag)
    db.flush()

    # 全局明细
    for rank, g in enumerate(ranked, 1):
        fcode = g.get("factor_code") or feat2factor.get(g["feature"])
        fd = fd_by_code.get(fcode)
        if fd is None:
            continue
        db.add(DiagnosisFactorDetail(
            diagnosis_id=diag.id, factor_id=fd.id, sampling_point_id=None,
            importance=g["mean_abs_shap"], shap_value=g["mean_abs_shap"],
            direction=g["direction"], rank=rank))
    # 局部解释: 风险概率最高的采样点
    worst_i = int(proba.argmax())
    worst_code = str(X.index[worst_i])
    sp = sp_by_code.get(worst_code)
    for item in shap_out["local"].get(worst_i, [])[:top_n]:
        fcode = feat2factor.get(item["feature"])
        fd = fd_by_code.get(fcode)
        if fd is None or sp is None:
            continue
        db.add(DiagnosisFactorDetail(
            diagnosis_id=diag.id, factor_id=fd.id, sampling_point_id=sp.id,
            importance=abs(item["shap_value"]), shap_value=item["shap_value"],
            direction="positive" if item["shap_value"] >= 0 else "negative",
            rank=None))
    db.commit()
    return {
        "diagnosis_id": diag.id, "site_id": site_id,
        "model_version": bundle["version"], "model_metrics": bundle["metrics"],
        "data_version": diag.data_version, "n_points": len(X),
        "risk_proba_mean": round(float(proba.mean()), 4),
        "worst_point": worst_code,
        "top_factors": [{
            "rank": i + 1,
            "factor": g.get("factor_code") or feat2factor.get(g["feature"], g["feature"]),
            "feature": g["feature"],
            "importance": g["mean_abs_shap"],
            "direction": g["direction"],
            "category": (g.get("category") or
                         (fd_by_code.get(g.get("factor_code") or feat2factor.get(g["feature"]))
                          .level1_category if fd_by_code.get(g.get("factor_code") or feat2factor.get(g["feature"])) else None)),
            "source": g.get("source", "rf_shap"),
            "mean_value": g.get("mean_value"),
            "diagnostic_value": g.get("diagnostic_value"),
            "affected_fraction": g.get("affected_fraction"),
            "threshold": g.get("threshold"),
            "note": g.get("note"),
        } for i, g in enumerate(ranked)],
        "imputed_features": imputed,
        "calculation_trace": calc_trace,
        "summary": summary,
    }
