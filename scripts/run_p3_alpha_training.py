#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
run_p3_alpha_training.py
====================================================================
P3-Alpha 训练入口(编排脚本)
====================================================================
放行口径(裴总批准):
- all/hm:production/ecology 双轨 × Full 消融 → 主模型(放行训练)
- op:production/ecology 双轨 × Full → 主模型(test 非零少,诚实声明)
- 消融(Full/MeasuredOnly/ContextOnly):仅在 all 上跑(节省时间)
- hm_op:不训练(仅外部案例)

每个组合产出:
- 模型 joblib + 指标 json + meta
- SHAP global/local parquet
====================================================================
"""
import os
import sys
import json
import time
from dataclasses import asdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import pandas as pd
import joblib

from ml.models.p3_regression_trainer import (
    P3RegressionTrainer, save_artifacts, load_subset, select_features, TRACK_TARGET
)
from ml.explain.shap_service import explain_regression

ARTIFACT = "ml/artifacts/p3_alpha"
GOLD = "autoresearch/obstacle_diagnosis_v0.8_gold_training_dataset"
D07 = f"{GOLD}/07_splits"


def log(msg):
    print(f"[p3_alpha] {msg}", flush=True)


def run_one(subset: str, track: str, ablation: str = "Full",
            model_name: str = "auto", do_shap: bool = True) -> dict:
    """训练单个组合并产出全部产物"""
    # 跳过已存在(model_name=auto 时先确定最优模型名再判断)
    t0 = time.time()
    log(f"── 训练 {subset}/{track}/{ablation}/{model_name} ──")
    trainer = P3RegressionTrainer(subset, track, ablation, model_name)
    result = trainer.train()
    tag = save_artifacts(result, trainer.model, trainer.feature_cols)
    log(f"  test: spearman={result.test_spearman:.4f} mae={result.test_mae:.4f} r2={result.test_r2:.4f} "
        f"CI=[{result.test_spearman_ci_low:.4f},{result.test_spearman_ci_high:.4f}] "
        f"top5_stab={result.top5_stability:.4f} ({time.time()-t0:.1f}s)")

    # ── SHAP(模型贡献度)──
    if do_shap:
        try:
            data = load_subset(subset)
            X_te = data["X_test"][trainer.feature_cols]
            test_sids = data["X_test"]["sample_id"].tolist()
            inner_model = trainer.model.named_steps["model"]
            shap_out = explain_regression(inner_model, X_te, sample_ids=test_sids,
                                          max_local=min(500, len(X_te)))
            # global → parquet
            pd.DataFrame(shap_out["global"]).to_parquet(
                f"{ARTIFACT}/{tag}_shap_global.parquet", index=False)
            # local → parquet(展平)
            local_rows = []
            for sid, items in shap_out["local"].items():
                for rank, it in enumerate(items):
                    local_rows.append({"sample_id": sid, "rank": rank, **it})
            pd.DataFrame(local_rows).to_parquet(
                f"{ARTIFACT}/{tag}_shap_local.parquet", index=False)
            # shap meta
            with open(f"{ARTIFACT}/{tag}_shap_meta.json", "w", encoding="utf-8") as f:
                json.dump({
                    "base_value": shap_out["base_value"],
                    "n_explained": shap_out["n_explained"],
                    "n_features": shap_out["n_features"],
                    "interpretation_note": shap_out["interpretation_note"],
                    "top5_global": [g["group"] for g in shap_out["global"][:5]],
                }, f, ensure_ascii=False, indent=2)
            log(f"  SHAP: global top3={[g['group'] for g in shap_out['global'][:3]]} "
                f"base={shap_out['base_value']:.4f}")
        except Exception as e:
            log(f"  ⚠️ SHAP 失败: {e}")
    return asdict(result)


def main():
    os.makedirs(ARTIFACT, exist_ok=True)
    log("=" * 60)
    log("P3-Alpha 双轨障碍指数回归训练")
    log("=" * 60)
    t_start = time.time()

    # 支持通过命令行参数指定要跑的子集批次,避免单次超时
    # 用法: python run_p3_alpha_training.py [batch]
    #   batch=main:  跑 all/hm/op × prod/eco × Full(主模型)
    #   batch=ablation: 跑 all × prod/eco × MeasuredOnly/ContextOnly(消融)
    #   batch=all:   全部(默认)
    #   batch=subset:track 形式可指定单组合, 如 hm:prod
    batch = sys.argv[1] if len(sys.argv) > 1 else "all"
    all_results = []

    def _should_run(subset, track, ablation):
        if batch == "all":
            return True
        if batch == "main":
            return ablation == "Full" and subset in ["all", "hm", "op"]
        if batch == "ablation":
            return subset == "all" and ablation != "Full"
        if ":" in batch:
            bs, bt = batch.split(":", 1)
            return subset == bs and track == bt
        return True

    # ── 主模型:all/hm/op × prod/eco × Full ──
    for subset in ["all", "hm", "op"]:
        if not os.path.exists(f"{GOLD}/08_training_ready/{subset}/X_train.parquet"):
            log(f"{subset} 不 ready, 跳过")
            continue
        for track in ["prod", "eco"]:
            if not _should_run(subset, track, "Full"):
                continue
            try:
                r = run_one(subset, track, "Full", "auto", do_shap=True)
                all_results.append(r)
            except Exception as e:
                log(f"  ❌ {subset}/{track} 失败: {e}")
                import traceback; traceback.print_exc()

    # ── 消融:仅在 all × prod/eco 上跑 MeasuredOnly/ContextOnly ──
    if batch in ("all", "ablation"):
        log("── 消融实验(all × prod/eco × 2 段)──")
        for track in ["prod", "eco"]:
            for ablation in ["MeasuredOnly", "ContextOnly"]:
                if not _should_run("all", track, ablation):
                    continue
                try:
                    r = run_one("all", track, ablation, "auto", do_shap=False)
                    all_results.append(r)
                except Exception as e:
                    log(f"  ❌ all/{track}/{ablation} 失败: {e}")

    # ── 汇总(增量合并已有 summary) ──
    summary_path = f"{ARTIFACT}/p3_alpha_summary.csv"
    existing = []
    if os.path.exists(summary_path):
        existing_df = pd.read_csv(summary_path)
        existing = existing_df.to_dict("records")
    combined = existing + all_results
    # 去重(同 subset/track/ablation/model_name 取最新)
    sdf = pd.DataFrame(combined)
    if len(sdf) > 0:
        sdf = sdf.drop_duplicates(subset=["subset", "track", "ablation", "model_name"], keep="last")
    sdf.to_csv(summary_path, index=False)
    log("=" * 60)
    log(f"本批完成 {len(all_results)} 个组合 ({time.time()-t_start:.1f}s), 累计 {len(sdf)} 个")
    if len(sdf[sdf["ablation"] == "Full"]) > 0:
        main_models = sdf[sdf["ablation"] == "Full"][
            ["subset", "track", "model_name", "n_features", "n_test",
             "test_spearman", "test_mae", "test_r2", "top5_stability"]
        ]
        log("\n主模型指标(Full):")
        log(main_models.to_string(index=False))
    log("=" * 60)


if __name__ == "__main__":
    main()
