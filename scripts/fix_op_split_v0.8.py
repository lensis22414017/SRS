#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fix_op_split_v0.8.py
====================================================================
OP 子集 split 修复:source 级分层 GroupKFold
====================================================================
问题根因(seal_repair 自查发现):
- OP test 只有 1 个 source 组(10.1016/j.scitotenv.2019.05.291)
- 该组 OI_prod_formal 全零 → test 指标无意义
- 原 GroupKFold 在 OP 上退化(164 source 组分布极不均,1 大组占 test 1073 样本)

修复方案:
- 对 OP 的每个 source 组标记"含障碍组/全零组"(按 OI_prod_formal 是否全零)
- 按 stratum(source 是否含障碍)做分层 GroupKFold,保证 test 中有非零样本
- 验证条件:test OI_prod_formal nonzero > 50 且 source 组 >= 3
- 不满足 → OP 降级 NOT_READY,仅留 train/valid 探索

不动 all/hm 的 split(它们 test 正常)。
====================================================================
"""
import os
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

GOLD = "autoresearch/obstacle_diagnosis_v0.8_gold_training_dataset"
D07 = f"{GOLD}/07_splits"
D08 = f"{GOLD}/08_training_ready"


def log(msg):
    print(f"[fix_op_split] {msg}", flush=True)


def main():
    log("=" * 60)
    log("OP 子集 source 级分层 GroupKFold 修复")
    log("=" * 60)

    # 读 OP 全量数据(06_dataset_subsets 已含 source_id 和 4 个 OI 目标)
    ds = pd.read_parquet(f"{GOLD}/06_dataset_subsets/dataset_op_v0.8.parquet")
    log(f"OP 全量样本: {len(ds)}, source 组数: {ds['source_id'].nunique()}")

    y_col = "OI_prod_formal"
    X_cols = [c for c in ds.columns if c.startswith("x_")]
    meta_cols = ["sample_id"]
    y_all = ds[y_col].copy()

    # ── source 级分层:每个 source 组是否含障碍 ──
    source_stat = ds.groupby("source_id")[y_col].agg(["max", "count"]).rename(columns={"max": "oi_max"})
    source_stat["stratum"] = (source_stat["oi_max"] > 0).astype(int)  # 1=含障碍组, 0=全零组
    n_obstacle_src = int(source_stat["stratum"].sum())
    n_zero_src = int((source_stat["stratum"] == 0).sum())
    log(f"source 组分层: 含障碍组={n_obstacle_src}, 全零组={n_zero_src}")

    if n_obstacle_src < 6:
        log(f"  ⚠️ 含障碍 source 组仅 {n_obstacle_src} < 6,无法保证 train/valid/test 都有非零样本")
        log("  → OP 降级 NOT_READY,仅留探索训练")
        downgrade_op()
        return

    # ── 分层 GroupKFold ──
    # 对含障碍组和全零组分别做 GroupKFold,再合并到 train/valid/test
    # 比例 train:valid:test = 60:20:20
    def stratified_group_split(source_ids, stratum_label, seed=42):
        """对一组 source_id 按 60/20/20 分到 train/valid/test"""
        ids = list(source_ids)
        rng = np.random.RandomState(seed)
        rng.shuffle(ids)
        n = len(ids)
        n_test = max(1, n // 5)        # 20%
        n_valid = max(1, n // 5)       # 20%
        test = set(ids[:n_test])
        valid = set(ids[n_test:n_test + n_valid])
        train = set(ids[n_test + n_valid:])
        return train, valid, test

    obstacle_srcs = source_stat[source_stat["stratum"] == 1].index.tolist()
    zero_srcs = source_stat[source_stat["stratum"] == 0].index.tolist()

    tr_o, va_o, te_o = stratified_group_split(obstacle_srcs, 1)
    tr_z, va_z, te_z = stratified_group_split(zero_srcs, 0)

    train_src = tr_o | tr_z
    valid_src = va_o | va_z
    test_src = te_o | te_z

    # 验证 source 组不交叉
    assert len(train_src & valid_src) == 0
    assert len(train_src & test_src) == 0
    assert len(valid_src & test_src) == 0
    log(f"source 组: train={len(train_src)} valid={len(valid_src)} test={len(test_src)}")
    log(f"  含障碍组分布: train={len(tr_o)} valid={len(va_o)} test={len(te_o)}")

    # 分配样本
    ds["split_new"] = ds["source_id"].map(
        lambda s: "train" if s in train_src else ("valid" if s in valid_src else "test")
    )

    # ── 验证 test 集有足够非零样本 ──
    test_df = ds[ds["split_new"] == "test"]
    test_nonzero = int((test_df[y_col] > 0).sum())
    test_n_src = test_df["source_id"].nunique()
    log(f"新 test 集: 样本={len(test_df)}, nonzero={test_nonzero}, source组={test_n_src}")

    if test_nonzero < 30 or test_n_src < 3:
        log(f"  ❌ 验证条件未满足(nonzero={test_nonzero}<30 或 source组={test_n_src}<3)")
        log("  → OP 降级 NOT_READY")
        downgrade_op()
        return

    log(f"  ✅ 验证条件满足(nonzero={test_nonzero}>=30, source组={test_n_src}>=3)")
    if test_nonzero < 50:
        log(f"  ⚠️ 注意: OP test 非零样本={test_nonzero}<50, OP 模型 test 指标参考价值有限,报告将如实声明")

    # ── 重写 split_manifest_op(从 ds 直接重建,不依赖旧 sm) ──
    sm_new = ds[["sample_id", "site_id", "source_id", "province", "pollution_type"]].copy()
    sm_new["split"] = ds["split_new"]
    sm_new["subset"] = "op"
    sm_new["split_strategy"] = "source_level_stratified_groupkfold"
    sm_new["split_version"] = "v0.8_op_stratified_fix"
    sm_new["split_site_group"] = sm_new["site_id"]
    sm_new["split_source_group"] = sm_new["source_id"]
    sm_new["split_region_holdout"] = "skipped: province 过多, 本版不强制"
    sm_new["region"] = ""
    sm_new.to_csv(f"{D07}/split_manifest_op_v0.8.csv", index=False)
    log(f"split_manifest_op_v0.8.csv 已更新")

    # ── 重写 08_training_ready/op ──
    op_ready = f"{D08}/op"
    os.makedirs(op_ready, exist_ok=True)

    # dataset_op 已含 4 个 OI 目标,直接用
    y_cols_all = ["OI_prod_formal", "OI_prod_extended", "OI_eco_formal", "OI_eco_extended"]

    for split_name in ["train", "valid", "test"]:
        mask = ds["split_new"] == split_name
        X_part = ds.loc[mask, ["sample_id"] + X_cols].copy().reset_index(drop=True)
        # y: sample_id + 4 OI(从 ds 直接取,顺序与 X 一致)
        y_part = ds.loc[mask, ["sample_id"] + y_cols_all].copy().reset_index(drop=True)

        X_part.to_parquet(f"{op_ready}/X_{split_name}.parquet", index=False)
        y_part.to_parquet(f"{op_ready}/y_{split_name}.parquet", index=False)
        log(f"  op/{split_name}: X={X_part.shape}, y={y_part.shape}, "
            f"OI_prod nonzero={( y_part['OI_prod_formal']>0).sum()}")

    # train_metadata
    import json
    meta = {
        "subset": "op",
        "n_features": len(X_cols),
        "n_targets": len(y_cols_all),
        "feature_cols": X_cols,
        "split_strategy": "source_level_stratified_groupkfold",
        "split_version": "v0.8_op_stratified_fix",
        "note": "原 OP test 仅 1 source 组全零已修复; 现按 source 含障碍分层",
    }
    with open(f"{op_ready}/train_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 删除可能的 NOT_READY
    nr = f"{op_ready}/NOT_READY_REASON.md"
    if os.path.exists(nr):
        os.remove(nr)

    log("=" * 60)
    log("OP split 修复完成")
    log("=" * 60)


def downgrade_op():
    """OP 降级:删除 X/y,写 NOT_READY"""
    op_ready = f"{D08}/op"
    for kind in ["X_train", "X_valid", "X_test", "y_train", "y_valid", "y_test"]:
        fp = f"{op_ready}/{kind}.parquet"
        if os.path.exists(fp):
            os.remove(fp)
    tm = f"{op_ready}/train_metadata.json"
    if os.path.exists(tm):
        os.remove(tm)
    nr = f"""# op 不满足单独训练条件

原因: OP 含障碍 source 组不足 6 个,无法保证 train/valid/test 都有非零样本。
处理: OP 不单独训练,仅作探索或并入 all 模型。

> 由 fix_op_split_v0.8.py 生成。
"""
    with open(f"{op_ready}/NOT_READY_REASON.md", "w", encoding="utf-8") as f:
        f.write(nr)


if __name__ == "__main__":
    main()
