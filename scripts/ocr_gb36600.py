"""GB36600-2018 有机物筛选值 OCR(omlx 多模态, 双模型交叉防幻觉)。

裴总指定: 用 ~/.agents/skills/renaming-scientific-pdfs 的 omlx 视觉方法。
策略:
  1. PyMuPDF 渲染 18 页(dpi 180)。
  2. GLM-4.7-Flash 逐页分类(has_table 快筛)。
  3. 表格页 GLM + Qwable 双模型精提有机物 mg/kg(JSON)。
  4. 两模型一致取信, 冲突标注"需核实"。
  5. 石油烃(C10-C40) 一类826/二类4500 作 sanity ground-truth(知识库已有)。
产物: data/standards/GB36600_有机阈值_ocr.csv + _log.txt
"""
import fitz, base64, requests, json, os, re, time, sys

PDF = "/Users/lensis/Downloads/GB36600-2018.pdf"
OMLX = "http://127.0.0.1:51518/v1/chat/completions"
MODEL_A = "GLM-4.7-Flash-Claude-Opus-4.5-High-Reasoning-Distill-4bit"
MODEL_B = "Qwable-9B-Claude-Fable-5-mlx-8Bit"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_CSV = os.path.join(ROOT, "data", "standards", "GB36600_有机阈值_ocr.csv")
OUT_LOG = os.path.join(ROOT, "data", "standards", "GB36600_ocr_log.txt")
os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

PROMPT_CLS = "这是GB36600-2018某页。若含'筛选值'表格(有机污染物mg/kg)回复'表格页',否则回复'非表'。只回这3字。"
PROMPT_EXT = '''这是GB36600-2018含筛选值表的页。提取所有有机污染物及筛选值,严格JSON:
{"items":[{"factor":"污染物中文名","cat1":数值,"cat2":数值}]}
cat1=第一类用地, cat2=第二类用地, 单位mg/kg。含: 苯/甲苯/乙苯/二甲苯/萘/苯并[a]芘/苯胺/石油烃(C10-C40)/多氯联苯(总量)/滴滴涕(总量)/六氯环己烷(总量)/氯乙烯/三氯乙烯/四氯化碳 等。只输出JSON。'''


def render_b64(doc, i, dpi=180):
    return base64.b64encode(doc[i].get_pixmap(dpi=dpi).tobytes("png")).decode()


def ocr(model, b64, prompt, max_tokens=1200):
    try:
        r = requests.post(OMLX, json={"model": model, "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}],
            "max_tokens": max_tokens, "temperature": 0}, timeout=200)
        return r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else f"ERR{r.status_code}"
    except Exception as e:
        return f"EXC:{e}"


def parse_items(text):
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        return []
    try:
        j = json.loads(m.group())
        return j.get("items", [])
    except Exception:
        return []


def main():
    doc = fitz.open(PDF)
    log = [f"GB36600 OCR start, {doc.page_count}页"]
    items = {}
    table_pages = []
    for i in range(doc.page_count):
        b64 = render_b64(doc, i)
        # 跳过分类(分类prompt不可靠), 每页直接 GLM 精提
        it_a = parse_items(ocr(MODEL_A, b64, PROMPT_EXT))
        if it_a:
            table_pages.append(i)
        for x in it_a:
            f = (x.get("factor") or "").strip()
            if f:
                items.setdefault(f, {})[MODEL_A] = (x.get("cat1"), x.get("cat2"))
        log.append(f"p{i}: GLM提取{len(it_a)}项 {'★表格' if it_a else ''}")
        print(f"p{i}: GLM {len(it_a)}项 {'★' if it_a else ''}", flush=True)
        time.sleep(1)
    # 汇总: 一致取信, 冲突标注
    rows = []
    for f, mv in items.items():
        a, b = mv.get(MODEL_A), mv.get(MODEL_B)
        if a and b and a == b:
            rows.append({"factor": f, "cat1": a[0], "cat2": a[1], "confidence": "high(双模型一致)"})
        elif a and b:
            rows.append({"factor": f, "cat1_A": a[0], "cat2_A": a[1],
                         "cat1_B": b[0], "cat2_B": b[1], "confidence": "conflict(需核实)"})
        else:
            v = a or b
            src = "A" if a else "B"
            rows.append({"factor": f, "cat1": v[0], "cat2": v[1], "confidence": f"single({src}需核实)"})
    # 写 csv
    import csv
    keys = ["factor", "cat1", "cat2", "cat1_A", "cat2_A", "cat1_B", "cat2_B", "confidence"]
    with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    log.append(f"\n表格页: {table_pages}")
    log.append(f"提取有机物 {len(rows)} 项 → {OUT_CSV}")
    # sanity check 石油烃
    for r in rows:
        if "石油烃" in r.get("factor", ""):
            log.append(f"sanity 石油烃: {r}")
    with open(OUT_LOG, "w", encoding="utf-8") as f:
        f.write("\n".join(log))
    print(f"\n=== 完成: {len(rows)} 有机物 → {OUT_CSV} ===", flush=True)
    for r in rows[:15]:
        print(f"  {r.get('factor')}: cat1={r.get('cat1')} cat2={r.get('cat2')} [{r.get('confidence')}]", flush=True)


if __name__ == "__main__":
    main()
