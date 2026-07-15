"""Phase 14 数据清理与合并脚本

1. 去重 (_dup_ 标记 → 保留行数最多的版本)
2. 剔除明显错误 (负值/超标/pH>14 等)
3. 按 sample_id 聚合 → OP-only / HM+OP 判定
4. 与现有 SOIL_CLEAN 合并
"""
from __future__ import annotations
import sys, csv, re
from pathlib import Path
from collections import defaultdict, Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PHASE14_DIR = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining\manual_extract\phase14")
OUT_DIR = Path(r"C:\Users\曾鸿\Desktop\SRS\outputs\literature_mining")

# HM/OP 判定 (对齐 common.py)
HM_POLLUTANTS = {"Cd_mgkg", "Pb_mgkg", "Cr_mgkg", "As_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg",
                 "Ni_mgkg", "Co_mgkg", "Mn_mgkg", "Sb_mgkg", "Fe_mgkg", "Al_mgkg", "V_mgkg", "Be_mgkg"}
OP_POLLUTANTS = {"Sum_PAH_ngg", "BaP_ngg", "SumPCB_ngg", "SumDDT_ngg", "SumHCH_ngg",
                 "SumPBDE_ngg", "SumOCP_ngg", "TotalPHC_mgkg", "SumPAE_ngg", "OPEs_ngg",
                 "Nap_ngg", "Acy_ngg", "Ace_ngg", "Flu_ngg", "Phe_ngg", "Ant_ngg",
                 "Flt_ngg", "Pyr_ngg", "BaA_ngg", "Chr_ngg", "BbF_ngg", "BkF_ngg",
                 "Ind_ngg", "DahA_ngg", "BghiP_ngg",
                 "SMZ_ngg", "CTC_ngg", "OTC_ngg", "ENRO_ngg", "SDZ_ngg",
                 "HM_total", "OP_total"}
PHYS_CHEM = {"pH", "OC_pct", "OM_pct", "CEC_cmolkg", "EC_mScm", "Clay_pct", "Sand_pct", "Silt_pct"}

# 合理值范围
VALID_RANGES = {
    "pH": (2.0, 14.0),
    "OC_pct": (0.0, 60.0),
    "OM_pct": (0.0, 80.0),
    "Clay_pct": (0.0, 100.0),
    "Sand_pct": (0.0, 100.0),
    "Silt_pct": (0.0, 100.0),
    "CEC_cmolkg": (0.0, 200.0),
    "EC_mScm": (0.0, 100.0),
    # HM (mg/kg) - 全球极端值上限
    "Cd_mgkg": (0.0, 10000.0),
    "Pb_mgkg": (0.0, 500000.0),
    "Cr_mgkg": (0.0, 500000.0),
    "As_mgkg": (0.0, 100000.0),
    "Hg_mgkg": (0.0, 10000.0),
    "Cu_mgkg": (0.0, 200000.0),
    "Zn_mgkg": (0.0, 200000.0),
    "Ni_mgkg": (0.0, 100000.0),
    "Co_mgkg": (0.0, 50000.0),
    "Mn_mgkg": (0.0, 200000.0),
    "Sb_mgkg": (0.0, 10000.0),
    "Fe_mgkg": (0.0, 200000.0),
    "Al_mgkg": (0.0, 500000.0),
    "V_mgkg": (0.0, 50000.0),
    "Be_mgkg": (0.0, 1000.0),
    # OP (ng/g)
    "Sum_PAH_ngg": (0.0, 500000.0),
    "BaP_ngg": (0.0, 50000.0),
    "SumPCB_ngg": (0.0, 100000.0),
    "SumDDT_ngg": (0.0, 200000.0),
    "SumHCH_ngg": (0.0, 200000.0),
    "SumPBDE_ngg": (0.0, 100000.0),
    "SumOCP_ngg": (0.0, 200000.0),
    "TotalPHC_mgkg": (0.0, 200000.0),
}

