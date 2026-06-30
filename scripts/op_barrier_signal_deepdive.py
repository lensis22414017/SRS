"""op 组 X_barrier 真信号深挖(裴总#4)。

op barrier AUC=0.958(唯一有泛化力的X_barrier块, ΔAUC仅0.04 vs full)。
深挖SHAP: 哪些协变量驱动有机超标判定, 验证"SoilpH/OC调控有机迁移"机制。
对比 full 组(AUC=0.9999标签泄漏) → 证op的0.958是真协变量信号非泄漏。
"""
import sys
import os
import joblib
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))
from data_prep import prepare  # noqa: E402
import shap  # noqa: E402

ART = os.path.join(ROOT, "ml", "artifacts")
OP_TRAIN = os.path.join(ROOT, "data", "training", "op", "imputed", "train.csv")


def analyze(model_path, label):
    import pandas as pd
    bundle = joblib.load(model_path)
    model = bundle["model"]
    feats = bundle["feature_list"]  # 模型训练特征(barrier=4 / full=28), 必须按此对齐
    medians = bundle["medians"]
    df = pd.read_csv(OP_TRAIN, low_memory=False)
    y = df["标签_生产"].astype(int) if "标签_生产" in df.columns else df["标签"].astype(int)
    X = pd.DataFrame(index=df.index)
    for f in feats:
        X[f] = df[f] if f in df.columns else medians.get(f, 0.0)
        X[f] = X[f].fillna(medians.get(f, 0.0))
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(X)
    if isinstance(sv, list):  # 旧版: [class0, class1]
        sv1 = sv[1]
    elif sv.ndim == 3:  # 新版二分类: (n_samples, n_features, 2)
        sv1 = sv[:, :, 1]
    else:  # 单 array
        sv1 = sv
    imp = np.abs(sv1).mean(axis=0)
    order = np.argsort(imp)[::-1]
    print(f"\n=== {label}: {bundle['version']} ===")
    print(f"  AUC={bundle['metrics']['auc']}  F1={bundle['metrics']['f1']}  feat={len(feats)}")
    print(f"  strategy={bundle.get('feature_strategy')}")
    print(f"  SHAP top:")
    for i in order[:6]:
        print(f"    {feats[i]:<22} |SHAP|={imp[i]:.4f}")
    return feats[order[0]], imp[order[0]]


print("op 组 X_barrier 真信号深挖 (裴总#4)")
print("=" * 60)

# barrier 组(防泄漏, 4协变量)
tf_b, tv_b = analyze(
    os.path.join(ART, "rf_barrier_factor_v0.1_20260625_op_prod_barrier.joblib"),
    "barrier组(X_barrier纯协变量)")

# full 组(含浓度, 标签泄漏对照)
tf_f, tv_f = analyze(
    os.path.join(ART, "rf_barrier_factor_v0.1_20260625_op_prod_full.joblib"),
    "full组(含浓度, 标签泄漏对照)")

print(f"\n{'=' * 60}")
print(f"=== 结论 ===")
print(f"barrier 组驱动因子: {tf_b} (|SHAP|={tv_b:.4f}) — 纯协变量真信号")
print(f"full    组驱动因子: {tf_f} (|SHAP|={tv_f:.4f}) — 含浓度(标签泄漏)")
if "OC" in tf_b or "pH" in tf_b or "有机" in tf_b:
    print("✓ barrier组由土壤理化协变量(OC/pH)驱动 = 真泛化信号(Hu2026机制)")
    print("  机制: 低OC→有机污染物吸附弱→迁移强→超标; 低pH增强部分有机物活性")
else:
    print(f"⚠ barrier组驱动因子{tf_b}非预期OC/pH, 需进一步核查")
