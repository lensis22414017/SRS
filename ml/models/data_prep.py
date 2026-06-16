"""RF 训练数据准备 (纯 pandas, 不依赖 sklearn, 可独立测试)。

⚠️ 数据真实性如实标注 (2026-06-15 peer-review 修正):
  - 当前默认数据源 `data/raw/模拟特征表_F127_n11690.csv` 是 **模拟特征表** (F1-F127 中文物理量, 11690 行),
    并非真实文献数据。之前文件名为"真实数据集.csv"+DATA_VERSION 标"真实_n1119" 属命名误导, 已正本清源。
  - IS_REAL_DATA = False: 当前模型 AUC≈1.0 是模拟数据 + 唯一 ID 泄漏所致的虚高, 不可外推真实场地。
  - 真实训练数据为 `data/raw/merged_std33,zh .xlsx` (41504×719, 带 DOI/Source), 后续重建模型时切换。

目标列: 标签 (0/1 二分类)
特征策略:
  - 剔除唯一标识列 (ID/StudyID/ExperimentID): 唯一标识进特征会导致 RF 学到"ID 区间→标签"伪规则 (泄漏)
  - 剔除分类元数据 (污染风险等级/土地利用类型/Texture): 避免标签派生列泄漏
  - 剔除缺失率 >95% 列
  - 其余数值列中位数填充 + 缺失标记列 (不伪造数据)
"""
from __future__ import annotations

import os

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# ⚠️ 模拟特征表 (非真实), 之前误命名为"真实数据集.csv"。真实数据为 merged_std33,zh .xlsx
DEFAULT_CSV = os.path.join(ROOT, "data", "raw", "模拟特征表_F127_n11690.csv")

TARGET = "标签"
# 唯一标识列 + 标签派生列: 绝不进特征 (防泄漏)
ID_COLS = ["ID", "StudyID", "ExperimentID"]  # ID 在模拟表中是 1..N 唯一序号, 必须剔除
META_COLS = ["污染风险等级", "土地利用类型", "Texture", "省市", "采样地类型", "经度", "纬度"]
DROP_MISSING_ABOVE = 0.95  # 缺失率阈值

# ⚠️ 如实标注: 当前为模拟数据 (非真实文献数据)
IS_REAL_DATA = False
DATA_VERSION = "模拟特征表_F127_n11690"  # 之前误标"真实数据集_n1119", 已正名


def load_raw(csv_path: str = DEFAULT_CSV) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def prepare(csv_path: str = DEFAULT_CSV, add_missing_flags: bool = True):
    """返回 (X, y, meta)。meta 含特征清单/填充值/剔除列/数据版本/真实性标记。"""
    df = load_raw(csv_path)
    assert TARGET in df.columns, f"缺目标列 {TARGET}"
    y = df[TARGET].astype(int)

    # 剔除唯一标识列 + 标签派生列 + 目标列 (防泄漏)
    drop_cols = [c for c in ID_COLS + META_COLS + [TARGET] if c in df.columns]
    feat = df.drop(columns=drop_cols)
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
        "is_real_data": IS_REAL_DATA,  # ⚠️ False=模拟数据, AUC 虚高不可外推
        "data_source": os.path.basename(csv_path),
        "dropped_leakage_cols": drop_cols,  # 记录剔除的泄漏列 (可追溯)
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
