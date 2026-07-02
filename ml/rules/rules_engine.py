"""P2: 规则引擎 + 权重引擎 + OI_t目标引擎。
规则层: B(障碍判定) + R(方向感知severity四型)
权重层: W(用途权重, 来自课题二)
目标层: OI_t(用途轨障碍指数, 回归目标)
"""
import os
import sys
import math
import json
import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_geocoded.csv")
THRESH_PROD = os.path.join(ROOT, "data", "thresholds", "threshold_library_production.csv")
THRESH_ECO = os.path.join(ROOT, "data", "thresholds", "threshold_library_ecology.csv")
WEIGHT_CSV = os.path.join(ROOT, "data", "weights", "track_weight_library.csv")
OUT_RULES = os.path.join(ROOT, "outputs", "rules")
OUT_TARGETS = os.path.join(ROOT, "outputs", "targets")
os.makedirs(OUT_RULES, exist_ok=True)
os.makedirs(OUT_TARGETS, exist_ok=True)

CAP_RATIO = 10  # severity截尾倍数


# ============ 规则引擎 ============

def compute_B(value, threshold_type, upper, lower, ideal_min, ideal_max):
    """障碍存在性 B: 0或1。"""
    if pd.isna(value):
        return 0
    val = float(value)
    if threshold_type == "upper":
        return 1 if (pd.notna(upper) and val > float(upper)) else 0
    elif threshold_type == "lower":
        return 1 if (pd.notna(lower) and val < float(lower)) else 0
    elif threshold_type == "interval":
        lo = float(ideal_min) if pd.notna(ideal_min) else None
        hi = float(ideal_max) if pd.notna(ideal_max) else None
        if lo is not None and hi is not None:
            return 0 if lo <= val <= hi else 1
        return 0
    elif threshold_type == "ordinal":
        return 0  # 等级型需自定义映射, 默认不判
    return 0


def compute_R(value, threshold_type, upper, lower, ideal_min, ideal_max, cap=CAP_RATIO):
    """规则严重度 R: 0~1。方向感知四型。"""
    if pd.isna(value):
        return 0.0
    val = float(value)
    eps = 1e-9
    if threshold_type == "upper":
        U = float(upper) if pd.notna(upper) else None
        if U is None or U <= 0:
            return 0.0
        if val <= U:
            return 0.0
        return min(1.0, math.log(1 + val / U) / math.log(1 + cap))
    elif threshold_type == "lower":
        L = float(lower) if pd.notna(lower) else None
        if L is None or L <= 0 or val <= 0:
            return 0.0
        if val >= L:
            return 0.0
        return min(1.0, math.log(1 + L / val) / math.log(1 + cap))
    elif threshold_type == "interval":
        lo = float(ideal_min) if pd.notna(ideal_min) else None
        hi = float(ideal_max) if pd.notna(ideal_max) else None
        if lo is None or hi is None:
            return 0.0
        if lo <= val <= hi:
            return 0.0
        d_low = max(lo * 0.3, 0.5)
        d_high = max(hi * 0.3, 0.5)
        if val < lo:
            return min(1.0, (lo - val) / d_low)
        else:
            return min(1.0, (val - hi) / d_high)
    return 0.0


# ============ 权重引擎 ============

def load_weights(track: str, perturbation: float = 0.0) -> dict:
    """加载用途权重, 返回 {factor_name: W}。perturbation: ±扰动比例。"""
    df = pd.read_csv(WEIGHT_CSV)
    df = df[df["track"] == track]
    rng = np.random.RandomState(42)
    weights = {}
    for _, r in df.iterrows():
        w = r["W_normalized"]
        if perturbation > 0:
            w = w * (1 + rng.uniform(-perturbation, perturbation))
        weights[r["factor_name"]] = max(0, w)
    return weights


# ============ OI引擎 ============

def compute_oi(rule_rows: list, weights: dict) -> float:
    """OI_t = Σ(B*R*W*D) / Σ(W*D)。D=已检测1/未检测0。"""
    numerator = 0.0
    denominator = 0.0
    for r in rule_rows:
        D = 1 if r["detected"] else 0
        W = weights.get(r.get("factor_name", ""), 0.0)
        B = r["B"]
        R = r["R"]
        numerator += B * R * W * D
        denominator += W * D
    if denominator == 0:
        return 0.0
    return numerator / denominator


# ============ 主流程: 生成rule_outputs + oi_targets ============