def is_valid_value(pollutant, value_str):
    """检查值是否在合理范围内。"""
    try:
        v = float(value_str)
    except (ValueError, TypeError):
        return False
    if v < 0:
        return False
    if pollutant in VALID_RANGES:
        lo, hi = VALID_RANGES[pollutant]
        return lo <= v <= hi
    # 默认上限: 1M
    return v <= 1000000.0


def dedup_papers(rows_by_paper):
    """去重: 同一论文多副本 (_dup_) 保留行数最多的版本。"""
    # 分组: 归一化 paper_id (去 _dup_ 后缀)
    normalized = defaultdict(list)
    for pid, paper_rows in rows_by_paper.items():
        # 去除 _dup_ 前缀和后缀
        base = re.sub(r'^_dup_', '', pid)
        base = re.sub(r'_dup\d*$', '', base)
        normalized[base].append((pid, len(paper_rows), paper_rows))

    kept = {}
    for base, candidates in normalized.items():
        # 按行数降序排列, 保留最多的
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_pid, nrows, best_rows = candidates[0]
        kept[best_pid] = best_rows
        if len(candidates) > 1 and len(candidates) <= 3:
            pass  # 不去重 (同一研究团队不同时期数据)

    return kept


def extract_site_info(paper_dir_name):
    """从目录名提取 DOI/来源信息。"""
    # 清理
    name = paper_dir_name.replace(".pdf", "").replace("-main", "")
    # 提取 DOI
    doi_match = re.search(r'(10\.\d{4,}/[^\s]+)', name)
    if doi_match:
        return doi_match.group(1)
    return name[:80]


