"""用锁定的autoresearch best在development拟合，并仅一次评价独立test。"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, r2_score

import prepare
import train


OUT = prepare.ROOT / "ml" / "artifacts" / "p3_candidate_20260715"


def split_ids(subset: str, data: pd.DataFrame) -> tuple[set, set]:
    manifest = prepare.GOLD / "07_splits" / f"split_manifest_{subset}_v0.8.csv"
    if manifest.exists():
        split = pd.read_csv(manifest)
        dev = set(split.loc[split.split.isin(["train", "valid"]), "sample_id"])
        test = set(split.loc[split.split.eq("test"), "sample_id"])
    else:
        test = set(pd.read_parquet(prepare.GOLD / "08_training_ready" / subset / "X_test.parquet")["sample_id"])
        dev = set(data.sample_id) - test
    return dev, test


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_metrics = []
    for subset in prepare.SUBSETS:
        data = pd.read_parquet(prepare.GOLD / "06_dataset_subsets" / f"dataset_{subset}_v0.8.parquet")
        dev_ids, test_ids = split_ids(subset, data)
        dev_mask, test_mask = data.sample_id.isin(dev_ids), data.sample_id.isin(test_ids)
        dev_sources = set(data.loc[dev_mask, "source_id"].astype(str))
        test_sources = set(data.loc[test_mask, "source_id"].astype(str))
        overlap = dev_sources & test_sources
        assert not overlap, f"{subset} source overlap: {list(overlap)[:5]}"
        feature_cols = prepare.load_subset(subset)["feature_cols"]
        schema_hash = hashlib.sha256("\n".join(feature_cols).encode()).hexdigest()
        for track, target in prepare.TRACKS.items():
            model = train.build_model(subset, track)
            model.fit(data.loc[dev_mask, feature_cols], data.loc[dev_mask, target])
            prediction = np.clip(model.predict(data.loc[test_mask, feature_cols]), 0.0, 1.0)
            truth = data.loc[test_mask, target].to_numpy()
            score = spearmanr(truth, prediction).statistic
            score = 0.0 if np.isnan(score) else float(score)
            metrics = {
                "subset": subset, "track": track, "target": target,
                "n_train": int(dev_mask.sum()), "n_test": int(test_mask.sum()),
                "n_train_groups": len(dev_sources), "n_test_groups": len(test_sources),
                "group_overlap": 0, "test_spearman": score,
                "test_mae": float(mean_absolute_error(truth, prediction)),
                "test_r2": float(r2_score(truth, prediction)),
                "feature_schema_hash": schema_hash, "n_features": len(feature_cols),
                "validation_strategy": "locked source holdout after GroupKFold autoresearch",
                "training_dataset_version": "v0.8_gold_model_ready; V2 additions held for external validation",
                "trained_at": datetime.now(timezone.utc).isoformat(),
            }
            tag = f"{subset}_{track}_Full_Autoresearch20260715"
            joblib.dump({"model": model, "feature_cols": feature_cols, "result": metrics}, OUT / f"{tag}.joblib")
            (OUT / f"{tag}_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
            all_metrics.append(metrics)
    pd.DataFrame(all_metrics).to_csv(OUT / "final_test_summary.csv", index=False, encoding="utf-8-sig")
    print(pd.DataFrame(all_metrics).to_string(index=False))


if __name__ == "__main__":
    main()
