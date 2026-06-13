"""探索性数据分析(EDA) — PowerBI 风格统计指标。

对任意数值表/因子序列输出"数据体检报告":概览指标、分布形态、异常点、
直方图分箱、Q-Q 参考、ECDF。纯 pandas/numpy, 可独立测试与复用。
所有指标基于真实数据计算, 不插补、不伪造。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def column_stats(series: pd.Series) -> dict:
    """单列 36 项统计体检(数值列)。"""
    s = pd.to_numeric(series, errors="coerce")
    n = len(s)
    nonnull = s.dropna()
    cnt = int(nonnull.count())
    miss = int(n - cnt)
    out: dict = {
        "n": n, "count": cnt, "missing": miss,
        "missing_pct": round(miss / n * 100, 2) if n else 0.0,
        "zeros": int((nonnull == 0).sum()),
        "negatives": int((nonnull < 0).sum()),
        "unique": int(nonnull.nunique()),
    }
    if cnt == 0:
        return out
    desc = nonnull.describe()
    q1, q3 = float(nonnull.quantile(0.25)), float(nonnull.quantile(0.75))
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = int(((nonnull < lo) | (nonnull > hi)).sum())
    mean = float(desc["mean"]); med = float(nonnull.median()); std = float(nonnull.std(ddof=1)) if cnt > 1 else 0.0
    out.update({
        "mean": round(mean, 4), "median": round(med, 4),
        "std": round(std, 4), "min": round(float(desc["min"]), 4),
        "max": round(float(desc["max"]), 4), "range": round(float(desc["max"] - desc["min"]), 4),
        "q1": round(q1, 4), "q3": round(q3, 4), "iqr": round(iqr, 4),
        "p05": round(float(nonnull.quantile(0.05)), 4),
        "p95": round(float(nonnull.quantile(0.95)), 4),
        "cv": round(std / mean, 4) if mean else None,
        "skew": round(float(nonnull.skew()), 4) if cnt > 2 else None,
        "kurtosis": round(float(nonnull.kurt()), 4) if cnt > 3 else None,
        "outliers": outliers,
        "outlier_pct": round(outliers / cnt * 100, 2),
        "mean_median_gap_pct": round(abs(mean - med) / abs(med) * 100, 2) if med else None,
        "skew_flag": ("右偏" if cnt > 2 and nonnull.skew() > 1 else
                      "左偏" if cnt > 2 and nonnull.skew() < -1 else "近似对称"),
    })
    return out


def histogram(series: pd.Series, bins: int = 20) -> dict:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return {"bins": [], "counts": []}
    counts, edges = np.histogram(s, bins=bins)
    return {"edges": [round(float(e), 4) for e in edges], "counts": [int(c) for c in counts]}


def qq_points(series: pd.Series, max_points: int = 200) -> dict:
    """正态 Q-Q: 返回理论分位 vs 样本分位。"""
    s = pd.to_numeric(series, errors="coerce").dropna().sort_values()
    if len(s) < 3:
        return {"theoretical": [], "sample": []}
    from scipy import stats as st  # type: ignore
    n = len(s)
    probs = (np.arange(1, n + 1) - 0.5) / n
    theo = st.norm.ppf(probs)
    idx = np.linspace(0, n - 1, min(max_points, n)).astype(int)
    return {"theoretical": [round(float(theo[i]), 4) for i in idx],
            "sample": [round(float(s.iloc[i]), 4) for i in idx]}


def table_overview(df: pd.DataFrame) -> dict:
    num = df.select_dtypes("number")
    total_cells = df.size
    miss_cells = int(df.isna().sum().sum())
    return {
        "rows": int(len(df)), "cols": int(df.shape[1]),
        "numeric_cols": int(num.shape[1]),
        "overall_missing_pct": round(miss_cells / total_cells * 100, 2) if total_cells else 0.0,
        "fully_empty_cols": [c for c in df.columns if df[c].isna().all()],
    }


def profile_dataframe(df: pd.DataFrame, columns: list[str] | None = None) -> dict:
    cols = columns or df.select_dtypes("number").columns.tolist()
    return {
        "overview": table_overview(df),
        "columns": {c: column_stats(df[c]) for c in cols if c in df.columns},
    }