def main():
    # 1. 读取全量数据
    all_csv = PHASE14_DIR / "_all_raw.csv"
    if not all_csv.exists():
        print("_all_raw.csv not found!")
        return

    with open(str(all_csv), "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        all_rows = list(reader)

    print(f"原始行数: {len(all_rows)}")

    # 2. 按 paper_id 分组
    rows_by_paper = defaultdict(list)
    for r in all_rows:
        rows_by_paper[r["paper_id"]].append(r)

    print(f"原始论文数: {len(rows_by_paper)}")

    # 3. 去重
    rows_by_paper = dedup_papers(rows_by_paper)
    print(f"去重后论文数: {len(rows_by_paper)}")

    # 4. 数据质量过滤
    clean_rows = []
    removed = Counter()
    for pid, paper_rows in rows_by_paper.items():
        for r in paper_rows:
            pid_std = r["pollutant_std"]
            # 跳过低置信度
            if r.get("confidence") == "low" and pid_std in ("HM_total", "OP_total"):
                removed["low_confidence"] += 1
                continue
            # 验证数值
            if not is_valid_value(pid_std, r["value"]):
                removed[f"invalid_{pid_std}"] += 1
                continue
            # 跳过纯理化指标 (非污染物)
            if pid_std in PHYS_CHEM:
                # 保留 pH 和 OC (重要协变量)
                if pid_std in ("pH", "OC_pct", "CEC_cmolkg"):
                    pass
                else:
                    removed[f"phys_chem_{pid_std}"] += 1
                    continue

            clean_rows.append(r)

    print(f"清理后行数: {len(clean_rows)}")
    print(f"剔除统计: {dict(removed.most_common(10))}")

    # 5. 按采样点聚合 → 判定 OP-only / HM-only / HM+OP
    # Phase 14 数据目前没有 lat/lon/province/matrix 等字段
    # 需要: (a) 按 sample_id 聚合; (b) 从 paper_id/DOI 推断省/矩阵/场地类型
    by_sample = defaultdict(list)
    for r in clean_rows:
        sid = r["sample_id"]
        by_sample[sid].append(r)

    print(f"唯一采样点: {len(by_sample)}")

    # 6. 判定每个采样点的类型
    op_only_samples = []
    hm_only_samples = []
    hm_op_samples = []

    for sid, srows in by_sample.items():
        pollutants = set(r["pollutant_std"] for r in srows)
        has_hm = bool(pollutants & HM_POLLUTANTS)
        has_op = bool(pollutants & OP_POLLUTANTS)

        if has_hm and has_op:
            hm_op_samples.append(sid)
        elif has_op:
            op_only_samples.append(sid)
        elif has_hm:
            hm_only_samples.append(sid)

    print(f"\nOP-only 采样点: {len(op_only_samples)}")
    print(f"HM-only 采样点: {len(hm_only_samples)}")
    print(f"HM+OP 采样点: {len(hm_op_samples)}")

    # 7. 输出清理后的数据
    # 为每行添加缺失字段
    fieldnames = ["paper_id", "sample_id", "site_label", "pollutant_std", "value",
                  "unit", "value_flag", "confidence", "evidence_location", "source_caption",
                  "matrix", "site_type", "province", "latitude", "longitude", "source_pool"]

    # 保存清理后的长格式
    cleaned_rows = []
    for r in clean_rows:
        nr = {k: r.get(k, "") for k in fieldnames}
        nr["source_pool"] = "phase14"
        nr["matrix"] = ""  # 待 Workflow agent 填充
        nr["province"] = ""  # 待从论文 MD 文本提取
        cleaned_rows.append(nr)

    cleaned_csv = OUT_DIR / "manual_extract" / "phase14" / "_cleaned_long.csv"
    with open(str(cleaned_csv), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    print(f"\n清理后数据: {cleaned_csv} ({len(cleaned_rows)} rows)")

    # 8. 生成各论文的单独 CSV
    phase14_op = PHASE14_DIR / "op_only"
    phase14_hmop = PHASE14_DIR / "hm_op"
    phase14_hm = PHASE14_DIR / "hm_only"
    phase14_op.mkdir(exist_ok=True)
    phase14_hmop.mkdir(exist_ok=True)
    phase14_hm.mkdir(exist_ok=True)

    op_only_pids = set()
    hm_op_pids = set()
    hm_only_pids = set()

    for r in cleaned_rows:
        sid = r["sample_id"]
        pid = r["paper_id"]
        if sid in op_only_samples:
            op_only_pids.add(pid)
        elif sid in hm_op_samples:
            hm_op_pids.add(pid)
        elif sid in hm_only_samples:
            hm_only_pids.add(pid)

    # 按论文分组保存
    for pid in op_only_pids:
        prows = [r for r in cleaned_rows if r["sample_id"] in op_only_samples and r["paper_id"] == pid]
        with open(str(phase14_op / f"{pid}.csv"), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(prows)

    for pid in hm_op_pids:
        prows = [r for r in cleaned_rows if r["sample_id"] in hm_op_samples and r["paper_id"] == pid]
        with open(str(phase14_hmop / f"{pid}.csv"), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(prows)

    for pid in hm_only_pids:
        prows = [r for r in cleaned_rows if r["sample_id"] in hm_only_samples and r["paper_id"] == pid]
        with open(str(phase14_hm / f"{pid}.csv"), "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(prows)

    print(f"OP-only 论文: {len(op_only_pids)} ({len(op_only_samples)} samples)")
    print(f"HM+OP 论文: {len(hm_op_pids)} ({len(hm_op_samples)} samples)")
    print(f"HM-only 论文: {len(hm_only_pids)} ({len(hm_only_samples)} samples)")

    # 9. 输出汇总统计
    print(f"\n{'='*60}")
    print(f"Phase 14 筛选统计")
    print(f"{'='*60}")
    print(f"总提取行: {len(all_rows)}")
    print(f"清理后: {len(cleaned_rows)}")
    print(f"剔除: {len(all_rows) - len(cleaned_rows)} ({100*(len(all_rows)-len(cleaned_rows))/len(all_rows):.1f}%)")
    print(f"")
    print(f"OP-only: {len(op_only_samples)} 样本/{len(op_only_pids)} 论文")
    print(f"HM+OP:   {len(hm_op_samples)} 样本/{len(hm_op_pids)} 论文")
    print(f"HM-only: {len(hm_only_samples)} 样本/{len(hm_only_pids)} 论文")

    return cleaned_rows

if __name__ == "__main__":
    main()
