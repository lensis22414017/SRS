"""P3 训练可用性判定 + 防伪复合检查

核心任务:
  1. 采样点归一化: _s{ri}_{label} + _tr{ci}_{label} 中相同采样点标签 → {pid}_{LABEL}
     → 救回跨表配对 (P01524 tbl#1 HM + tbl#3 PCB, 同批采样点 A/B/C)
  2. readiness 判定 (按 canonical_sample_id):
     - training_ready_hm_op: 同一 canonical 同时有 HM 族 + OP 族 (A 级)
     - site_level_hm_op_only: 同 source_id+site_name 有 HM 和 OP 但 canonical 不匹配 (B 级)
     - op_only_ready: 仅 OP (无 HM 配对)
     - hm_only_ready: 仅 HM (无 OP 配对, 备用)
     - not_training_ready: summary mean / 无有效数值 / 假阳性
  3. 防伪复合 (裴总铁律):
     - 不把风险指数当浓度 (已在 P2 排除 risk_or_source)
     - 不把全省均值当场地 (summary _mean 标记)
     - 不把模型预测当实测 (无 proxy 数据进 measured)
     - 跨表配对必须同 source_id + 同采样点标签 (不允许跨论文拼接)
  4. 假阳性最终标记: value=1 漏标 / 合并单元格伪值

输出:
  - extracted_observations_long_op_hmop.csv (更新: +canonical_sample_id, +readiness)
  - site_dataset_summary_op_hmop.csv (每 canonical 一行)
"""
from __future__ import annotations
import sys
import re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, HM_RAW, OP_RAW  # noqa: E402

import pandas as pd  # noqa: E402

HM_STD_SET = set(HM_RAW)  # 8 个 HM
OP_STD_SET = set(OP_RAW)  # 10 个 OP 族 (含 BaP, SumOCP 等)


def canonical_sample_id(pid: str, sample_id: str) -> tuple[str, bool]:
    """归一化 sample_id. 返回 (canonical_id, is_cross_table_pairable).

    规则:
      _s{ri}_{label} / _tr{ci}_{label} 中 label 为单字母/字母+数字 → {pid}_{LABEL}
      _mean → 保持原样 (site-level summary, 不跨表配对)
      描述性 label (中文/recycle/optimum) → 保持原样 (不可跨表配对)
    """
    if sample_id == pid:
        return sample_id, False
    # 匹配 _s{数字}_{label} 或 _tr{数字}_{label}
    m = re.match(rf"^{re.escape(pid)}_(?:s|tr)\d+_(.+)$", sample_id)
    if not m:
        # _mean 或其他
        return sample_id, False
    label_raw = m.group(1)
    # 清洗: 去非字母数字
    label_clean = re.sub(r"[^\w]", "", label_raw)
    # 单字母 (A-Z/a-z) 或 字母+1数字 (A1/B2) → 跨表配对 key
    if re.match(r"^[A-Za-z]\d?$", label_clean):
        return f"{pid}_{label_clean.upper()}", True
    # 多字符字母 (如 AB/ABC) 也可能是采样点编号
    if re.match(r"^[A-Za-z]{1,3}$", label_clean) and len(label_clean) <= 3:
        return f"{pid}_{label_clean.upper()}", True
    # 数字编号 (S1/S2/sample1)
    if re.match(r"^[A-Za-z]?\d{1,3}$", label_clean):
        return f"{pid}_{label_clean.upper()}", True
    # 描述性 (中文/recycle/optimum/场地类型) → 不配对
    return sample_id, False


