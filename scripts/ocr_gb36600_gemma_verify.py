"""GB36600 gemma-4-E4B 多模态 OCR 验证(Wave B, 裴总授权)。

目的: 验证 gemma-4-E4B(未试过的真多模态)是否突破之前 GLM/Qwen 的 OCR 幻觉。
memory教训(2026-06-23): 所有LLM对GB36600扫描表OCR都幻觉。本脚本验证gemma新模型。
sanity ground-truth: 石油烃(C10-C40) 一类826/二类4500(生态库已有,裴总核对原文)。
  通过→gemma可作交叉验证源; 失败→维持生态库OP权威(xlsx+人工核对)。
"""
import fitz
import base64
import requests
import os
import re
import time
import csv

PDF = "/Users/lensis/Downloads/GB36600-2018.pdf"
OMLX = "http://127.0.0.1:51518/v1/chat/completions"
MODEL = "gemma-4-26b-a4b-it-4bit"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "data", "standards", "GB36600_gemma_ocr_verify.csv")

PROMPT = '''这是GB36600-2018《建设用地土壤污染风险管控标准》某页。
若含"筛选值"表格(有机污染物mg/kg),逐行提取,严格格式(每行一条,无解释无JSON):
<因子中文名> | 一类:<数值> | 二类:<数值> mg/kg
含: 苯/甲苯/乙苯/二甲苯/萘/苯并[a]芘/苯胺/石油烃(C10-C40)/多氯联苯(总量)/滴滴涕/六氯环己烷/氯乙烯/三氯乙烯/四氯化碳/1,2-二氯乙烷 等。
例: 石油烃(C10-C40) | 一类:826 | 二类:4500 mg/kg
若本页无筛选值表,只输出"非表"。'''


def render_b64(doc, i, dpi=200):
    return base64.b64encode(doc[i].get_pixmap(dpi=dpi).tobytes("png")).decode()


def ocr(b64):
    try:
        r = requests.post(OMLX, json={"model": MODEL, "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}],
            "max_tokens": 1500, "temperature": 0,
            "extra_body": {"enable_thinking": False}}, timeout=200)
        return r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else f"ERR{r.status_code}: {r.text[:100]}"
    except Exception as e:
        return f"EXC:{e}"


def parse(text):
    items = []
    for line in (text or "").split("\n"):
        m = re.search(r"([^\|:]{2,25}?)\s*\|\s*一类[:：]\s*([\d.]+)\s*\|\s*二类[:：\s]*([\d.\-]+)", line)
        if m:
            f = m.group(1).strip().strip("（(【《").strip()
            try:
                c2 = None if m.group(3) in ("-", "—", "") else float(m.group(3))
                items.append({"factor": f, "cat1": float(m.group(2)), "cat2": c2})
            except ValueError:
                pass
    return items


def main():
    doc = fitz.open(PDF)
    print(f"GB36600 {doc.page_count}页, gemma-4-E4B({MODEL}) OCR验证")
    print(f"sanity: 石油烃(C10-C40) 一类826/二类4500\n")
    all_items = {}
    table_pages = []
    for i in range(5, min(10, doc.page_count)):  # 测有机筛选值表页(p5-9, 附录区)
        b64 = render_b64(doc, i)
        text = ocr(b64)
        items = parse(text)
        if items:
            table_pages.append(i)
            print(f"p{i}: ★{len(items)}项")
            for x in items:
                f = x["factor"].strip()
                if f:
                    all_items.setdefault(f, []).append(x)
        else:
            tag = "非表" if "非表" in (text or "") else f"?({(text or '')[:40]})"
            print(f"p{i}: {tag}")
        time.sleep(0.5)

    print(f"\n表格页: {table_pages}")
    print(f"提取有机物: {len(all_items)} 种\n")

    # sanity: 石油烃 ground-truth
    print("=== sanity 石油烃(ground-truth 一类826/二类4500) ===")
    sanity_ok = False
    for f, lst in all_items.items():
        if "石油烃" in f or "C10" in f or "C10-C40" in f:
            for x in lst:
                c1ok = abs(x["cat1"] - 826) < 1
                c2ok = x.get("cat2") is not None and abs(x["cat2"] - 4500) < 1
                sanity_ok = c1ok and c2ok
                print(f"  {f}: 一类={x['cat1']}({'✓' if c1ok else '✗应826'}) "
                      f"二类={x.get('cat2')}({'✓' if c2ok else '✗应4500'})")
    print(f"\nsanity 判定: {'✓ gemma突破幻觉(石油烃正确)' if sanity_ok else '✗ gemma仍幻觉/未提取石油烃'}")

    # 写 csv
    rows = []
    for f, lst in sorted(all_items.items()):
        x = lst[0]
        rows.append({"factor": f, "cat1": x["cat1"], "cat2": x.get("cat2"), "n_pages": len(lst)})
    with open(OUT, "w", encoding="utf-8-sig", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=["factor", "cat1", "cat2", "n_pages"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n→ {OUT} ({len(rows)} 有机物)")
    for r in rows[:20]:
        print(f"  {r['factor']}: 一类={r['cat1']} 二类={r['cat2']}")


if __name__ == "__main__":
    main()
