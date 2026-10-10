"""v1.2.1: 生成方法边界材料(02_METHODS) — 全部从代码/数据表读取, 不手写数值。

输出(--out 目录):
  indicator_state_matrix.csv            各课题指标状态: 可导入 / 仅展示 / 赋分 / 计权 / 模型输入 / 不适用
  thresholds_official_vs_reference.csv  阈值来源分层: 官方(GB 15618/36600) / 文献参考 / 启发式 / 不判定
  crosswalk_s1_s2_s3.csv                三课题指标对照; 无对应关系记 not_applicable 并写原因, 不强行等同
用法: python docs/methods/build_methods_v121.py --out <dir>
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (os.path.join(ROOT, "backend"), os.path.join(ROOT, "ml", "evaluation")):
    sys.path.insert(0, p)


def _w(path, header, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh); w.writerow(header); w.writerows(rows)
    return len(rows)


def main(out: str):
    os.makedirs(out, exist_ok=True)
    import pandas as pd
    import reconstruction_m2025 as M
    import yaml
    from app.services import threshold_resolver as TR
    canon = {k: v for k, v in yaml.safe_load(open(os.path.join(ROOT, "data", "knowledge", "factor_aliases_v0.8.yaml"),
                                                   encoding="utf-8")).items() if isinstance(v, dict)}
    shap_dir = os.path.join(ROOT, "artifacts", "overnight_20260703", "shap_filtered")
    model_groups = {}
    for tag in ("hm_prod", "hm_eco", "all_prod", "all_eco"):
        f = os.path.join(shap_dir, f"{tag}_measured_contribution_global.csv")
        if os.path.isfile(f):
            df = pd.read_csv(f)
            col = "group" if "group" in df.columns else df.columns[0]
            model_groups[tag] = set(df[col].astype(str))
    fb = TR._GB15618_EXTENDED_FALLBACK
    db_names = TR._CANONICAL_TO_DB_NAME
    gb15618 = {r["factor"] for r in csv.DictReader(open(os.path.join(ROOT, "data", "standards", "gb15618_2018_official.csv"), encoding="utf-8"))}
    gb36600 = {r["pollutant"] for r in csv.DictReader(open(os.path.join(ROOT, "data", "standards", "gb36600_2018_official.csv"), encoding="utf-8"))}
    sym = {"砷": "As", "镉": "Cd", "铬（六价）": "Cr(VI)", "铜": "Cu", "铅": "Pb", "汞": "Hg", "镍": "Ni"}
    gb36600_names = gb36600 | {sym.get(x, x) for x in gb36600}
    rows = []
    for c in sorted(canon):
        dbn = db_names.get(c, c)
        off_p, off_e = dbn in gb15618, dbn in gb36600_names
        ref = fb.get(dbn) or fb.get(c)
        mi = [t for t, g in model_groups.items() if c in g]
        state = ("display_only" if dbn == "__advisory__" else "scored_official" if (off_p or off_e)
                 else "exploratory_reference" if ref else "importable_no_threshold")
        rows.append(["S1 课题一", c, canon[c].get("preferred_unit", ""), "是", "是",
                     "KOS 规则层 R" if state in ("scored_official", "exploratory_reference") else "否",
                     "W(用途权重)" if state != "display_only" else "否", "、".join(mi) or "否",
                     ("GB 15618" if off_p else "") + (" / GB 36600" if off_e else "") or "—",
                     f"{ref['type']} {ref['limit']} {ref.get('unit', '')} · {ref['standard']}" if ref else "—", state])
    for fid, sp in M.FEATURES.items():
        wp, we = M.T218.get(fid), M.T220_FEATURE.get(fid)
        note = sp.get("eco_no_rule") or sp.get("prod_no_rule") or ""
        if fid in ("soc", "profile"):
            note = (note + "; " if note else "") + "M-03 全指标路径只赋分展示不计权; 缺失数据路径按表2.19 准则层计权"
        rows.append(["S2 课题二", f"{fid}({sp['cn']})", sp["unit"], "是", "是", "表2.22 分档赋分",
                     f"{wp}" if wp is not None else ("表2.19 准则层" if fid in M.T219 else "不计权"), "否(冻结方法)",
                     f"{we}" if we is not None else ("表2.21 准则层" if fid in M.T221 else ("生态补充指标" if sp.get("eco_only") else "不计权")),
                     "RECON_28" if fid in M.RECON_28 else "生态补充/六价铬", note or "scored"])
    W = json.load(open(os.path.join(ROOT, "data", "standards", "ssui_weights_pptx_v1.json"), encoding="utf-8"))
    for ind in W["indicators"]:
        econ = int(ind["code"][1:]) >= 18
        rows.append(["S3 课题三", f"{ind['code']} {ind['name']}", "得分 0–1", "是(得分录入)", "是", "得分直接录入",
                     f"{ind['w_production']}", "否", f"{ind['w_ecology']}", ind["criterion"],
                     "score_input_only(原始值→得分规则未提供)" + ("; 经济类, 经济 JSON 不参与" if econ else "")])
    n1 = _w(os.path.join(out, "indicator_state_matrix.csv"),
            ["课题", "指标", "单位", "可导入", "可展示", "赋分方式", "计权(生产)", "模型输入", "计权(生态)", "官方阈值/参考/分组", "状态"], rows)
    trows = [["GB 15618-2018", f, "官方 表1 筛选值/表3 管制值(其他农用地; 镉汞砷铅铬另有水田口径)", "upper", "A", "正式 Top-N(生产) / 法规门禁"] for f in sorted(gb15618)]
    trows += [["GB 36600-2018", f, "官方 表1/表2 第一类/第二类用地", "upper", "A", "正式 Top-N(生态) / 法规门禁"] for f in sorted(gb36600)]
    trows += [[v["standard"], k, "文献参考 / 行业标准(非本轨官方)", v["type"], "C", "仅探索性列表"] for k, v in sorted(fb.items())]
    trows += [["系统参考区间", "pH", "heuristic 区间", "interval", "C", "仅探索性列表"],
              ["(跨路径)", "生产轨借用 GB 36600 / 生态轨借用 GB 15618", "cross_track_fallback", "upper", "C", "仅探索性列表"],
              ["(缺 pH/用地)", "取最严档", "strictest_tier_fallback", "upper", "C", "仅探索性列表"],
              ["(行业/文献标准行)", "NY/T 1749 等入库行", "secondary_standard", "知识库方向或 unknown", "B", "仅探索性列表; 方向未知不判定"],
              ["(备注暂定/待审定)", "—", "provisional", "—", "C", "仅探索性列表"],
              ["(其他)", "无阈值 / 用地或 pH 不明 / 单位不可换算", "not_found / ambiguous / unit_unresolved", "—", "—", "不判定, 不进入任何排名"]]
    n2 = _w(os.path.join(out, "thresholds_official_vs_reference.csv"), ["来源", "因子", "层级", "方向", "证据等级", "用途"], trows)
    special = {"total_n": "TN_gkg", "cec": "CEC_cmolkg", "ph": "pH",
               "soc": "OC_pct(有机碳; 不与有机质 OM_gkg 换算)", "bulk_density": "SoilBD_gcm3(数值; 课题二生产轨为类别, 不等同)",
               "cr": "Cr_mgkg(总铬; 不换算为六价铬)", "cr6": "Cr6_mgkg(六价铬)", "bap": "BaP_ngg(值以 ng/g 存, 与 mg/kg 阈值换算比较)"}
    inv = {v: k for k, v in db_names.items()}
    cw = []
    for fid, sp in M.FEATURES.items():
        s1 = special.get(fid) or inv.get(sp.get("gb15618") or "") or inv.get(sp["cn"])
        cw.append([f"{fid}({sp['cn']})", s1 or "not_applicable", "" if s1 else "课题一无同义因子; 不强行映射",
                   "not_applicable", "课题三为 D1–D25 得分口径, 无原始值→得分规则, 不建立等同关系"])
    for ind in W["indicators"]:
        cw.append([f"(课题三) {ind['code']} {ind['name']}", "not_applicable", "得分口径", "—", "独立指标体系; 待课题三提供原始指标定义"])
    n3 = _w(os.path.join(out, "crosswalk_s1_s2_s3.csv"), ["课题二指标", "课题一 canonical", "说明(课题一)", "课题三", "说明(课题三)"], cw)
    return {"indicator_state_matrix": n1, "thresholds": n2, "crosswalk": n3, "model_groups": {k: len(v) for k, v in model_groups.items()}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True)
    print(json.dumps(main(ap.parse_args().out), ensure_ascii=False))
