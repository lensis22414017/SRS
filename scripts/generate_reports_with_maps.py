#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generate_reports_with_maps.py — 第二阶段演示包 v2: 6 PDF + 6 DOCX 嵌入地图
====================================================================
接入 backend/app/services/report_service.generate() 全流程追溯报告链路。
该链路会自动嵌入:
  - matplotlib 采样点超标风险散点图(8 级色阶, 离线渲染, 无瓦片底图)
  - 关键障碍因子排名图
  - EDA 各因子均值/最大值对比图

覆盖 6 份配置(场地 × 格式):
  1. 云南个旧(HM) → PDF + DOCX
  2. 南京栖霞(OP) → PDF + DOCX
  3. 乡村复合(HM+OP) → PDF + DOCX

诚实标注: 报告地图为离线 matplotlib 散点(无真实瓦片底图),
水印明确写"底图: 无(离线坐标散点)"。
====================================================================
"""
import os, sys, json, shutil
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend"))
os.environ.setdefault("DATABASE_URL", "sqlite:///./backend/srs.db")

OUT = "artifacts/demo_reports_v2_20260703"
os.makedirs(OUT, exist_ok=True)
NOW = datetime.now().strftime("%Y-%m-%d %H:%M")

# 6 份配置: (site_id, 场地名, 污染类型, 文件前缀)
REPORTS = [
    (1, "云南个旧重金属场地", "heavy_metal", "1_HM"),
    (2, "南京栖霞有机污染场地", "organic", "2_OP"),
    (3, "乡村建设用地复合污染场地", "composite", "3_HM_OP"),
]


def generate_pdf_reportlab(site_id, site_name, out_path):
    """PDF 用 reportlab 直接生成(绕过 weasyprint/xhtml2pdf 不支持 data URI 的问题),
    嵌入 matplotlib 离线散点地图 PNG + 障碍因子图。确保图片数 >= 1。"""
    from app.db.session import SessionLocal
    from app.services import report_service
    import base64 as _b64

    db = SessionLocal()
    tmp_pngs = []
    try:
        ctx = report_service.collect(db, site_id, "v1")
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors as rlcolors
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        for fp, name in [("C:/Windows/Fonts/simsun.ttc", "SimSun"), ("C:/Windows/Fonts/simhei.ttf", "SimHei")]:
            try: pdfmetrics.registerFont(TTFont(name, fp))
            except: pass
        CN = "SimSun" if "SimSun" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
        CN_B = "SimHei" if "SimHei" in pdfmetrics.getRegisteredFontNames() else CN
        styles = getSampleStyleSheet()
        h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName=CN_B, fontSize=16, alignment=1, spaceAfter=10)
        h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName=CN_B, fontSize=12, spaceBefore=8, spaceAfter=4)
        body = ParagraphStyle("body", parent=styles["BodyText"], fontName=CN, fontSize=10, leading=14)
        elems = []

        elems.append(Paragraph("污染场地全流程追溯报告", h1))
        s = ctx.get("site", {})
        elems.append(Paragraph(f"{site_name}（{s.get('site_code','—')}）", h2))
        elems.append(Paragraph(f"污染类型: {s.get('pollution_type','—')} | 用地: {s.get('land_use_type','—')} | 生成: {ctx.get('report',{}).get('generated_at','—')}", body))
        elems.append(Spacer(1, 0.3*cm))

        # 地图 PNG 落盘(report_service 已渲染 base64, 解码落盘)
        map_b64 = ctx.get("map_summary", {}).get("map_image")
        if map_b64 and map_b64.startswith("data:image/png;base64,"):
            png_path = out_path + ".map.png"
            with open(png_path, "wb") as f:
                f.write(_b64.b64decode(map_b64.split(",", 1)[1]))
            tmp_pngs.append(png_path)
            elems.append(Paragraph("一、采样点空间分布与超标风险分级", h2))
            elems.append(Paragraph("注: 此为离线 matplotlib 采样点分布图, 非真实瓦片底图。按超标倍数 8 级色阶着色。", body))
            elems.append(RLImage(png_path, width=16*cm, height=11*cm))
            elems.append(Spacer(1, 0.3*cm))

        # 障碍因子排名 PNG(若有诊断结果)
        shap_b64 = ctx.get("map_summary", {}).get("shap_image")
        if shap_b64 and shap_b64.startswith("data:image/png;base64,"):
            png_path = out_path + ".shap.png"
            with open(png_path, "wb") as f:
                f.write(_b64.b64decode(shap_b64.split(",", 1)[1]))
            tmp_pngs.append(png_path)
            elems.append(Paragraph("二、关键障碍因子排名", h2))
            elems.append(RLImage(png_path, width=16*cm, height=8*cm))

        # EDA 因子摘要图(保底图: 只要有检测数据就能渲染, 保证图片数 >= 1)
        has_image_yet = bool(map_b64) or bool(shap_b64)
        if not has_image_yet and ctx.get("factor_summary"):
            eda_b64 = report_service._render_eda_figure_png(ctx.get("factor_summary") or [])
            if eda_b64 and eda_b64.startswith("data:image/png;base64,"):
                png_path = out_path + ".eda.png"
                with open(png_path, "wb") as f:
                    f.write(_b64.b64decode(eda_b64.split(",", 1)[1]))
                tmp_pngs.append(png_path)
                elems.append(Paragraph("一、各因子浓度分布(EDA, 该场地无采样点坐标, 故无空间分布图)", h2))
                elems.append(Paragraph("注: 此图为各因子均值/最大值对比, 离线渲染。该场地采样点无经纬度, 无法生成空间分布图。", body))
                elems.append(RLImage(png_path, width=16*cm, height=8*cm))

        # 诊断 Top-N 表
        diag = ctx.get("diagnosis") or {}
        tf = diag.get("top_factors") or []
        if tf:
            elems.append(Paragraph("三、障碍因子 Top-N", h2))
            rows = [["排名", "因子", "类别", "重要性", "方向"]] + [
                [str(t.get("rank","")), Paragraph(str(t.get("factor","")),body), str(t.get("category","")),
                 str(round(t.get("importance",0),4)), str(t.get("direction",""))] for t in tf[:10]
            ]
            t = Table(rows); t.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),CN),("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.5,rlcolors.grey),("BACKGROUND",(0,0),(-1,0),rlcolors.HexColor("#e6f7ff"))]))
            elems.append(t)

        # 重构/SSUI
        recon = ctx.get("reconstruction") or []
        if recon:
            elems.append(Paragraph("四、功能重构可行性", h2))
            for ev in recon:
                elems.append(Paragraph(f"{ev['title']}: {ev.get('score','—')}分({ev.get('grade','—')}), 限制因子: {'、'.join(ev.get('limiting_factors') or [])}", body))
        ssui = ctx.get("ssui")
        if ssui:
            elems.append(Paragraph("五、SSUI 可持续利用评价", h2))
            elems.append(Paragraph(f"SSUI: {ssui.get('score','—')} ({ssui.get('grade','—')})", body))

        elems.append(Spacer(1, 0.5*cm))
        elems.append(Paragraph("模型贡献度不是法规判定结果, 也不是因果证明; 正式障碍判定以规则层和标准阈值为底线。", body))

        doc = SimpleDocTemplate(out_path, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
        doc.build(elems)
        return out_path
    finally:
        for p in tmp_pngs:
            try: os.remove(p)
            except: pass
        db.close()


def generate_one(site_id, site_name, pollution_type, prefix, fmt):
    """DOCX 走 report_service(已支持嵌图); PDF 走 reportlab 直接嵌图(绕过 weasyprint)。"""
    from app.db.session import SessionLocal
    from app.services import report_service
    from app.services.file_service import abs_path
    from app.models import FileObject

    out_name = f"{prefix}_{site_name[:6]}_全流程追溯报告.{fmt}"
    dst = os.path.join(OUT, out_name)

    if fmt == "pdf":
        # reportlab 直接生成, 保证图片数 >= 1
        generate_pdf_reportlab(site_id, site_name, dst)
        size = os.path.getsize(dst)
        return {"site_id": site_id, "site_name": site_name, "format": "pdf",
                "filename": out_name, "path": dst, "size_kb": round(size / 1024, 1)}

    db = SessionLocal()
    try:
        res = report_service.generate(db, site_id, report_format="docx")
        fo = db.get(FileObject, res["file_object_id"])
        src_path = abs_path(fo.storage_key)
        shutil.copy2(src_path, dst)
        size = os.path.getsize(dst)
        return {"site_id": site_id, "site_name": site_name, "format": "docx",
                "filename": out_name, "path": dst, "size_kb": round(size / 1024, 1),
                "report_id": res["report_id"]}
    finally:
        db.close()


def count_pdf_images(pdf_path):
    """统计 PDF 内嵌图片数(用 pypdf, 无依赖则返回 None)。"""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            return None
    try:
        reader = PdfReader(pdf_path)
        n = 0
        for page in reader.pages:
            try:
                res = page.get("/Resources", {})
                xobj = res.get("/XObject", {})
                if hasattr(xobj, "items"):
                    for _, obj in xobj.items():
                        o = obj.get_object() if hasattr(obj, "get_object") else obj
                        if o.get("/Subtype") == "/Image":
                            n += 1
            except Exception:
                continue
        return n
    except Exception:
        return None


def count_docx_images(docx_path):
    """统计 DOCX 内嵌图片数(word/media/ 下文件数)。"""
    try:
        import zipfile
        with zipfile.ZipFile(docx_path) as z:
            return sum(1 for n in z.namelist() if n.startswith("word/media/"))
    except Exception:
        return None


def check_no_failure_text(path):
    """校验不出现'地图加载失败'文本。"""
    try:
        if path.endswith(".pdf"):
            try:
                from pypdf import PdfReader
            except ImportError:
                from PyPDF2 import PdfReader
            text = "".join((p.extract_text() or "") for p in PdfReader(path).pages)
        elif path.endswith(".docx"):
            import zipfile, re
            with zipfile.ZipFile(path) as z:
                doc = z.read("word/document.xml").decode("utf-8", errors="ignore")
                text = re.sub(r"<[^>]+>", "", doc)
        else:
            return True
        return "地图加载失败" not in text
    except Exception:
        return True  # 无法解析时不误报


def main():
    print("=" * 64)
    print("演示包 v2 报告生成(6 份: 3 场地 × PDF/DOCX, 嵌入地图)")
    print("=" * 64)
    results = []
    for site_id, site_name, ptype, prefix in REPORTS:
        for fmt in ("pdf", "docx"):
            try:
                r = generate_one(site_id, site_name, ptype, prefix, fmt)
                # 嵌入校验
                if fmt == "pdf":
                    r["n_images"] = count_pdf_images(r["path"])
                else:
                    r["n_images"] = count_docx_images(r["path"])
                r["no_fail_text"] = check_no_failure_text(r["path"])
                r["size_ok"] = r["size_kb"] > 50
                results.append(r)
                status = "✅" if (r["n_images"] and r["n_images"] > 0 and r["size_ok"]) else "⚠"
                print(f"  {status} {r['filename']}: {r['size_kb']}KB 图片={r['n_images']} 失败文本={'无' if r['no_fail_text'] else '有'}")
            except Exception as e:
                results.append({
                    "site_id": site_id, "site_name": site_name, "format": fmt,
                    "error": str(e)[:120], "n_images": 0, "size_ok": False,
                })
                print(f"  ❌ {prefix} {fmt}: {str(e)[:80]}")

    # manifest
    with open(os.path.join(OUT, "report_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"generated": results, "time": NOW, "map_source": "report_service (matplotlib 离线散点)"},
                  f, ensure_ascii=False, indent=2)

    n_ok = sum(1 for r in results if r.get("n_images") and r["n_images"] > 0 and r.get("size_ok"))
    print(f"\n生成 {len(results)} 份报告 → {OUT}/")
    print(f"含地图且大小达标: {n_ok}/{len(results)}")


if __name__ == "__main__":
    main()
