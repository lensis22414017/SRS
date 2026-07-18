#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v1.0.2: MICE 缺失值处理(方法学 + GPT 第五节)。

方法学(段落[439]):
  1. 识别缺失位置和模式
  2. 初步插补(均值/中位数)
  3. 链式方程迭代插补
  4. 生成多个完整数据集
  5. 对每个数据集独立分析
  6. Rubin 规则汇总

实现: 用 sklearn.experimental.IterativeImputer(MICE 标准实现)
参数: m=5 次插补, max_iter=10, sample_posterior=True(多次插补)
"""
from __future__ import annotations

import numpy as np
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer


def mice_impute(data: np.ndarray, n_imputations: int = 5,
                max_iter: int = 10, random_state: int = 42) -> dict:
    """MICE 多重插补。

    data: m×n 矩阵, np.nan 表示缺失。
    n_imputations: 插补次数 m(方法学, 默认 5)。
    返回 {imputed_datasets, mean, is_imputed_mask}。
    """
    imputed_datasets = []
    for i in range(n_imputations):
        # sample_posterior=True 产生不同的插补结果(多次插补的核心)
        imputer = IterativeImputer(
            max_iter=max_iter,
            sample_posterior=True,
            random_state=random_state + i,
            min_value=-np.inf,
            max_value=np.inf,
        )
        imputed = imputer.fit_transform(data)
        imputed_datasets.append(imputed)

    # Rubin 规则: 取 m 次插补的平均作为最终值
    stacked = np.stack(imputed_datasets)
    mean_imputed = stacked.mean(axis=0)

    # 记录哪些位置被插补
    is_imputed = np.isnan(data)

    return {
        "imputed_datasets": imputed_datasets,
        "mean": mean_imputed,
        "is_imputed_mask": is_imputed,
        "n_imputed_cells": int(is_imputed.sum()),
        "n_imputations": n_imputations,
    }


def apply_mice_to_values(values: dict, all_factors: list[str],
                         n_imputations: int = 5) -> dict:
    """对场地指标值应用 MICE 插补。

    values: {factor: value}, 缺失的 factor 不在 dict 中或为 None。
    all_factors: 完整指标列表(方法学定义的全部指标)。
    返回 {factor: imputed_value, is_imputed: bool}。
    """
    # 构造 1×n 矩阵(单场地)
    data = np.array([[float(values.get(f, np.nan)) if values.get(f) is not None else np.nan
                      for f in all_factors]])

    n_missing = np.isnan(data).sum()
    if n_missing == 0:
        # 无缺失, 直接返回
        return {f: {"value": values[f], "is_imputed": False} for f in all_factors if f in values}

    result = {}
    if n_missing > 0 and data.shape[1] > 1:
        try:
            imp = mice_impute(data, n_imputations=n_imputations)
            mean = imp["mean"][0]  # 取第一行(唯一场地)
            mask = imp["is_imputed_mask"][0]
            for i, f in enumerate(all_factors):
                if f in values and values[f] is not None:
                    result[f] = {"value": values[f], "is_imputed": False}
                else:
                    result[f] = {"value": float(mean[i]), "is_imputed": bool(mask[i])}
        except Exception as e:
            # MICE 失败(如全部缺失), 用中位数兜底
            valid = [v for v in values.values() if v is not None]
            med = float(np.median(valid)) if valid else 0.0
            for f in all_factors:
                if f in values and values[f] is not None:
                    result[f] = {"value": values[f], "is_imputed": False}
                else:
                    result[f] = {"value": med, "is_imputed": True, "fallback": str(e)}
    return result
