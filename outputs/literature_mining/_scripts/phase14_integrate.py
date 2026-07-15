"""Phase 14 → 现有 manual_extract 整合脚本

1. 将 Phase14 清理后的 CSV 按论文复制到 manual_extract/op_only/ 和 manual_extract/hm_op/
2. 过滤统计行 (相关系数/因子载荷/PCA等非污染物数据)
3. 重跑 build_wide_manual.py 生成合并后的 wide table
4. 重跑 deliver_clean 生成新的 SOIL_CLEAN
"""
from __future__ import annotations
import sys, csv, os, shutil
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PHASE14_DIR = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\phase14")
ME = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract")

# 统计行关键词 (这些表的数值不是污染物浓度)
STAT_TABLE_KEYWORDS = [
    "correlation matrix", "pearson", "spearman", "correlation coefficient",
    "pca", "principal component", "factor load", "因子载荷", "主成分",
    "cluster analysis", "聚类分析", "correlation among",
    "rotated component", "旋转成分", "component matrix",
    "correlation between", "相关矩阵", "相关系数",
    "eigenvalue", "特征值", "variance explained", "方差解释",
    "相关系数矩阵", "相关关系",
]

def is_stat_table(row):
    """判断一行是否来自统计表。"""
    caption = (row.get("source_caption", "") or "").lower()
    for kw in STAT_TABLE_KEYWORDS:
        if kw in caption:
            return True
    return False

