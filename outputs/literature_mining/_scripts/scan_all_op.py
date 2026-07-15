# -*- coding: utf-8 -*-
"""扩展关键词全量筛catalog, 找所有未读OP/HM+OP候选加入workflow"""
import sys, json, re
from pathlib import Path
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except: pass
import pandas as pd

cat = pd.read_csv(r"G:\文献整理_最终\文献目录_literature_catalog.csv", dtype=str, keep_default_na=False)

# 扩展OP关键词(正则, 词边界防soil误匹配oil; 覆盖新污染物)
OP_PAT = re.compile(
    r"\bpah\b|polycyclic|benzo|pyrene|fluoranthene|phenanthrene|naphthalene|"
    r"多环芳烃|苯并|芘|菲|蒽|"
    r"\bpcb\b|多氯联苯|"
    r"\bddt\b|\bhch\b|\bbhc\b|chlordane|lindane|endosulfan|有机氯农药|六六六|滴滴涕|氯丹|硫丹|"
    r"\bpbde\b|多溴|\bbde\b|dbdpe|十溴|hbcd|六溴|阻燃|flame.?retardant|"
    r"\btph\b|petroleum|石油烃|原油|crude.?oil|oil.?spill|oil.?contamin|oil.?pollut|矿物油|diesel|汽油|柴油|btex|苯系物|"
    r"pesticide|herbicide|atrazine|glyphosate|农药|除草|杀虫|杀菌|阿特拉津|草甘膦|有机磷农药|organophosphate|chlorpyrifos|"
    r"antibiotic|抗生素|四环素|磺胺|喹诺酮|oxytetracycline|"
    r"\bpfas\b|\bpfoa\b|\bfos\b|全氟|"
    r"\bvoc\b|\bsvoc\b|volatile organic|氯代|含氯|含溴|卤代|trichloro|三氯|"
    r"phenol|酚类|bisphenol|双酚|triclosan|三氯生|"
    r"有机污染物|有机污染|\bpops\b|持久性有机|新兴污染物|新污染物|"
    r"dioxin|二噁英|二恶英|呋喃|"
    r"phthalate|邻苯二甲酸酯|\bdbp\b|\bdehp\b|"
    r"\bope\b|有机磷酸酯|有机磷酯|"
    r"\bsccp\b|氯化石蜡|紫外吸收|合成麝香|内分泌干扰|\bedc\b|性激素|新烟碱|"
    r"焦化|石化|电子垃圾|e-waste|农药厂|加油站|油田|化工|垃圾焚烧",
    re.I)

HM_KW = ["heavy metal", "重金属", "cadmium", "lead", "chromium", "arsenic", "mercury",
         "copper", "zinc", "nickel", "镉", "铅", "铬", "砷", "汞", "铜", "锌", "镍", "trace metal"]

china = cat[cat["region"].str.strip().str.lower() == "china"].copy()
china["tl"] = (china["英文标题"] + " " + china["中文标题"] + " " + china["中文摘要"]).str.lower()
china["has_op"] = china["tl"].apply(lambda t: bool(OP_PAT.search(t)))
china["has_hm"] = china["tl"].apply(lambda t: any(k in t for k in HM_KW))

op = china[china["has_op"]]
done = set()
for sub in ["hm_op", "op_only"]:
    d = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract") / sub
    if d.exists():
        for f in d.glob("*.csv"):
            done.add(f.stem)

wf = set(["P04678","P03100","P09090","P00829","P01182","P04627","P11424","P01360","P01795",
          "P01223","P01746","P07067","P04074","P11293","P00650","P01993","P03328","P01532",
          "P00742","P02482","P10441","P09271","P01583","P07068","P08462","P01294","P06121",
          "P06840","P10531","P07154","P06288","P09516","P00671","P00611","P01741","P01718",
          "P01524","P01301","P10991","P00303","P11676","P08510","P08700","P08473","P01069"])

todo = op[~op["序号"].isin(done) & ~op["序号"].isin(wf)]
hmop_todo = todo[todo["has_hm"]]
op_todo = todo[~todo["has_hm"]]
print(f"扩展OP中国: {len(op)}篇(已读{len(done)}+WF{len(wf)})")
print(f"未读未WF: {len(todo)} (HM+OP:{len(hmop_todo)}, OP-only:{len(op_todo)})")

papers = [{"paper_id": r["序号"], "stem": r["stem"], "title": r["英文标题"][:50], "has_hm": bool(r["has_hm"])}
          for _, r in todo.iterrows()]
json.dump(papers, open(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\_scripts\all_op_todo.json", "w", encoding="utf-8"), ensure_ascii=False)
print(f"输出 all_op_todo.json: {len(papers)}篇")

# 验证: P00113(纯HM)是否被误标
p00113 = china[china["序号"] == "P00113"]
if len(p00113):
    m = OP_PAT.search(p00113.iloc[0]["tl"])
    print(f"\n验证 P00113(大坝重金属): has_op={bool(m)}, 匹配词={m.group() if m else None}")
