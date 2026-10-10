"""SRS v1.2.2 演示数据: 场地 H —— 方案推荐 + 五阶段业务追溯(模拟数据——仅供测试/演示)。

不改动 A–G 的任何文件。生成:
  cases_v122/H/01_MCDEMO-H_五阶段追溯_修复前检测数据_模拟数据_仅供测试演示.xlsx
      重金属(镉/铅)超过 GB 15618-2018 “其他”类筛选值; pH 全部落在 5.5<pH≤6.5 同一档,
      便于独立核算超标倍数(阈值读官方 CSV, 不调用 SRS 评价代码)。
  cases_v122/H/attachments/*.pdf  五个业务阶段各一份模拟材料 + 施工监理退回后的修订稿,
      每页水印“模拟材料——仅供测试/演示, 非真实审批文件”; 审核人一律为“模拟审核员”, 不冒用真实机构或官员。
  metadata.json["cases_v122"]  文件指纹、阶段操作脚本(谁上传/谁审核/意见)、角色检查与期望。

用法: python scripts/mc_demo_v122_workflow.py --out demo/mc_v12
随机流: numpy SeedSequence([20261009, 1222]) — 与 A–G 的流独立。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from mc_demo_v121_cases import PRE_COLS, _gb15618_other  # noqa: E402

LABEL = "模拟数据——仅供测试/演示"
FILE_LABEL = "模拟数据_仅供测试演示"
DOC_MARK = "模拟材料——仅供测试/演示, 非真实审批文件"
SEED = 20261009
GEN_VERSION = "mc_demo_v122_workflow.1"
N = 12

# 演示账户(均为模拟身份; 密码只用于本地/CI 独立演示库)
USERS = {
    "enterprise": {"username": "demo_h_enterprise", "display_name": "模拟企业填报员（演示）", "role": "enterprise",
                   "organization_name": "模拟修复责任企业H（演示）", "via": "register+approve"},
    "reviewer": {"username": "demo_h_reviewer", "display_name": "模拟审核员（synthetic reviewer）", "role": "admin",
                 "via": "system/users"},
    "regulator": {"username": "demo_h_regulator", "display_name": "模拟监管查看员（演示）", "role": "regulator",
                  "via": "system/users"},
    "other_enterprise": {"username": "demo_h_other_ent", "display_name": "模拟其他企业用户（演示）", "role": "enterprise",
                         "organization_name": "模拟无关企业（演示）", "via": "register+approve"},
}
DEMO_PASSWORD = "Demo@H2026!"

STAGES = [
    ("survey", "调查评估", "调查评估报告", "H1_调查评估报告_模拟材料.pdf",
     "模拟数据: 场地 H 初步调查与详细调查(12 个模拟采样点)", "模拟审核: 调查点位与检测项目齐全, 同意进入方案审批"),
    ("approval", "方案审批", "修复方案及审批意见", "H2_修复方案与比选_模拟材料.pdf",
     "模拟数据: 基于系统推荐结果的方案比选", "模拟审核: 同意按选定方案实施(演示, 非真实批复)"),
    ("construction", "施工监理", "施工监理记录", "H3_施工监理记录_模拟材料.pdf",
     "模拟数据: 施工日志与监理记录", "模拟审核: 修订稿已补充第 2 批次监理记录, 同意"),
    ("effect", "效果评估", "效果评估报告", "H4_效果评估报告_模拟材料.pdf",
     "模拟数据: 修复后采样与效果评估", "模拟审核: 效果评估材料齐全(演示)"),
    ("maintenance", "后期管护", "后期管护计划", "H5_后期管护计划_模拟材料.pdf",
     "模拟数据: 管护与跟踪监测计划", "模拟审核: 管护计划已备案(演示)"),
]
RETURN = {"stage": "construction", "reason": "模拟退回: 缺少第 2 批次施工监理记录, 请补充后重新提交",
          "revision_file": "H3b_施工监理记录_修订稿_模拟材料.pdf"}


CN = {"Cd_mgkg": "镉", "Pb_mgkg": "铅", "Hg_mgkg": "汞", "As_mgkg": "砷", "Cr_mgkg": "铬", "Cu_mgkg": "铜",
      "Ni_mgkg": "镍", "Zn_mgkg": "锌"}


def _sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def _pdf(path: str, title: str, lines: list[str]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    c = canvas.Canvas(path, pagesize=A4, invariant=1)
    c.setTitle(title); c.setAuthor("SRS demo generator (synthetic)"); c.setSubject(DOC_MARK)
    w, h = A4
    c.saveState(); c.setFillColorRGB(0.85, 0.85, 0.85); c.setFont("STSong-Light", 30)
    c.translate(w / 2, h / 2); c.rotate(35)
    for dy in (-200, 0, 200):
        c.drawCentredString(0, dy, DOC_MARK)
    c.restoreState()
    c.setFont("STSong-Light", 16); c.drawString(60, h - 80, title)
    c.setFont("STSong-Light", 10.5); c.setFillColorRGB(0.7, 0.1, 0.1); c.drawString(60, h - 102, DOC_MARK)
    c.setFillColorRGB(0, 0, 0); y = h - 135
    for ln in lines:
        c.drawString(60, y, ln); y -= 18
    c.drawString(60, 60, f"生成器 {GEN_VERSION}; 本文件不代表任何真实单位、人员或审批结论。")
    c.showPage(); c.save()


def generate(out: str) -> dict:
    from openpyxl import Workbook
    rng = np.random.default_rng(np.random.SeedSequence([SEED, 1222]))
    d = os.path.join(out, "cases_v122", "H"); ad = os.path.join(d, "attachments")
    os.makedirs(ad, exist_ok=True)
    rows = []
    for i in range(N):
        ph = round(float(rng.uniform(5.8, 6.3)), 2)
        lim = _gb15618_other(ph)
        r = {"采样点编号": f"H{i + 1:02d}", "经度": round(120.6 + rng.uniform(0, .02), 6), "纬度": round(30.6 + rng.uniform(0, .02), 6),
             "深度_上限(cm)": 0, "深度_下限(cm)": 20, "土壤类型": "水稻土", "pH": ph}
        for col, f in (("汞_Hg(mg/kg)", "Hg"), ("砷_As(mg/kg)", "As"), ("铬_Cr(mg/kg)", "Cr"), ("铜_Cu(mg/kg)", "Cu"),
                       ("镍_Ni(mg/kg)", "Ni"), ("锌_Zn(mg/kg)", "Zn")):
            r[col] = round(lim[f] * float(rng.uniform(0.2, 0.6)), 4)
        r["镉_Cd(mg/kg)"] = round(lim["Cd"] * float(rng.uniform(1.5, 4.0)), 4)
        r["铅_Pb(mg/kg)"] = round(lim["Pb"] * float(rng.uniform(0.9, 1.8)), 3)
        r["六价铬_Cr(VI)(mg/kg)"] = round(float(rng.uniform(0.1, 0.5)), 3)
        r["有机质(g/kg)"] = round(float(rng.uniform(18, 30)), 2)
        r["全氮(g/kg)"] = round(float(rng.uniform(1.2, 2.0)), 3)
        r["阳离子交换量(cmol/kg)"] = round(float(rng.uniform(12, 20)), 2)
        rows.append(r)
    wb = Workbook(); ws = wb.active; ws.title = "检测数据"; ws.append(PRE_COLS)
    for r in rows:
        ws.append([r.get(c) for c in PRE_COLS])
    g = wb.create_sheet("说明")
    g.cell(1, 1, f"本文件为{LABEL}; 生成器 {GEN_VERSION}, 种子 SeedSequence([{SEED}, 1222]); 场景 H: 方案推荐 + 五阶段追溯")
    fH = os.path.join(d, f"01_MCDEMO-H_五阶段追溯_修复前检测数据_{FILE_LABEL}.xlsx")
    wb.save(fH)
    lim = _gb15618_other(6.0)
    exp_off = {}
    for col, key, f in (("镉_Cd(mg/kg)", "Cd_mgkg", "Cd"), ("铅_Pb(mg/kg)", "Pb_mgkg", "Pb"), ("汞_Hg(mg/kg)", "Hg_mgkg", "Hg"),
                        ("砷_As(mg/kg)", "As_mgkg", "As"), ("铬_Cr(mg/kg)", "Cr_mgkg", "Cr"), ("铜_Cu(mg/kg)", "Cu_mgkg", "Cu"),
                        ("镍_Ni(mg/kg)", "Ni_mgkg", "Ni"), ("锌_Zn(mg/kg)", "Zn_mgkg", "Zn")):
        mx = max(r[col] for r in rows)
        if mx > lim[f]:
            exp_off[key] = {"max_mgkg": mx, "screening_mgkg": lim[f], "ratio": round(mx / lim[f], 4)}
    files = {}
    for code, name, role, fn, src, comment in STAGES:
        p = os.path.join(ad, fn)
        _pdf(p, f"场地 MCDEMO-H {name}（{role}）", [
            f"阶段: {name} ({code})", f"材料类型: {role}", f"数据来源: {src}",
            "填报: 模拟企业填报员（演示）", "审核: 模拟审核员（synthetic reviewer）",
            f"计划审核意见: {comment}", "", "本材料用于验证五阶段追溯功能: 上传→审核→追溯到报告。"])
        files[os.path.relpath(p, out)] = None
    p = os.path.join(ad, RETURN["revision_file"])
    _pdf(p, "场地 MCDEMO-H 施工监理（施工监理记录 修订稿）", [
        "阶段: 施工监理 (construction) — 修订稿", f"退回原因: {RETURN['reason']}", "补充: 第 2 批次施工监理记录(模拟)",
        "填报: 模拟企业填报员（演示）"])
    files[os.path.relpath(p, out)] = None
    files[os.path.relpath(fH, out)] = None
    files = {k: _sha(os.path.join(out, k)) for k in files}
    case = {
        "title": "方案推荐 + 五阶段业务追溯(生产轨 GB 15618 其他)", "file": os.path.relpath(fH, out),
        "kos": {"track": "prod", "subset": "hm", "farmland_type": "其他"},
        "expected": {"official_factors": sorted(exp_off), "official_detail": exp_off,
                     # 推荐引擎以中文因子名匹配技术库(镉/铅…), 与 KOS 代码(Cd_mgkg…)一一对应
                     "recommendation": {"min_candidates": 1,
                                        "top_must_match_any": sorted(CN[k] for k in exp_off)},
                     "business_completed": 5, "business_with_documents": 5, "n_attachments": len(STAGES) + 1},
        "users": USERS, "password": DEMO_PASSWORD,
        "stages": [{"stage": c, "name": n, "file_role": r, "file": os.path.relpath(os.path.join(ad, fn), out),
                    "data_source": s, "review_comment": m} for c, n, r, fn, s, m in STAGES],
        "return_cycle": {**RETURN, "revision_file": os.path.relpath(os.path.join(ad, RETURN["revision_file"]), out)},
        "role_checks": [
            {"who": "regulator", "action": "update_stage", "expect_status": 403},
            {"who": "regulator", "action": "upload_attachment", "expect_status": 403},
            {"who": "regulator", "action": "view_workflow", "expect_status": 200},
            {"who": "regulator", "action": "download_attachment", "expect_status": 200},
            {"who": "other_enterprise", "action": "view_workflow", "expect_status": 403},
            {"who": "other_enterprise", "action": "download_attachment", "expect_status": 403},
            {"who": "reviewer", "action": "complete_from_not_started", "expect_status": 400},
            {"who": "reviewer", "action": "return_without_reason", "expect_status": 400},
            {"who": "enterprise", "action": "spoof_operator_id", "expect": "operator recorded as the authenticated user"},
        ],
        "limitations": ["产品当前无独立“审核”权限: 具备 data:input 的企业/机构用户也可把阶段标记为完成; "
                        "本演示由管理员角色的“模拟审核员”执行审核动作, 职责分离需业主决定是否增加 workflow:review 权限。"],
    }
    # ── P: 邻苯二甲酸酯单体/总量(T02) — 固定值, 期望由 GB 36600 官方 CSV 独立判定 ──
    import csv
    off = {r["pollutant"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "standards", "gb36600_2018_official.csv"),
                                                          encoding="utf-8"))}
    dP = os.path.join(out, "cases_v122", "P"); os.makedirs(dP, exist_ok=True)
    hdr = ["采样点编号", "经度", "纬度", "深度_上限(cm)", "深度_下限(cm)", "土壤类型", "pH",
           "邻苯二甲酸酯总量_PAEs(mg/kg)", "邻苯二甲酸二(2-乙基己基)酯(mg/kg)", "邻苯二甲酸二正辛酯(μg/kg)", "邻苯二甲酸二甲酯(mg/kg)"]
    vals = {"DEHP_mgkg": 50.0, "DnOP_ugkg": 50000.0, "PAEs_total_mgkg": 50.0, "DMP_mgkg": 5.0}
    wb = Workbook(); ws = wb.active; ws.title = "检测数据"; ws.append(hdr)
    for i in range(6):
        ws.append([f"P{i + 1:02d}", round(120.8 + i / 1000, 6), 30.8, 0, 20, "潮土", 7.0, vals["PAEs_total_mgkg"], vals["DEHP_mgkg"],
                   vals["DnOP_ugkg"], vals["DMP_mgkg"]])
    wb.create_sheet("说明").cell(1, 1, f"本文件为{LABEL}; 生成器 {GEN_VERSION}; 场景 P: 邻苯二甲酸酯单体/总量判定(固定值)")
    fP = os.path.join(dP, f"01_MCDEMO-P_邻苯二甲酸酯_修复前检测数据_{FILE_LABEL}.xlsx"); wb.save(fP)
    DEHP, DNOP = "邻苯二甲酸二(2-乙基己基)酯", "邻苯二甲酸二正辛酯"
    exp_p = {}
    for land, col in (("第一类用地", "screening_cat1"), ("第二类用地", "screening_cat2")):
        e = {}
        for name, v in ((DEHP, vals["DEHP_mgkg"]), (DNOP, vals["DnOP_ugkg"] / 1000.0)):
            lim = float(off[name][col])
            if v > lim:
                e[name] = {"cas": off[name]["cas"], "value_mgkg": v, "screening_mgkg": lim, "ratio": round(v / lim, 4)}
        exp_p[land] = {"official_factors": sorted(e), "official_detail": e,
                       "dnop_threshold_mgkg": float(off[DNOP][col]), "dnop_value_mgkg": vals["DnOP_ugkg"] / 1000.0}
    caseP = {"title": "邻苯二甲酸酯: 单体按 CAS 绑定官方值, 总量无官方值不判定, 未登记单体人工复核(生态轨 GB 36600)",
             "file": os.path.relpath(fP, out), "values": vals, "expected": exp_p,
             "identity": {"邻苯二甲酸酯总量": "family_total", DEHP: "117-81-7", DNOP: "117-84-0"},
             "must_be_unmapped_with_review": ["邻苯二甲酸二甲酯"], "must_not_judge": ["SumPAE_ugkg"]}
    files[os.path.relpath(fP, out)] = _sha(fP)
    meta_p = os.path.join(out, "metadata.json")
    meta = json.load(open(meta_p, encoding="utf-8"))
    meta["cases_v122"] = {"generator": GEN_VERSION, "seed": f"SeedSequence([{SEED}, 1222])", "label": LABEL,
                          "doc_mark": DOC_MARK, "cases": {"H": case, "P": caseP}, "files": files}
    json.dump(meta, open(meta_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return meta["cases_v122"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "demo", "mc_v12"))
    a = ap.parse_args()
    r = generate(a.out)
    print(json.dumps({"files": len(r["files"]), "expected": r["cases"]["H"]["expected"]}, ensure_ascii=False, indent=1))
