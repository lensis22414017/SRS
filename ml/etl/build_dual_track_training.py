"""双轨训练集构建 zzv0.3 重训版(0泄漏 + 保留非派生浓度列 + 原生NaN)。

防泄漏红线(项目组, � = group split(DOI/Source 连通分量跨集零重叠) + GroupKFold CV。
  只剔除 20 个标签派生因子列(HM_COLS 8 + ORG_COLS_MAP 12, 标签直接由这些列的国标阈值算出 → 保留=标签泄漏)。
  其余 ~454 个非派生浓度列(PAH单体/PCB同系物/Fe/Mn等)保留作特征 —— 真实诊断时这些就是输入信号。
缺失值: 不再中位数填充, 保留原始NaN, 由 sklearn 1.4+ 的 RF/ET/HGB 原生处理(树分裂时学缺失值走左/右)。
  仅保留 __missing 标记列记录缺失位置。
双轨标签: 复用 build_training_splits._attach_dual_labels
  prod=GB15618 pH四段+GB36600一类(严) / eco=GB36600二类(宽)。
group-split: 复用 dataset_splits.build_real_splits(DOI/Source 连通分量零泄漏)。
输出: data/training/dual_track/{train,valid,test,external}_{X_barrier,y_prod,y_eco,groups}.csv + meta.json
"""
import os
import sys
import re
import json

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows GBK终端兼容emoji
except Exception:
    pass

import pandas as pd
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))
sys.path.insert(0, os.path.join(ROOT, "ml", "etl"))

from dataset_splits import build_real_splits  # noqa: E402
from build_training_splits import (  # noqa: E402
    HM_COLS, ORG_COLS_MAP, _attach_dual_labels, _load_thresh_csv, _load_org_thresholds,
    THRESH_PROD, THRESH_ECO,
)

GEOCODED_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_geocoded.csv")
GEE_COV_CSV = os.path.join(ROOT, "data", "covariates", "merged_std33_gee_covariates.csv")
OUT_DIR = os.path.join(ROOT, "data", "training", "dual_track")

# 理化+环境协变量(数据湖自带, 稀疏但真实, 非污染物)
# 7基础理化 + 4数据湖环境协变量(Elevation_m地形/MAP_mm气候/EC_mScm电导率/TN_gkg全氮)
PHYS_CHEM_COLS = ["SoilpH", "OC_pct", "CEC_cmolkg", "Sand_pct", "Silt_pct",
                  "Clay_pct", "SoilBD_gcm3",
                  "Elevation_m", "MAP_mm", "EC_mScm", "TN_gkg"]
# GEE协变量(gee_fetch.py 输出15列)
GEE_COLS = ["gee_ndvi", "gee_precip_annual_mm", "gee_temp_mean_c",
            "gee_elevation_m", "gee_slope_deg", "gee_aspect_deg",
            "gee_soil_pH", "gee_soc_g_kg", "gee_cec_cmol_kg", "gee_clay_pct",
            "gee_sand_pct", "gee_silt_pct", "gee_bulk_density_g_cm3", "gee_nitrogen_g_kg"]

# ── zzv0.3 重训: 浓度列策略 ──────────────────────────────────────────────
# 标签派生因子列(20个): 标签_生产/标签_生态 直接由这些列按国标阈值算出。
#   保留它们作特征 = 标签泄漏(AUC虚高到0.99), 必须剔除。
LABEL_FACTOR_COLS = set(HM_COLS) | set(ORG_COLS_MAP.keys())  # 8 HM + 12 OP = 20

# 非派生浓度列识别(与旧防泄漏逻辑同款, 但仅用于统计, 不再剔除)
POLLUTANT_SUFFIX_RE = re.compile(r"(_mgkg|_ngg|_ugkg)$", re.IGNORECASE)
POLLUTANT_KEYWORDS = {"HCH", "PAH", "PCB", "DDT", "PAE", "PFAS", "PBDE", "TPH", "BDE",
                      "DBDPE", "BaP", "BaA", "BbF", "BkF", "BghiP", "DahA", "Flt", "Flu",
                      "Ind", "Nap", "Acy", "Ace", "Chr", "Ant", "Pyr", "Phe", "HBB",
                      "PBEB", "AntiDP", "BTEX", "Sum_"}


def _is_pollutant_col(col: str) -> bool:
    """判定列是否污染物浓度(供统计用)。理化/GEE 列显式白名单豁免。"""
    if col in PHYS_CHEM_COLS or col in GEE_COLS:
        return False
    if POLLUTANT_SUFFIX_RE.search(col):
        return True
    upper = col.upper()
    return any(k.upper() in upper for k in POLLUTANT_KEYWORDS)


def _add_missing_markers(df, cols):
    """zzv0.3: 对特征列加 __missing 标记(1=缺失,0=实测), 不再中位数填充(保留原始NaN供树模型原生处理)。
    返回 (df, missing_cols)。"""
    missing_cols = []
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")  # 混合字符串/nan → 数值
        mc = f"{c}__missing"
        df[mc] = df[c].isna().astype(int)
        missing_cols.append(mc)  # 只标记, 不 fillna —— 树模型原生吃 NaN
    return df, missing_cols