def main():
    df = pd.read_csv(OUT_DIR / "extracted_observations_long_op_hmop.csv",
                     dtype=str, keep_default_na=False)
    df["value_std"] = pd.to_numeric(df["value_std"], errors="coerce")
    print(f"加载观测: {len(df)} 条, {df['paper_id'].nunique()} 论文")

    # ===== Step 1: canonical_sample_id 归一化 =====
    canons = []
    pairable_flags = []
    for _, r in df.iterrows():
        c, p = canonical_sample_id(r["paper_id"], r["sample_id"])
        canons.append(c)
        pairable_flags.append(p)
    df["canonical_sample_id"] = canons
    df["cross_table_pairable"] = pairable_flags

    n_paired = df[df["cross_table_pairable"]]["canonical_sample_id"].nunique()
    print(f"归一化后 canonical_sample_id: {df['canonical_sample_id'].nunique()} (其中可跨表配对标签: {n_paired})")

    # ===== Step 2: 假阳性最终标记 =====
    # value=1 且未标 qa_flag 的, 补标
    v1_mask = (df["value_std"] == 1.0) & (~df["qa_flag"].str.contains("value_is_1", na=False))
    df.loc[v1_mask, "qa_flag"] = df.loc[v1_mask, "qa_flag"].apply(
        lambda x: (x + ";value_is_1_suspicious") if x else "value_is_1_suspicious")
    print(f"补标 value=1 可疑: {v1_mask.sum()} 条")

    # ===== Step 3: 按 canonical_sample_id 判 readiness =====
    # 有效观测 = 有 value_std 且非 non_numeric 且非负 (浓度物理非负)
    neg_mask = df["value_std"] < 0
    df.loc[neg_mask, "qa_flag"] = df.loc[neg_mask, "qa_flag"].apply(
        lambda x: (x + ";negative_invalid") if x else "negative_invalid")
    df.loc[neg_mask, "value_std"] = pd.NA  # 清空负值
    valid = df[df["value_std"].notna() & (df["censoring_flag"] != "non_numeric")].copy()
    # 排除 value=1 伪值 (qa_flag 标记的)
    valid = valid[~valid["qa_flag"].str.contains("value_is_1", na=False)]
    # 去重: 同 source+canonical+pollutant 多值 (转置表多 Total 行) 取首个
    valid_clean = valid.drop_duplicates(
        subset=["source_id", "canonical_sample_id", "pollutant_name_std"], keep="first").copy()

    # 按 canonical 聚合
    def classify_group(g):
        families = set(g["pollutant_family"])
        has_hm = "HM" in families
        has_op = len(families - {"HM"}) > 0
        ev_levels = set(g["evidence_level"])
        is_summary_only = (ev_levels == {"B_site_summary"})
        hm_elements = sorted(set(g.loc[g["pollutant_family"] == "HM", "pollutant_name_std"]))
        op_families = sorted(families - {"HM"})
        return pd.Series({
            "source_id": g["source_id"].iloc[0],
            "paper_id": g["paper_id"].iloc[0],
            "site_name": g["site_name"].iloc[0][:40],
            "n_hm_obs": (g["pollutant_family"] == "HM").sum(),
            "n_op_obs": (g["pollutant_family"] != "HM").sum(),
            "n_hm_elements": len(hm_elements),
            "n_op_families": len(op_families),
            "hm_elements": ",".join(hm_elements),
            "op_families": ",".join(op_families),
            "has_hm": has_hm,
            "has_op": has_op,
            "hm_op_paired": has_hm and has_op,
            "is_summary_only": is_summary_only,
            "evidence_level": "B_site_summary" if is_summary_only else "A_sample_table",
            "land_use": g["land_use"].iloc[0],
            "province": g["province"].iloc[0],
        })

    summary = valid_clean.groupby("canonical_sample_id").apply(classify_group, include_groups=False).reset_index()

    def readiness_label(r):
        if r["hm_op_paired"] and not r["is_summary_only"]:
            return "training_ready_hm_op"
        if r["hm_op_paired"] and r["is_summary_only"]:
            return "site_level_hm_op_only"
        if r["has_op"] and not r["has_hm"]:
            return "op_only_ready"
        if r["has_hm"] and not r["has_op"]:
            return "hm_only_ready"
        return "not_training_ready"

    summary["readiness"] = summary.apply(readiness_label, axis=1)

    # ===== Step 4: 跨表配对验证 (防伪复合) =====
    # 确认每个 training_ready_hm_op 的 HM 和 OP 来自同一 source_id (不跨论文拼接)
    cross_check = valid_clean.groupby("canonical_sample_id").agg(
        n_source=("source_id", "nunique"),
        n_paper=("paper_id", "nunique"),
    ).reset_index()
    summary = summary.merge(cross_check, on="canonical_sample_id", how="left")
    # 单 source 的才能训练 (多 source = 跨论文误拼)
    summary.loc[summary["n_source"] > 1, "readiness"] = "not_training_ready_cross_source"
    summary.loc[summary["n_source"] > 1, "qa_flag"] = "cross_source_invalid"

    # ===== Step 4b: 矩阵标记 (沉积物/污泥/降尘等非土壤基质, 保留但标记) =====
    # 裴总铁律: 不把非土壤当土壤训练. 沉积物接近电子垃圾场地但需裴总定夺.
    title_by_pid = df.drop_duplicates("paper_id").set_index("paper_id")["title"].to_dict()
    sediment_pids = {pid for pid, t in title_by_pid.items()
                     if re.search(r"\bsediment|sludge|降尘|污泥|沉积物|\bdust\b", str(t), re.I)}
    summary["matrix_flag"] = summary.apply(
        lambda r: "sediment_not_soil" if r["paper_id"] in sediment_pids else "soil", axis=1)
    if "qa_flag" not in summary.columns:
        summary["qa_flag"] = ""
    summary["qa_flag"] = summary["qa_flag"].fillna("")
    summary["qa_flag"] = summary.apply(
        lambda r: (r["qa_flag"] + ";sediment_not_soil" if r["qa_flag"]
                   else "sediment_not_soil") if r["paper_id"] in sediment_pids
        else r["qa_flag"], axis=1)

    # ===== Step 4c: 质量门禁 (跑题/重复/化学代号 sample) =====
    # (a) 跑题论文 (大气化学/遥感/甲醛模型, 非土壤污染)
    OFFTOPIC_PAT = re.compile(
        r"formaldehyde|\bhcho\b|geos-chem|atmospheric chemistry|"
        r"air quality model|satellite retrieval|\bozone\b|\bpm2\.5\b", re.I)
    offtopic_pids = {pid for pid, t in title_by_pid.items() if OFFTOPIC_PAT.search(str(t))}
    # (b) 重复论文 (同规范化标题只保留 paper_id 最小者, 其余标 duplicate)
    seen_titles: dict[str, str] = {}
    dup_pids: set[str] = set()
    for pid in sorted(summary["paper_id"].unique()):
        t = re.sub(r"\W+", "", str(title_by_pid.get(pid, "")).lower())[:80]
        if not t:
            continue
        if t in seen_titles:
            dup_pids.add(pid)
        else:
            seen_titles[t] = pid
    # (c) canonical 尾部是化学/族群代号 (find_label_column 误选元素列)
    CHEM_LABEL_PAT = re.compile(
        r"_(AS|CR|CU|CD|PB|ZN|HG|NI|CO|MN|FE|AL|SB|V|SE|SN|"
        r"DDT|HCH|PAH|PCB|PBDE|PFAS|PAE|OCP|TPH|PHC|BAP)$")

    # (d) 统计行 label (Max/Mean/Median/Min/SD/SEM/Range/Average 拼接)
    # 防止把转置表的统计行 (site-level summary) 误当独立采样点 (裴总铁律: 不把 summary 当场地样本)
    def is_stat_label(sample_id, pid):
        m = re.match(rf"^{re.escape(pid)}_(.+)$", str(sample_id))
        label = m.group(1) if m else ""
        s = label
        for u in ["cngg", "mgkg", "ugg", "cng", "ngg", "ppm", "ppb", "ppt", "ng", "mg", "ug", "kg", "gg", "cn", "g", "c"]:
            s = re.sub(re.escape(u), "", s, flags=re.I)
        s = re.sub(r"[\d\s_\-/.*()]", "", s).lower()
        if not s or len(s) < 2:
            return False
        # 排除含真实场景词 (煤矿/农田/站点等, "mining" 含 "min" 但非统计行)
        if re.search(r"mining|coal|farm|field|site|point|sample|station|village|town|factory|plant|park|road|river|lake", s):
            return False
        return bool(re.fullmatch(
            r"(mean|median|max|min|sem|sd|std|average|averag|range|"
            r"平均|均值|中位数|中位|最大值|最大|最小值|最小|标准差|方差|总和|极差|范围|极值)+", s, re.I))

    def _append_qa(old, tag):
        return (old + ";" + tag) if old else tag

    offtopic_mask = summary["paper_id"].isin(offtopic_pids)
    dup_mask = summary["paper_id"].isin(dup_pids)
    chem_mask = summary["canonical_sample_id"].str.contains(CHEM_LABEL_PAT, na=False, regex=True)
    stat_mask = summary.apply(lambda r: is_stat_label(r["canonical_sample_id"], r["paper_id"]), axis=1)
    for mask, ready_tag, qa_tag in [
        (offtopic_mask, "not_training_ready_offtopic", "offtopic_atmospheric"),
        (dup_mask, "not_training_ready_duplicate", "duplicate_paper"),
        (chem_mask, "not_training_ready_chem_label", "chem_symbol_as_sample"),
        (stat_mask, "not_training_ready_stat_row", "stat_row_as_sample"),
    ]:
        summary.loc[mask, "readiness"] = ready_tag
        summary.loc[mask, "qa_flag"] = summary.loc[mask, "qa_flag"].apply(
            lambda x, t=qa_tag: _append_qa(x, t))

    # ===== Step 5: 写 extracted CSV (加 canonical + readiness + matrix_flag) =====
    readiness_map = dict(zip(summary["canonical_sample_id"], summary["readiness"]))
    df["readiness"] = df["canonical_sample_id"].map(readiness_map).fillna("not_training_ready_no_value")
    # matrix_flag 映射到 long format (方便裴总审查每条观测的基质)
    pid_matrix = summary.drop_duplicates("paper_id").set_index("paper_id")["matrix_flag"].to_dict()
    df["matrix_flag"] = df["paper_id"].map(pid_matrix).fillna("soil")
    df.to_csv(OUT_DIR / "extracted_observations_long_op_hmop.csv", index=False, encoding="utf-8-sig")

    # site_dataset_summary_op_hmop.csv
    summary_out = summary[[
        "canonical_sample_id", "source_id", "paper_id", "site_name", "land_use", "province",
        "n_hm_obs", "n_op_obs", "n_hm_elements", "n_op_families",
        "hm_elements", "op_families", "has_hm", "has_op", "hm_op_paired",
        "is_summary_only", "evidence_level", "n_source", "matrix_flag", "readiness", "qa_flag",
    ]].rename(columns={"canonical_sample_id": "sample_id"})
    sd_path = OUT_DIR / "site_dataset_summary_op_hmop.csv"
    try:
        summary_out.to_csv(sd_path, index=False, encoding="utf-8-sig")
    except PermissionError:
        sd_path = OUT_DIR / "site_dataset_summary_op_hmop_v2.csv"
        summary_out.to_csv(sd_path, index=False, encoding="utf-8-sig")
        print(f"[警告] site_dataset_summary_op_hmop.csv 被 Excel 占用 → 写入 {sd_path.name}")
        print(f"       裴总请关闭 Excel 后重跑 P8 以恢复原名")

    # ===== 统计 =====
    print(f"\n=== P3 训练可用性判定结果 ===")
    print(f"canonical_sample_id 总数: {len(summary)}")
    print(f"\nreadiness 分布:")
    print(summary["readiness"].value_counts().to_string())

    tr = summary[summary["readiness"] == "training_ready_hm_op"]
    print(f"\n=== training_ready_hm_op (核心目标) ===")
    print(f"sample_id 数: {len(tr)}")
    print(f"source_groups (论文数): {tr['paper_id'].nunique()}")
    # 双口径: 纯土壤 vs 含沉积物 (裴总铁律: 沉积物非土壤, 需裴总定夺)
    tr_soil = tr[tr["matrix_flag"] == "soil"]
    tr_sed = tr[tr["matrix_flag"] == "sediment_not_soil"]
    print(f"  纯土壤: {len(tr_soil)} sample / {tr_soil['paper_id'].nunique()} source")
    print(f"  沉积物(标 qa_flag): {len(tr_sed)} sample / {tr_sed['paper_id'].nunique()} source")
    total = len(tr)
    sources = tr['paper_id'].nunique()
    print(f"达裴总门槛 (≥100 sample + ≥10 source):")
    print(f"  含沉积物口径 ({total}/{sources}): {'✅ 达标' if total >= 100 and sources >= 10 else '❌ 未达'}")
    print(f"  纯土壤口径 ({len(tr_soil)}/{tr_soil['paper_id'].nunique()}): {'✅ 达标' if len(tr_soil) >= 100 and tr_soil['paper_id'].nunique() >= 10 else '❌ 未达 (按裴总铁律不训练, 输出数据补强+缺口)'}")
    print(f"\ntraining_ready 论文贡献 (sample 数, 含基质标记):")
    tr_contrib = tr.groupby(["paper_id", "matrix_flag"]).size().reset_index(name="n")
    print(tr_contrib.sort_values("n", ascending=False).head(25).to_string(index=False))
    print(f"\n质量门禁排除统计:")
    for tag in ["not_training_ready_offtopic", "not_training_ready_duplicate",
                "not_training_ready_chem_label", "not_training_ready_stat_row"]:
        n = (summary["readiness"] == tag).sum()
        if n:
            pids = summary.loc[summary["readiness"] == tag, "paper_id"].unique()
            print(f"  {tag}: {n} sample ({list(pids)[:5]})")

    print(f"\n=== OP-only (OP 子模型补强) ===")
    op_only = summary[summary["readiness"] == "op_only_ready"]
    print(f"sample_id 数: {len(op_only)}, 论文: {op_only['paper_id'].nunique()}")

    print(f"\n=== site_level_hm_op_only (B 级, summary 配对) ===")
    sl = summary[summary["readiness"] == "site_level_hm_op_only"]
    print(f"sample_id 数: {len(sl)}, 论文: {sl['paper_id'].nunique()}")

    print(f"\n输出:")
    print(f"  extracted_observations_long_op_hmop.csv (含 canonical_sample_id + readiness)")
    print(f"  site_dataset_summary_op_hmop.csv ({len(summary_out)} 行)")


if __name__ == "__main__":
    main()
