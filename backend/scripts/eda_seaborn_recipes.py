import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

def missingness_heatmap(df: pd.DataFrame, out: str):
    plt.figure(figsize=(12,6), dpi=160)
    sns.heatmap(df.isna(), cbar=False)
    plt.title("字段缺失分布热力图")
    plt.tight_layout(); plt.savefig(out, bbox_inches="tight"); plt.close()

def correlation_heatmap(df: pd.DataFrame, numeric_cols: list[str], out: str, method='spearman'):
    corr = df[numeric_cols].corr(method=method)
    plt.figure(figsize=(10,8), dpi=160)
    sns.heatmap(corr, cmap='vlag', center=0)
    plt.title(f"{method}相关性热图")
    plt.tight_layout(); plt.savefig(out, bbox_inches="tight"); plt.close()