def build_dual_track():
    os.makedirs(OUT_DIR, exist_ok=True)
    print("=" * 64)
    print("双轨训练集构建(防泄漏 + GEE协变量增强)")
    print("=" * 64)

    # 1. 读 geocoded 子集
    df = pd.read_csv(GEOCODED_CSV, low_memory=False)
    n_total = len(df)
    print(f"[1] merged_std33_geocoded: {n_total} 行 × {len(df.columns)} 列")

    # 2. 合并 GEE 协变量(按 site_id)
    gee_cov_ok = False
    if os.path.exists(GEE_COV_CSV):
        gee = pd.read_csv(GEE_COV_CSV)
        df = df.merge(gee, on="site_id", how="left")
        gee_cov_ok = True
        print(f"[2] 合并 GEE 协变量: {len(gee)} 行 × {len(gee.columns)} 列")
    else:
        print(f"[2] ⚠️ GEE协变量不存在({GEE_COV_CSV}), 仅用理化(预期AUC偏低)")

    # 3. 双轨标签(复用 _attach_dual_labels, HM_COLS key 与 merged 英文列名零转换)
    factor_cols = {**HM_COLS, **ORG_COLS_MAP}
    factor_cols = {k: v for k, v in factor_cols.items() if k in df.columns}
    prod_rows = _load_thresh_csv(THRESH_PROD)
    eco_rows = _load_thresh_csv(THRESH_ECO)
    org_thresh = _load_org_thresholds()
    _attach_dual_labels(df, factor_cols, prod_rows, eco_rows, org_thresh)
    print(f"[3] 双轨标签: 因子列{len(factor_cols)}个 | prod正={df['标签_生产'].mean():.2%} eco正={df['标签_生态'].mean():.2%}")

    # 4. 构造 X_barrier 特征矩阵(理化 + GEE + 非派生浓度列 + __missing)
    #    zzv0.3: 保留非派生浓度列(剔除20个标签派生列防标签泄漏), 缺失值不填充(树模型原生NaN)
    feature_cols = [c for c in PHYS_CHEM_COLS]
    if gee_cov_ok:
        feature_cols += [c for c in GEE_COLS if c in df.columns]
    # 非派生浓度列: 是污染物浓度列, 但不在20个标签派生列中 → 保留作特征
    all_pollutant = [c for c in df.columns if _is_pollutant_col(c)]
    non_label_pollutant = [c for c in all_pollutant if c not in LABEL_FACTOR_COLS]
    pollutant_in_x = [c for c in all_pollutant if c in LABEL_FACTOR_COLS]  # 应=20
    feature_cols += non_label_pollutant  # 保留非派生浓度列
    df, missing_cols = _add_missing_markers(df, feature_cols)
    X_all_cols = feature_cols + missing_cols

    # 5. 防泄漏红线自检: 0泄漏 = 标签派生列不在特征中 + group split all_passed
    leaked = [c for c in X_all_cols if c in LABEL_FACTOR_COLS]
    assert len(leaked) == 0, f"🔴 标签泄漏! X_barrier 含标签派生列: {leaked}"
    n_phys = len([c for c in feature_cols if c in PHYS_CHEM_COLS])
    n_gee = len([c for c in feature_cols if c in GEE_COLS])
    n_conc = len(non_label_pollutant)
    print(f"[4] X_barrier 特征: {len(X_all_cols)}个 (理化{n_phys} + GEE{n_gee} + 非派生浓度列{n_conc} + __missing{len(missing_cols)})")
    print(f"[5] 防泄漏自检: 标签派生列(20个)已剔除 ✅ | 保留非派生浓度列{n_conc}个")

    # 6. group-split(需 id_DOI/id_Source/标签)
    df["id_DOI"] = df.get("DOI", "").fillna("").astype(str)
    df["id_Source"] = df.get("Source", "").fillna("").astype(str)
    splits, checks = build_real_splits(df, seed=42)
    print(f"[6] group-split 零泄漏 all_passed: {checks['all_passed']}")

    # 7. 输出切分(含 groups.csv 供 GroupKFold 用, 解决 CV 同文献跨折泄漏)
    rename = {"train_real": "train", "valid_real_group_split": "valid",
              "test_real_group_split": "test", "external_literature_holdout": "external"}
    summary = {}
    for k, sdf in splits.items():
        name = rename.get(k, k)
        X = sdf[X_all_cols].copy()
        y_prod = sdf["标签_生产"].astype(int)
        y_eco = sdf["标签_生态"].astype(int)
        X.to_csv(os.path.join(OUT_DIR, f"{name}_X_barrier.csv"), index=False)
        y_prod.to_csv(os.path.join(OUT_DIR, f"{name}_y_prod.csv"), index=False)
        y_eco.to_csv(os.path.join(OUT_DIR, f"{name}_y_eco.csv"), index=False)
        # zzv0.3: 导出 groups(DOI 连通分量键) 供 GroupKFold 防 CV 内部同文献跨折泄漏
        sdf[["id_DOI", "id_Source"]].to_csv(
            os.path.join(OUT_DIR, f"{name}_groups.csv"), index=False)
        summary[name] = {"n": len(sdf), "prod_pos": int(y_prod.sum()),
                         "eco_pos": int(y_eco.sum())}
    for name, s in summary.items():
        print(f"      {name}: {s['n']}行 (prod正{s['prod_pos']}/eco正{s['eco_pos']})")

    # 8. meta.json
    meta = {
        "version": "zzv0.3_0leakage_conc_retrain",
        "n_total_geocoded": n_total, "feature_cols": feature_cols,
        "missing_cols": missing_cols, "n_features": len(X_all_cols),
        "n_label_factor_dropped": len(pollutant_in_x),  # 剔除的标签派生列(20)
        "n_non_label_conc_kept": len(non_label_pollutant),  # 保留的非派生浓度列
        "gee_cov_ok": gee_cov_ok,
        "splits": summary, "leakage_all_passed": checks["all_passed"],
        "factor_cols_used": list(factor_cols.keys()),
        "label_prod_pos_rate": float(df["标签_生产"].mean()),
        "label_eco_pos_rate": float(df["标签_生态"].mean()),
        "missing_value_policy": "原生NaN(树模型处理, 不填充)",
    }
    with open(os.path.join(OUT_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 9. print 审查报告 + 写 REVIEW_REPORT.txt
    _print_review_report(df, meta, non_label_pollutant, pollutant_in_x, summary)
    return meta


def _print_review_report(df, meta, non_label_pollutant, label_factor_dropped, summary):
    """print 完整审查报告 + 写 REVIEW_REPORT.txt(项目组审核闸门)。zzv0.3 重训版。"""
    lines = []

    def p(s=""):
        print(s)
        lines.append(s)

    p("=" * 64)
    p("双轨训练集审查报告 zzv0.3 重训版 (0泄漏 + 保留非派生浓度列 + 原生NaN)")
    p("=" * 64)
    p(f"\n【1. 行列数】")
    p(f"  merged_std33_geocoded 有坐标行: {meta['n_total_geocoded']}")
    p(f"  GEE协变量: {'✅已合并' if meta['gee_cov_ok'] else '⚠️缺失'}")
    p(f"  {'split':<10} {'行数':<8} {'prod正':<8} {'eco正':<8}")
    for name, s in summary.items():
        p(f"  {name:<10} {s['n']:<8} {s['prod_pos']:<8} {s['eco_pos']:<8}")
    p(f"\n【2. X_barrier 特征清单】(共{meta['n_features']}个)")
    p(f"  理化协变量(原生NaN, __missing标记):")
    for c in meta['feature_cols']:
        if c in PHYS_CHEM_COLS:
            nn = df[c].notna().sum() if c in df.columns else 0
            p(f"    {c:<22} 非空率 {nn / len(df) * 100:.1f}%")
    p(f"  GEE协变量(栅格采样):")
    for c in meta['feature_cols']:
        if c in GEE_COLS:
            nn = df[c].notna().sum() if c in df.columns else 0
            p(f"    {c:<22} 非空率 {nn / len(df) * 100:.1f}%")
    p(f"  非派生浓度列(原生NaN): {meta['n_non_label_conc_kept']}个")
    sig = [(c, df[c].notna().mean()) for c in non_label_pollutant if c in df.columns]
    sig = sorted(sig, key=lambda x: -x[1])[:10]
    p(f"    非空率TOP10: " + ", ".join(f"{c}({r*100:.1f}%)" for c, r in sig))
    p(f"  __missing标记列: {len(meta['missing_cols'])}个")
    p(f"\n【3. 防泄漏自检(0泄漏红线)】")
    p(f"  标签派生列剔除: {meta['n_label_factor_dropped']}个 ✅ ({label_factor_dropped})")
    p(f"  非派生浓度列保留: {meta['n_non_label_conc_kept']}个(非标签来源, 合法特征)")
    p(f"  group-split 跨集零重叠: {meta['leakage_all_passed']}")
    p(f"\n【4. 双轨标签分布】")
    p(f"  标签_生产(严): 正样本率 {meta['label_prod_pos_rate']:.2%}")
    p(f"  标签_生态(宽): 正样本率 {meta['label_eco_pos_rate']:.2%}")
    p(f"\n【5. 缺失值策略】")
    p(f"  {meta['missing_value_policy']} —— 树模型(RF/ET/HGB sklearn1.4+)原生处理NaN")
    p(f"\n确认后, 运行 ml/autoresearch_dual_track/ 进入 karpathy 迭代训练。")
    p("=" * 64)
    with open(os.path.join(OUT_DIR, "REVIEW_REPORT.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n📝 审查报告已写: {OUT_DIR}/REVIEW_REPORT.txt")


if __name__ == "__main__":
    build_dual_track()
