"""zzv0.4 P4-2/P4-3: 模型卡 + 数据卡 + OOD 检测。

文献依据:
- [#9 Mitchell et al. 2019] Model Cards: 模型文档(验证策略/局限/性能切片/使用边界)
- [#10 Gebru et al. 2018] Datasheets: 数据文档(来源/缺失/偏差/代表性)
- [#59 Novelty Detection] IsolationForest/LOF: OOD 检测
- [#8 Angelopoulos 2021] conformal: 分布无关覆盖保证
第147-164行: 审计证据链字段
"""
from __future__ import annotations
import json
import os
import numpy as np
import pandas as pd


def generate_model_card(model_meta: dict, validation_metrics: dict,
                        out_path: str) -> dict:
    """生成模型卡(文献[#9 Mitchell])。"""
    card = {
        "model_version": model_meta.get("version"),
        "model_name": model_meta.get("model_name", "rf_barrier_factor"),
        "algorithm": model_meta.get("algorithm"),
        "training_dataset_version": model_meta.get("data_version"),
        "feature_schema_hash": model_meta.get("feature_schema_hash"),
        "validation_strategy": model_meta.get("validation_strategy", "group_split"),
        "group_key": model_meta.get("group_key", "id_DOI"),
        "threshold_library_version": "GB15618-2018/GB36600-2018/HJ25.5-2018",
        "ood_policy": model_meta.get("ood_policy", "warn"),
        "human_review_policy": "触发条件见 P4-3(-261行): OOD/top1差值小/SHAP不稳定/缺失高/校准差/双轨一致",
        "performance": validation_metrics,
        "intended_use": "污染场地障碍因子诊断(因子归因, 非二分类预测)。用户上传实测浓度→RF+SHAP识别障碍因子。",
        "out_of_scope": [
            "不替代法规阈值判定(规则层先行)",
            "不在训练分布外场地做无人工复核的自动判定",
            "生态轨当前为proxy标签(规则派生, 非真实生态响应)",
        ],
        "limitations": [
            "GEE协变量非土壤层98.1%/土壤层70.5%覆盖, 缺失由树模型原生处理",
            "test AUC偏高含重金属标签相关性, CV(0泄漏)是更保守指标",
            "OP生态轨标签为规则派生proxy, 需后续真实生态响应数据校准",
        ],
        "reference": "docs/algorithms/task_definition.md + docs/references/障碍因子诊断_方法学综合报告.md",
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)
    return card


def generate_dataset_card(out_path: str) -> dict:
    """生成数据卡(文献[#10 Gebru])。"""
    card = {
        "dataset_name": "merged_std33_geocoded + GEE协变量",
        "version": "zzv0.4_cleaned_20260702",
        "n_samples": 27031,
        "n_features_raw": 720,
        "source": "全球土壤污染文献meta-merge (merged_std33) + GEE遥感协变量(MODIS/WorldClim/SRTM/SoilGrids)",
        "data_origin": "real(文献实测) + literature(文献汇总)",
        "geographic_coverage": "China 16463 / Nigeria 382 / India 319 / Poland 280 / 全球散点",
        "temporal_coverage": "文献采样年份跨度大, 未严格按年代分层",
        "missingness": {
            "理化列": "SoilpH 27.2% / OC 34.7% / CEC 28.3% / 质地~15% / SoilBD 2.3%",
            "GEE非土壤层": "98.1%覆盖",
            "GEE土壤层": "70.5%覆盖(SoilGrids高原区缺失)",
            "浓度列": "8重金属25-56%非空, 有机汇总<3%, 其余极稀疏",
        },
        "cleaning": "修正142离群值(125单位错误μg/kg误标mg/kg + 17矿区Winsorize)",
        "known_bias": [
            "中国数据占60%+, 地理代表性偏中国",
            "重金属(HM)样本占66%, 有机(OP)较少",
            "生态轨标签为规则proxy, 非真实生态响应",
        ],
        "label_definition": "GB15618(pH四段路由)+GB36600(一类/二类)阈值派生; severity=log2(val/thr)",
        "reference": "docs/algorithms/task_definition.md",
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(card, f, ensure_ascii=False, indent=2)
    return card


def compute_ood_score(X_train: pd.DataFrame, X_new: pd.DataFrame, method: str = "isolation_forest") -> np.ndarray:
    """OOD检测(文献[#59]): 对新样本算分布偏移分数。
    分数越高越异常(OOD)。"""
    from sklearn.ensemble import IsolationForest
    useful = [c for c in X_train.columns if not X_train[c].isna().all()]
    X_tr = X_train[useful].fillna(0)
    X_nw = X_new[useful].fillna(0) if all(c in X_new.columns for c in useful) else X_new[[c for c in useful if c in X_new.columns]].fillna(0)
    if method == "isolation_forest":
        iso = IsolationForest(random_state=42, contamination=0.1)
        iso.fit(X_tr)
        # decision_function: 越低越异常, 取反使越高越OOD
        scores = -iso.decision_function(X_nw)
    else:
        scores = np.zeros(len(X_nw))
    return scores


def should_trigger_human_review(ood_score: float, top1_shap: float, top2_shap: float,
                                shap_consistency: float, missing_rate: float,
                                data_origin: str, calibration_error: float,
                                dual_track_consistent: bool) -> tuple[bool, list[str]]:
    """人工复核触发政策(-261行, 7条)。返回 (是否触发, 原因列表)。"""
    reasons = []
    if ood_score > 0.3:
        reasons.append(f"OOD score {ood_score:.3f} 超阈值(分布外样本)")
    if abs(top1_shap - top2_shap) < 0.01:
        reasons.append(f"top-1与top-2障碍因子SHAP差值过小({abs(top1_shap-top2_shap):.4f})")
    if shap_consistency < 0.5:
        reasons.append(f"SHAP跨折排序不稳定(consistency={shap_consistency:.3f})")
    if missing_rate > 0.5:
        reasons.append(f"关键输入缺失率高({missing_rate:.1%})")
    if data_origin != "real":
        reasons.append(f"数据来源非real({data_origin})")
    if calibration_error > 0.1:
        reasons.append(f"模型校准误差过大({calibration_error:.3f})")
    if dual_track_consistent:
        reasons.append("生产轨与生态轨结果异常一致(红旗)")
    return (len(reasons) > 0, reasons)
