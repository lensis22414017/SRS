"""P4 质量检查 (QA) + GroupKFold 分组统计

检查项 (裴总第五阶段):
  Q1: source_id + canonical_sample_id + pollutant_name_std 去重 (重复 → 报告)
  Q2: value_std 非负
  Q3: 单位换算 conversion_note 完整性 (有 value_std 但无 conversion_note)
  Q4: HM_OP training_ready 真配对验证 (同 canonical 同时含 HM 族 + OP 族)
  Q5: GroupKFold source_id 分组可行性 (每 source 的 sample 数, 最大组占比, 外层 5 折)
  Q6: pollutant_name_std 规范名覆盖率 (HM_RAW/OP_RAW 白名单)
  Q7: evidence_level + evidence_location 可追溯性

输出: qa_summary.json
"""
from __future__ import annotations
import sys
import json
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, HM_RAW, OP_RAW  # noqa: E402

import pandas as pd  # noqa: E402

VALID_STD = set(HM_RAW) | set(OP_RAW) | {"SumOPFR_ngg", "Co_mgkg", "Mn_mgkg"}


def main():
    df = pd.read_csv(OUT_DIR / "extracted_observations_long_op_hmop.csv",
                     dtype=str, keep_default_na=False)
    site = pd.read_csv(OUT_DIR / "site_dataset_summary_op_hmop.csv",
                      dtype=str, keep_default_na=False)
    df["value_std_num"] = pd.to_numeric(df["value_std"], errors="coerce")
    tr = df[df["readiness"] == "training_ready_hm_op"]
    qa = {}

    # ===== Q1: 主键去重 =====
    valid_obs = df[df["value_std_num"].notna()]
    key_cols = ["source_id", "canonical_sample_id", "pollutant_name_std"]
    dup = valid_obs[valid_obs.duplicated(subset=key_cols, keep=False)]
    qa["Q1_duplicate_obs"] = {
        "n_duplicate_rows": int(len(dup)),
        "n_duplicate_keys": int(dup[key_cols].drop_duplicates().shape[0]),
        "examples": dup[key_cols].drop_duplicates().head(5).to_dict("records"),
    }

    # ===== Q2: 非负 =====
    neg = df[df["value_std_num"] < 0]
    qa["Q2_negative_value"] = {"n_negative": int(len(neg))}

    # ===== Q3: conversion_note 完整性 =====
    has_val_no_note = df[(df["value_std_num"].notna()) &
                         (df["conversion_note"].str.strip() == "") &
                         (~df["unit_original"].str.lower().isin(["", "unknown", "nan"]))]
    qa["Q3_missing_conversion_note"] = {
        "n_missing": int(len(has_val_no_note)),
        "note": "unit_original 有值但 conversion_note 空 (单位可能未换算)",
    }

    # ===== Q4: HM_OP 真配对验证 =====
    tr_fam = tr.groupby("canonical_sample_id")["pollutant_family"].apply(lambda x: set(x))
    real_pair = [s for s, f in tr_fam.items() if "HM" in f and len(f - {"HM"}) > 0]
    fake_pair = [s for s, f in tr_fam.items() if not ("HM" in f and len(f - {"HM"}) > 0)]
    qa["Q4_hm_op_pairing"] = {
        "training_ready_samples": int(len(tr_fam)),
        "real_hm_op_paired": int(len(real_pair)),
        "suspicious_no_pair": int(len(fake_pair)),
        "note": "真配对 = 同 canonical 同时含 HM 族 + OP 族",
    }

    # ===== Q5: GroupKFold source 分组 =====
    tr_sites = site[site["readiness"] == "training_ready_hm_op"]
    source_counts = tr_sites.groupby("source_id")["sample_id"].nunique().sort_values(ascending=False)
    n_sources = source_counts.shape[0]
    total_samples = int(source_counts.sum())
    max_source = int(source_counts.max()) if n_sources else 0
    max_ratio = max_source / total_samples if total_samples else 0
    # 外层 5 折: 至少需要 5 个 source, 每折 source 数均衡
    min_folds = min(5, n_sources)
    fold_feasible = n_sources >= 5
    qa["Q5_groupkfold_source"] = {
        "n_sources": int(n_sources),
        "total_samples": total_samples,
        "max_source_samples": max_source,
        "max_source_ratio": round(max_ratio, 3),
        "outer_folds_feasible": bool(fold_feasible),
        "source_distribution": source_counts.head(15).to_dict(),
        "leakage_risk": "高" if max_ratio > 0.3 else "中" if max_ratio > 0.15 else "低",
        "note": "GroupKFold 按 source_id 分组防泄漏; max_source_ratio>0.3 表示单论文占比过高",
    }

    # ===== Q6: 规范名覆盖率 =====
    invalid_std = df[~df["pollutant_name_std"].isin(VALID_STD)]
    qa["Q6_std_name_coverage"] = {
        "n_invalid_std_name": int(len(invalid_std)),
        "invalid_names": list(invalid_std["pollutant_name_std"].unique())[:10],
        "valid_whitelist_size": len(VALID_STD),
    }

    # ===== Q7: 可追溯性 =====
    no_evidence = df[df["evidence_location"].str.strip() == ""]
    no_level = df[~df["evidence_level"].isin(["A_sample_table", "B_site_summary"])]
    qa["Q7_traceability"] = {
        "n_missing_evidence_location": int(len(no_evidence)),
        "n_invalid_evidence_level": int(len(no_level)),
    }

    # ===== 总览 =====
    qa["summary"] = {
        "total_observations": int(len(df)),
        "total_papers": int(df["paper_id"].nunique()),
        "total_canonical_samples": int(site.shape[0]),
        "training_ready_hm_op_samples": int(len(tr_sites)),
        "training_ready_soil_samples": int((tr_sites["matrix_flag"] == "soil").sum()),
        "training_ready_sediment_samples": int((tr_sites["matrix_flag"] == "sediment_not_soil").sum()),
        "op_only_samples": int((site["readiness"] == "op_only_ready").sum()),
        "hm_only_samples": int((site["readiness"] == "hm_only_ready").sum()),
        "source_groups_tr": int(n_sources),
        "peizong_threshold_100sample_10source": bool(total_samples >= 100 and n_sources >= 10),
        "soil_threshold_100sample_10source": bool(
            (tr_sites["matrix_flag"] == "soil").sum() >= 100 and
            tr_sites[tr_sites["matrix_flag"] == "soil"]["source_id"].nunique() >= 10),
    }

    # 输出 JSON
    out_path = OUT_DIR / "qa_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(qa, f, ensure_ascii=False, indent=2)

    # 打印
    print(f"=== P4 QA 结果 ===\n")
    print(f"[Q1 重复观测] {qa['Q1_duplicate_obs']['n_duplicate_rows']} 行 / {qa['Q1_duplicate_obs']['n_duplicate_keys']} 键")
    print(f"[Q2 负值] {qa['Q2_negative_value']['n_negative']}")
    print(f"[Q3 缺 conversion_note] {qa['Q3_missing_conversion_note']['n_missing']}")
    print(f"[Q4 真配对] {qa['Q4_hm_op_pairing']['real_hm_op_paired']}/{qa['Q4_hm_op_pairing']['training_ready_samples']}")
    print(f"[Q5 GroupKFold] {n_sources} source / {total_samples} sample / 最大源占比 {max_ratio:.1%} / 泄漏风险={qa['Q5_groupkfold_source']['leakage_risk']}")
    print(f"[Q6 规范名] {qa['Q6_std_name_coverage']['n_invalid_std_name']} 个非白名单")
    print(f"[Q7 可追溯] missing_location={qa['Q7_traceability']['n_missing_evidence_location']} invalid_level={qa['Q7_traceability']['n_invalid_evidence_level']}")
    print(f"\n[总览] training_ready: {qa['summary']['training_ready_hm_op_samples']} (土壤 {qa['summary']['training_ready_soil_samples']} + 沉积物 {qa['summary']['training_ready_sediment_samples']})")
    print(f"  含沉积物达门槛: {qa['summary']['peizong_threshold_100sample_10source']}")
    print(f"  纯土壤达门槛: {qa['summary']['soil_threshold_100sample_10source']}")
    print(f"\n输出: {out_path}")


if __name__ == "__main__":
    main()
