#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_model_registry.py — P3-Alpha 模型注册表生成
读 ml/artifacts/p3_alpha/*_metrics.json,组装 model_registry_v0.8.json
"""
import os, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
ART = "ml/artifacts/p3_alpha"

# 注册规则
RULES = {
    ("all", "prod"): ("approved_alpha", True, "通用生产用途诊断,可用于系统演示"),
    ("all", "eco"):  ("approved_alpha", True, "通用生态用途诊断,可用于系统演示"),
    ("hm", "prod"):  ("approved_alpha", True, "重金属生产用途场景"),
    ("hm", "eco"):   ("approved_alpha", True, "重金属生态用途场景"),
    ("op", "prod"):  ("exploratory", False, "OP 模型 Spearman 偏低且 GEE 主导,仅探索参考"),
    ("op", "eco"):   ("exploratory", False, "OP 模型 Spearman 偏低且 GEE 主导,仅探索参考"),
    ("hm_op", "prod"): ("exploratory", False, "HM+OP生产轨,仅限规则辅助与人工复核"),
    ("hm_op", "eco"):  ("exploratory", False, "HM+OP生态轨,仅限规则辅助与人工复核"),
}

LIMITATIONS = {
    "approved_alpha": "source-level 验证(非 site-level);SHAP 含缺失指示器需经 KOS 清洗;Spearman 含地理混淆",
    "exploratory": "OP 信号稀疏;SHAP 由 GEE 背景主导非污染物;test 非零样本少;不建议作正式 OP 诊断依据",
}

registry = {"version": "v0.8", "generated_by": "build_model_registry.py", "models": {}}

for mf in sorted(glob.glob(f"{ART}/*_Full_*_metrics.json")):
    with open(mf, encoding="utf-8") as f:
        m = json.load(f)
    subset, track = m["subset"], m["track"]
    model_id = f"{subset}_{track}_Full_RandomForest"
    status, fe, use = RULES.get((subset, track), ("unknown", False, ""))
    entry = {
        "model_id": model_id,
        "subset": subset,
        "track": track,
        "target": m.get("target_col", f"OI_{track}_formal"),
        "algorithm": m.get("model_name", "RandomForest"),
        "model_file": f"{ART}/{model_id}.joblib",
        "metrics_file": mf,
        "shap_global_file": f"{ART}/{model_id}_shap_global.parquet" if os.path.exists(f"{ART}/{model_id}_shap_global.parquet") else None,
        "shap_local_file": f"{ART}/{model_id}_shap_local.parquet" if os.path.exists(f"{ART}/{model_id}_shap_local.parquet") else None,
        "status": status,
        "recommended_use": use,
        "limitations": LIMITATIONS[status],
        "frontend_enabled": fe,
        "metrics": {
            "test_spearman": m["test_spearman"],
            "test_mae": m["test_mae"],
            "test_r2": m["test_r2"],
            "cv_spearman_mean": m["cv_spearman_mean"],
            "top5_stability": m["top5_stability"],
        },
        "n_features": m["n_features"],
        "n_train": m["n_train"],
        "n_test": m["n_test"],
    }
    registry["models"][model_id] = entry

out = f"{ART}/model_registry_v0.8.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(registry, f, ensure_ascii=False, indent=2)

print(f"模型注册表已生成: {out}")
print(f"共 {len(registry['models'])} 个模型:")
for mid, e in registry["models"].items():
    print(f"  {mid}: status={e['status']} frontend={e['frontend_enabled']} spearman={e['metrics']['test_spearman']:.4f}")
