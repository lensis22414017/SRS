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


def boxplot_summary(series: pd.Series) -> dict:
    """箱线图五数 + 须线 + 离群点(基于真实分位, 不插补)。

    返回 ECharts boxplot 所需结构: lower(下须), q1, median, q3, upper(上须),
    whisker_low/high(1.5*IQR 边界), outliers[] (采样上限 200 个, 防 OOM)。
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < 4:
        return {"lower": None, "q1": None, "median": None, "q3": None, "upper": None,
                "whisker_low": None, "whisker_high": None, "outliers": [], "n_outliers": 0}
    q1 = float(s.quantile(0.25)); q3 = float(s.quantile(0.75))
    med = float(s.median()); iqr = q3 - q1
    wlo, whi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inner = s[(s >= wlo) & (s <= whi)]
    lower = float(inner.min()) if len(inner) else float(s.min())
    upper = float(inner.max()) if len(inner) else float(s.max())
    out = s[(s < wlo) | (s > whi)]
    # 离群点采样上限 200, 避免极端值过多撑爆响应; 保持数量统计准确
    out_vals = sorted([round(float(v), 4) for v in out.tolist()])
    if len(out_vals) > 200:
        step = max(1, len(out_vals) // 200)
        out_vals = out_vals[::step][:200]
    return {"lower": round(lower, 4), "q1": round(q1, 4), "median": round(med, 4),
            "q3": round(q3, 4), "upper": round(upper, 4),
            "whisker_low": round(wlo, 4), "whisker_high": round(whi, 4),
            "outliers": out_vals, "n_outliers": int(len(out))}


def distribution_sample(series: pd.Series, max_points: int = 2000) -> dict:
    """原始分布采样(排序后等距抽样), 供前端 KDE/小提琴图。

    上限默认 2000 点防响应爆炸; 原始数量 n_total 单独返回以保证可追溯。
    """
    s = pd.to_numeric(series, errors="coerce").dropna().sort_values()
    n = len(s)
    if n == 0:
        return {"values": [], "n_total": 0}
    if n <= max_points:
        return {"values": [round(float(v), 4) for v in s.tolist()], "n_total": n}
    idx = np.linspace(0, n - 1, max_points).astype(int)
    return {"values": [round(float(s.iloc[i]), 4) for i in idx], "n_total": n}


def correlation_matrix(df: pd.DataFrame, method: str = "pearson") -> dict:
    """跨因子相关系数矩阵(三角阵友好)。返回 labels + matrix(二维 list)。

    df: 列为因子、值为数值的宽表 pivot。样本数 < 3 或全常数列返回空。
    """
    num = df.select_dtypes("number")
    # 剔除全常数列(无方差, corr 为 NaN)与全空列
    valid = [c for c in num.columns if num[c].notna().sum() >= 3 and num[c].std(ddof=0) > 0]
    if len(valid) < 2:
        return {"labels": [], "matrix": []}
    sub = num[valid]
    corr = sub.corr(method=method)
    corr = corr.fillna(0.0)
    labels = [str(c) for c in corr.columns]
    matrix = [[round(float(corr.loc[r, c]), 4) for c in corr.columns] for r in corr.index]
    return {"labels": labels, "matrix": matrix, "method": method}


def grouped_stats(df: pd.DataFrame, value_col: str, group_col: str) -> dict:
    """按 group_col 分组的 value_col 统计(均值/中位/std/计数/超标计数需外部阈值)。

    用于 EDA 按区域/深度/污染物分层的对比柱状图。基于真实数据。
    """
    if group_col not in df.columns or value_col not in df.columns:
        return {"groups": []}
    sub = df[[group_col, value_col]].copy()
    sub[value_col] = pd.to_numeric(sub[value_col], errors="coerce")
    sub = sub.dropna()
    groups = []
    for g, part in sub.groupby(group_col):
        if len(part) == 0:
            continue
        vals = part[value_col]
        groups.append({
            "group": str(g) if g is not None else "—", "n": int(len(vals)),
            "mean": round(float(vals.mean()), 4),
            "median": round(float(vals.median()), 4),
            "std": round(float(vals.std(ddof=1)), 4) if len(vals) > 1 else 0.0,
            "min": round(float(vals.min()), 4),
            "max": round(float(vals.max()), 4),
        })
    groups.sort(key=lambda x: x["mean"], reverse=True)
    return {"group_col": group_col, "value_col": value_col, "groups": groups}


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
