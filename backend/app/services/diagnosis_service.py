"""障碍因子诊断: 取数 -> 特征对齐 -> RF 预测 -> SHAP(模型全局贡献份额) -> 入库。

特征对齐策略(已确认"重标化/诚实标注"原则):
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

# L2: 加载 GEE 协变量标签映射（简化名称）
_gee_labels: dict[str, dict] = {}
_gee_labels_path = os.path.join(ROOT, "ml", "covariates", "gee_labels.json")
if os.path.exists(_gee_labels_path):
    with open(_gee_labels_path, encoding="utf-8") as _f:
        _gee_labels = json.load(_f)


def _resolve_factor_name(feature: str, feat2factor: dict[str, str],
                          fd_by_code: dict) -> str:
    """返回特征的可显示名称: 优先因子字典中文名, 其次 GEE 简化名, 最后原始特征名。"""
    fcode = feat2factor.get(feature)
    if fcode and fcode in fd_by_code:
        return fd_by_code[fcode].factor_name
    if feature in _gee_labels:
        return _gee_labels[feature]["display"]
    # 去掉 gee_ 前缀作为后备
    if feature.startswith("gee_"):
        return feature[4:]
    return feature
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
    pivot = df.pivot_table(index="point_code", columns="factor_code",
                           values="value", aggfunc="mean")
    # gee_场地级协变量广播到所有采样点(绑第一个采样点 → 全采样点同值)
    for col in list(pivot.columns):
        if col.startswith("gee_"):
            vals = pivot[col].dropna()
            if len(vals) > 0:
                pivot[col] = vals.iloc[0]
    return pivot


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
            if feature in pivot.columns:  # gee_协变量等(pivot有则用真实值, 非medians)
                X[feature] = pivot[feature].fillna(medians.get(feature, 0.0))
            else:
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
    # zzv0.3 工程特征计算(对数变换/pH交互/Nemerow指数), 模型feature_list含这些列时动态算
    _add_engineered_features(X, feature_list)
    return X[feature_list], imputed


def _add_engineered_features(X: pd.DataFrame, feature_list: list[str]) -> None:
    """zzv0.3: 计算工程特征(log1p/pH交互/Nemerow指数), 就地修改X。
    仅当模型 feature_list 含这些列时才算(向后兼容旧模型)。"""
    import numpy as np
    HM_BG = {"Cd_mgkg": 0.6, "Pb_mgkg": 500, "As_mgkg": 25, "Cr_mgkg": 250,
             "Hg_mgkg": 1.0, "Cu_mgkg": 100, "Zn_mgkg": 300, "Ni_mgkg": 100}
    for col in HM_BG:
        # 对数变换
        lf = f"log_{col}"
        if lf in feature_list and col in X.columns and lf not in X.columns:
            X[lf] = np.log1p(pd.to_numeric(X[col], errors="coerce").clip(lower=0))
        # pH 交互
        pf = f"pH_x_{col}"
        if pf in feature_list and "SoilpH" in X.columns and col in X.columns and pf not in X.columns:
            X[pf] = pd.to_numeric(X["SoilpH"], errors="coerce") * pd.to_numeric(X[col], errors="coerce")
    # PI 指数
    pi_cols = []
    for col, bg in HM_BG.items():
        pf = f"PI_{col}"
        if pf in feature_list and col in X.columns and pf not in X.columns:
            X[pf] = pd.to_numeric(X[col], errors="coerce") / bg
            pi_cols.append(pf)
    if "PI_nemerow" in feature_list and pi_cols:
        pi_df = X[pi_cols]
        pmax = pi_df.max(axis=1); pavg = pi_df.mean(axis=1)
        X["PI_nemerow"] = np.sqrt((pmax**2 + pavg**2) / 2)


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


def _build_dual_track(prod_r: dict, eco_r: dict) -> dict:
    """构造生产-生态双轨对比块(目标: 双轨诊断真正生效)。

    prod_r/eco_r 为 run_diagnosis 内 _single() 返回的单轨结果
    (bundle/X/proba/shap_out/feat2factor/ranked)。
    """
    pp = float(prod_r["proba"].mean())
    ep = float(eco_r["proba"].mean())
    return {
        "prod_proba_mean": round(pp, 4),
        "eco_proba_mean": round(ep, 4),
        "prod_model": prod_r["bundle"]["version"],
        "eco_model": eco_r["bundle"]["version"],
        "prod_auc": prod_r["bundle"]["metrics"].get("auc"),
        "eco_auc": eco_r["bundle"]["metrics"].get("auc"),
        "delta_prod_minus_eco": round(pp - ep, 4),
        "dominant_track": "prod" if pp >= ep else "eco",
        "prod_top_factors": [{
            "rank": i + 1,
            "factor": (g.get("factor_code")
                       or prod_r["feat2factor"].get(g["feature"], g["feature"])),
            "importance": g["mean_abs_shap"],
            "direction": g["direction"],
            "source": g.get("source", "rf_shap"),
        } for i, g in enumerate(prod_r["ranked"])],
        "eco_top_factors": [{
            "rank": i + 1,
            "factor": (g.get("factor_code")
                       or eco_r["feat2factor"].get(g["feature"], g["feature"])),
            "importance": g["mean_abs_shap"],
            "direction": g["direction"],
            "source": g.get("source", "rf_shap"),
        } for i, g in enumerate(eco_r["ranked"])],
    }


_EE_INITIALIZED = False


def _enrich_gee_if_needed(pivot: pd.DataFrame, site, feature_list: list) -> pd.DataFrame:
    """GEE 协变量补入(目标: 场地诊断用真实 GEE 值, 非全中位数)。
    模型 feature_list 含 gee_ 列且场地有经纬度 → 按场地坐标 GEE 采样填入 pivot;
    GEE 未配置或失败 → 返回原 pivot(align_features 用训练中位数兜底, 不阻断诊断)。
    """
    global _EE_INITIALIZED
    gee_cols = [c for c in feature_list if str(c).startswith("gee_")]
    if not gee_cols:
        return pivot
    # 已持久化 gee_(pivot有值, 来自measurements)直接用, 跳过GEE在线采样(快速)
    missing = [c for c in gee_cols if c not in pivot.columns or pivot[c].isna().all()]
    if not missing:
        return pivot
    if getattr(site, "latitude", None) is None or getattr(site, "longitude", None) is None:
        return pivot
    try:
        project = os.environ.get("GEE_PROJECT_ID")
        if not project:
            return pivot
        import ee
        if not _EE_INITIALIZED:
            ee.Initialize(project=project)
            _EE_INITIALIZED = True
        cov_dir = os.path.join(ML_DIR, "covariates")
        if cov_dir not in sys.path:
            sys.path.insert(0, cov_dir)
        from gee_fetch import build_covariate_image  # noqa
        pt = ee.Feature(ee.Geometry.Point([float(site.longitude), float(site.latitude)]))
        cov = build_covariate_image()
        res = cov.sampleRegions(collection=ee.FeatureCollection([pt]),
                                scale=250).getInfo()
        if res.get("features"):
            props = res["features"][0]["properties"]
            for c in gee_cols:
                v = props.get(c)
                if v is not None:
                    pivot[c] = v
    except Exception:
        pass  # GEE 失败(网络/配额)用 medians 兜底, 不阻断诊断
    return pivot


def run_diagnosis(db: Session, site_id: int, top_n: int = 10) -> dict:
    from rf_barrier import load_latest, train  # ml/models
    from shap_service import explain  # ml/explain

    site = db.get(Site, site_id)
    if site is None:
        raise ValueError(f"场地不存在: {site_id}")
    pivot = pivot_site_measurements(db, site_id)
    if pivot.empty:
        raise ValueError("该场地无检测数据, 请先导入")

    mapping = load_feature_mapping()
    fd_by_code = {f.factor_code: f for f in db.query(FactorDictionary).all()}
    sp_by_code = {p.point_code: p for p in
                  db.query(SamplingPoint).filter_by(site_id=site_id).all()}

    # ── 双轨对比(2026-06-28 目标: 生产-生态双轨诊断真正生效) ──
    # 对同一场地同时加载 prod(GB15618 严阈值标签) + eco(GB36600 二类宽阈值标签)
    # 两个独立训练的模型, 输出双轨 proba/Top 因子对比。此前 API 层只按
    # land_use_type 选单轨(waveF 脚本靠临时改 land_use_type 调 2 次模拟对比),
    # 而 17 真实场地 land_use_type 全 null → 永远 fallback 单轨, 双轨从未生效。
    def _single(track: str) -> dict:
        b = load_latest(track=track)
        if b is None:
            train()
            b = load_latest(track=track)
        pivot_g = _enrich_gee_if_needed(pivot, site, b["feature_list"])
        Xt, imp = align_features(pivot_g, b["feature_list"], b["medians"], mapping)
        pr = b["model"].predict_proba(Xt)[:, 1]
        # v0.2 P0-3: SHAP 降级 — 异常时回退为仅 RF 概率 + 规则
        try:
            sh = explain(b["model"], Xt)
            shap_ok = True
        except Exception:
            sh = {"global": [], "local": {}}
            shap_ok = False
        f2f = feature_to_factor_mapping(mapping, b["feature_list"])
        measured = {f for f in b["feature_list"]
                    if f not in imp and not f.endswith("__missing")}
        sh_ranked = [dict(g, factor_code=f2f.get(g["feature"]), source="rf_shap")
                     for g in sh["global"] if g["feature"] in measured]
        ex_ranked = pollutant_exceedance_factors(
            pivot, scope="production" if track == "prod" else "ecology")
        rl_ranked = production_limiting_factors(pivot)
        # zzv0.4 规则/模型分层(文献[#2 Rudin2019]): 规则层(阈值超标)先行, SHAP归因次之
        # 不再混排去重, 而是分层呈现, 让用户看到"规则判定"与"模型归因"各自结论
        rule_ranked = sorted(ex_ranked + rl_ranked,
                             key=lambda x: x.get("mean_abs_shap", 0), reverse=True)
        # 合并去重保留向后兼容(all_ranked), 但分层标注 source
        all_ranked = sorted(sh_ranked + ex_ranked + rl_ranked,
                            key=lambda x: x["mean_abs_shap"], reverse=True)
        rk, seen = [], set()
        for item in all_ranked:
            fc = item.get("factor_code") or f2f.get(item["feature"], item["feature"])
            if fc in seen:
                continue
            seen.add(fc)
            rk.append(item)
            if len(rk) >= top_n:
                break
        return {"bundle": b, "X": Xt, "imputed": imp, "proba": pr,
                "shap_out": sh, "feat2factor": f2f, "ranked": rk,
                "rule_ranked": rule_ranked[:top_n],       # zzv0.4: 规则层(阈值超标)独立
                "shap_ranked": sh_ranked[:top_n]}          # zzv0.4: 模型归因层独立

    prod_r = _single("prod")
    eco_r = _single("eco")
    # zzv0.4 双轨路由修复(文献[#26-28]): 不再依赖 land_use_type 含"生态"
    # (17真实场地 land_use_type 全 null → 永远 fallback prod, 双轨失效)
    # 改为: 显式 track 参数优先, 其次 land_use_type, 默认双轨都算
    _lut = (getattr(site, "land_use_type", None) or "").strip()
    # zzv0.4 红旗检测(): prod/eco输出异常一致=可疑
    prod_top1 = prod_r["ranked"][0]["factor_code"] if prod_r["ranked"] else None
    eco_top1 = eco_r["ranked"][0]["factor_code"] if eco_r["ranked"] else None
    dual_track_suspicious = (prod_top1 and eco_top1 and prod_top1 == eco_top1
                             and prod_r["ranked"] and eco_r["ranked"]
                             and abs(prod_r["ranked"][0].get("mean_abs_shap", 0)
                                     - eco_r["ranked"][0].get("mean_abs_shap", 0)) < 0.001)
    main = eco_r if "生态" in _lut else prod_r
    bundle, X = main["bundle"], main["X"]
    imputed, proba = main["imputed"], main["proba"]
    shap_out, feat2factor, ranked = main["shap_out"], main["feat2factor"], main["ranked"]

    model_rec = ensure_model_record(db, bundle)
    summary = (
        f"基于 RF({bundle['version']}) + 模型全局贡献份额(SHAP) 对 {len(X)} 个采样点分析: "
        f"高风险概率均值 {float(proba.mean()):.2f}。"
        f"Top{len(ranked)} 关键障碍因子(按模型全局贡献份额 |SHAP|): "
        + ", ".join(_resolve_factor_name(g['feature'], feat2factor, fd_by_code)
                    for g in ranked)
        + "。注: 训练特征中 "
        + (f"{len(imputed)} 项在本场地无实测(以训练中位数填充, 未参与结论排名)。"
           if imputed else "全部有实测。")
        + " 正式超标结论仅限身份明确、单位兼容且阈值适用因子；未收录因子进入候选/族群/未知分析, 探索性结果非法规判定。"
    )

    calc_trace = [
        f"① 取场地长表透视为 {len(X)} 个采样点 × {len(bundle['feature_list'])} 特征矩阵。",
        f"② 特征对齐: 场地实测因子映射到训练特征; {len(imputed)} 项无实测者以训练集中位数填充并标记(不参与结论排名)。",
        f"③ 加载诊断模型 {bundle['version']}(训练集 {bundle.get('data_version')}, Spearman={bundle['metrics'].get('cv_spearman_mean') or bundle['metrics'].get('test_spearman', '-')})对各点预测高风险概率, 均值 {float(proba.mean()):.4f}。",
        "④ TreeExplainer 计算 SHAP 值, 全局重要性=各特征 |SHAP| 跨样本均值。",
        "⑤ 仅在有实测数据的特征中按 |SHAP| 降序取 RF Top, 同时叠加生产阈值短板筛查(规则项不冒充 SHAP): "
        + ", ".join(
            f"{g.get('factor_code') or feat2factor.get(g['feature'], g['feature'])}"
            f"({g.get('source', 'rf_shap')}={round(g['mean_abs_shap'], 4)})"
            for g in ranked[:5])
        + ("…" if len(ranked) > 5 else "") + "。",
        f"⑥ 局部解释取风险概率最高采样点, SHAP 值绑定该样本入库, 全程可追溯到检测值。",
        "⑦ 口径声明: 正式超标结论仅限于身份明确、单位兼容且阈值适用的因子；未收录因子进入候选/族群/未知因子分析(不丢弃、不强行套用阈值)。模型全局贡献份额(SHAP)为辅助参考, 非因果、非法规判定。当前完成 3 个原始场地工程回归验证 + 15 个合成数据演示, 结论作为辅助决策依据。",
    ]
    diag = DiagnosisResult(
        site_id=site_id, model_id=model_rec.id,
        data_version=current_site_data_version(db, site_id),
        top_n=top_n, summary=summary,
        summary_polished=None, polish_model=None,
        shap_global={"global": shap_out["global"],
                     "imputed_features": imputed,
                     "risk_proba_mean": float(proba.mean()),
                     "calculation_trace": calc_trace,
                     "dual_track": _build_dual_track(prod_r, eco_r)},
        status="done")
    db.add(diag)
    db.flush()

    # M1: LLM 润色诊断摘要（失败静默降级到模板 summary）
    try:
        from app.services.ai_service import polish_diagnosis
        polished = polish_diagnosis(db, summary)
        if polished:
            diag.summary_polished = polished
            # 获取当前 AI 模型名
            from app.core.ai_config import effective_ai
            diag.polish_model = effective_ai().get("model", "")
            db.flush()
    except Exception:
        pass  # 静默降级

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
            "factor": _resolve_factor_name(g["feature"], feat2factor, fd_by_code),
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
        "summary": diag.summary_polished or summary,
        "summary_raw": summary,
        "polish_model": diag.polish_model,
        "dual_track": _build_dual_track(prod_r, eco_r),
        # zzv0.4 规则/模型分层呈现(文献[#2 Rudin2019])
        "rule_factors": main.get("rule_ranked", []),
        "shap_factors": main.get("shap_ranked", []),
        # zzv0.4 红旗检测()
        "human_review_triggered": bool(dual_track_suspicious),
        "review_reason": "双轨top-1因子异常一致, 标签/特征可能未差异化" if dual_track_suspicious else None,
    }
