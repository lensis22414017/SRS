"""Targeted dump for 4 risk points flagged by quality_audit.

1. P11362: 17 Sum_PAH outliers up to 4.5M ng/g — check for stat-row / unit error
2. P01626 vs P09065: both "Taizhou e-waste" Cu=9600 — suspected duplicate
3. P01524 sid=K5 SumPCB=484500, P03118 sid=S9 Cr=15060 — extreme singletons
4. Off-list OP pollutants (antibiotics/phthalates) — scope decision for 裴总
"""
import csv
import glob
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"
HM = {"Cd_mgkg", "Pb_mgkg", "Cr_mgkg", "As_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg"}
# SRS 标准 OP 清单 (6 大类)
OP_STD = {"Sum_PAH_ngg", "BaP_ngg", "SumPCB_ngg", "SumDDT_ngg", "SumHCH_ngg", "SumPBDE_ngg", "TotalPHC_mgkg"}


def load(pid_dirs):
    """pid_dirs: list of (pid, [dirs]). Returns rows list."""
    out = []
    for pid, dirs in pid_dirs:
        for d in dirs:
            f = f"{BASE}/{d}/{pid}.csv"
            try:
                rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
            except FileNotFoundError:
                continue
            for r in rows:
                r["_pool"] = d
                out.append(r)
    return out


# ---- 1. P11362 Sum_PAH 异常值详情 ----
print("=" * 70)
print("1. P11362 Sum_PAH 异常值 (最高 4,545,880 ng/g)")
print("=" * 70)
rows = load([("P11362", ["hm_op", "op_only"])])
pah = [r for r in rows if r.get("pollutant_std") == "Sum_PAH_ngg"]
print(f"P11362 总行数: {len(rows)}, 其中 Sum_PAH 行: {len(pah)}")
# 值分布 + 看 sid 是否含统计行
vals = []
for r in pah:
    try:
        v = float(r.get("value", ""))
        vals.append(v)
    except ValueError:
        pass
if vals:
    vals.sort()
    print(f"Sum_PAH 值范围: [{vals[0]}, {vals[-1]}]")
    print(f"  中位数: {vals[len(vals)//2]}, >100000 的有 {sum(1 for v in vals if v>100000)} 条")
# dump 前 5 条 + 后 5 条, 看 evidence_location / notes
print("--- 前3条 + 后3条 (看 sid/单位/notes) ---")
pah_sorted = sorted(pah, key=lambda r: float(r.get("value","0") or 0))
for r in (pah_sorted[:3] + pah_sorted[-3:]):
    print(f"  sid={r.get('sample_id')!r} val={r.get('value')!r} unit={r.get('unit')!r} "
          f"matrix={r.get('matrix')!r} loc={r.get('evidence_location')!r}")
    notes = r.get("extract_notes", "")
    if notes:
        print(f"    notes: {notes[:120]}")

# ---- 2. P01626 vs P09065 重复性 ----
print("\n" + "=" * 70)
print("2. P01626 vs P09065 重复嫌疑 (同为台州电子废物 Cu=9600)")
print("=" * 70)
for pid in ["P01626", "P09065"]:
    rows = load([(pid, ["hm_op", "op_only"])])
    print(f"\n[{pid}] {len(rows)} 行")
    if rows:
        print(f"  matrix: {rows[0].get('matrix')!r}, province: {rows[0].get('province')!r}, site_type: {rows[0].get('site_type')!r}")
        # Cu 值
        cus = [(r.get("sample_id"), r.get("value")) for r in rows if r.get("pollutant_std") == "Cu_mgkg"]
        print(f"  Cu_mgkg: {cus[:5]}")
        # 所有 sid
        sids = sorted(set(r.get("sample_id","") for r in rows))
        print(f"  sample_id ({len(sids)}): {sids[:8]}")

# ---- 3. 极端单点 ----
print("\n" + "=" * 70)
print("3. 极端单点核查")
print("=" * 70)
for pid, sid, poll in [("P01524", "K5", "SumPCB_ngg"), ("P03118", "S9", "Cr_mgkg")]:
    rows = load([(pid, ["hm_op", "op_only"])])
    hit = [r for r in rows if r.get("sample_id") == sid and r.get("pollutant_std") == poll]
    if hit:
        r = hit[0]
        print(f"\n[{pid}] sid={sid} {poll}={r.get('value')} unit={r.get('unit')!r}")
        print(f"  matrix={r.get('matrix')!r} site_type={r.get('site_type')!r} loc={r.get('evidence_location')!r}")
        notes = r.get("extract_notes", "")
        if notes:
            print(f"  notes: {notes[:150]}")
    # 该论文同污染物其他值, 看是否离群
    same = [float(x.get("value","0") or 0) for x in rows if x.get("pollutant_std")==poll]
    if len(same) > 1:
        print(f"  该论文全部 {poll} 值 ({len(same)}个): min={min(same)} max={max(same)} mean={sum(same)/len(same):.1f}")

# ---- 4. 清单外 OP 污染物分布 ----
print("\n" + "=" * 70)
print("4. 清单外 OP 污染物 (抗生素/塑化剂/其他农药) 分布")
print("=" * 70)
offlist = defaultdict(lambda: [0, set()])  # poll -> [count, set(paper_id)]
for d in ["hm_op", "op_only"]:
    for f in glob.glob(f"{BASE}/{d}/*.csv"):
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
        except Exception:
            continue
        for r in rows:
            poll = r.get("pollutant_std", "")
            if poll and poll not in HM and poll not in OP_STD:
                offlist[poll][0] += 1
                offlist[poll][1].add(r.get("paper_id", ""))
print(f"共 {len(offlist)} 种清单外 OP 污染物:")
for poll, (cnt, pids) in sorted(offlist.items(), key=lambda x: -x[1][0]):
    print(f"  {poll}: {cnt} 行 / {len(pids)} 篇 / 论文 {sorted(pids)[:5]}")
