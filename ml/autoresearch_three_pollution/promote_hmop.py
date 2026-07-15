"""将通过独立测试的HM+OP双轨模型提升为生产目录中的探索性模型。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap

import prepare
from finalize_models import split_ids


CANDIDATE = prepare.ROOT / "ml" / "artifacts" / "p3_candidate_20260715"
PRODUCTION = prepare.ROOT / "ml" / "artifacts" / "p3_alpha"


def group_name(feature: str) -> str:
    value = str(feature)
    if value.startswith("missingindicator_"):
        return "缺失指示_" + value.removeprefix("missingindicator_").removeprefix("x_measured_")
    if value.startswith("x_missing_"):
        return "缺失指示_" + value.removeprefix("x_missing_")
    return value.removeprefix("x_measured_").removeprefix("x_proxy_gee_")


def main() -> None:
    data = pd.read_parquet(prepare.GOLD / "06_dataset_subsets" / "dataset_hm_op_v0.8.parquet")
    _, test_ids = split_ids("hm_op", data)
    test = data[data.sample_id.isin(test_ids)]
    for track in ("prod", "eco"):
        source_tag = f"hm_op_{track}_Full_Autoresearch20260715"
        logical_tag = f"hm_op_{track}_Full_RandomForest"
        bundle = joblib.load(CANDIDATE / f"{source_tag}.joblib")
        feature_cols = bundle["feature_cols"]
        pipeline = bundle["model"]
        transformed = pipeline.named_steps["imputer"].transform(test[feature_cols])
        names = pipeline.named_steps["imputer"].get_feature_names_out(feature_cols)
        explainer = shap.TreeExplainer(pipeline.named_steps["model"])
        values = np.asarray(explainer.shap_values(transformed))
        global_frame = pd.DataFrame({
            "group": [group_name(value) for value in names],
            "mean_abs_shap": np.abs(values).mean(axis=0),
            "mean_signed": values.mean(axis=0),
            "n_features": 1,
            "members": [[str(value)] for value in names],
        })
        global_frame["direction"] = np.where(global_frame.mean_signed >= 0, "positive", "negative")
        total = global_frame.mean_abs_shap.sum()
        global_frame["contribution_share"] = global_frame.mean_abs_shap / total if total else 0.0
        global_frame = global_frame.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
        result = dict(bundle["result"])
        result.update({
            "model_name": "ExtraTreesAutoresearch20260715", "ablation": "Full",
            "cv_spearman_mean": 0.7819 if track == "prod" else 0.7485,
            "cv_spearman_std": None, "top5_stability": None,
            "test_spearman_ci_low": None, "test_spearman_ci_high": None,
            "grouped_stability_std": None, "target_zero_rate_test": float((test[result["target"]] == 0).mean()),
            "target_col": result["target"],
            "training_dataset_version": "v0.8_gold_model_ready; V2 additions held for external validation",
        })
        shutil.copy2(CANDIDATE / f"{source_tag}.joblib", PRODUCTION / f"{logical_tag}.joblib")
        (PRODUCTION / f"{logical_tag}_metrics.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        global_frame.to_parquet(PRODUCTION / f"{logical_tag}_shap_global.parquet", index=False)
        print(f"promoted {logical_tag}: test_spearman={result['test_spearman']:.4f}")


if __name__ == "__main__":
    main()
