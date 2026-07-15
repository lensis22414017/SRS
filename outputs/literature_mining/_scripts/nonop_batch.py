"""输出非OP文献批次(标题+摘要), 供子agent精读找关键词漏筛的OP/复合污染"""
import sys
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import pandas as pd

cat = pd.read_csv(r"G:\文献整理_最终\文献目录_literature_catalog.csv", dtype=str, keep_default_na=False)
china = cat[cat["region"].str.strip().str.lower() == "china"].copy()
china["text"] = china["英文标题"].fillna("") + " || " + china["中文标题"].fillna("") + " || " + china["中文摘要"].fillna("")
china["tl"] = china["text"].str.lower()
OP_KW = ["pah", "polycyclic aromatic", "benzo", "pyrene", "fluoranthene", "chrysene",
         "phenanthrene", "naphthalene", "多环芳烃", "苯并芘", "芘", "菲",
         "pcb", "polychlorinated biphenyl", "多氯联苯", "ddt", "dde", "hch", "bhc",
         "chlordane", "lindane", "endosulfan", "有机氯农药", "六六六", "滴滴涕",
         "pbde", "polybrominated", "多溴", "bde-", "tph", "petroleum", "石油烃", "原油",
         "btex", "pesticide", "herbicide", "农药", "除草剂", "杀虫",
         "antibiotic", "抗生素", "四环素", "磺胺", "pfas", "pfoa", "pfos", "全氟",
         "voc", "volatile organic", "氯代", "phenol", "酚", "organic pollutant",
         "有机污染", "pops", "dioxin", "二噁英", "phthalate", "邻苯二甲酸酯", "矿物油"]
china["has_op"] = china["tl"].apply(lambda t: any(k in t for k in OP_KW))
non_op = china[~china["has_op"]].copy()
print(f"中国文献: {len(china)}, OP命中: {china['has_op'].sum()}, 非OP待审: {len(non_op)}")
out = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\nonop_batches")
out.mkdir(exist_ok=True)
n = (len(non_op) + 199) // 200
for i in range(n):
    b = non_op.iloc[i * 200:(i + 1) * 200]
    b[["序号", "英文标题", "中文标题", "中文摘要"]].to_csv(out / f"batch_{i:02d}.csv", index=False, encoding="utf-8-sig")
print(f"输出 {n} 批 (每批200篇) → nonop_batches/")
