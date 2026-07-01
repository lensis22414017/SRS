"""RF 插补有机缺失(项目组指定, 非均值填补)。

用 sklearn IterativeImputer(RandomForestRegressor) 在 **train 内 fit**(防泄漏),
transform train/valid/test。保留 __missing 标记列(诚实标注插补来源)。
极稀疏列(有效<5%)回退中位数(RF 无信号, 诚实)。

运行: cd backend && .venv/bin/python ../ml/cleaning/rf_impute.py [hm|op|composite|all]
"""
import os, sys, json
import pandas as pd
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TRAIN_BASE = os.path.join(ROOT, "data", "training")
SPLITS = ["train", "valid", "test", "external"]
# 非特征列(不插补, 保留)
META = {"id_DOI", "id_Source", "DOI", "Source", "Latitude", "Longitude", "Province",
        "City", "Pollution_Type", "标签", "标签_生产", "标签_生态", "split_source",
        "is_synthetic", "ID", "Year", "LandUse", "SamplingDepth", "region"}


def _feature_cols(df):
    return [c for c in df.columns if c not in META and df[c].dtype.kind in "fi" and df[c].isna().any()]


def rf_impute_block(name):
    from sklearn.experimental import enable_iterative_imputer  # noqa
    from sklearn.impute import IterativeImputer
    from sklearn.ensemble import RandomForestRegressor

    block_dir = os.path.join(TRAIN_BASE, name)
    if not os.path.isdir(block_dir):
        print(f"[{name}] 无切分目录, 跳过"); return
    splits = {s: pd.read_csv(os.path.join(block_dir, f"{s}.csv")) for s in SPLITS
              if os.path.exists(os.path.join(block_dir, f"{s}.csv"))}
    if "train" not in splits:
        print(f"[{name}] 无 train.csv"); return
    train = splits["train"]
    feat = _feature_cols(train)
    if not feat:
        print(f"[{name}] 无缺失特征列, 跳过插补"); return
    # 按缺失率分: <95% 用 RF插补, >=95% 回退中位数(诚实, RF无信号)
    miss_rate = train[feat].isna().mean()
    rf_cols = [c for c in feat if miss_rate[c] < 0.95]
    med_cols = [c for c in feat if miss_rate[c] >= 0.95]
    print(f"[{name}] 特征列{len(feat)}: RF插补{len(rf_cols)}(缺失<95%), 中位数{len(med_cols)}(极稀疏)")

    # __missing 标记(所有缺失列)
    for df in splits.values():
        for c in feat:
            if c in df.columns:
                df[f"{c}__missing"] = df[c].isna().astype(int)

    # 中位数列(全 split 用 train 中位数)
    med = train[med_cols].median()
    for df in splits.values():
        for c in med_cols:
            if c in df.columns:
                df[c] = df[c].fillna(med[c])

    # RF 插补列(fit train only)
    if rf_cols:
        # 仅对数值 + rf_cols 子矩阵 fit
        all_num = [c for c in train.columns if c not in META and train[c].dtype.kind in "fi"]
        imputer = IterativeImputer(
            estimator=RandomForestRegressor(n_estimators=40, max_depth=8, n_jobs=-1, random_state=42),
            max_iter=4, initial_strategy="median", imputation_order="ascending",
            random_state=42, sample_posterior=False, min_value=-1e9, max_value=1e9)
        imputer.fit(train[all_num])
        for s, df in splits.items():
            arr = imputer.transform(df[all_num])
            df[all_num] = arr
    # 写回
    out_dir = os.path.join(block_dir, "imputed")
    os.makedirs(out_dir, exist_ok=True)
    summary = {}
    for s, df in splits.items():
        df.to_csv(os.path.join(out_dir, f"{s}.csv"), index=False, encoding="utf-8-sig")
        summary[s] = len(df)
    print(f"  → {out_dir}: {summary}")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name in (["hm", "op", "composite"] if which == "all" else [which]):
        rf_impute_block(name)
    print("\n完成。三块 imputed/train|valid|test.csv → data/training/{hm,op,composite}/imputed/")
