"""生成真实/合成数据集 split registry。"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))

from dataset_splits import build_split_registry  # noqa: E402


if __name__ == "__main__":
    reg = build_split_registry()
    print("已生成: data/splits/dataset_split_registry.json")
    for name, meta in reg["splits"].items():
        print(f"{name:36} rows={meta['rows']:6} synthetic={meta['is_synthetic']}")
