"""SRS v1.2.1 演示数据补充场景(模拟数据——仅供测试/演示)。

不改动 v1.2.0 演示包 A–E 的任何文件(哈希保持), 另生成两个修复前检测场景, 覆盖审计 R07/R08 指出的空白:
  F  有机-重金属复合污染(GB 36600 第一类用地, 生态轨): 苯并[a]芘/萘/石油烃以 mg/kg 填报, 检验单位换算后
     与 GB 36600 阈值同单位比较; 同时含 1 个只有文献参考阈值的因子(锰) → 只进探索性列表。
  G  仅启发式/文献参考阈值触发(生产轨): 8 项重金属均低于 GB 15618 筛选值, 阳离子交换量/全氮/有机质偏低
     → 正式 Top-N 为“证据不足”, 肥力不足只在探索性列表(下限方向)。
期望值由本脚本独立计算(读取官方阈值 CSV, 不调用 SRS 评价代码)。

用法: python scripts/mc_demo_v121_cases.py --out demo/mc_v12
随机流: numpy SeedSequence([20261009, 121]) — 与 A–E 的流独立, A–E 结果不变。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABEL = "模拟数据——仅供测试/演示"
FILE_LABEL = "模拟数据_仅供测试演示"
SEED = 20261009
GEN_VERSION = "mc_demo_v121_cases.1"
N = 12
PRE_COLS = ["采样点编号", "经度", "纬度", "深度_上限(cm)", "深度_下限(cm)", "土壤类型", "pH",
            "镉_Cd(mg/kg)", "汞_Hg(mg/kg)", "砷_As(mg/kg)", "铅_Pb(mg/kg)", "铬_Cr(mg/kg)", "铜_Cu(mg/kg)",
            "镍_Ni(mg/kg)", "锌_Zn(mg/kg)", "六价铬_Cr(VI)(mg/kg)", "有机质(g/kg)", "全氮(g/kg)", "阳离子交换量(cmol/kg)"]
ORG_COLS = {"苯并[a]芘(mg/kg)": ("苯并[a]芘", 0.55), "萘(mg/kg)": ("萘", 25.0), "石油烃(C10-C40)(mg/kg)": ("石油烃(C10-C40)", 826.0)}
EXTRA = {"锰(mg/kg)": 1500.0}


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _gb15618_other(ph: float) -> dict:
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "data", "standards", "gb15618_2018_official.csv"), encoding="utf-8"))
            if r["value_type"] == "screening"]

    def ok(b):
        return (b in ("all", "") or (b == "pH<=5.5" and ph <= 5.5) or (b == "5.5<pH<=6.5" and 5.5 < ph <= 6.5)
                or (b == "6.5<pH<=7.5" and 6.5 < ph <= 7.5) or (b == "pH>7.5" and ph > 7.5))
    out = {}
    for r in rows:
        if ok(r["pH_bin"]) and r["farmland"] in ("其他", "all"):
            out.setdefault(r["factor"], float(r["value"]))
    return out


def _gb36600_cat1() -> dict:
    out = {}
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "standards", "gb36600_2018_official.csv"), encoding="utf-8")):
        if r.get("table") in ("表1", "表2") and r.get("screening_cat1"):
            out[r["pollutant"]] = float(r["screening_cat1"])
    return out


def _write(path, rows, extra_cols):
    from openpyxl import Workbook
    wb = Workbook(); ws = wb.active; ws.title = "检测数据"
    cols = PRE_COLS + extra_cols
    ws.append(cols)
    for r in rows:
        ws.append([r.get(c) for c in cols])
    g = wb.create_sheet("说明")
    g.cell(1, 1, f"本文件为{LABEL}; 生成器 {GEN_VERSION}, 种子 SeedSequence([{SEED}, 121])")
    wb.save(path)


def generate(out: str) -> dict:
    rng = np.random.default_rng(np.random.SeedSequence([SEED, 121]))
    d = os.path.join(out, "cases_v121"); os.makedirs(d, exist_ok=True)
    cat1 = _gb36600_cat1()
    cases = {}
    # ── F: 有机-重金属复合污染, 生态轨 第一类用地 ──
    rows = []
    for i in range(N):
        ph = round(float(rng.normal(6.8, 0.2)), 2)
        r = {"采样点编号": f"F{i + 1:02d}", "经度": round(120.2 + rng.uniform(0, .02), 6), "纬度": round(30.3 + rng.uniform(0, .02), 6),
             "深度_上限(cm)": 0, "深度_下限(cm)": 20, "土壤类型": "潮土", "pH": ph,
             "镉_Cd(mg/kg)": round(float(np.exp(rng.normal(math.log(8), .35))), 3), "汞_Hg(mg/kg)": round(float(np.exp(rng.normal(math.log(.3), .3))), 4),
             "砷_As(mg/kg)": round(float(np.exp(rng.normal(math.log(12), .25))), 3), "铅_Pb(mg/kg)": round(float(np.exp(rng.normal(math.log(150), .3))), 2),
             "铬_Cr(mg/kg)": round(float(np.exp(rng.normal(math.log(70), .2))), 2), "铜_Cu(mg/kg)": round(float(np.exp(rng.normal(math.log(40), .2))), 2),
             "镍_Ni(mg/kg)": round(float(np.exp(rng.normal(math.log(30), .2))), 2), "锌_Zn(mg/kg)": round(float(np.exp(rng.normal(math.log(120), .2))), 2),
             "六价铬_Cr(VI)(mg/kg)": round(float(np.exp(rng.normal(math.log(1.5), .3))), 3),
             "有机质(g/kg)": round(float(np.exp(rng.normal(math.log(22), .2))), 2), "全氮(g/kg)": round(float(np.exp(rng.normal(math.log(1.3), .2))), 3),
             "阳离子交换量(cmol/kg)": round(float(np.exp(rng.normal(math.log(14), .2))), 2),
             "苯并[a]芘(mg/kg)": round(float(np.exp(rng.normal(math.log(1.2), .5))), 4),
             "萘(mg/kg)": round(float(np.exp(rng.normal(math.log(8), .4))), 3),
             "石油烃(C10-C40)(mg/kg)": round(float(np.exp(rng.normal(math.log(700), .25))), 1),
             "锰(mg/kg)": round(float(np.exp(rng.normal(math.log(1800), .2))), 1)}
        rows.append(r)
    fF = os.path.join(d, f"01_MCDEMO-F_有机重金属复合_修复前检测数据_{FILE_LABEL}.xlsx")
    _write(fF, rows, list(ORG_COLS) + list(EXTRA))
    exp_off = {}
    for col, key in (("镉_Cd(mg/kg)", "Cd_mgkg"), ("铅_Pb(mg/kg)", "Pb_mgkg"), ("砷_As(mg/kg)", "As_mgkg"),
                     ("汞_Hg(mg/kg)", "Hg_mgkg"), ("铜_Cu(mg/kg)", "Cu_mgkg"), ("镍_Ni(mg/kg)", "Ni_mgkg"),
                     ("六价铬_Cr(VI)(mg/kg)", "Cr6_mgkg")):
        name = {"Cd_mgkg": "镉", "Pb_mgkg": "铅", "As_mgkg": "砷", "Hg_mgkg": "汞", "Cu_mgkg": "铜", "Ni_mgkg": "镍", "Cr6_mgkg": "铬（六价）"}[key]
        lim = cat1.get(name)
        if lim is None:
            continue
        mx = max(r[col] for r in rows)
        if mx > lim:
            exp_off[key] = {"max_mgkg": mx, "screening_mgkg": lim, "ratio": round(mx / lim, 4)}
    for col, (name, _lim) in ORG_COLS.items():
        lim = cat1[name]
        mx = max(r[col] for r in rows)
        key = {"苯并[a]芘": "BaP_ngg", "萘": "萘", "石油烃(C10-C40)": "TPH_ngg"}[name]
        if mx > lim:
            exp_off[key] = {"max_mgkg": mx, "screening_mgkg": lim, "ratio": round(mx / lim, 4),
                            "value_unit_in_system": "ng/g", "threshold_in_system": lim * 1000}
    cases["F"] = {"title": "有机-重金属复合污染(生态轨 GB 36600 第一类用地)", "file": os.path.relpath(fF, out),
                  "kos": {"track": "eco", "subset": "all", "eco_land_class": "第一类用地"},
                  "expected": {"official_factors": sorted(exp_off), "official_detail": exp_off,
                               "exploratory_must_include": ["Mn_mgkg"], "official_must_exclude": ["Mn_mgkg", "CEC_cmolkg", "TN_gkg", "OM_gkg"]},
                  "checks": "正式 Top-N = GB 36600 第一类筛选值超标因子(有机物经 mg/kg→ng/g 同单位比较); 锰仅探索性"}
    # ── G: 仅文献参考阈值触发, 生产轨 ──
    rows = []
    for i in range(N):
        ph = round(float(rng.normal(6.0, 0.2)), 2)
        r = {"采样点编号": f"G{i + 1:02d}", "经度": round(120.4 + rng.uniform(0, .02), 6), "纬度": round(30.1 + rng.uniform(0, .02), 6),
             "深度_上限(cm)": 0, "深度_下限(cm)": 20, "土壤类型": "红壤", "pH": ph}
        lim = _gb15618_other(ph)
        for col, f in (("镉_Cd(mg/kg)", "Cd"), ("汞_Hg(mg/kg)", "Hg"), ("砷_As(mg/kg)", "As"), ("铅_Pb(mg/kg)", "Pb"),
                       ("铬_Cr(mg/kg)", "Cr"), ("铜_Cu(mg/kg)", "Cu"), ("镍_Ni(mg/kg)", "Ni"), ("锌_Zn(mg/kg)", "Zn")):
            r[col] = round(lim[f] * float(rng.uniform(0.2, 0.6)), 4)
        r["六价铬_Cr(VI)(mg/kg)"] = round(float(rng.uniform(0.1, 0.5)), 3)
        r["有机质(g/kg)"] = round(float(rng.uniform(3.5, 9.0)), 2)
        r["全氮(g/kg)"] = round(float(rng.uniform(0.4, 1.2)), 3)
        r["阳离子交换量(cmol/kg)"] = round(float(rng.uniform(4.0, 11.0)), 2)
        rows.append(r)
    fG = os.path.join(d, f"01_MCDEMO-G_仅文献参考阈值_修复前检测数据_{FILE_LABEL}.xlsx")
    _write(fG, rows, [])
    low = {k: min(r[c] for r in rows) < L for k, (c, L) in
           {"CEC_cmolkg": ("阳离子交换量(cmol/kg)", 10.0), "TN_gkg": ("全氮(g/kg)", 1.0), "OM_gkg": ("有机质(g/kg)", 6.0)}.items()}
    cases["G"] = {"title": "无官方阈值超标、仅肥力下限不足(生产轨)", "file": os.path.relpath(fG, out),
                  "kos": {"track": "prod", "subset": "hm", "farmland_type": "其他"},
                  "expected": {"official_ranking_status": "insufficient_evidence", "official_factors": [],
                               "exploratory_must_include": sorted(k for k, v in low.items() if v),
                               "exploratory_direction": "lower"},
                  "checks": "8 项重金属均 < GB 15618 筛选值(其他, 按点位 pH); CEC/全氮/有机质低于文献参考下限 → 只在探索性列表"}
    meta_p = os.path.join(out, "metadata.json")
    meta = json.load(open(meta_p, encoding="utf-8"))
    meta["cases_v121"] = {"generator": GEN_VERSION, "seed": f"SeedSequence([{SEED}, 121])", "label": LABEL,
                          "cases": cases, "files": {c["file"]: _sha(os.path.join(out, c["file"])) for c in cases.values()}}
    meta["economic_inputs_note"] = ("05_*_场地经济输入 JSON 为独立演示文件, 当前版本课题三 SSUI 采用得分录入模式(D1–D25/D18–D25 得分由 Beta 分布生成),"
                                    " 不读取经济 JSON; 经济原值→得分的计算闭环未实现, 不得表述为“经济原值计算 SSUI 已完成”。")
    meta["score_input_mode"] = {"S3": "得分录入(D1–D25 生产 / D1–D25 生态, 其中 D18–D25 为经济类指标得分); 原始值/单位列为空",
                                "raw_value_closure": "未实现(待课题三提供原始指标→得分规则)"}
    json.dump(meta, open(meta_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta["cases_v121"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "demo", "mc_v12"))
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    r = generate(a.out)
    print(json.dumps({k: {"file": v["file"], "expected": v["expected"]} for k, v in r["cases"].items()}, ensure_ascii=False, indent=1))
