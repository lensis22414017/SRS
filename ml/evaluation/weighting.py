#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""v1.0.2: AHP + 熵权法/CRITIC 主客观组合赋权(方法学文件 + GPT 第五节)。

方法学:
  - 第2章重构评价: 主观权重 50% + 客观权重 50%(段落[411])
  - 客观权重 = 熵权法 + CRITIC 法的平均(段落[439])
  - AHP 一致性检验 CR < 0.1(段落[365], Table[16] 全部通过)

实现:
  1. AHP 主观权重: 从判断矩阵计算特征向量 + CR 一致性检验
  2. 熵权法客观权重: 基于指标变异程度
  3. CRITIC 法客观权重: 基于对比强度 + 冲突性
  4. 组合: 主观 50% + 客观 50%
"""
from __future__ import annotations

import numpy as np


# ── AHP 主观权重 ──────────────────────────────────────────────────────

def ahp_weights(judgment_matrix: np.ndarray) -> tuple[np.ndarray, float]:
    """AHP 计算权重 + 一致性检验 CR。

    judgment_matrix: n×n 判断矩阵(1-9 标度)
    返回 (weights, CR)。CR < 0.1 则一致性可接受。
    """
    n = len(judgment_matrix)
    # 特征值法: 最大特征值对应的特征向量(归一化)
    eigenvalues, eigenvectors = np.linalg.eig(judgment_matrix)
    max_idx = np.argmax(eigenvalues.real)
    max_eigenvalue = eigenvalues[max_idx].real
    weights = np.abs(eigenvectors[:, max_idx].real)
    weights = weights / weights.sum()  # 归一化

    # 一致性检验
    CI = (max_eigenvalue - n) / (n - 1) if n > 1 else 0
    # RI 表(n=1~11, 用户 Table[50])
    RI_TABLE = [0, 0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49, 1.51]
    RI = RI_TABLE[n - 1] if n <= len(RI_TABLE) else 1.51
    CR = CI / RI if RI > 0 else 0

    return weights, CR


# ── 熵权法客观权重 ────────────────────────────────────────────────────

def entropy_weights(data: np.ndarray) -> np.ndarray:
    """熵权法计算客观权重。

    data: m×n 矩阵(m 样本, n 指标), 已归一化到 [0,1] 或含正值。
    返回 n 维权重向量。
    """
    # 归一化到 [0,1](每列)
    col_min = data.min(axis=0)
    col_max = data.max(axis=0)
    col_range = np.where(col_max - col_min > 0, col_max - col_min, 1)
    normalized = (data - col_min) / col_range

    # 计算熵值
    m = len(data)
    # 避免 log(0), 加微小值
    p = normalized / normalized.sum(axis=0, keepdims=True).clip(min=1e-10)
    k = 1.0 / np.log(m) if m > 1 else 1
    entropy = -k * (p * np.log(p.clip(min=1e-10))).sum(axis=0)

    # 熵权: (1 - E) / Σ(1 - E)
    d = 1 - entropy
    weights = d / d.sum() if d.sum() > 0 else np.ones(len(d)) / len(d)
    return weights


# ── CRITIC 法客观权重 ─────────────────────────────────────────────────

def critic_weights(data: np.ndarray) -> np.ndarray:
    """CRITIC 法计算客观权重(对比强度 + 冲突性)。

    data: m×n 矩阵(m 样本, n 指标)。
    返回 n 维权重向量。
    """
    n = data.shape[1]
    # 对比强度: 每列标准差
    std = data.std(axis=0, ddof=1) if len(data) > 1 else np.zeros(n)

    # 冲突性: 1 - 相关系数之和(每列与其他列的)
    if len(data) > 1:
        corr = np.corrcoef(data.T) if n > 1 else np.array([[1.0]])
        conflict = (1 - corr).sum(axis=1)
    else:
        conflict = np.ones(n)

    # 信息量 = 对比强度 × 冲突性
    info = std * conflict
    weights = info / info.sum() if info.sum() > 0 else np.ones(n) / n
    return weights


# ── 主客观 50/50 组合赋权 ─────────────────────────────────────────────

def combined_weights(subjective: np.ndarray, objective: np.ndarray,
                     alpha: float = 0.5) -> np.ndarray:
    """主客观组合赋权(用户第2章: alpha=0.5)。

    alpha: 主观权重占比(0.5 = 各半)。
    """
    combined = alpha * subjective + (1 - alpha) * objective
    return combined / combined.sum()  # 归一化


def evaluate_combined_weights(judgment_matrix: np.ndarray, data: np.ndarray,
                              alpha: float = 0.5) -> dict:
    """完整主客观组合赋权流程。

    返回 {weights, cr, subjective, entropy, critic, is_consistent}。
    """
    subjective, cr = ahp_weights(judgment_matrix)
    ent = entropy_weights(data)
    crit = critic_weights(data)
    # 客观权重 = 熵权 + CRITIC 的平均(方法学)
    objective = (ent + crit) / 2
    objective = objective / objective.sum()
    combined = combined_weights(subjective, objective, alpha)
    return {
        "weights": combined.tolist(),
        "cr": float(cr),
        "is_consistent": cr < 0.1,
        "subjective_weights": subjective.tolist(),
        "entropy_weights": ent.tolist(),
        "critic_weights": crit.tolist(),
        "objective_weights": objective.tolist(),
        "alpha": alpha,
    }