def run_track(track: str, thresh_csv: str):
    """对一条轨道跑规则层, 输出rule_outputs + oi_targets。"""
    print(f"\n{'='*48}")
    print(f"[{track}] 规则层计算")
    print(f"{'='*48}")

    df = pd.read_csv(RAW_CSV, low_memory=False)
    thresh = pd.read_csv(thresh_csv, encoding="utf-8-sig")
    weights = load_weights(track)

    # 因子名→数据列名映射
    name_to_col = {
        "镉": "Cd_mgkg", "铅": "Pb_mgkg", "砷": "As_mgkg", "铬": "Cr_mgkg",
        "汞": "Hg_mgkg", "铜": "Cu_mgkg", "锌": "Zn_mgkg", "镍": "Ni_mgkg",
        "苯并[a]芘": "BaP_ngg", "多环芳烃总量": "Sum_PAH_ngg",
        "滴滴涕": "SumDDTs_ngg", "六六六": "SumHCHs_ngg", "多氯联苯": "SumPCB_ngg",
        "pH": "SoilpH", "有机质": "OC_pct", "有机碳含量": "OC_pct",
        "阳离子交换量": "CEC_cmolkg", "土壤容重": "SoilBD_gcm3",
        "盐渍化程度": "EC_mScm", "全氮": "TN_gkg",
    }

    # 去重阈值(每因子取第一条)
    thresh_unique = thresh.drop_duplicates(subset="factor_name", keep="first")

    all_rule_rows = []
    oi_values = []

    factors_matched = 0
    factors_unmatched = []

    for _, thr in thresh_unique.iterrows():
        fname = thr["factor_name"]
        col = name_to_col.get(fname)
        if col is None or col not in df.columns:
            factors_unmatched.append(fname)
            continue
        factors_matched += 1

        values = pd.to_numeric(df[col], errors="coerce")
        ttype = thr["threshold_type"]
        upper = thr.get("upper_limit")
        lower = thr.get("lower_limit")
        imin = thr.get("ideal_min")
        imax = thr.get("ideal_max")

        for idx, val in values.items():
            if pd.isna(val):
                all_rule_rows.append({
                    "sample_idx": idx, "site_id": df.loc[idx, "site_id"] if "site_id" in df else idx,
                    "factor_name": fname, "factor_col": col, "track": track,
                    "value": None, "detected": False, "B": 0, "R": 0.0,
                    "threshold_type": ttype, "upper_limit": upper, "lower_limit": lower,
                    "standard_source": thr.get("standard_source"),
                })
            else:
                B = compute_B(val, ttype, upper, lower, imin, imax)
                R = compute_R(val, ttype, upper, lower, imin, imax)
                all_rule_rows.append({
                    "sample_idx": idx, "site_id": df.loc[idx, "site_id"] if "site_id" in df else idx,
                    "factor_name": fname, "factor_col": col, "track": track,
                    "value": float(val), "detected": True, "B": B, "R": round(R, 4),
                    "threshold_type": ttype, "upper_limit": upper, "lower_limit": lower,
                    "standard_source": thr.get("standard_source"),
                })

    # 输出rule_outputs(采样, 避免文件过大: 每个场地取代表行)
    rule_df = pd.DataFrame(all_rule_rows)
    # 只输出B=1的(明确障碍) + 每因子的统计, 减小文件
    obstacle_rows = rule_df[rule_df["B"] == 1].copy()
    obstacle_rows.to_csv(os.path.join(OUT_RULES, f"rule_outputs_{track}.csv"),
                         index=False, encoding="utf-8-sig")
    print(f"  规则输出: {len(obstacle_rows)}条障碍记录 → rule_outputs_{track}.csv")
    print(f"  因子匹配: {factors_matched}个匹配, {len(factors_unmatched)}个未匹配")
    if factors_unmatched:
        print(f"  未匹配因子: {factors_unmatched[:10]}")

    # 按场地(site_id/sample_idx)算OI_t
    oi_rows = []
    for idx in rule_df["sample_idx"].unique():
        sub = rule_df[rule_df["sample_idx"] == idx]
        oi = compute_oi(sub.to_dict("records"), weights)
        oi_rows.append({"sample_idx": idx,
                        "site_id": sub.iloc[0]["site_id"],
                        "track": track, "OI_t": round(oi, 4)})
    oi_df = pd.DataFrame(oi_rows)
    oi_df.to_csv(os.path.join(OUT_TARGETS, f"oi_targets_{track}.csv"),
                 index=False, encoding="utf-8-sig")
    print(f"  OI_t目标: {len(oi_df)}个样本 → oi_targets_{track}.csv")
    print(f"  OI_t分布: min={oi_df['OI_t'].min():.4f} max={oi_df['OI_t'].max():.4f} "
          f"mean={oi_df['OI_t'].mean():.4f} 正样本率(OI>0)={((oi_df['OI_t']>0).mean()*100):.1f}%")

    return {"track": track, "factors_matched": factors_matched,
            "factors_unmatched": factors_unmatched,
            "n_obstacles": len(obstacle_rows), "oi_mean": float(oi_df["OI_t"].mean())}


if __name__ == "__main__":
    print("=" * 64)
    print("P2: 规则引擎 + 权重引擎 + OI引擎")
    print("=" * 64)
    results = []
    results.append(run_track("production", THRESH_PROD))
    results.append(run_track("ecology", THRESH_ECO))

    # 汇总
    print("\n" + "=" * 64)
    print("P2 汇总")
    print("=" * 64)
    for r in results:
        print(f"  {r['track']}: 匹配{r['factors_matched']}因子, 障碍{r['n_obstacles']}条, "
              f"OI均值{r['oi_mean']:.4f}, 未匹配{len(r['factors_unmatched'])}因子")
    json.dump(results, open(os.path.join(ROOT, "outputs", "p2_summary.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n✅ P2 完成")
