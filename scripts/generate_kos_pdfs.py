#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generate_kos_pdfs.py — 用 reportlab 从 KOS 诊断结果直接生成 6 份 PDF
"""
import os, sys, json, requests
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
BASE = "http://127.0.0.1:8000/api/v1"
OUT = "artifacts/demo_reports_round4"
os.makedirs(OUT, exist_ok=True)
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

# 注册中文字体
for fp, name in [("C:/Windows/Fonts/simsun.ttc", "SimSun"), ("C:/Windows/Fonts/simhei.ttf", "SimHei")]:
    try: pdfmetrics.registerFont(TTFont(name, fp))
    except: pass
CN = "SimSun" if "SimSun" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
CN_B = "SimHei" if "SimHei" in pdfmetrics.getRegisteredFontNames() else CN


def login():
    r = requests.post(f"{BASE}/auth/login", json={"username": "admin", "password": "Demo@2026"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

def run_kos(H, sid, track, subset):
    r = requests.post(f"{BASE}/sites/{sid}/kos-diagnosis?track={track}&subset={subset}", headers=H, timeout=60)
    return r.json() if r.status_code == 200 else {}


def gen_pdf(kos, site_name, track_label, filename):
    fp = os.path.join(OUT, filename)
    doc = SimpleDocTemplate(fp, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName=CN_B, fontSize=16, alignment=1, spaceAfter=12)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName=CN_B, fontSize=12, spaceBefore=10, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName=CN, fontSize=10, leading=14)
    cell = ParagraphStyle("cell", fontName=CN, fontSize=8, leading=10)
    elems = []

    elems.append(Paragraph(f"污染场地障碍因子诊断报告", h1))
    elems.append(Paragraph(f"{site_name} · {track_label}", h2))
    elems.append(Paragraph(f"生成时间:{NOW} | 数据版本:{kos.get('data_version','—')} | 模型:{kos.get('model_id','—')}", body))
    elems.append(Spacer(1, 0.5*cm))

    # 明确障碍
    elems.append(Paragraph("一、明确障碍因子(规则判定超标)", h2))
    eo = kos.get("explicit_obstacles", [])
    if eo:
        t = Table([["因子","实测值","严重度R"]] + [[Paragraph(str(e.get("factor","")),cell), str(round(e.get("value",0),3)), str(round(e.get("severity_R",0),3))] for e in eo])
        t.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),CN),("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.5,colors.grey),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e6f7ff"))]))
        elems.append(t)
    else:
        elems.append(Paragraph("无明确超标因子。", body))

    # 关键障碍 Top-N
    elems.append(Paragraph("二、关键障碍因子 Top-N(KOS 排序)", h2))
    ko = kos.get("key_obstacles", [])
    if ko:
        rows = [["排名","因子","KOS","实测值","证据"]]
        for k in ko:
            rows.append([str(k.get("rank","")), Paragraph(str(k.get("factor","")),cell), str(round(k.get("KOS",0),4)), str(round(k.get("value",0),3)), str(k.get("evidence",""))])
        t = Table(rows)
        t.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),CN),("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.5,colors.grey),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#fff7e6"))]))
        elems.append(t)
        elems.append(Paragraph("KOS = B×(0.30R+0.25W+0.15M+0.20S+0.10E),非因果非障碍高度。", body))
    else:
        elems.append(Paragraph("无关键障碍因子。", body))

    # 模型关注
    elems.append(Paragraph("三、模型关注因子(需专家复核)", h2))
    ma = [m for m in kos.get("model_attention_factors", []) if m.get("layer") == "model_attention"]
    if ma:
        rows = [["因子","模型贡献M","原因"]]
        for m in ma[:10]:
            rows.append([Paragraph(str(m.get("factor","")),cell), str(round(m.get("M",0),4)), Paragraph(str(m.get("reason",""))[:25],cell)])
        t = Table(rows)
        t.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),CN),("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.5,colors.grey)]))
        elems.append(t)
    else:
        elems.append(Paragraph("无模型关注因子。", body))

    # 族群+未知
    fw = kos.get("family_warnings", [])
    ua = kos.get("unknown_alerts", [])
    elems.append(Paragraph(f"四、族群预警({len(fw)})/未知物({len(ua)})", h2))
    if fw:
        rows = [["物质","浓度","族群","说明"]]
        for f in fw[:8]:
            rows.append([Paragraph(str(f.get("name","")),cell), str(round(f.get("value",0),3)), str(f.get("family","")), Paragraph(str(f.get("note",""))[:20],cell)])
        elems.append(Table(rows, style=[("FONTNAME",(0,0),(-1,-1),CN),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),0.5,colors.grey)]))
    if ua:
        elems.append(Paragraph(f"完全未知({len(ua)}项,建议送检):", body))
        rows = [["物质","浓度","说明"]]
        for u in ua[:8]:
            rows.append([Paragraph(str(u.get("name","")),cell), str(round(u.get("value",0),3)), Paragraph(str(u.get("note",""))[:20],cell)])
        elems.append(Table(rows, style=[("FONTNAME",(0,0),(-1,-1),CN),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),0.5,colors.grey)]))

    # 补测
    elems.append(Paragraph("五、建议补测因子", h2))
    rt = kos.get("recommended_tests", [])
    if rt:
        rows = [["因子","原因","证据"]]
        for r in rt[:10]:
            rows.append([Paragraph(str(r.get("factor","")),cell), Paragraph(str(r.get("reason",""))[:25],cell), str(r.get("evidence",""))])
        elems.append(Table(rows, style=[("FONTNAME",(0,0),(-1,-1),CN),("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.5,colors.grey)]))
    else:
        elems.append(Paragraph("无补测建议。", body))

    # 质量标记
    elems.append(Paragraph("六、数据质量与复核", h2))
    for f in kos.get("data_quality_flags", []):
        elems.append(Paragraph(f"⚠ {f}", body))
    elems.append(Paragraph(f"需人工复核:{'是' if kos.get('review_required') else '否'}", body))
    elems.append(Paragraph(f"局限性:{kos.get('limitations','—')}", body))

    doc.build(elems)
    return fp


def main():
    H = login()
    reports = [
        (1,"prod","hm","云南个旧重金属场地","生产用途","1_HM生产用途诊断报告.pdf"),
        (1,"eco","hm","云南个旧重金属场地","生态用途","2_HM生态用途诊断报告.pdf"),
        (2,"prod","op","南京栖霞有机污染场地","生产用途","3_OP生产用途诊断报告.pdf"),
        (2,"eco","op","南京栖霞有机污染场地","生态用途","4_OP生态用途诊断报告.pdf"),
        (3,"prod","all","乡村建设用地复合污染场地","生产用途(复合)","5_HM+OP复合污染诊断报告.pdf"),
        (1,"prod","hm","云南个旧重金属场地","追溯档案样例Alpha","6_追溯档案样例_Alpha.pdf"),
    ]
    print("="*60)
    print("KOS PDF 报告生成(6 份)")
    print("="*60)
    gen = []
    for sid,track,subset,sname,tlabel,fname in reports:
        kos = run_kos(H, sid, track, subset)
        if kos:
            fp = gen_pdf(kos, sname, tlabel, fname)
            sz = os.path.getsize(fp)
            print(f"  ✅ {fname}: {sz//1024}KB key={len(kos.get('key_obstacles',[]))}")
            gen.append(fname)
        else:
            print(f"  ❌ {fname}: API失败")
    with open(os.path.join(OUT,"report_manifest.json"),"w",encoding="utf-8") as f:
        json.dump({"generated":gen,"total":len(gen),"time":NOW,"format":"pdf"},f,ensure_ascii=False,indent=2)
    print(f"\n生成 {len(gen)}/6 份 PDF → {OUT}/")


if __name__ == "__main__":
    main()
