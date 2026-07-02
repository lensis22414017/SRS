#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
shap_contribution_filter.py — SHAP 三态清洗
====================================================================
把 *_shap_global.parquet 拆成四类:
  - measured_contribution: x_measured_* (实测因子,进 KOS 正式 Top-N)
  - family_contribution: x_family_* (族群,进 extended KOS)
  - missing_signal: x_missing_* (缺失指示器,只做数据质量)
  - proxy_signal: x_proxy_gee_* (GEE 背景协变量,只做背景解释)

前端关键障碍只读 measured + family。
====================================================================
"""
import os
import glob
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT)
ART = "ml/artifacts/p3_alpha"
OUT = "artifacts/overnight_20260703/shap_filtered"


def classify_group(group_name: str) -> str:
    """根据 group 名判断四类"""
    g = str(group_name)
    if "缺失指示" in g:
        return "missing_signal"
    if g.startswith("GEE_"):
        return "proxy_signal"
    if "族群" in g:
        return "family_contribution"
    return "measured_contribution"


def filter_model(model_id: str) -> dict:
    """清洗单个模型的 SHAP global"""
    sg_path = f"{ART}/{model_id}_shap_global.parquet"
    if not os.path.exists(sg_path):
        return {"model_id": model_id, "error": "shap_global 不存在"}
    sg = pd.read_parquet(sg_path)
    sg["category"] = sg["group"].apply(classify_group)

    measured = sg[sg["category"] == "measured_contribution"].copy()
    family = sg[sg["category"] == "family_contribution"].copy()
    missing = sg[sg["category"] == "missing_signal"].copy()
    proxy = sg[sg["category"] == "proxy_signal"].copy()

    # 归一化 measured 贡献份额(用于 KOS M)
    if len(measured) > 0 and measured["mean_abs_shap"].sum() > 0:
        measured["contribution_share_normalized"] = measured["mean_abs_shap"] / measured["mean_abs_shap"].sum()

    # 保存
    tag = model_id.replace("_Full_RandomForest", "")
    measured.to_csv(f"{OUT}/{tag}_measured_contribution_global.csv", index=False)
    if len(family) > 0:
        family.to_csv(f"{OUT}/{tag}_family_contribution_global.csv", index=False)
    if len(missing) > 0:
        missing.to_csv(f"{OUT}/{tag}_missing_signal_global.csv", index=False)
    if len(proxy) > 0:
        proxy.to_csv(f"{OUT}/{tag}_proxy_signal_global.csv", index=False)

    return {
        "model_id": model_id,
        "measured": len(measured),
        "family": len(family),
        "missing": len(missing),
        "proxy": len(proxy),
        "measured_top3": measured.head(3)["group"].tolist() if len(measured) > 0 else [],
    }


def main():
    os.makedirs(OUT, exist_ok=True)
    print("=" * 60)
    print("SHAP 三态清洗")
    print("=" * 60)

    summary = []
    for sg_path in sorted(glob.glob(f"{ART}/*_Full_*_shap_global.parquet")):
        model_id = os.path.basename(sg_path).replace("_shap_global.parquet", "")
        r = filter_model(model_id)
        summary.append(r)
        if "error" not in r:
            print(f"  {model_id}: measured={r['measured']} family={r['family']} missing={r['missing']} proxy={r['proxy']}")
            print(f"    measured Top3: {r['measured_top3']}")

    # 汇总报告
    md = ["# SHAP 三态清洗汇总", ""]
    md.append("| 模型 | measured | family | missing | proxy | measured Top-3 |")
    md.append("|---|---|---|---|---|---|")
    for r in summary:
        if "error" not in r:
            md.append(f"| {r['model_id']} | {r['measured']} | {r['family']} | {r['missing']} | {r['proxy']} | {r['measured_top3']} |")
    md.append("")
    md.append("**规则**:前端关键障碍只读 measured + family;missing/proxy 只进数据质量提示,不进障碍排名。")
    with open(f"{OUT}/shap_filter_summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\n汇总: {OUT}/shap_filter_summary.md")


if __name__ == "__main__":
    main()
