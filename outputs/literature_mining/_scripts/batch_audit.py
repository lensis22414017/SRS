"""批量审计所有 training_ready 论文的基质真实性.
对 17 篇 training_ready 论文, 从标题判定: soil / sediment / experiment / plant / unknown.
发现疑点论文 → dump 表标题确认.
"""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, LIT_ROOT
import pandas as pd

df = pd.read_csv(OUT_DIR / "extracted_observations_long_op_hmop.csv", dtype=str, keep_default_na=False)
cand = pd.read_csv(OUT_DIR / "candidate_literature_op_hmop.csv", dtype=str, keep_default_na=False)

tr_pids = df[df["readiness"] == "training_ready_hm_op"]["paper_id"].unique()
print(f"training_ready_hm_op 论文: {len(tr_pids)} 篇\n")

SOIL_SIGNALS = ["soil", "contaminated site", "agricultural", "farmland", "paddy",
                "industrial site", "mining", "mine area", "e-waste site", "coking",
                "oilfield", "petrochemical", "urban soil", "park", "roadside",
                "green space", "brownfield", "landfill", "场地", "土壤", "农田",
                "矿区", "工业区", "电子垃圾", "焦化", "石化", "油田", "垃圾"]
EXP_SIGNALS = ["bioremediation", "remediation experiment", "pot experiment", "greenhouse",
               "hydroponic", "incubation", "microcosm", "spike", "biochar amendment",
               "盆栽", "培养实验", "修复实验"]
PLANT_SIGNALS = ["plant tissue", "in plant", "of plant", "leaf", "root", "shoot",
                 "maize", "wheat", "rice plant", "vegetable"]

print(f"{'paper_id':<10}{'n_samp':<8}{'matrix':<14}{'flag':<8}标题")
print("-"*110)
suspect = []
for pid in tr_pids:
    pdf = df[(df["paper_id"] == pid) & (df["readiness"] == "training_ready_hm_op")]
    n_samp = pdf["canonical_sample_id"].nunique()
    matrix = pdf["matrix_flag"].iloc[0] if "matrix_flag" in pdf.columns else "?"
    title_row = cand[cand["paper_id"] == pid]
    title = title_row["title"].iloc[0] if len(title_row) else "?"
    low = title.lower()
    is_exp = any(s in low for s in EXP_SIGNALS)
    is_plant = any(s in low for s in PLANT_SIGNALS)
    is_sediment = bool(re.search(r"\bsediment\b|sludge|dust", low))
    is_soil = any(s in low for s in SOIL_SIGNALS)
    if is_exp or is_plant:
        flag = "⚠实验/植物"
        suspect.append((pid, "experiment_or_plant", title))
    elif is_sediment:
        flag = "◇沉积物"
    elif is_soil:
        flag = "✓土壤"
    else:
        flag = "?未明"
        suspect.append((pid, "unknown_matrix", title))
    print(f"{pid:<10}{n_samp:<8}{matrix:<14}{flag:<8}{title[:70]}")

print(f"\n=== 疑点论文 ({len(suspect)} 篇, 需 dump 确认) ===")
for pid, reason, title in suspect:
    print(f"\n[{pid}] {reason}: {title[:90]}")
    pdf = df[df["paper_id"] == pid]
    stem = pdf["evidence_location"].iloc[0].split("/")[0]
    md = LIT_ROOT / stem / "parsed" / "paper.md"
    if md.exists():
        text = md.read_text(encoding="utf-8", errors="ignore")
        titles = re.findall(r"(Table\s*\d+[^\n]{0,90})", text)
        print(f"  site_name: {pdf['site_name'].drop_duplicates().head(4).tolist()}")
        print(f"  表标题 (前 4):")
        for t in titles[:4]:
            print(f"    {t[:80]}")
