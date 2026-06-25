"""Mann-Kendall 非参数趋势检验 — 地下水/土壤监测时间序列趋势分析。

竞品完善 H3(2026-06-24): 地下水监测井污染物浓度趋势检验, 检测单调趋势
(上升=污染扩散预警 / 下降=修复见效), 辅助监管决策"是否需进一步干预"。
非参数方法, 不要求正态分布, 耐异常值, 适合环境监测稀疏非平稳序列。
Sen's slope 量化趋势速率(单位/期)。

参考: Mann(1945), Kendall(1975), Gilbert(1987); GB 地下水监测规范常用趋势检验。
依赖: numpy, scipy。
"""
from __future__ import annotations
import numpy as np
from scipy import stats


def mann_kendall(x) -> dict:
    """Mann-Kendall 趋势检验。

    Args:
        x: 数值序列(按时间顺序), 含 NaN 自动剔除。
    Returns:
        dict: n, z(检验统计量), p(双侧p值), trend(趋势判定), sen_slope(趋势速率中位)。
    """
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 4:
        return {"n": int(n), "z": None, "p": None, "trend": "数据不足(<4点)", "sen_slope": None}
    # S 统计量
    s = 0
    for i in range(n - 1):
        s += np.sum(np.sign(x[i + 1:] - x[i]))
    # 并列修正方差
    unique, counts = np.unique(x, return_counts=True)
    tie = counts[counts > 1]
    var = (n * (n - 1) * (2 * n + 5)) / 18.0
    if tie.size:
        var -= np.sum(tie * (tie - 1) * (2 * tie + 5)) / 18.0
    # Z 统计量(连续性修正)
    if s > 0:
        z = (s - 1) / np.sqrt(var) if var > 0 else 0.0
    elif s < 0:
        z = (s + 1) / np.sqrt(var) if var > 0 else 0.0
    else:
        z = 0.0
    p = 2 * (1 - stats.norm.cdf(abs(z)))
    if p < 0.05 and z > 0:
        trend = "显著上升↑(污染扩散预警)"
    elif p < 0.05 and z < 0:
        trend = "显著下降↓(修复见效)"
    else:
        trend = "无显著趋势(p≥0.05)"
    # Sen's slope(所有点对斜率中位数, 稳健趋势速率)
    slopes = [(x[j] - x[i]) / (j - i) for i in range(n - 1) for j in range(i + 1, n)]
    sen = float(np.nanmedian(slopes)) if slopes else None
    return {"n": int(n), "z": round(float(z), 3), "p": round(float(p), 4),
            "trend": trend, "sen_slope": round(sen, 4) if sen is not None else None}


if __name__ == "__main__":
    print("=== Mann-Kendall 自测(三类典型序列) ===")
    print("上升(扩散预警):", mann_kendall([1, 2, 3, 5, 8, 13, 21]))
    print("下降(修复见效):", mann_kendall([50, 42, 35, 28, 20, 12, 5]))
    print("平稳(无趋势) :", mann_kendall([10, 12, 9, 11, 10, 13, 9]))
    print("含NaN上升    :", mann_kendall([1.0, np.nan, 3, 5, np.nan, 8, 11, 14]))
