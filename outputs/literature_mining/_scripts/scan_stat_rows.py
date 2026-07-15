"""Scan manual_extract CSVs for statistical-row contamination.

P06579 lesson: stat rows (Mean/SD/Max/Min) from descriptive tables get
mislabeled as sampling points. This scans sample_id for stat-label patterns
so we can catch contamination before it pollutes the training set.
"""
import csv
import glob
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"

# Stat-label patterns (CN+EN)
STAT_PAT = re.compile(
    r"(mean|median|average|averag|max|minimum|maximum|min|sd|std|sem|"
    r"range|total|sum|平均|均值|平均值|中位数|中位|最大值|最大|最小值|最小|"
    r"标准差|方差|总和|极差|范围|极值)",
    re.I,
)

# Suspicious value patterns: risk indices, grade labels, GB thresholds
RISK_PAT = re.compile(r"\b(HQ|HI|TEQ|RI|PLI|Igeo|CF|ER|CR|TQ|NQMQ|Grade|Class|等级|类别)\b", re.I)
GB_PAT = re.compile(r"(GB\s*\d|一类|二类|三类|农用地|建设用地|筛选值|管控值)", re.I)

hits_stat = []   # (dir, file, sample_id, pollutant, value)
hits_risk = []
hits_gb = []
sample_id_counter = Counter()

for d in ["hm_op", "op_only"]:
    for f in sorted(glob.glob(f"{BASE}/{d}/*.csv")):
        fname = f.replace("\\", "/").split("/")[-1]
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
        except Exception:
            continue
        for r in rows:
            sid = str(r.get("sample_id", ""))
            poll = str(r.get("pollutant_std", ""))
            val = str(r.get("value", ""))
            notes = str(r.get("extract_notes", ""))
            sample_id_counter[d] += 1
            if STAT_PAT.search(sid):
                hits_stat.append((d, fname, sid, poll, val))
            if RISK_PAT.search(poll) or RISK_PAT.search(notes):
                hits_risk.append((d, fname, sid, poll, val))
            if GB_PAT.search(sid) or GB_PAT.search(notes):
                hits_gb.append((d, fname, sid, poll, val))

print(f"=== 统计行/风险值/阈值 扫描 ===")
print(f"总数据行: hm_op={sample_id_counter['hm_op']} op_only={sample_id_counter['op_only']}")
print(f"\n[统计行嫌疑 sample_id] {len(hits_stat)} 条:")
for h in hits_stat[:40]:
    print(f"  {h[0]}/{h[1]}  sid={h[2]!r}  {h[3]}={h[4]}")
print(f"\n[风险指数/等级嫌疑 pollutant/notes] {len(hits_risk)} 条:")
for h in hits_risk[:20]:
    print(f"  {h[0]}/{h[1]}  sid={h[2]!r}  {h[3]}={h[4]}")
print(f"\n[GB标准/阈值嫌疑] {len(hits_gb)} 条:")
for h in hits_gb[:20]:
    print(f"  {h[0]}/{h[1]}  sid={h[2]!r}  {h[3]}={h[4]}")
