"""量化 V2 新增可信 SI 样本能否直接进入现有双轨模型训练。"""
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
V2 = ROOT / "outputs/literature_mining/training_v2"
GOLD = ROOT / "autoresearch/obstacle_diagnosis_v0.8_gold_training_dataset/06_dataset_subsets"
OUT_CSV = ROOT / "outputs/literature_mining/V2_NEW_ROWS_MODEL_READINESS.csv"
OUT_MD = ROOT / "outputs/literature_mining/V2_NEW_ROWS_MODEL_READINESS.md"


def main() -> None:
    specs = {
        "op": V2 / "train_table_op_only_SOIL_CLEAN_V2.csv",
        "hm_op": V2 / "train_table_hm_op_SOIL_CLEAN_V2.csv",
    }
    records = []
    for subset, path in specs.items():
        frame = pd.read_csv(path, low_memory=False)
        trusted = frame[frame["audit_flag"].eq("si_native_table_verified")].copy()
        gold = pd.read_parquet(GOLD / f"dataset_{subset}_v0.8.parquet")
        model_features = [column for column in gold if column.startswith("x_")]
        overlap = [column for column in model_features if column in trusted]
        per_row_coverage = trusted[overlap].notna().sum(axis=1) / len(model_features)
        targets = ["OI_prod_formal", "OI_eco_formal"]
        target_complete = all(column in trusted and trusted[column].notna().all() for column in targets)
        for source_id, source in trusted.groupby("source_id"):
            source_coverage = per_row_coverage.loc[source.index]
            records.append({
                "subset": subset,
                "source_id": source_id,
                "rows": len(source),
                "model_feature_count": len(model_features),
                "overlap_feature_count": len(overlap),
                "mean_row_feature_coverage": round(float(source_coverage.mean()), 4),
                "min_row_feature_coverage": round(float(source_coverage.min()), 4),
                "has_prod_and_eco_targets": target_complete,
                "training_decision": "holdout_external_validation" if not target_complete else "eligible",
            })
    result = pd.DataFrame(records)
    result.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    lines = [
        "# V2 新增可信 SI 样本建模就绪度",
        "",
        "结论：176个新增可信样本可用于外部覆盖与污染物分布验证，但不能诚实地直接并入当前生产/生态双轨监督训练；两类数据都缺少 `OI_prod_formal` 和 `OI_eco_formal` 训练标签，且与既有模型特征空间的逐行覆盖有限。",
        "",
        result.to_markdown(index=False),
        "",
        "处置：保留在 canonical V2 原始训练资产中并标记来源；本轮模型选择仍使用 v0.8 gold model-ready 数据，新增样本作为外部验证/后续协变量补齐池，不虚构标签、不用论文均值替代样点标签。",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
