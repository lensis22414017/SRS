"""运行 RF 行级随机 vs DOI/Source group split 对照训练。"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))

from group_split_training import DEFAULT_MODEL_READY, train_from_csv  # noqa: E402


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL_READY
    res = train_from_csv(csv_path)
    print("已生成: ml/artifacts/rf_group_split_metrics.json")
    print("已生成: docs/model/rf_group_split_report.md")
    print("row_random ROC-AUC:", res["row_random"].get("roc_auc"))
    print("group splits:", {k: v.get("roc_auc") for k, v in res["group_splits"].items()})
