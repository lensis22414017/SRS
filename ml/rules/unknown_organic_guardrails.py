import sys
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
unknown_organic_guardrails.py — 未知有机物三道防线
====================================================================
防线1: 正式 KOS 排名只认 实测+有阈值+训练见过+B=1
防线2: 族群异常预警(未知单体归族群,总量超阈值报警)
防线3: TEF 毒性当量降级(证据降为C)
====================================================================
"""
import os
import math
import pandas as pd
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# PyInstaller 打包后数据在 _MEIPASS 或其 _internal 子目录
if getattr(sys, "frozen", False):
    _mep = sys._MEIPASS
    if os.path.isdir(os.path.join(_mep, "ml")) or os.path.isdir(os.path.join(_mep, "data")):
        ROOT = _mep
    elif os.path.isdir(os.path.join(_mep, "_internal", "ml")):
        ROOT = os.path.join(_mep, "_internal")

# 族群映射规则 (简化版,基于知识库 V1.0 的族群结构)
FAMILY_MAP = {
    "PAH": ["萘", "苊", "芴", "菲", "蒽", "荧蒽", "芘", "苯并[a]蒽", "屈", "苯并[b]荧蒽",
            "苯并[k]荧蒽", "苯并[a]芘", "二苯并[a,h]蒽", "苯并[g,h,i]苝", "茚并[1,2,3-cd]芘",
            "苝", "PAH", "pah", "苯并", "蒽", "芘", "菲", "荧", "nap", "ace", "flu", "phe", "ant", "flt", "pyr", "baa", "chr", "bbf", "bkf", "bap", "dahA", "ind", "bghiP"],
    "OCP": ["HCH", "DDT", "氯丹", "七氯", "毒杀芬", "六氯苯", "灭蚁灵", "OCP", "ocp", "六六六", "滴滴"],
    "PCB": ["PCB", "pcb", "多氯联苯", "联苯"],
    "PBDE": ["PBDE", "pbde", "多溴联苯醚", "BDE"],
    "PFAS": ["PFAS", "pfas", "全氟", "PFOA", "PFOS"],
    "PAE": ["PAE", "pae", "邻苯二甲酸", "DBP", "DEHP", "DMP", "DEP"],
    "TPH": ["TPH", "tph", "石油烃", "矿物油", "总石油"],
    "烷烃": ["烷", "二十烷", "十六烷", "十七烷", "十九烷", "二十四烷", "二十七烷"],
    "萜烯": ["蒎烯", "戊烯", "萜"],
    "酮酯": ["酮", "酯", "丁酯", "酰胺", "脲"],
}

# 族群阈值 (mg/kg,简化;实际应从阈值库读)
FAMILY_THRESHOLDS = {
    "PAH": 10.0, "OCP": 0.5, "PCB": 0.5, "PBDE": 1.0, "PFAS": 0.1, "PAE": 10.0, "TPH": 1000.0,
    "烷烃": None, "萜烯": None, "酮酯": None,  # 无国标阈值
}

# TEF (BaP 毒性当量因子, EPA)
PAH_TEF = {
    "萘": 0.001, "苊烯": 0.001, "苊": 0.001, "芴": 0.001, "菲": 0.001, "蒽": 0.01,
    "荧蒽": 0.08, "芘": 0.001, "苯并[a]蒽": 0.1, "屈": 0.1, "苯并[b]荧蒽": 0.1,
    "苯并[k]荧蒽": 0.1, "苯并[a]芘": 1.0, "二苯并[a,h]蒽": 1.0, "苯并[g,h,i]苝": 0.01, "茚并[1,2,3-cd]芘": 0.1,
}


def classify_pollutant(name: str) -> tuple[str, bool]:
    """把污染物名归到族群。返回 (族群名, 是否已知)"""
    for fam, kws in FAMILY_MAP.items():
        for kw in kws:
            if kw in name:
                return fam, True
    return "未知族群", False


def guardrail_check(factor_values: dict, known_factors: set) -> dict:
    """三道防线检查。
    factor_values: {污染物名: 浓度}
    known_factors: 训练集/阈值库已知因子集合
    """
    formal_ranked = []     # 防线1: 已知有阈值的
    family_warnings = []   # 防线2: 族群异常预警
    tef_estimates = []     # 防线3: TEF 降级
    unknown_substances = []  # 完全未知

    for name, conc in factor_values.items():
        if conc is None or (isinstance(conc, float) and math.isnan(conc)) or conc <= 0:
            continue
        family, is_known_family = classify_pollutant(name)
        is_in_kb = name in known_factors

        if is_in_kb:
            # 防线1: 已知,走正式 KOS
            formal_ranked.append({"name": name, "value": conc, "family": family, "guardrail": "formal"})
        elif is_known_family:
            # 防线2: 族群内未知单体
            thr = FAMILY_THRESHOLDS.get(family)
            if thr is not None:
                family_warnings.append({
                    "name": name, "value": conc, "family": family,
                    "family_threshold": thr,
                    "exceeds_family": conc > thr,
                    "guardrail": "family_warning",
                    "note": f"{family} 族群未收录单体,浓度={conc},族群阈值={thr}",
                })
            else:
                family_warnings.append({
                    "name": name, "value": conc, "family": family,
                    "family_threshold": None,
                    "exceeds_family": None,
                    "guardrail": "family_warning",
                    "note": f"{family} 族群无国标阈值,无法判障碍,建议送检鉴定",
                })
            # 防线3: PAH 族群用 TEF
            if family == "PAH":
                base_name = name.split("(")[0].split("mg")[0].strip()
                # 模糊匹配 TEF
                for pahtef, tef in PAH_TEF.items():
                    if pahtef in name or name in pahtef:
                        bap_eq = conc * tef
                        tef_estimates.append({
                            "name": name, "value": conc, "tef": tef,
                            "bap_equivalent": round(bap_eq, 6),
                            "evidence_downgraded_to": "C",
                            "guardrail": "tef_estimate",
                            "note": f"基于 BaP-TEF 估算,证据等级降为 C",
                        })
                        break
        else:
            # 完全未知
            unknown_substances.append({
                "name": name, "value": conc, "family": "未知",
                "guardrail": "unknown",
                "note": "因子库/族群库/TEF 库均无收录,无法评估障碍风险,强烈建议送检毒性鉴定",
            })

    return {
        "formal_ranked": formal_ranked,
        "family_warnings": family_warnings,
        "tef_estimates": tef_estimates,
        "unknown_substances": unknown_substances,
        "summary": {
            "n_formal": len(formal_ranked),
            "n_family_warning": len(family_warnings),
            "n_tef": len(tef_estimates),
            "n_unknown": len(unknown_substances),
            "has_unknown_risk": len(family_warnings) + len(unknown_substances) > 0,
        },
    }


def selftest():
    """用南京栖霞 32 种有机物做三道防线测试"""
    print("=" * 60)
    print("未知有机物三道防线自测 (南京栖霞数据)")
    print("=" * 60)
    nj_path = os.path.join(os.path.dirname(ROOT), "000", "数据集", "3.实际样本集",
                           "2.20250731_有机污染场地数据表(南京栖霞)_完整版.xlsx")
    if not os.path.exists(nj_path):
        print(f"⚠️ 南京数据不存在: {nj_path},用模拟数据")
        factor_values = {"1,2-二氯苯": 34.9, "2-蒎烯": 79.9, "二十烷": 0.4, "苯并[a]芘": 0.5, "未知物X": 1.2}
        known_factors = {"1,2-二氯苯", "苯并[a]芘"}
    else:
        nj = pd.read_excel(nj_path, sheet_name="南京栖霞完整数据")
        factor_values = {}
        for c in nj.columns:
            if "(mg/kg)" in c:
                base = c.replace("(mg/kg)", "").strip()
                vals = pd.to_numeric(nj[c], errors="coerce").dropna()
                if len(vals) > 0:
                    factor_values[base] = float(vals.max())
        # 知识库已知(简化)
        known_factors = {"1,2-二氯苯", "四氯乙烯", "二氯甲烷", "氯仿", "苯并[a]芘", "苯并[k]荧蒽", "荧蒽", "蒽", "芘", "屈"}

    result = guardrail_check(factor_values, known_factors)
    print(f"\n防线1 正式排名(已知有阈值): {result['summary']['n_formal']} 个")
    for f in result["formal_ranked"][:5]:
        print(f"  {f['name']}: {f['value']} ({f['family']})")
    print(f"\n防线2 族群异常预警: {result['summary']['n_family_warning']} 个")
    for f in result["family_warnings"][:8]:
        print(f"  {f['name']}: {f['value']} → {f['note']}")
    print(f"\n防线3 TEF 降级估算: {result['summary']['n_tef']} 个")
    for f in result["tef_estimates"][:3]:
        print(f"  {f['name']}: BaP当量={f['bap_equivalent']}")
    print(f"\n完全未知: {result['summary']['n_unknown']} 个")
    for f in result["unknown_substances"][:5]:
        print(f"  {f['name']}: {f['value']} → {f['note']}")

    out = "artifacts/overnight_20260703/unknown_organic_guardrails_report.csv"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rows = result["formal_ranked"] + result["family_warnings"] + result["tef_estimates"] + result["unknown_substances"]
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n报告: {out}")
    return result


if __name__ == "__main__":
    selftest()
