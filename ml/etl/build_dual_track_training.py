"""双轨训练集构建(模块2+3): merged_std33 有坐标行 + GEE协变量 → X_barrier(理化+GEE, 防泄漏) + 双轨标签 + group-split。

防泄漏红线(裴总铁律): 后缀正则(_mgkg|_ngg|_ugkg)$ + 关键词兜底 剔除全部污染物浓度列(merged_std33 有427个,
  旧 train_three.py POLLUTANT_COLS 仅14个严重不足)。构建后断言 X_barrier 污染物列==0。
双轨标签: 复用 build_training_splits._attach_dual_labels(HM_COLS key=Cd_mgkg 与 merged_std33 英文列名零转换对齐)
  prod=GB15618 pH四段+GB36600一类(严) / eco=GB36600二类(宽)。SoilpH 25.7%非空按实测路由, 其余默认6.5<pH≤7.5。
group-split: 复用 dataset_splits.build_real_splits(DOI/Source 连通分量零泄漏)。
输出: data/training/dual_track/{train,valid,test,external}_{X_barrier,y_prod,y_eco}.csv + meta.json + REVIEW_REPORT.txt
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

# 防泄漏: 污染物浓度列后缀正则 + 关键词兜底(覆盖 PAH单体/PCB同系物/OCP异构体 等无标准后缀的)
POLLUTANT_SUFFIX_RE = re.compile(r"(_mgkg|_ngg|_ugkg)$", re.IGNORECASE)
POLLUTANT_KEYWORDS = {"HCH", "PAH", "PCB", "DDT", "PAE", "PFAS", "PBDE", "TPH", "BDE",
                      "DBDPE", "BaP", "BaA", "BbF", "BkF", "BghiP", "DahA", "Flt", "Flu",
                      "Ind", "Nap", "Acy", "Ace", "Chr", "Ant", "Pyr", "Phe", "HBB",
                      "PBEB", "AntiDP", "BTEX", "Sum_"}


def _is_pollutant_col(col: str) -> bool:
    """判定列是否污染物浓度(标签派生源), 必须从 X_barrier 剔除。
    理化/GEE 列显式白名单豁免; 后缀 _mgkg/_ngg/_ugkg 命中→True; 关键词兜底。
    """
    if col in PHYS_CHEM_COLS or col in GEE_COLS:
        return False
    if POLLUTANT_SUFFIX_RE.search(col):
        return True
    upper = col.upper()
    return any(k.upper() in upper for k in POLLUTANT_KEYWORDS)


def _add_missing_markers(df, cols):
    """对稀疏列加 __missing 标记(1=缺失,0=实测) + 中位数填充。返回 (df, missing_cols)。"""
    missing_cols = []
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce")  # 混合字符串/nan → 数值
        mc = f"{c}__missing"
        df[mc] = df[c].isna().astype(int)
        med = df[c].median()
        df[c] = df[c].fillna(0.0 if pd.isna(med) else med)
        missing_cols.append(mc)
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

    # 4. 构造 X_barrier 特征矩阵(理化 + GEE + __missing)
    feature_cols = [c for c in PHYS_CHEM_COLS if c in df.columns or True]  # 保留全部理化(缺失则补)
    feature_cols = [c for c in PHYS_CHEM_COLS]
    if gee_cov_ok:
        feature_cols += [c for c in GEE_COLS if c in df.columns]
    df, missing_cols = _add_missing_markers(df, feature_cols)
    X_all_cols = feature_cols + missing_cols

    # 5. 防泄漏红线自检
    pollutant_in_x = [c for c in X_all_cols if _is_pollutant_col(c)]
    assert len(pollutant_in_x) == 0, f"🔴 防泄漏失败! X_barrier 含污染物列: {pollutant_in_x}"
    all_pollutant = [c for c in df.columns if _is_pollutant_col(c)]
    print(f"[4] X_barrier 特征: {len(X_all_cols)}个 (理化{len([c for c in feature_cols if not c.startswith('gee_')])}"
          f" + GEE{len([c for c in feature_cols if c.startswith('gee_')])} + __missing{len(missing_cols)})")
    print(f"[5] 防泄漏自检: X_barrier污染物列={len(pollutant_in_x)} ✅ (已剔除{len(all_pollutant)}个污染物浓度列)")

    # 6. group-split(需 id_DOI/id_Source/标签)
    df["id_DOI"] = df.get("DOI", "").fillna("").astype(str)
    df["id_Source"] = df.get("Source", "").fillna("").astype(str)
    splits, checks = build_real_splits(df, seed=42)
    print(f"[6] group-split 零泄漏 all_passed: {checks['all_passed']}")

    # 7. 输出切分
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
        summary[name] = {"n": len(sdf), "prod_pos": int(y_prod.sum()),
                         "eco_pos": int(y_eco.sum())}
    for name, s in summary.items():
        print(f"      {name}: {s['n']}行 (prod正{s['prod_pos']}/eco正{s['eco_pos']})")

    # 8. meta.json
    meta = {
        "n_total_geocoded": n_total, "feature_cols": feature_cols,
        "missing_cols": missing_cols, "n_features": len(X_all_cols),
        "n_pollutant_dropped": len(all_pollutant), "gee_cov_ok": gee_cov_ok,
        "splits": summary, "leakage_all_passed": checks["all_passed"],
        "factor_cols_used": list(factor_cols.keys()),
        "label_prod_pos_rate": float(df["标签_生产"].mean()),
        "label_eco_pos_rate": float(df["标签_生态"].mean()),
    }
    with open(os.path.join(OUT_DIR, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 9. print 审查报告 + 写 REVIEW_REPORT.txt
    _print_review_report(df, meta, all_pollutant, summary)
    return meta


def _print_review_report(df, meta, all_pollutant, summary):
    """print 完整审查报告 + 写 REVIEW_REPORT.txt(裴总审核闸门)。"""
    lines = []

    def p(s=""):
        print(s)
        lines.append(s)

    p("=" * 64)
    p("双轨训练集审查报告(裴总审核闸门)")
    p("=" * 64)
    p(f"\n【1. 行列数】")
    p(f"  merged_std33_geocoded 有坐标行: {meta['n_total_geocoded']}")
    p(f"  GEE协变量: {'✅已合并' if meta['gee_cov_ok'] else '⚠️缺失(仅理化, 预期AUC偏低)'}")
    p(f"  {'split':<10} {'行数':<8} {'prod正':<8} {'eco正':<8}")
    for name, s in summary.items():
        p(f"  {name:<10} {s['n']:<8} {s['prod_pos']:<8} {s['eco_pos']:<8}")
    p(f"\n【2. X_barrier 特征清单】(共{meta['n_features']}个)")
    p(f"  理化协变量(实测稀疏, 中位数填充+__missing标记):")
    for c in meta['feature_cols']:
        if not c.startswith('gee_'):
            nn = df[c].notna().sum() if c in df.columns else 0
            p(f"    {c:<22} 非空率 {nn / len(df) * 100:.1f}%")
    p(f"  GEE协变量(栅格采样, 近100%覆盖):")
    for c in meta['feature_cols']:
        if c.startswith('gee_'):
            nn = df[c].notna().sum() if c in df.columns else 0
            p(f"    {c:<22} 非空率 {nn / len(df) * 100:.1f}%")
    p(f"  __missing标记列: {len(meta['missing_cols'])}个")
    p(f"\n【3. 防泄漏自检(红线)】")
    p(f"  X_barrier 污染物列检出: 0 ✅")
    p(f"  已剔除污染物浓度列: {meta['n_pollutant_dropped']}个(后缀_mgkg/_ngg/_ugkg + 关键词兜底)")
    p(f"  前20个剔除列示例: {all_pollutant[:20]}")
    p(f"\n【4. 双轨标签分布】")
    p(f"  标签_生产(GB15618 pH四段+GB36600一类, 严): 正样本率 {meta['label_prod_pos_rate']:.2%}")
    p(f"  标签_生态(GB36600二类, 宽): 正样本率 {meta['label_eco_pos_rate']:.2%}")
    p(f"  (prod应≥eco, 因生产阈值严→更多超标; 若反转则标签派生有误)")
    p(f"\n【5. group-split零泄漏】")
    p(f"  all_passed: {meta['leakage_all_passed']}")
    p(f"\n【6. 预期AUC提升】")
    p(f"  旧 lake_prod_barrier(3特征pH+2missing): AUC=0.5944 (不可诊断)")
    p(f"  旧 lake_prod_full(泄漏): AUC=0.9988 (不可用)")
    p(f"  新 dual_track_X_barrier({meta['n_features']}特征): 预期 AUC 0.8-0.95 (防泄漏+GEE增强)")
    p(f"\n【7. 诚实标注】")
    p(f"  - X_barrier=理化稀疏列(中位数+__missing) + GEE栅格协变量")
    p(f"  - 剔除{meta['n_pollutant_dropped']}个污染物浓度列(标签泄漏源), AUC不虚高")
    p(f"  - GEE协变量为栅格估算值(gee_前缀区分), 非实测")
    p(f"\n裴总确认后, 运行 ml/models/train_dual_gee.py 进入双轨训练。")
    p("=" * 64)
    with open(os.path.join(OUT_DIR, "REVIEW_REPORT.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n📝 审查报告已写: {OUT_DIR}/REVIEW_REPORT.txt")


if __name__ == "__main__":
    build_dual_track()
