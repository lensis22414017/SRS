"""zzv0.4 P1-5/P1-6: 障碍因子诊断排序指标 + 统计检验。

因子归因任务的核心指标不是AUC(那是分类健康指标), 而是:
- top-k precision/recall: 障碍因子是否被正确识别进 top-k
- rank correlation (Kendall/Spearman): 排序稳定性
- SHAP consistency: 跨折排序可复现性
文献: docs/references/障碍因子诊断_方法学综合报告.md [裴总报告139行, #64 bootstrap, #65 permutation]
"""
from __future__ import annotations
import numpy as np
from typing import Sequence


def topk_precision(pred_top_k: Sequence[str], true_top_k: Sequence[str]) -> float:
    """top-k precision: 预测的top-k因子里有多少在真实top-k中。"""
    if not pred_top_k:
        return 0.0
    true_set = set(true_top_k)
    hits = sum(1 for f in pred_top_k if f in true_set)
    return hits / len(pred_top_k)


def topk_recall(pred_top_k: Sequence[str], true_top_k: Sequence[str]) -> float:
    """top-k recall: 真实top-k里有多少被预测命中。"""
    if not true_top_k:
        return 0.0
    pred_set = set(pred_top_k)
    hits = sum(1 for f in true_top_k if f in pred_set)
    return hits / len(true_top_k)


def rank_correlation(rank_a: Sequence[str], rank_b: Sequence[str], method: str = "kendall") -> float:
    """两个因子排序的 Kendall/Spearman 相关(排序稳定性)。
    rank_a/rank_b: 因子名列表(按重要性降序)。共同因子参与计算。"""
    common = [f for f in rank_a if f in rank_b]
    if len(common) < 2:
        return 0.0
    pos_a = {f: i for i, f in enumerate(rank_a)}
    pos_b = {f: i for i, f in enumerate(rank_b)}
    ranks_a = [pos_a[f] for f in common]
    ranks_b = [pos_b[f] for f in common]
    try:
        from scipy.stats import kendalltau, spearmanr
        if method == "kendall":
            return float(kendalltau(ranks_a, ranks_b).statistic)
        return float(spearmanr(ranks_a, ranks_b).statistic)
    except ImportError:
        # 无scipy时的简化Kendall
        n = len(common)
        concordant = 0
        for i in range(n):
            for j in range(i + 1, n):
                da = ranks_a[i] - ranks_a[j]
                db = ranks_b[i] - ranks_b[j]
                if da * db > 0:
                    concordant += 1
                elif da * db < 0:
                    concordant -= 1
        total = n * (n - 1) / 2
        return concordant / total if total > 0 else 0.0


def shap_consistency(per_fold_rankings: list[list[str]], method: str = "kendall") -> float:
    """SHAP consistency: 多个CV折的因子排序之间的平均相关(可复现性)。
    per_fold_rankings: 每折的top-k因子名列表。"""
    if len(per_fold_rankings) < 2:
        return 1.0
    corrs = []
    for i in range(len(per_fold_rankings)):
        for j in range(i + 1, len(per_fold_rankings)):
            corrs.append(rank_correlation(per_fold_rankings[i], per_fold_rankings[j], method))
    return float(np.mean(corrs)) if corrs else 1.0


def bootstrap_ci(scores: list[float], confidence: float = 0.95, n_boot: int = 1000, seed: int = 42) -> tuple[float, float]:
    """bootstrap 95% CI。文献[#64 scipy.bootstrap]"""
    if len(scores) < 2:
        return (0.0, 0.0)
    rng = np.random.RandomState(seed)
    arr = np.array(scores)
    boot_means = [arr[rng.choice(len(arr), len(arr), replace=True)].mean() for _ in range(n_boot)]
    alpha = (1 - confidence) / 2
    lo = float(np.percentile(boot_means, alpha * 100))
    hi = float(np.percentile(boot_means, (1 - alpha) * 100))
    return (lo, hi)


def permutation_test_diff(scores_a: list[float], scores_b: list[float], n_perm: int = 1000, seed: int = 42) -> float:
    """两组指标差异的 permutation test p-value。文献[#65 scipy.permutation_test]"""
    if len(scores_a) < 2 or len(scores_b) < 2:
        return 1.0
    rng = np.random.RandomState(seed)
    a = np.array(scores_a)
    b = np.array(scores_b)
    obs_diff = abs(a.mean() - b.mean())
    combined = np.concatenate([a, b])
    n_a = len(a)
    count = 0
    for _ in range(n_perm):
        perm = rng.permutation(len(combined))
        perm_a = combined[perm[:n_a]]
        perm_b = combined[perm[n_a:]]
        if abs(perm_a.mean() - perm_b.mean()) >= obs_diff:
            count += 1
    return count / n_perm


def evaluate_ranking(pred_ranking: list[str], true_ranking: list[str], k: int = 5) -> dict:
    """一次诊断的排序评估(核心交付指标)。"""
    return {
        "topk_precision": round(topk_precision(pred_ranking[:k], true_ranking[:k]), 4),
        "topk_recall": round(topk_recall(pred_ranking[:k], true_ranking[:k]), 4),
        "rank_kendall": round(rank_correlation(pred_ranking, true_ranking, "kendall"), 4),
        "rank_spearman": round(rank_correlation(pred_ranking, true_ranking, "spearman"), 4),
    }
