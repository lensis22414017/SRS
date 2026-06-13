"""RF 训练数据准备 (纯 pandas, 不依赖 sklearn, 可独立测试)。

数据源: data/raw/真实数据集.csv (1119 样本)
目标列: 标签 (0/1 二分类; 0=973, 1=146, 不均衡)
特征策略 (经数据勘察, 2026-06-10):
  - 重金属 8 列齐全: Cr,Hg,As,Pb,Cu,Zn,Ni,Cd
  - 有机物 4 列缺失 38-51%: OCPs,PAHs,PCBs,PAEs -> 中位数填充 + 缺失标记列
  - 理化列缺失 >95% 的剔除 (CEC,EC_T,BS_T,Aggre_T)
  - 其余理化列中位数填充
  - 不伪造数据: 填充仅用于模型输入, 缺失事实记录在 *_missing 标记列与元数据
"""
from __future__ import annotations

import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CSV = os.path.join(ROOT, "data", "raw", "真实数据集.csv")

TARGET = "标签"
ID_COLS = ["StudyID", "ExperimentID"]
META_COLS = ["污染风险等级", "土地利用类型", "Texture"]
DROP_MISSING_ABOVE = 0.95  # 缺失率阈值

DATA_VERSION = "真实数据集_20250731_n1119"


def load_raw(csv_path: str = DEFAULT_CSV) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def prepare(csv_path: str = DEFAULT_CSV, add_missing_flags: bool = True):
    """返回 (X, y, meta)。meta 含特征清单/填充值/剔除列/数据版本。"""
    df = load_raw(csv_path)
    assert TARGET in df.columns, f"缺目标列 {TARGET}"
    y = df[TARGET].astype(int)

    feat = df.drop(columns=[c for c in ID_COLS + META_COLS + [TARGET] if c in df.columns])
    feat = feat.select_dtypes("number")

    # 剔除高缺失列
    miss_rate = feat.isna().mean()
    dropped = sorted(miss_rate[miss_rate > DROP_MISSING_ABOVE].index.tolist())
    feat = feat.drop(columns=dropped)

    # 缺失标记 + 中位数填充
    medians = feat.median(numeric_only=True)
    flags = {}
    if add_missing_flags:
        for c in feat.columns[feat.isna().any()]:
            flags[f"{c}__missing"] = feat[c].isna().astype(int)
    X = feat.fillna(medians)
    for k, v in flags.items():
        X[k] = v

    meta = {
        "data_version": DATA_VERSION,
        "n_samples": int(len(X)),
        "n_features": int(X.shape[1]),
        "feature_list": X.columns.tolist(),
        "base_features": feat.columns.tolist(),
        "dropped_high_missing": dropped,
        "imputation": "median",
        "medians": {k: float(v) for k, v in medians.items()},
        "target": TARGET,
        "class_balance": y.value_counts().to_dict(),
    }
    return X, y, meta
