"""zzv0.4 P2-3: 反事实解释 → 修复行动建议。

文献依据:
- [#24 Wachter et al. 2017]: 反事实解释, "如果想让某因子不再进入top-3, 应改变什么"
- [#44 AHP-TOPSIS植物筛选], [#50 可持续修复], [#51 纳米修复]: 修复技术库映射
裴总报告1第145行: 反事实把障碍因子转成行动建议
"""
from __future__ import annotations
import numpy as np
import pandas as pd


# 障碍因子 → 修复技术映射(锚定技术库, 文献[#44,#50,#51])
FACTOR_REMEDIATION_MAP = {
    "Cd_mgkg": {"技术": "植物提取(超富集植物如伴矿景天)", "方向": "降低镉生物有效性",
                "参考": "[#44 AHP-TOPSIS植物筛选]"},
    "Pb_mgkg": {"技术": "固化/稳定化(磷酸盐/生物炭)", "方向": "降低铅迁移性",
                "参考": "[#50 可持续修复]"},
    "As_mgkg": {"技术": "土壤淋洗/铁氧化物固定", "方向": "降低砷生物有效性",
                "参考": "[#51 纳米修复农地]"},
    "Cr_mgkg": {"技术": "还原稳定化(硫酸亚铁/有机质)", "方向": "Cr(VI)→Cr(III)降毒",
                "参考": "[#50]"},
    "Hg_mgkg": {"技术": "热脱附/固化稳定化", "方向": "降低汞挥发与生物累积",
                "参考": "[#50]"},
    "Cu_mgkg": {"技术": "植物修复/有机质改良", "方向": "降低铜植物毒性",
                "参考": "[#44]"},
    "Zn_mgkg": {"技术": "植物富集/石灰调节pH", "方向": "降低锌有效性",
                "参考": "[#44]"},
    "Ni_mgkg": {"技术": "pH调节/有机质固定", "方向": "降低镍生物有效性",
                "参考": "[#50]"},
    "Sum_PAH_ngg": {"技术": "微生物降解(白腐菌)/植物修复", "方向": "PAH矿化降解",
                    "参考": "[#52生态修复]"},
    "BaP_ngg": {"技术": "强化生物降解/化学氧化", "方向": "高环PAH靶向降解",
                "参考": "[#52]"},
    "SumDDTs_ngg": {"技术": "化学还原/生物降解", "方向": "DDT脱氯降解",
                    "参考": "[#51]"},
    "SumPCB_ngg": {"技术": "化学脱氯/生物修复", "方向": "PCB脱氯减毒",
                   "参考": "[#51]"},
}


def counterfactual_factor(model, X_sample: pd.Series, feature: str,
                          target_reduction: float = 0.5) -> dict:
    """反事实: 要让该因子的SHAP贡献降低, 特征值应降到多少(文献[#24])。
    target_reduction: 目标降低比例(0.5=降到阈值以下)。"""
    val = X_sample.get(feature)
    if val is None or pd.isna(val):
        return {"feature": feature, "note": "该因子无实测值, 无法反事实"}
    # 简化: 找到让预测概率下降的目标值(二分搜索)
    original_proba = float(model.predict_proba(pd.DataFrame([X_sample]))[0, 1])
    lo, hi = 0.0, float(val)
    target_proba = original_proba * (1 - target_reduction)
    best_val = float(val)
    for _ in range(20):
        mid = (lo + hi) / 2
        X_test = X_sample.copy()
        X_test[feature] = mid
        try:
            proba = float(model.predict_proba(pd.DataFrame([X_test]))[0, 1])
        except Exception:
            break
        if proba <= target_proba:
            best_val = mid
            lo = mid
        else:
            hi = mid
    remediation = FACTOR_REMEDIATION_MAP.get(feature, {"技术": "需专家评估", "方向": "—", "参考": "—"})
    return {
        "feature": feature,
        "current_value": round(float(val), 4),
        "counterfactual_value": round(best_val, 4),
        "reduction_needed_pct": round((1 - best_val / float(val)) * 100, 1) if float(val) > 0 else 0,
        "predicted_proba_original": round(original_proba, 4),
        "predicted_proba_target": round(target_proba, 4),
        "remediation": remediation,
        "note": f"若将{feature}从{val:.2f}降至{best_val:.2f}(降幅{(1-best_val/float(val))*100:.0f}%), "
                f"障碍概率可从{original_proba:.3f}降至约{target_proba:.3f}。"
                f"建议技术: {remediation['技术']}",
    }


def generate_remediation_advice(model, X_sample: pd.Series, top_factors: list[dict]) -> list[dict]:
    """对top障碍因子生成反事实+修复建议(文献[#24]+[#44,#50,#51])。"""
    advice = []
    for f in top_factors[:3]:  # top-3因子给修复建议
        feature = f.get("factor_code") or f.get("feature")
        if feature:
            advice.append(counterfactual_factor(model, X_sample, feature))
    return advice
