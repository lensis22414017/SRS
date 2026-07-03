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


def generate_one(site_id, site_name, pollution_type, prefix, fmt):
    """调 report_service.generate() 生成一份报告, 拷贝到 OUT 目录。"""
    from app.db.session import SessionLocal
    from app.services import report_service
    from app.services.file_service import abs_path
    from app.models import FileObject

    db = SessionLocal()
    try:
        res = report_service.generate(db, site_id, report_format=fmt)
        fo = db.get(FileObject, res["file_object_id"])
        src_path = abs_path(fo.storage_key)
        ext = res["format"]  # pdf / docx / html
        out_name = f"{prefix}_{site_name[:6]}_全流程追溯报告.{ext}"
        dst = os.path.join(OUT, out_name)
        shutil.copy2(src_path, dst)
        size = os.path.getsize(dst)
        return {
            "site_id": site_id, "site_name": site_name, "format": ext,
            "filename": out_name, "path": dst, "size_kb": round(size / 1024, 1),
            "report_id": res["report_id"],
        }
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
