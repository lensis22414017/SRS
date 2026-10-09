"""SRS v1.2 全功能蒙特卡洛演示数据包 — 模拟数据——仅供测试/演示。

两条演示轨道:
  1) 合成全功能轨道(本脚本 generate): 5 个独立合成场地, 覆盖 28 项重构指标 + 六价铬 + 生态补充指标,
     课题三 D1–D25 得分与原始值(得分录入模式), GB 15618 / GB 36600 表1 45 项基本项目, 场地级经济输入;
     每个场地对应一种利用决策分支; 另附边界/错误夹具。
  2) 子课题原始数据轨道: 不在本脚本内修改任何原始值, 由 demo_runner 直接上传原文件(来源未核实标注)。

用法:
  python scripts/mc_demo_v12.py generate --out demo/mc_v12
  python scripts/mc_demo_v12.py run --out demo/mc_v12 --db demo/mc_v12/srs_demo_v12.db   # 进程内 API 演示(独立演示库)
记录: 种子、生成器版本、分布与参数来源、相关结构、约束、阶段假设、单位 → metadata.json;
独立期望值(不调用系统评价代码) → expected.json。
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
from datetime import datetime, timezone

import numpy as np

LABEL = "模拟数据——仅供测试/演示"
FILE_LABEL = "模拟数据_仅供测试演示"
SEED = 20261009
GEN_VERSION = "mc_demo_v12.0"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N_POINTS = 20

# ───────────── 分布与参数(场景假设, 非拟合结果; 来源见 PARAM_SOURCE) ─────────────
PARAM_SOURCE = ("场景假设: 量级参照 GB 15618/GB 36600 阈值与表2.22 分档设计以覆盖各分支; "
                "未用任何甲方/子课题真实记录拟合分布(子课题宽表含赋分值/来源未核实, 不宜作原始浓度分布)。")
METALS = ["cd", "hg", "as", "pb", "cr", "cu", "ni", "zn"]
METAL_CORR = np.array([  # Gaussian copula 相关矩阵(Cd-Pb-Zn-As 同源 ρ=0.6; 其余 ρ=0.3)
    [1, .3, .6, .6, .3, .3, .3, .6], [.3, 1, .3, .3, .3, .3, .3, .3], [.6, .3, 1, .6, .3, .3, .3, .6],
    [.6, .3, .6, 1, .3, .3, .3, .6], [.3, .3, .3, .3, 1, .3, .3, .3], [.3, .3, .3, .3, .3, 1, .3, .3],
    [.3, .3, .3, .3, .3, .3, 1, .3], [.6, .3, .6, .6, .3, .3, .3, 1]])
GSD = {"cd": 1.4, "hg": 1.4, "as": 1.3, "pb": 1.35, "cr": 1.2, "cu": 1.3, "ni": 1.2, "zn": 1.3}

# 修复前(课题一/二) 场地中位数 — 设计: Cd/Pb/As 超 GB 15618 筛选值、低于管制值
PRE_MEDIAN = {"cd": 0.9, "hg": 0.25, "as": 32, "pb": 160, "cr": 85, "cu": 45, "ni": 38, "zn": 160}
# 修复后(课题三) 场景设计 — 每个场地一个分支
SCENARIOS = {
    "A": {"title": "两轨均支持(both_supported)", "post_median": {"cd": 0.18, "hg": 0.08, "as": 11, "pb": 40, "cr": 60,
          "cu": 24, "ni": 28, "zn": 85}, "crvi": 0.4, "organics": True, "ssui_beta": {"production": (16, 4), "ecology": (16, 4)},
          "linked_pre": True},
    "B": {"title": "仅生产支持(production_supported)", "post_median": {"cd": 0.18, "hg": 0.08, "as": 11, "pb": 40, "cr": 60,
          "cu": 24, "ni": 28, "zn": 85}, "crvi": 0.4, "organics": True, "ssui_beta": {"production": (16, 4), "ecology": (6, 14)}},
    "C": {"title": "仅生态支持(ecology_supported)", "post_median": {"cd": 3.6, "hg": 0.08, "as": 11, "pb": 40, "cr": 60,
          "cu": 24, "ni": 28, "zn": 85}, "crvi": 0.4, "organics": True, "ssui_beta": {"production": (16, 4), "ecology": (16, 4)},
          "cd_floor": 3.1},
    "D": {"title": "两轨均不支持·重度超标(neither_supported)", "post_median": {"cd": 0.3, "hg": 0.1, "as": 190, "pb": 60,
          "cr": 60, "cu": 24, "ni": 28, "zn": 85}, "crvi": 0.4, "organics": True, "ssui_beta": {"production": (16, 4), "ecology": (16, 4)},
          "as_floor": 125},
    "E": {"title": "证据不足·缺测关键项目(insufficient_evidence)", "post_median": {"hg": 0.08, "as": 11, "pb": 40, "cr": 60,
          "cu": 24, "ni": 28, "zn": 85}, "crvi": None, "organics": False, "ssui_beta": {"production": (16, 4), "ecology": (16, 4)}},
}
T_YEARS, INTENSITY, FARMLAND, ECO_CLASS = 3, "中等强度", "水田", "第一类用地"
CN_METAL = {"cd": "镉", "hg": "汞", "as": "砷", "pb": "铅", "cr": "铬", "cu": "铜", "ni": "镍", "zn": "锌"}
SYM = {"cd": "Cd", "hg": "Hg", "as": "As", "pb": "Pb", "cr": "Cr", "cu": "Cu", "ni": "Ni", "zn": "Zn"}
PH_POST = (6.9, 0.15)        # 水田, pH 6.5–7.5 档
PH_PRE = (6.4, 0.3)


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _paths():
    for p in (os.path.join(ROOT, "backend"), os.path.join(ROOT, "ml", "evaluation")):
        if p not in sys.path:
            sys.path.insert(0, p)


def _metals(rng, med: dict, n: int):
    keys = [k for k in METALS if k in med]
    idx = [METALS.index(k) for k in keys]
    C = METAL_CORR[np.ix_(idx, idx)]
    z = rng.multivariate_normal(np.zeros(len(keys)), C, size=n)
    return [{k: round(float(med[k] * math.exp(z[i, j] * math.log(GSD[k]))), 4) for j, k in enumerate(keys)} for i in range(n)]


def _recon_point(rng, i, metals):
    """28 项重构指标 + 生态补充指标。派生关系: TN = SOC / (C:N); CEC = 4 + 0.55·SOC + ε; 盐渍化等级由含盐量派生。"""
    soc = float(np.clip(15 * math.exp(rng.normal(0, math.log(1.3))), 3, 60))
    cn = float(np.clip(rng.normal(10, 1.2), 7, 14))
    salt = float(np.clip(0.4 * math.exp(rng.normal(0, math.log(1.6))), 0.05, 5))
    p = {**metals, "bhc": round(float(0.02 * math.exp(rng.normal(0, .5))), 4), "ddt": round(float(0.03 * math.exp(rng.normal(0, .5))), 4),
         "bap": round(float(0.12 * math.exp(rng.normal(0, .4))), 4),
         "soil_depth": round(float(np.clip(rng.normal(110, 25), 25, 200)), 1),
         "ph": round(float(np.clip(rng.normal(*PH_PRE), 4.5, 8.5)), 2),
         "bulk_density": str(rng.choice(["适中", "偏轻", "偏重"], p=[.7, .2, .1])),
         "biodiversity": str(rng.choice(["丰富", "一般", "不丰富"], p=[.3, .5, .2])),
         "salinization": "无、轻度" if salt < 1 else ("轻度、中度" if salt < 3 else "中度、重度"),
         "total_n": round(soc / cn, 3), "avail_p": round(float(18 * math.exp(rng.normal(0, math.log(1.5)))), 2),
         "avail_k": round(float(120 * math.exp(rng.normal(0, math.log(1.3)))), 1),
         "cec": round(float(np.clip(4 + 0.55 * soc + rng.normal(0, 1.5), 2, 60)), 2),
         "light_temp": round(float(rng.normal(3200, 150)), 0), "slope": round(float(3 * math.exp(rng.normal(0, math.log(1.8)))), 2),
         "irrigation_drainage": str(rng.choice(["充分满足、满足", "满足、基本满足", "基本满足、不满足"], p=[.4, .45, .15])),
         "groundwater_depth": round(float(np.clip(rng.normal(3, 0.8), 0.5, 8)), 2),
         "texture": str(rng.choice(["壤土", "粘土", "砂土", "砾质土"], p=[.5, .3, .15, .05])),
         "carbon_factor": "温带/北温带潮湿", "soc": round(soc, 2),
         "profile": str(rng.choice(["通体壤", "壤/粘/壤", "壤/砂/砂", "砂/粘/粘", "通体沙"], p=[.35, .25, .2, .15, .05])),
         "cr6": round(float(0.6 * math.exp(rng.normal(0, .4))), 3),
         "salt_content": round(salt, 3), "infiltration": round(float(10 * math.exp(rng.normal(0, math.log(1.6)))), 2),
         "hydrolysable_n": round(soc / cn * 1000 * float(np.clip(rng.normal(0.08, 0.01), 0.05, 0.12)), 1),
         "avail_s": round(float(40 * math.exp(rng.normal(0, .4))), 1), "avail_mg": round(float(120 * math.exp(rng.normal(0, .4))), 1),
         "avail_ca": round(float(1200 * math.exp(rng.normal(0, .4))), 0), "avail_fe": round(float(60 * math.exp(rng.normal(0, .5))), 1),
         "avail_mn": round(float(8 * math.exp(rng.normal(0, .5))), 2), "avail_cu": round(float(2 * math.exp(rng.normal(0, .5))), 2),
         "avail_zn": round(float(3 * math.exp(rng.normal(0, .5))), 2), "avail_mo": round(float(0.2 * math.exp(rng.normal(0, .5))), 3),
         "soluble_cl": round(float(18 * math.exp(rng.normal(0, .5))), 1)}
    return p


def _gb36600_official():
    with open(os.path.join(ROOT, "data", "standards", "gb36600_2018_official.csv"), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _economics(rng, scenario):
    """场地级经济输入(按年度): 成本与收益由组分相加派生, 比率由组分计算, 不独立随机。"""
    area_mu = 1.0  # 亩
    labour = float(rng.normal(900, 80)); machine = float(rng.normal(420, 40)); fert = float(rng.normal(380, 30))
    seed_ = float(rng.normal(120, 10)); water = float(rng.normal(90, 10))
    yield_kg = float(rng.normal(520, 40)); price = float(rng.normal(2.7, 0.1))
    cost = labour + machine + fert + seed_ + water
    revenue = yield_kg * price
    return {"unit": "元/亩·年", "area_mu": area_mu, "labour_cost": round(labour, 1), "machinery_cost": round(machine, 1),
            "fertilizer_cost": round(fert, 1), "seed_cost": round(seed_, 1), "irrigation_cost": round(water, 1),
            "total_cost": round(cost, 1), "yield_kg": round(yield_kg, 1), "price_yuan_per_kg": round(price, 3),
            "revenue": round(revenue, 1), "net_income": round(revenue - cost, 1),
            "benefit_cost_ratio": round(revenue / cost, 4), "derivation": "total_cost=Σ组分; revenue=yield×price; ratio=revenue/total_cost"}


# ───────────── 独立期望值(不调用系统评价代码) ─────────────
def _gb15618_paddy_pH65_75():
    # GB 15618-2018 表1 水田 6.5<pH≤7.5 / 表3 管制值 6.5<pH≤7.5 (官方 PDF); 铜 '其他'; 镍锌不分类型
    scr = {"Cd": 0.6, "Hg": 0.6, "As": 25, "Pb": 140, "Cr": 300, "Cu": 100, "Ni": 100, "Zn": 250}
    ctl = {"Cd": 3.0, "Hg": 4.0, "As": 120, "Pb": 700, "Cr": 1000}
    return scr, ctl


def expected_gates(points: list[dict], has_all_organics: bool, crvi: bool):
    scr, ctl = _gb15618_paddy_pH65_75()
    prod = "pass"
    for f in scr:
        vals = [p.get(f) for p in points]
        if any(v is None for v in vals):
            prod = "insufficient"; break
        if f in ctl and max(vals) > ctl[f]:
            prod = "fail"; break
        if max(vals) > scr[f]:
            prod = "conditional"
    if prod == "insufficient":
        pass
    off = {r["pollutant"]: r for r in _gb36600_official()}
    sym = {"砷": "As", "镉": "Cd", "铬（六价）": "Cr(VI)", "铜": "Cu", "铅": "Pb", "汞": "Hg", "镍": "Ni"}
    eco = "pass"
    any_fail = any_cond = missing = False
    for r in off.values():
        if r["table"] != "表1":
            continue
        key = sym.get(r["pollutant"], r["pollutant"])
        vals = [p.get(key) for p in points]
        if any(v is None for v in vals):
            missing = True; continue
        if max(vals) > float(r["control_cat1"]):
            any_fail = True
        elif max(vals) > float(r["screening_cat1"]):
            any_cond = True
    eco = "fail" if any_fail else ("insufficient" if missing else ("conditional" if any_cond else "pass"))
    return prod, eco


def expected_decision(prod_gate, eco_gate, ps_ok, es_ok):
    def track(g, ok, eco):
        if g == "fail":
            return "not_supported"
        if g == "insufficient":
            return "insufficient"
        if g == "conditional" and eco:
            return "insufficient"
        return "supported" if ok else "not_supported"
    p, e = track(prod_gate, ps_ok, False), track(eco_gate, es_ok, True)
    if p == "supported" and e == "supported":
        return "both_supported"
    if p == "supported":
        return "production_supported"
    if e == "supported":
        return "ecology_supported"
    if "insufficient" in (p, e):
        return "insufficient_evidence"
    return "neither_supported"


# ───────────── 生成 ─────────────
def generate(out: str) -> dict:
    _paths()
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(out, "_gen_unused.db"))
    from openpyxl import load_workbook
    from app.api.v11 import PRE_TEMPLATE_COLUMNS, build_pre_template
    from app.services import recon_import_service as RI
    from app.services.ssui_post_service import build_template as ssui_template
    import ssui_v11 as SV
    os.makedirs(out, exist_ok=True)
    ss = np.random.SeedSequence(SEED)
    streams = dict(zip(["PRE", *SCENARIOS, "FIX"], [np.random.default_rng(s) for s in ss.spawn(2 + len(SCENARIOS))]))
    W = SV.load_weights(ROOT)
    off = _gb36600_official()
    organics = [r for r in off if r["table"] == "表1" and r["group"] != "重金属和无机物"]
    meta = {"label": LABEL, "generator": GEN_VERSION, "seed": SEED, "numpy": np.__version__,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "param_source": PARAM_SOURCE, "n_points_per_site": N_POINTS,
            "distributions": {"metals": "对数正态, 中位数×GSD, Gaussian copula 相关", "metal_gsd": GSD,
                              "metal_corr_order": METALS, "metal_corr": METAL_CORR.tolist(), "pre_median": PRE_MEDIAN,
                              "pH_pre_normal": PH_PRE, "pH_post_normal": PH_POST,
                              "SOC": "对数正态 中位数15 g/kg GSD1.3, 截断[3,60]", "C:N": "正态(10,1.2) 截断[7,14]; TN=SOC/C:N",
                              "CEC": "4+0.55·SOC+N(0,1.5)", "盐渍化等级": "由含盐量派生: <1 无、轻度; 1–3 轻度、中度; >3 中度、重度(场景假设)",
                              "categorical": "多项分布(概率见源码 _recon_point)", "SSUI 得分 s_i": "Beta(a,b), 各场景见 scenarios",
                              "organics_post": "表1 VOC/SVOC 38 项, 取第一类筛选值的 1%–5% 均匀分布(低于筛选值)",
                              "removal(仅场地A)": "修复后 = 修复前 × (1−r), r~Beta(7,3)"},
            "constraints": ["浓度非负", "pH∈[4.5,8.5]", "场地 C: 修复后 Cd 下限 3.1 mg/kg(>水田管制值 3.0)",
                            "场地 D: 修复后 As 下限 125 mg/kg(>GB15618 与 GB36600 一类管制值 120)"],
            "stage_assumptions": ["修复前文件只进入课题一/二; 修复后文件只经课题三导入",
                                  "场地 A 的修复前/后为显式生成的关联情景, 不代表真实修复效果",
                                  f"课题三 t={T_YEARS} 年, 管理强度 {INTENSITY}; 生产门禁农用地类型 {FARMLAND}; 生态 {ECO_CLASS}"],
            "units": {"重金属/有机物": "mg/kg", "全氮/有机碳": "g/kg", "有效磷/速效钾": "mg/kg", "CEC": "cmol(+)/kg",
                      "有效土层": "cm", "地下水埋深": "m", "坡度": "°"},
            "scenarios": {}, "files": {}, "fixtures": {}, "import_order": [
                "1 场地管理→数据导入: 01_修复前检测数据(创建场地, 课题一 KOS)",
                "2 课题二重构指标导入: 02_课题二重构指标(修复前)",
                "3 课题三: 03_课题三SSUI_生产, 04_课题三SSUI_生态(修复后)",
                "4 利用方向结论: 修复前情景 + 修复后结论",
                "5 报告导出 / 全流程追溯"],
            "usage_rule": "仅用于测试/演示; 只能导入独立演示库或演示账号; 所有结果显示模拟数据标签; 不得用于正式报告或模型训练"}
    expected = {"generator": GEN_VERSION, "seed": SEED, "method": "独立实现(不调用 SRS 评价代码)", "scenarios": {}}
    for code, sc in SCENARIOS.items():
        rng = streams[code]
        d = os.path.join(out, f"site_{code}")
        os.makedirs(d, exist_ok=True)
        site_code = f"MCDEMO-{code}"
        pre_m = _metals(rng, PRE_MEDIAN, N_POINTS)
        # 01 修复前(课题一 KOS 检测表)
        wb = load_workbook(io.BytesIO(build_pre_template())); ws = wb["检测数据"]
        recon_pts = []
        for i in range(N_POINTS):
            rp = _recon_point(rng, i, pre_m[i]); recon_pts.append(rp)
            row = {"采样点编号": f"{code}{i + 1:02d}", "经度": round(120.10 + 0.05 * ord(code) % 1 + rng.uniform(0, 0.02), 6),
                   "纬度": round(30.20 + rng.uniform(0, 0.02), 6), "深度_上限(cm)": 0, "深度_下限(cm)": 20, "土壤类型": "水稻土",
                   "pH": rp["ph"], "镉_Cd(mg/kg)": rp["cd"], "汞_Hg(mg/kg)": rp["hg"], "砷_As(mg/kg)": rp["as"],
                   "铅_Pb(mg/kg)": rp["pb"], "铬_Cr(mg/kg)": rp["cr"], "铜_Cu(mg/kg)": rp["cu"], "镍_Ni(mg/kg)": rp["ni"],
                   "锌_Zn(mg/kg)": rp["zn"], "六价铬_Cr(VI)(mg/kg)": rp["cr6"], "有机质(g/kg)": round(rp["soc"] * 1.724, 2),
                   "全氮(g/kg)": rp["total_n"], "阳离子交换量(cmol/kg)": rp["cec"], "备注": LABEL}
            for c, h in enumerate(PRE_TEMPLATE_COLUMNS, 1):
                ws.cell(i + 2, c, row.get(h))
        wb["说明"].cell(8, 1, f"本文件为{LABEL}; 生成器 {GEN_VERSION}, 种子 {SEED}, 场景 {code}: {sc['title']}")
        f1 = os.path.join(d, f"01_{site_code}_修复前检测数据_{FILE_LABEL}.xlsx"); wb.save(f1)
        # 02 课题二 重构指标
        # 场地编号 B2 留空: 修复前导入时系统分配编号(SRS-<字母>), 留空即以页面所选场地为准, 演示时无需改表
        wb = load_workbook(io.BytesIO(RI.build_template("")))
        m = wb["批次信息"]; m["B4"] = LABEL; m["B5"] = RI.PROVENANCE["verified"]; m["B6"] = "水田"; m["B7"] = ECO_CLASS
        m["B8"] = f"{GEN_VERSION} seed={SEED} 场景{code}"
        ws = wb["指标数据"]
        for i, rp in enumerate(recon_pts):
            ws.cell(i + 2, 1, f"{code}{i + 1:02d}")
            for j, fid in enumerate(RI.TEMPLATE_FEATURES, 2):
                ws.cell(i + 2, j, rp.get(fid))
        f2 = os.path.join(d, f"02_{site_code}_课题二重构指标_{FILE_LABEL}.xlsx"); wb.save(f2)
        # 修复后点位
        if sc.get("linked_pre"):
            r = rng.beta(7, 3, size=N_POINTS)
            post_m = [{k: round(pre_m[i][k] * (1 - r[i]) * (0.25 if k in ("cd", "pb", "as") else 1), 4) for k in pre_m[i]}
                      for i in range(N_POINTS)]
        else:
            post_m = _metals(rng, sc["post_median"], N_POINTS)
        for pm in post_m:
            if "cd_floor" in sc:
                pm["cd"] = max(pm["cd"], sc["cd_floor"])
            if "as_floor" in sc:
                pm["as"] = max(pm["as"], sc["as_floor"])
        post_pts = []
        for i, pm in enumerate(post_m):
            pt = {"point": f"{code}P{i + 1:02d}", "pH": round(float(np.clip(rng.normal(*PH_POST), 6.55, 7.45)), 2)}
            for k, v in pm.items():
                pt[SYM[k]] = v
            if sc["crvi"] is not None:
                pt["Cr(VI)"] = round(float(sc["crvi"] * math.exp(rng.normal(0, .3))), 3)
            if sc["organics"]:
                for org in organics:
                    pt[org["pollutant"]] = round(float(org["screening_cat1"]) * float(rng.uniform(0.01, 0.05)), 6)
            post_pts.append(pt)
        ssui_files, exp_ssui = {}, {}
        for track, cn in (("production", "生产"), ("ecology", "生态")):
            wb = load_workbook(io.BytesIO(ssui_template(track, "")))
            mm = wb["批次信息"]; mm["B4"] = 2026; mm["B5"] = T_YEARS; mm["B6"] = INTENSITY; mm["B8"] = LABEL
            mm["B9"] = f"{GEN_VERSION} seed={SEED} 场景{code}"
            s = wb["指标得分"]
            a, b = sc["ssui_beta"][track]
            scores = [round(float(rng.beta(a, b)), 4) for _ in range(25)]
            for r_, sv in enumerate(scores, 2):
                s.cell(r_, 7, sv); s.cell(r_, 8, f"{LABEL}; 得分录入模式")
            p = wb["修复后污染物检测"]; p.delete_rows(2, 1)
            r_ = 2
            for pt in post_pts:
                for k, v in pt.items():
                    if k in ("point", "pH"):
                        continue
                    name = {"Cd": "镉", "Hg": "汞", "As": "砷", "Pb": "铅", "Cr": "铬", "Cu": "铜", "Ni": "镍", "Zn": "锌",
                            "Cr(VI)": "六价铬"}.get(k, k)
                    p.cell(r_, 1, pt["point"]); p.cell(r_, 2, pt["pH"]); p.cell(r_, 3, name); p.cell(r_, 4, v)
                    p.cell(r_, 5, "mg/kg"); p.cell(r_, 6, "2026-09-15"); p.cell(r_, 7, LABEL); r_ += 1
            fp = os.path.join(d, f"0{3 if track == 'production' else 4}_{site_code}_课题三SSUI_{cn}_{FILE_LABEL}.xlsx")
            wb.save(fp); ssui_files[track] = fp
            # 期望 SSUI(独立实现, 方法 PPT 第13–15页)
            inds = W["indicators"]
            by_c: dict = {}
            for ind, sv in zip(inds, scores):
                by_c.setdefault(ind["criterion"], 0.0)
                by_c[ind["criterion"]] += ind["w_" + track] * sv
            crit = W["criterion_weights"][track]
            M = {"production": 1.15, "ecology": 1.075}[track]
            ssui = (1 + 0.03 * T_YEARS) * sum(crit[c] * v for c, v in by_c.items()) * M
            exp_ssui[track] = {"ssui": round(ssui, 6), "feasible_threshold_provisional": 0.6, "feasible": ssui >= 0.6,
                               "criterion_scores": {c: round(v, 6) for c, v in by_c.items()}, "M": M, "t": T_YEARS}
        pg, eg = expected_gates(post_pts, sc["organics"], sc["crvi"] is not None)
        econ = _economics(rng, code)
        json.dump(econ, open(os.path.join(d, f"05_{site_code}_场地经济输入_{FILE_LABEL}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        expected["scenarios"][code] = {
            "title": sc["title"], "site_code_template": site_code,
            "post_gates": {"production": pg, "ecology": eg},
            "post_decision": expected_decision(pg, eg, exp_ssui["production"]["feasible"], exp_ssui["ecology"]["feasible"]),
            "ssui": exp_ssui, "economics": econ,
            "recon_points": N_POINTS, "recon_features_provided": len(RI.TEMPLATE_FEATURES)}
        meta["scenarios"][code] = {"title": sc["title"], "design": {k: v for k, v in sc.items() if k != "title"}}
        for f in (f1, f2, *ssui_files.values(), os.path.join(d, f"05_{site_code}_场地经济输入_{FILE_LABEL}.json")):
            meta["files"][os.path.relpath(f, out)] = _sha(f)
    # ───── 边界/错误夹具 ─────
    rng = streams["FIX"]
    fx = os.path.join(out, "fixtures"); os.makedirs(fx, exist_ok=True)
    base_rows = [_recon_point(rng, i, _metals(rng, PRE_MEDIAN, 1)[0]) for i in range(4)]

    def recon_file(name, mutate=None, stage="修复前"):
        wb = load_workbook(io.BytesIO(RI.build_template("")))
        m = wb["批次信息"]; m["B3"] = stage; m["B4"] = LABEL; m["B5"] = RI.PROVENANCE["verified"]
        ws = wb["指标数据"]
        rows = [dict(r) for r in base_rows]
        if mutate:
            rows = mutate(rows)
        for i, rp in enumerate(rows):
            ws.cell(i + 2, 1, rp.get("_label", f"FX{i + 1:02d}"))
            for j, fid in enumerate(RI.TEMPLATE_FEATURES, 2):
                ws.cell(i + 2, j, rp.get(fid))
        path = os.path.join(fx, name); wb.save(path)
        return path

    def bad_cat(rows):
        rows[1]["texture"] = "很黏"; return rows

    def dup_point(rows):
        rows[2]["_label"] = "FX01"; return rows

    def unit_err(rows):
        rows[0]["ph"] = 72; return rows   # pH 填成 72(疑似漏小数点) → 物理范围错误

    def const_col(rows):
        for r in rows:
            r["avail_k"] = 150.0
        return rows

    def single(rows):
        return rows[:1]

    fixtures = {
        "F01_wrong_stage": (recon_file("F01_课题二_阶段填修复后_应拒绝.xlsx", stage="修复后"), "error", "数据阶段"),
        "F02_invalid_category": (recon_file("F02_课题二_非法类别_应拒绝.xlsx", bad_cat), "error", "无法识别的类别"),
        "F03_duplicate_point": (recon_file("F03_课题二_点位重复_应拒绝.xlsx", dup_point), "error", "重复"),
        "F04_unit_error_pH": (recon_file("F04_课题二_pH超物理范围_应拒绝.xlsx", unit_err), "error", "超出物理范围"),
        "F05_constant_column": (recon_file("F05_课题二_常数列_仅告警.xlsx", const_col), "warning", "常数列"),
        "F06_single_row": (recon_file("F06_课题二_单点位_仅告警.xlsx", single), "warning", "仅 1 个点位"),
    }
    # F07 课题三 单位错误: 浓度单位 μg/kg 写成 'ppm'
    wb = load_workbook(io.BytesIO(ssui_template("production", "")))
    mm = wb["批次信息"]; mm["B4"] = 2026; mm["B5"] = 2; mm["B6"] = INTENSITY; mm["B8"] = LABEL
    s = wb["指标得分"]
    for r_ in range(2, 27):
        s.cell(r_, 7, 0.7)
    p = wb["修复后污染物检测"]; p.delete_rows(2, 1)
    p.cell(2, 1, "FXP1"); p.cell(2, 2, 6.8); p.cell(2, 3, "镉"); p.cell(2, 4, 0.2); p.cell(2, 5, "ppm")
    f7 = os.path.join(fx, "F07_课题三_浓度单位非mgkg_应拒绝.xlsx"); wb.save(f7)
    fixtures["F07_post_unit_error"] = (f7, "error", "单位")
    # F08 重复导入: 复用场地 A 的课题二文件(第二次上传应被拒绝)
    fixtures["F08_duplicate_import"] = (os.path.join(out, "site_A", f"02_MCDEMO-A_课题二重构指标_{FILE_LABEL}.xlsx"), "error_on_second", "已在批次")
    for k, (path, kind, msg) in fixtures.items():
        meta["fixtures"][k] = {"file": os.path.relpath(path, out), "expect": kind, "message_contains": msg}
        if not k.startswith("F08"):
            meta["files"][os.path.relpath(path, out)] = _sha(path)
    expected["fixtures"] = meta["fixtures"]
    json.dump(meta, open(os.path.join(out, "metadata.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(expected, open(os.path.join(out, "expected.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta


def run(out: str, db: str) -> dict:
    """在独立演示库中经 HTTP API(进程内 TestClient)执行完整导入顺序, 与 expected.json 比对。"""
    p = os.path.abspath(db)
    if not os.path.basename(p).startswith("srs_demo") or "AppData" in p or "Application Support/SRS" in p:
        raise SystemExit(f"拒绝写入: 演示库文件名须以 srs_demo 开头且不得为用户默认库 ({p})")
    os.environ["DATABASE_URL"] = "sqlite:///" + p
    os.environ.setdefault("SECRET_KEY", "demo_only_key_" + "x" * 40)
    _paths()
    sys.path.insert(0, os.path.join(ROOT, "packaging", "ci"))
    from fastapi.testclient import TestClient
    from app.main import app
    import demo_runner as DR
    with TestClient(app) as c:
        return DR.run_all(DR.Http(c, ""), out, os.path.join(out, "actual"), admin=("admin", "Demo@Run2026x"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["generate", "run"])
    ap.add_argument("--out", default=os.path.join(ROOT, "demo", "mc_v12"))
    ap.add_argument("--db")
    a = ap.parse_args()
    if a.cmd == "generate":
        m = generate(a.out)
        print(json.dumps({"files": len(m["files"]), "fixtures": list(m["fixtures"])}, ensure_ascii=False))
    else:
        if not a.db:
            raise SystemExit("run 需要 --db 指定独立演示库")
        r = run(a.out, a.db)
        print(json.dumps(r["summary"], ensure_ascii=False, indent=1))
