"""Phase 14 第二批整合管道
一步完成: 清理 → 填充 matrix → 整合到 manual_extract/
"""
from __future__ import annotations
import sys, csv, os, re
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BATCH2_RAW = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\phase14\_all_raw_batch2.csv")
PHASE14_DIR = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\phase14")
ME_OP = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\op_only")
ME_HMOP = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\hm_op")
BASE = Path(r"G:\所有文献\14.第十阶段小补充 4 文献解析")

# ===== 统计表关键词 =====
STAT_TABLE_KEYWORDS = [
    "correlation matrix", "pearson", "spearman", "correlation coefficient",
    "pca", "principal component", "factor load", "因子载荷", "主成分",
    "cluster analysis", "聚类分析", "correlation among",
    "rotated component", "旋转成分", "component matrix",
    "correlation between", "相关矩阵", "相关系数",
    "eigenvalue", "特征值", "variance explained", "方差解释",
]

# ===== Matrix 关键词 =====
MATRIX_KEYWORDS = {
    "soil": [r"\bsoil\b", r"\bsoils\b", r"\b土壤\b", r"topsoil", r"surface\s*soil",
             r"agricultural\s*(?:soil|land|field)", r"farmland", r"paddy\s*soil",
             r"soil\s*sample", r"soil\s*collected"],
    "sediment": [r"\bsediment\b", r"\bsediments\b", r"\b沉积物\b", r"\b底泥\b"],
    "water": [r"\bwater\b", r"\bwaters\b", r"\b水样\b", r"\b水体\b", r"surface\s*water", r"groundwater"],
    "dust": [r"\bdust\b", r"\bdusts\b", r"\b灰尘\b", r"\b粉尘\b"],
}

# 正式 OP 范围：抗生素暂不纳入生产训练集。
FORMAL_OP_POLLUTANTS = {
    "Sum_PAH_ngg", "BaP_ngg", "SumPCB_ngg", "SumDDT_ngg", "SumHCH_ngg",
    "SumPBDE_ngg", "SumOCP_ngg", "TotalPHC_mgkg", "SumPAE_ngg", "OPEs_ngg",
    "Nap_ngg", "Acy_ngg", "Ace_ngg", "Flu_ngg", "Phe_ngg", "Ant_ngg",
    "Flt_ngg", "Pyr_ngg", "BaA_ngg", "Chr_ngg", "BbF_ngg", "BkF_ngg",
    "Ind_ngg", "DahA_ngg", "BghiP_ngg",
}
HM_POLLUTANTS = {
    "Cd_mgkg", "Pb_mgkg", "Cr_mgkg", "As_mgkg", "Hg_mgkg", "Cu_mgkg",
    "Zn_mgkg", "Ni_mgkg", "Co_mgkg", "Mn_mgkg", "Sb_mgkg", "Fe_mgkg",
    "Al_mgkg", "V_mgkg", "Be_mgkg",
}


def partition_rows_by_sample(rows):
    """按同一采样点判定复合污染，禁止论文级伪拼接。"""
    by_sample = defaultdict(list)
    for row in rows:
        by_sample[row["sample_id"]].append(row)
    partitions = {"hm_op": [], "op_only": [], "hm_only": [], "other": []}
    for sample_rows in by_sample.values():
        pollutants = {row["pollutant_std"] for row in sample_rows}
        has_hm = bool(pollutants & HM_POLLUTANTS)
        has_op = bool(pollutants & FORMAL_OP_POLLUTANTS)
        key = "hm_op" if has_hm and has_op else "op_only" if has_op else "hm_only" if has_hm else "other"
        partitions[key].extend(sample_rows)
    return partitions

# ===== 值域守卫 =====
def is_valid_value(val_str, pollutant_std):
    """检查浓度值是否在合理范围。"""
    try:
        v = float(val_str)
    except (ValueError, TypeError):
        return False
    if pollutant_std.endswith("_mgkg"):
        if v <= 0: return False
        if v > 1_000_000: return False  # 100万 mg/kg 不可能
    elif pollutant_std.endswith("_ngg"):
        if v <= 0: return False
        if v > 10_000_000: return False  # 10M ng/g = 10g/g 不可能
    elif pollutant_std == "pH":
        if v < 0 or v > 14: return False
    elif pollutant_std in ("OC_pct", "OM_pct"):
        if v < 0 or v > 100: return False
    elif pollutant_std == "CEC_cmolkg":
        if v < 0 or v > 500: return False
    elif pollutant_std in ("Clay_pct", "Sand_pct", "Silt_pct"):
        if v < 0 or v > 100: return False
    return True


def infer_matrix_from_md(dir_name):
    """从 MinerU 解析的 MD 文本关键词匹配推断 matrix。"""
    full = BASE / dir_name
    if not full.exists(): return "unknown", "no_dir"
    try:
        inner_name = os.listdir(str(full))[0]
        inner = full / inner_name / "auto"
        md_files = list(inner.glob("*.md"))
        if not md_files: return "unknown", "no_md"
        text = open(str(md_files[0]), "r", encoding="utf-8").read()
    except Exception:
        return "unknown", "err"

    text_lower = text.lower()
    title_text = text[:500].lower()
    scores = Counter()
    for mtype, patterns in MATRIX_KEYWORDS.items():
        for pat in patterns:
            scores[mtype] += len(re.findall(pat, title_text, re.I)) * 3
            scores[mtype] += len(re.findall(pat, text_lower, re.I))
    if not scores: return "unknown", "no_matrix_evidence"
    best = scores.most_common(1)[0]
    conf = "high" if best[1] >= 20 else ("medium" if best[1] >= 10 else "low")
    return best[0], f"score={best[1]}:{conf}"