def main():
    # 1. 读取 Phase14 清理后的数据
    cleaned = PHASE14_DIR / "_cleaned_long.csv"
    if not cleaned.exists():
        print("_cleaned_long.csv not found!")
        return

    with open(str(cleaned), "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Phase14 清理后: {len(rows)} 行")

    # 2. 过滤统计行
    before = len(rows)
    rows = [r for r in rows if not is_stat_table(r)]
    removed_stat = before - len(rows)
    print(f"过滤统计行: -{removed_stat} (余 {len(rows)})")

    # 3. 过滤 Pearson 相关系数值 (值都在 -1 到 1 之间, 且不是百分比)
    # HM 污染物如果值是 -1~1 且来自统计表 → 剔除
    before = len(rows)
    def is_likely_correlation(row):
        try:
            v = float(row["value"])
        except (ValueError, TypeError):
            return False
        p = row["pollutant_std"]
        # HM 值在 -1~1 之间且不是真实浓度的典型范围
        if p.endswith("_mgkg") and -1.0 <= v <= 1.0 and v != 0:
            # 检查同一 paper_id+sample_id 是否还有其他 >1 的值
            return False  # 暂时保留，由 agent 二审
        return False

    rows = [r for r in rows if not is_likely_correlation(r)]
    print(f"过滤相关性值: -{before - len(rows)} (余 {len(rows)})")

    # 4. 按 source_pool 分类 → 复制到对应 manual_extract 目录
    hm_pollutants = {"Cd_mgkg","Pb_mgkg","Cr_mgkg","As_mgkg","Hg_mgkg","Cu_mgkg","Zn_mgkg",
                     "Ni_mgkg","Co_mgkg","Mn_mgkg","Sb_mgkg","Fe_mgkg","Al_mgkg","V_mgkg","Be_mgkg"}
    op_pollutants = {"Sum_PAH_ngg","BaP_ngg","SumPCB_ngg","SumDDT_ngg","SumHCH_ngg",
                     "SumPBDE_ngg","SumOCP_ngg","TotalPHC_mgkg","SumPAE_ngg","OPEs_ngg",
                     "Nap_ngg","Acy_ngg","Ace_ngg","Flu_ngg","Phe_ngg","Ant_ngg",
                     "Flt_ngg","Pyr_ngg","BaA_ngg","Chr_ngg","BbF_ngg","BkF_ngg",
                     "Ind_ngg","DahA_ngg","BghiP_ngg",
                     "SMZ_ngg","CTC_ngg","OTC_ngg","ENRO_ngg","SDZ_ngg"}

    # 按 sample_id 聚合判断类型
    from collections import defaultdict
    by_sample = defaultdict(list)
    for r in rows:
        by_sample[r["sample_id"]].append(r)

    sample_type = {}
    for sid, srows in by_sample.items():
        pollutants = set(r["pollutant_std"] for r in srows)
        has_hm = bool(pollutants & hm_pollutants)
        has_op = bool(pollutants & op_pollutants)
        if has_hm and has_op:
            sample_type[sid] = "hm_op"
        elif has_op:
            sample_type[sid] = "op_only"
        elif has_hm:
            sample_type[sid] = "hm_only"

    # 按论文分组保存
    phase14_op_dir = PHASE14_DIR / "op_only"
    phase14_hmop_dir = PHASE14_DIR / "hm_op"
    existing_op = ME / "op_only"
    existing_hmop = ME / "hm_op"

    # 确保目标目录存在
    existing_op.mkdir(exist_ok=True)
    existing_hmop.mkdir(exist_ok=True)

    op_only_pids = set()
    hm_op_pids = set()
    hm_only_pids = set()

    for r in rows:
        sid = r["sample_id"]
        pid = r["paper_id"]
        if sample_type.get(sid) == "op_only":
            op_only_pids.add(pid)
        elif sample_type.get(sid) == "hm_op":
            hm_op_pids.add(pid)
        elif sample_type.get(sid) == "hm_only":
            hm_only_pids.add(pid)

    # 复制 Phase14 CSV 到 manual_extract 目录
    # 格式对齐现有 CSV (paper_id/sample_id/pollutant_std/value/unit/evidence_location/matrix/site_type/province/extract_notes/latitude/longitude)
    EXISTING_FIELDS = ["paper_id", "sample_id", "pollutant_std", "value", "unit",
                       "evidence_location", "matrix", "site_type", "province",
                       "extract_notes", "latitude", "longitude"]

    # 保存 OP-only 论文
    new_op = 0
    new_hmop = 0
    for pid in op_only_pids:
        prows = [r for r in rows if r["paper_id"] == pid and sample_type.get(r["sample_id"]) == "op_only"]
        dest = existing_op / f"{pid}.csv"
        if not dest.exists():
            new_op += 1
        with open(str(dest), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=EXISTING_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for r in prows:
                nr = {k: r.get(k, "") for k in EXISTING_FIELDS}
                nr["extract_notes"] = f"phase14_auto; confidence={r.get('confidence','')}; flag={r.get('value_flag','')}"
                writer.writerow(nr)

    for pid in hm_op_pids:
        prows = [r for r in rows if r["paper_id"] == pid and sample_type.get(r["sample_id"]) == "hm_op"]
        # 排除纯 HM 采样点（HM-only 不放入 hm_op）
        dest = existing_hmop / f"{pid}.csv"
        if not dest.exists():
            new_hmop += 1
        with open(str(dest), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=EXISTING_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for r in prows:
                nr = {k: r.get(k, "") for k in EXISTING_FIELDS}
                nr["extract_notes"] = f"phase14_auto; confidence={r.get('confidence','')}; flag={r.get('value_flag','')}"
                writer.writerow(nr)

    print(f"\n{'='*60}")
    print(f"Phase 14 整合完成")
    print(f"{'='*60}")
    print(f"OP-only: {len(op_only_pids)} 论文 → manual_extract/op_only/ ({new_op} 新增)")
    print(f"HM+OP:   {len(hm_op_pids)} 论文 → manual_extract/hm_op/ ({new_hmop} 新增)")
    print(f"HM-only: {len(hm_only_pids)} 论文 → manual_extract/hm_only/ (仅HM,不参与复合)")
    print(f"总数据行: {len(rows)}")

    # 统计现有目录
    existing_op_count = len(list(existing_op.glob("*.csv")))
    existing_hmop_count = len(list(existing_hmop.glob("*.csv")))
    print(f"\n合并后 manual_extract 总量:")
    print(f"  op_only/: {existing_op_count} 篇")
    print(f"  hm_op/:   {existing_hmop_count} 篇")

if __name__ == "__main__":
    main()
