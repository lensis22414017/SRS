"""v1.1 (C3): 修复后利用方向决策引擎 — 法规安全门禁 + 功能评分。

设计原则(任务书 / 李老师 7-30 意见 C3):
  1. 法规安全门禁不可被任何评分抵消: 生产轨道按 GB 15618-2018, 生态轨道按 GB 36600-2018。
  2. 证据缺失永不视为通过: 必测项目缺测、阈值缺失、pH 未知导致无法判定 → "insufficient"。
  3. 修复前(pre_remediation)只给"修复目标/情景"结论, 不给修复后利用结论。
  4. 生态用地类别未指定 → 按第一类用地(最严)评价, 并在 assumptions 中注明。
  5. 农用地类型未指定 → 筛选值取水田/其他中较严者; 判"超管制值"取 pH 分档中最宽者(只在确定时判失败)。

门禁状态: pass / conditional / fail / insufficient
  生产 conditional = 筛选值 < C ≤ 管制值(安全利用类, 须采取安全利用措施)
  生态 conditional = 筛选值 < C ≤ 管制值(须开展详细风险评估, 评估前不支持利用)

决策状态(5 类): production_supported / ecology_supported / both_supported /
                 neither_supported / insufficient_evidence
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from typing import Any

METHOD_VERSION = "utilization_v1.1.0"
METHOD_STATUS = "provisional"  # 方法口径待陈亮/伟杰确认(methodology_questions 第 16 条)

PRE = "pre_remediation"
POST = "post_remediation"

GB15618_REQUIRED = ["Cd", "Hg", "As", "Pb", "Cr", "Cu", "Ni", "Zn"]  # 4.1.1 基本项目(必测)

# GB 36600-2018 表1 基本项目 45 项(名称; 阈值来自 gb36600_2018_v12.csv, 缺阈值的项目无法判定)
GB36600_BASIC_METALS = ["As", "Cd", "Cr(VI)", "Cu", "Pb", "Hg", "Ni"]
GB36600_BASIC_VOC = [
    "四氯化碳", "氯仿", "氯甲烷", "1,1-二氯乙烷", "1,2-二氯乙烷", "1,1-二氯乙烯", "顺-1,2-二氯乙烯",
    "反-1,2-二氯乙烯", "二氯甲烷", "1,2-二氯丙烷", "1,1,1,2-四氯乙烷", "1,1,2,2-四氯乙烷", "四氯乙烯",
    "1,1,1-三氯乙烷", "1,1,2-三氯乙烷", "三氯乙烯", "1,2,3-三氯丙烷", "氯乙烯", "苯", "氯苯",
    "1,2-二氯苯", "1,4-二氯苯", "乙苯", "苯乙烯", "甲苯", "间二甲苯+对二甲苯", "邻二甲苯",
]
GB36600_BASIC_SVOC = [
    "硝基苯", "苯胺", "2-氯酚", "苯并[a]蒽", "苯并[a]芘", "苯并[b]荧蒽", "苯并[k]荧蒽", "䓛",
    "二苯并[a,h]蒽", "茚并[1,2,3-cd]芘", "萘",
]
GB36600_BASIC = GB36600_BASIC_METALS + GB36600_BASIC_VOC + GB36600_BASIC_SVOC
assert len(GB36600_BASIC) == 45

_PH_BINS = [("pH<=5.5", None, 5.5), ("5.5<pH<=6.5", 5.5, 6.5), ("6.5<pH<=7.5", 6.5, 7.5), ("pH>7.5", 7.5, None)]

_ALIASES = {
    "镉": "Cd", "汞": "Hg", "砷": "As", "铅": "Pb", "铬": "Cr", "总铬": "Cr", "铜": "Cu", "镍": "Ni", "锌": "Zn",
    "六价铬": "Cr(VI)", "铬(六价)": "Cr(VI)", "cr6+": "Cr(VI)", "cr(vi)": "Cr(VI)",
    "cd_mgkg": "Cd", "hg_mgkg": "Hg", "as_mgkg": "As", "pb_mgkg": "Pb", "cr_mgkg": "Cr",
    "cu_mgkg": "Cu", "ni_mgkg": "Ni", "zn_mgkg": "Zn",
    "苯并芘": "苯并[a]芘", "bap": "苯并[a]芘",
}


def _norm(name: str) -> str:
    s = str(name or "").strip()
    s = s.replace("（", "(").replace("）", ")").replace("，", ",").replace("－", "-").replace("‘", "'")
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"\(mg/kg\)|mg/kg$", "", s, flags=re.I)
    return s


def _key(name: str) -> str:
    """比较用键: 去掉连字符/空格并小写(邻-二甲苯 == 邻二甲苯)。"""
    return _norm(name).replace("-", "").lower()


def canonical_factor(name: str) -> str:
    n = _norm(name)
    m = re.fullmatch(r"[\u4e00-\u9fa5]+_([A-Za-z]{1,2})", n)  # 甲方表头 "铅_Pb(mg/kg)"
    if m:
        n = m.group(1)
    for k in (n, n.lower()):
        if k in _ALIASES:
            return _ALIASES[k]
    upper = {"cd": "Cd", "hg": "Hg", "as": "As", "pb": "Pb", "cr": "Cr", "cu": "Cu", "ni": "Ni", "zn": "Zn"}
    if n.lower() in upper:
        return upper[n.lower()]
    return n


def _standards_dir(root: str | None = None) -> str:
    if root:
        return os.path.join(root, "data", "standards")
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(os.path.dirname(here)), "data", "standards")


def load_standards(root: str | None = None) -> dict:
    d = _standards_dir(root)
    gb15618: dict = {}
    with open(os.path.join(d, "gb15618_2018_v12.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            gb15618.setdefault((r["factor"], r["value_type"], r["farmland"]), {})[r["pH_bin"]] = {
                "value": float(r["value"]), "confidence": r["confidence"], "source": r["source"]}
    gb36600: dict = {}
    with open(os.path.join(d, "gb36600_2018_v12.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            gb36600[(_key(r["factor"]), r["land_class"])] = {
                "factor": r["factor"], "screening": float(r["screening"]) if r["screening"] else None,
                "control": float(r["control"]) if r["control"] else None,
                "confidence": r["confidence"], "table_ref": r["table_ref"]}
    with open(os.path.join(d, "gb15618_2018_v12.csv"), "rb") as a, open(os.path.join(d, "gb36600_2018_v12.csv"), "rb") as b:
        sha = hashlib.sha256(a.read() + b.read()).hexdigest()
    return {"gb15618": gb15618, "gb36600": gb36600, "sha256": sha}


def _ph_bin(ph: float) -> str:
    for label, lo, hi in _PH_BINS:
        if (lo is None or ph > lo) and (hi is None or ph <= hi):
            return label
    return _PH_BINS[-1][0]


def _gb15618_limits(std: dict, factor: str, ph: float | None, farmland: str | None):
    """返回 (screening_for_pass, control_for_fail, notes)。pH/农用地类型未知时取保守组合。"""
    notes = []
    farms = [farmland] if farmland in ("水田", "其他") else ["水田", "其他"]
    bins = [_ph_bin(ph)] if ph is not None else [b[0] for b in _PH_BINS]
    scr_vals = [std["gb15618"].get((factor, "screening", f), {}).get(b, {}).get("value") for f in farms for b in bins]
    scr_vals = [v for v in scr_vals if v is not None]
    ctrl_vals = [std["gb15618"].get((factor, "control", "all"), {}).get(b, {}).get("value") for b in bins]
    ctrl_vals = [v for v in ctrl_vals if v is not None]
    if ph is None:
        notes.append("pH 未知: 筛选值取各 pH 档最严值, 管制值取最宽值(仅在确定时判超管制)")
    if farmland not in ("水田", "其他"):
        notes.append("农用地类型未指定: 筛选值取水田/其他较严者")
    return (min(scr_vals) if scr_vals else None,
            max(ctrl_vals) if ctrl_vals else None,
            # 无法判定区间上界: 若 pH 未知, C 介于(最严筛选, 最宽筛选]时无法确定是否超筛选
            max(scr_vals) if scr_vals else None,
            min(ctrl_vals) if ctrl_vals else None,
            notes)


def _values_by_factor(points: list[dict]) -> dict:
    out: dict = {}
    for p in points:
        for k, v in p.items():
            if k in ("point", "pH", "ph"):
                continue
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            out.setdefault(canonical_factor(k), []).append((p.get("point"), fv, p.get("pH", p.get("ph"))))
    return out


def production_gate(points: list[dict], std: dict, farmland: str | None = None) -> dict:
    vals = _values_by_factor(points)
    n_points = len(points)
    missing, partial, exceed_scr, exceed_ctrl, undetermined, factors = [], [], [], [], [], {}
    notes: set = set()
    for f in GB15618_REQUIRED:
        obs = vals.get(f, [])
        if not obs:
            missing.append(f); continue
        if len(obs) < n_points:
            partial.append({"factor": f, "measured_points": len(obs), "n_points": n_points})
        n_s = n_c = n_u = 0
        worst = None
        for point, c, ph in obs:
            try:
                ph = float(ph) if ph is not None else None
            except (TypeError, ValueError):
                ph = None
            scr_strict, ctrl_wide, scr_wide, ctrl_strict, nts = _gb15618_limits(std, f, ph, farmland)
            notes.update(nts)
            if ctrl_wide is not None and c > ctrl_wide:
                n_c += 1
                n_s += 1  # 超管制必然超筛选(与生态门禁计数口径一致: 含超管制点位)
            elif scr_strict is not None and c > scr_strict:
                # 确定超筛选: C > 最宽筛选值; 否则(pH/类型未知)仅为可能超筛选
                if scr_wide is not None and c > scr_wide:
                    n_s += 1
                    if ctrl_strict is not None and c > ctrl_strict:
                        n_u += 1  # 可能超管制(取决于 pH)
                else:
                    n_u += 1
            ratio = c / scr_strict if scr_strict else None
            if ratio is not None and (worst is None or ratio > worst["ratio_to_screening"]):
                worst = {"point": point, "value": c, "pH": ph, "screening": scr_strict,
                         "control": ctrl_wide, "ratio_to_screening": round(ratio, 3)}
        factors[f] = {"n_obs": len(obs), "n_exceed_control": n_c, "n_exceed_screening": n_s,
                      "n_undetermined": n_u, "worst": worst,
                      "has_control_value": bool(std["gb15618"].get((f, "control", "all")))}
        if n_c: exceed_ctrl.append(f)
        elif n_s: exceed_scr.append(f)
        if n_u: undetermined.append(f)
    if exceed_ctrl:
        state = "fail"
    elif missing or partial or undetermined:
        state = "insufficient"
    elif exceed_scr:
        state = "conditional"
    else:
        state = "pass"
    return {"standard": "GB 15618-2018", "state": state, "required": GB15618_REQUIRED,
            "missing_required": missing, "partial_required": partial,
            "exceed_control": exceed_ctrl, "exceed_screening_only": exceed_scr,
            "undetermined": undetermined, "factors": factors, "notes": sorted(notes),
            "farmland_type": farmland or "未指定"}


def ecology_gate(points: list[dict], std: dict, land_class: str | None = None,
                 required: list[str] | None = None) -> dict:
    assumptions = []
    if land_class not in ("第一类用地", "第二类用地"):
        assumptions.append("生态用地类别未指定, 按 GB 36600 第一类用地(最严)评价 — 保守假设")
        land_class = "第一类用地"
    required = required or GB36600_BASIC
    vals = _values_by_factor(points)
    vals_k = {_key(k): (k, v) for k, v in vals.items()}
    n_points = len(points)
    missing, partial, no_threshold, low_conf, exceed_scr, exceed_ctrl, factors = [], [], [], [], [], [], {}
    for f in required:
        hit = vals_k.get(_key(f))
        if hit is None:
            missing.append(f); continue
        _, obs = hit
        if len(obs) < n_points:
            partial.append({"factor": f, "measured_points": len(obs), "n_points": n_points})
        th = std["gb36600"].get((_key(f), land_class))
        if th is None or th["screening"] is None:
            no_threshold.append(f); factors[f] = {"n_obs": len(obs), "threshold": None}; continue
        if th["confidence"] == "low":
            low_conf.append(f)
        n_s = sum(1 for _, c, _ in obs if c > th["screening"])
        n_c = sum(1 for _, c, _ in obs if th["control"] is not None and c > th["control"])
        mx = max(obs, key=lambda t: t[1])
        factors[f] = {"n_obs": len(obs), "screening": th["screening"], "control": th["control"],
                      "confidence": th["confidence"], "n_exceed_screening": n_s, "n_exceed_control": n_c,
                      "max": {"point": mx[0], "value": mx[1], "ratio_to_screening": round(mx[1] / th["screening"], 3)}}
        if n_c and th["confidence"] != "low":
            exceed_ctrl.append(f)
        elif n_s:
            exceed_scr.append(f)
    # 非基本项目但有阈值的实测因子(如石油烃): 超管制同样判失败
    extra = []
    for k, (name, obs) in vals_k.items():
        if any(_key(r) == k for r in required):
            continue
        th = std["gb36600"].get((k, land_class))
        if not th or th["screening"] is None:
            continue
        n_s = sum(1 for _, c, _ in obs if c > th["screening"])
        n_c = sum(1 for _, c, _ in obs if th["control"] is not None and c > th["control"])
        if n_s or n_c:
            extra.append({"factor": name, "n_exceed_screening": n_s, "n_exceed_control": n_c,
                          "confidence": th["confidence"]})
            if n_c and th["confidence"] != "low":
                exceed_ctrl.append(name)
            else:
                exceed_scr.append(name)
    if exceed_ctrl:
        state = "fail"
    elif missing or partial or no_threshold or low_conf:
        state = "insufficient"
    elif exceed_scr:
        state = "conditional"
    else:
        state = "pass"
    return {"standard": "GB 36600-2018", "land_class": land_class, "state": state,
            "required_count": len(required), "missing_required": missing, "partial_required": partial,
            "threshold_missing": no_threshold, "low_confidence_threshold": low_conf,
            "exceed_control": exceed_ctrl, "exceed_screening_only": exceed_scr,
            "non_basic_exceedances": extra, "factors": factors, "assumptions": assumptions}


def _track_status(gate: dict, score: dict | None, track: str) -> tuple[str, list[str]]:
    """门禁 + 评分 → 轨道状态 supported / not_supported / insufficient (+ 条件)。"""
    conds = []
    g = gate["state"]
    if g == "fail":
        return "not_supported", conds
    if g == "insufficient":
        return "insufficient", conds
    if g == "conditional":
        if track == "ecology":
            return "insufficient", ["生态轨道超筛选值: 须完成详细风险评估后再判定"]
        conds.append("安全利用类: 须采取农艺调控、替代种植等安全利用措施并开展农产品协同监测")
    if score and score.get("status") == "out_of_domain":
        # v1.2.2(T01): 域外功能评分不得产生“支持”; 门禁失败已在上面返回 not_supported
        conds.append("功能评分超出等级有效域[0, 1.0]: 原值保留, 不分级、不作功能支持判断")
        return "insufficient", conds
    if not score or score.get("feasible") is None:
        return "insufficient", conds
    return ("supported" if score["feasible"] else "not_supported"), conds


# v1.2.2(T03): 用途/适用性(Q09/Q17 暂定处理)
FARMLAND_TYPES = ("水田", "其他")
ECO_LAND_CLASSES = ("第一类用地", "第二类用地")
ECO_NON_CONSTRUCTION = "非建设用地生态用途"
USE_SCOPE_NOTE = ("GB 36600-2018 适用于建设用地; 第一类/第二类用地须由使用者按规划用途明确选择。"
                  "“生态重构”对应建设用地类别的映射未经核实, 选择“非建设用地生态用途”时 GB 36600 的适用性未定, "
                  "不给出正式生态利用结论。GB 15618-2018 须明确水田/其他农用地。未选择用途时只给出保守假设筛查(非正式结论)。")


def use_states(farmland_type: str | None, eco_land_class: str | None) -> dict:
    if farmland_type is not None and farmland_type not in FARMLAND_TYPES:
        raise ValueError(f"farmland_type 必须为 {'/'.join(FARMLAND_TYPES)} 或留空: {farmland_type}")
    if eco_land_class is not None and eco_land_class not in ECO_LAND_CLASSES + (ECO_NON_CONSTRUCTION,):
        raise ValueError(f"eco_land_class 必须为 {'/'.join(ECO_LAND_CLASSES + (ECO_NON_CONSTRUCTION,))} 或留空: {eco_land_class}")
    return {"production": "explicit" if farmland_type in FARMLAND_TYPES else "needs_manual_use_selection",
            "ecology": ("explicit" if eco_land_class in ECO_LAND_CLASSES else
                        "regulatory_applicability_unresolved" if eco_land_class == ECO_NON_CONSTRUCTION
                        else "needs_manual_use_selection")}


_TRACK_CN = {"production": "生产(农用地)", "ecology": "生态"}


def decide(stage: str, points: list[dict], *, pollution_type: str | None = None,
           farmland_type: str | None = None, eco_land_class: str | None = None,
           production_score: dict | None = None, ecology_score: dict | None = None,
           data_origin: str = "field", standards: dict | None = None,
           eco_required: list[str] | None = None) -> dict:
    """主入口。score 形如 {"value": 63.3, "label": "可行", "feasible": True, "source": "S2 重构可行性"}。"""
    if stage not in (PRE, POST):
        raise ValueError(f"stage 必须为 {PRE}/{POST}: {stage}")
    std = standards or load_standards()
    us = use_states(farmland_type, eco_land_class)
    pg = production_gate(points, std, farmland_type if us["production"] == "explicit" else None)
    eg = ecology_gate(points, std, eco_land_class if us["ecology"] == "explicit" else None, eco_required)
    ps, pc = _track_status(pg, production_score, "production")
    es, ec = _track_status(eg, ecology_score, "ecology")
    hypothetical = None
    if us["production"] != "explicit" or us["ecology"] != "explicit":
        hypothetical = {"label": "hypothetical_conservative_screen", "production": ps, "ecology": es,
                        "note": "未选择用途时的保守假设筛查(最严档), 非正式利用结论; " + USE_SCOPE_NOTE}
    if us["production"] != "explicit":
        # GB 15618 管制值不分农用地类型 → 超管制为与用途无关的硬性失败; 其余结论暂缓
        if not (pg["state"] == "fail"):
            ps = "withheld_use"
        pc = pc + ["须明确农用地类型(水田/其他)后才能给出正式生产利用结论"]
    if us["ecology"] != "explicit":
        hard = False
        if us["ecology"] == "needs_manual_use_selection" and eg["state"] == "fail":
            hard = ecology_gate(points, std, "第二类用地", eco_required)["state"] == "fail"  # 最宽类别仍失败
        if not hard:
            es = "withheld_use"
        ec = ec + (["所选生态用途不是 GB 36600 建设用地类别, 法规适用性未定, 不给出正式生态利用结论"]
                   if us["ecology"] == "regulatory_applicability_unresolved"
                   else ["须明确建设用地类别(第一类/第二类用地)后才能给出正式生态利用结论"])
    if ps == "supported" and es == "supported":
        state = "both_supported"
    elif ps == "supported":
        state = "production_supported"
    elif es == "supported":
        state = "ecology_supported"
    elif "insufficient" in (ps, es):
        state = "insufficient_evidence"
    elif "withheld_use" in (ps, es):
        non_explicit = [v for v in us.values() if v != "explicit"]
        state = ("regulatory_applicability_unresolved"
                 if non_explicit and all(v == "regulatory_applicability_unresolved" for v in non_explicit)
                 else "needs_manual_use_selection")
    else:
        state = "neither_supported"

    missing_evidence = []
    for name, g in (("生产", pg), ("生态", eg)):
        if g["missing_required"]:
            missing_evidence.append(f"{name}门禁缺测必测项目 {len(g['missing_required'])} 项: "
                                    + "、".join(g["missing_required"][:12])
                                    + (" 等" if len(g["missing_required"]) > 12 else ""))
        for p in g["partial_required"]:
            missing_evidence.append(f"{name}门禁 {p['factor']} 仅 {p['measured_points']}/{p['n_points']} 个点位有测值")
    if pg.get("undetermined"):
        why = []
        if pg["farmland_type"] == "未指定":
            why.append("农用地类型(水田/其他)")
        if any("pH 未知" in n for n in pg["notes"]):
            why.append("点位 pH")
        missing_evidence.append(f"生产门禁需补充{'与'.join(why) or '判定条件'}才能判定: " + "、".join(pg["undetermined"]))
    if eg.get("threshold_missing"):
        missing_evidence.append("生态门禁缺权威阈值: " + "、".join(eg["threshold_missing"]))
    if eg.get("low_confidence_threshold"):
        missing_evidence.append("生态门禁阈值置信度低(族群参考): " + "、".join(eg["low_confidence_threshold"]))
    if us["production"] != "explicit":
        missing_evidence.append("生产轨道未选择农用地类型(水田/其他)")
    if us["ecology"] == "needs_manual_use_selection":
        missing_evidence.append("生态轨道未选择建设用地类别(第一类/第二类用地)")
    elif us["ecology"] == "regulatory_applicability_unresolved":
        missing_evidence.append("生态用途为非建设用地: GB 36600 适用性待主管部门/课题组确认")
    for lbl, sc, st in (("生产", production_score, ps), ("生态", ecology_score, es)):
        if (not sc or sc.get("feasible") is None) and st == "insufficient":
            missing_evidence.append(f"{lbl}功能评分不可用({(sc or {}).get('reason', '未计算或证据不足')})")

    assumptions = list(eg["assumptions"]) + pg["notes"]
    if data_origin != "field" and data_origin != "client_real":
        assumptions.append(f"输入数据来源为 {data_origin}: 结论仅供测试/演示, 不得用于正式报告")

    comparison = None
    if state == "both_supported":
        a, b = production_score.get("value"), ecology_score.get("value")
        comparison = {"production": a, "ecology": b,
                      "note": "两轨评分采用不同指标权重体系, 数值差仅作参考; 最终方向由管理目标确定"}

    text = _conclusion_text(stage, state, pg, eg, ps, es, pc + ec, comparison)
    payload = {"stage": stage, "points": points, "pollution_type": pollution_type,
               "farmland_type": farmland_type, "eco_land_class": eco_land_class,
               "production_score": production_score, "ecology_score": ecology_score,
               "standards_sha256": std["sha256"], "method_version": METHOD_VERSION}
    fp = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    return {
        "stage": stage, "is_post_remediation_conclusion": stage == POST,
        "decision_state": state, "conclusion_text": text,
        "production": {"gate": pg, "score": production_score, "track_status": ps, "conditions": pc,
                       "use_state": us["production"]},
        "ecology": {"gate": eg, "score": ecology_score, "track_status": es, "conditions": ec,
                    "use_state": us["ecology"]},
        "use_state": us, "hypothetical_screen": hypothetical, "use_scope_note": USE_SCOPE_NOTE,
        "comparison": comparison, "missing_evidence": missing_evidence, "assumptions": assumptions,
        "remediation_targets": _targets(pg, eg) if stage == PRE else None,
        "method_version": METHOD_VERSION, "method_status": METHOD_STATUS,
        "standards_sha256": std["sha256"], "input_fingerprint": fp, "data_origin": data_origin,
        "n_points": len(points),
    }


def _targets(pg: dict, eg: dict) -> dict:
    """修复前: 各轨道需降至筛选值以下的因子(修复目标)。"""
    return {
        "production": sorted(set(pg["exceed_control"] + pg["exceed_screening_only"])),
        "ecology": sorted(set(eg["exceed_control"] + eg["exceed_screening_only"])),
        "note": "修复目标 = 将对应因子降至所选用途的风险筛选值以下; 修复后须以修复后数据重新评价",
    }


_STATE_CN = {
    "both_supported": "生产与生态利用均获支持",
    "production_supported": "支持生产(农用地)利用",
    "ecology_supported": "支持生态利用",
    "neither_supported": "生产与生态利用均不支持",
    "insufficient_evidence": "证据不足, 暂不能给出利用结论",
    "needs_manual_use_selection": "须人工选择用途后才能给出正式利用结论(当前仅为保守假设筛查)",
    "regulatory_applicability_unresolved": "所选用途的法规适用性未确定, 不给出正式利用结论",
}


def _conclusion_text(stage, state, pg, eg, ps, es, conds, comparison) -> str:
    parts = []
    if stage == PRE:
        parts.append("【修复前情景判断, 非修复后利用结论】")
    parts.append(_STATE_CN[state] + "。")
    for cn, g, st in (("生产", pg, ps), ("生态", eg, es)):
        if g["state"] == "fail":
            parts.append(f"{cn}门禁未通过({g['standard']}): " + "、".join(g["exceed_control"]) + " 超风险管制值, 不可被评分抵消。")
        elif g["state"] == "conditional":
            parts.append(f"{cn}门禁为条件通过: " + "、".join(g["exceed_screening_only"]) + " 超风险筛选值。")
        elif g["state"] == "insufficient":
            parts.append(f"{cn}门禁证据不足。")
        else:
            parts.append(f"{cn}门禁通过; 功能评分状态: {st}。")
        if st == "withheld_use":
            parts.append(f"{cn}轨道用途未明确或法规适用性未定: 正式结论暂缓。")
    if conds:
        parts.append("条件: " + "; ".join(conds) + "。")
    if comparison:
        parts.append("两轨均支持, " + comparison["note"] + "。")
    if stage == PRE:
        parts.append("修复完成后应导入修复后数据(课题三 SSUI)重新判定。")
    parts.append(f"方法状态: {METHOD_STATUS}(待课题组确认)。")
    return "".join(parts)