def is_training_evidence_complete(record):
    """正式训练记录必须能追溯到原文表格、明确单位和土壤介质。"""
    required = ("paper_id", "sample_id", "pollutant_std", "value", "unit",
                "evidence_location", "matrix")
    if any(not str(record.get(field, "")).strip() for field in required):
        return False
    if str(record["unit"]).strip().lower() in {"unknown", "na", "n/a"}:
        return False
    if record["matrix"] != "soil":
        return False
    return str(record["evidence_location"]).startswith("table_p")


def main():
    # 1. 读取原始数据
    if not BATCH2_RAW.exists():
        print(f"{BATCH2_RAW} not found!")
        return
    with open(str(BATCH2_RAW), "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"原始: {len(rows)} 行")

    # 2. 清理: 过滤统计表、值域
    before = len(rows)
    rows = [r for r in rows if not any(
        kw in (r.get("source_caption", "") or "").lower() for kw in STAT_TABLE_KEYWORDS)]
    print(f"过滤统计表: -{before - len(rows)} (余 {len(rows)})")

    before = len(rows)
    rows = [r for r in rows if is_valid_value(r["value"], r["pollutant_std"])]
    print(f"过滤无效值: -{before - len(rows)} (余 {len(rows)})")

    # 保存清理后
    cleaned_csv = PHASE14_DIR / "_batch2_cleaned_long.csv"
    with open(str(cleaned_csv), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"清理后: {len(rows)} 行 → {cleaned_csv}")

    # 3. 填充 matrix (按 dir_name 批处理)
    pids = list(set(r["paper_id"] for r in rows))
    dir_map = {}
    all_parsed = [d for d in os.listdir(str(BASE)) if os.path.isdir(str(BASE / d))]
    for d in all_parsed:
        dpid = d.replace(".pdf", "").replace("-main", "").replace("%2528", "(").replace("%2529", ")")[:50]
        for pid in pids:
            if pid in dpid or dpid in pid:
                dir_map[pid] = d
                break
    print(f"Matrix 目录映射: {len(dir_map)}/{len(pids)}")

    matrix_cache = {}
    for pid in pids:
        if pid not in matrix_cache:
            if pid in dir_map:
                m, note = infer_matrix_from_md(dir_map[pid])
            else:
                m, note = "unknown", "no_dir_map"
            matrix_cache[pid] = (m, note)
    matrix_counts = Counter(m for m, _ in matrix_cache.values())
    print(f"Matrix 分布: {dict(matrix_counts.most_common())}")

    # 4. 分类型保存 → manual_extract/op_only/ 和 hm_op/
    EXISTING_FIELDS = ["paper_id", "sample_id", "pollutant_std", "value", "unit",
                       "evidence_location", "matrix", "site_type", "province",
                       "extract_notes", "latitude", "longitude"]

    hm_pollutants = HM_POLLUTANTS
    op_pollutants = FORMAL_OP_POLLUTANTS

    # 按 paper_id 聚合分类
    by_paper = defaultdict(list)
    for r in rows:
        by_paper[r["paper_id"]].append(r)

    op_only_pids, hm_op_pids, hm_only_pids = [], [], []
    op_new, hmop_new = 0, 0
    total_hm_op_rows = 0

    for pid, prows in by_paper.items():
        partitions = partition_rows_by_sample(prows)
        has_hm = bool(partitions["hm_only"] or partitions["hm_op"])
        has_op = bool(partitions["op_only"] or partitions["hm_op"])

        if partitions["hm_op"]:
            pool = "hm_op"
            hm_op_pids.append(pid)
            prows = partitions["hm_op"]
        elif partitions["op_only"]:
            pool = "op_only"
            op_only_pids.append(pid)
            prows = partitions["op_only"]
        elif has_hm:
            pool = "hm_only"
            hm_only_pids.append(pid)
        else:
            pool = "other"
            continue  # 仅有理化性质，不入训练集

        m, note = matrix_cache.get(pid, ("unknown", "missing_matrix_evidence"))

        # 写入对应目录 (CSV 逐 paper)
        if pool == "op_only":
            dest = ME_OP / f"{pid}.csv"
        elif pool == "hm_op":
            dest = ME_HMOP / f"{pid}.csv"
        else:
            continue  # hm_only 不参加复合

        if not dest.exists():
            if pool == "op_only": op_new += 1
            else: hmop_new += 1

        with open(str(dest), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=EXISTING_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for r in prows:
                nr = {k: r.get(k, "") for k in EXISTING_FIELDS}
                nr["matrix"] = m
                nr["extract_notes"] = f"phase14_batch2; matrix={note}; conf={r.get('confidence','')}; flag={r.get('value_flag','')}"
                writer.writerow(nr)

        if pool == "hm_op":
            total_hm_op_rows += sum(1 for r in prows if r["pollutant_std"] in op_pollutants)

    print(f"\n{'='*60}")
    print(f"Phase 14 第二批整合完成")
    print(f"{'='*60}")
    print(f"原始: {len(rows)} 行 / {len(by_paper)} 论文")
    print(f"OP-only: {len(op_only_pids)} 论文 ({op_new} 新增)")
    print(f"HM+OP:   {len(hm_op_pids)} 论文 ({hmop_new} 新增, {total_hm_op_rows} OP行)")
    print(f"HM-only: {len(hm_only_pids)} 论文")

    total_op = len(list(ME_OP.glob("*.csv")))
    total_hmop = len(list(ME_HMOP.glob("*.csv")))
    print(f"\n合并后 manual_extract 总量:")
    print(f"  op_only/: {total_op} 篇")
    print(f"  hm_op/:   {total_hmop} 篇")

if __name__ == "__main__":
    main()
