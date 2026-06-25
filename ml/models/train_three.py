"""阶段C: 三块分别训练 RF + 数据湖合并训练。

裴总: 重金属/OP/复合三块分别训练 + 合并数据湖完整再训练(autoresearch)。
产物: ml/artifacts/rf_barrier_factor_v0.1_<date>_<name>.joblib (4 model: hm/op/composite/lake)。
load_latest 加载最新(lake 最后, 含重金属+有机, diagnosis 用它)。

运行: cd backend && .venv/bin/python ../ml/models/train_three.py
"""
import os, sys, json
import pandas as pd
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))
from data_prep import prepare  # noqa
ARTIFACTS = os.path.join(ROOT, "ml", "artifacts")
TRAIN_BASE = os.path.join(ROOT, "data", "training")
DROP_COLS = ["Latitude", "Longitude", "Province", "City", "Pollution_Type", "DOI",
             "Source", "id_DOI", "id_Source", "ID", "Year", "LandUse", "SamplingDepth",
             "split_source", "is_synthetic"]

# 污染物浓度列 (X_barrier 必须排除 — 标签由浓度派生, 进特征则标签泄漏, AUC虚高无泛化意义)
# 中英双套: 覆盖 HM_CSV 块(中文列名) + merged/composite/lake 块(英文列名)
# 依据: Hu et al. 2026 Commun Earth Environ 7:214 — 障碍因子RF特征应为土壤性质(pH/OC/CEC/clay), 非浓度本身
POLLUTANT_COLS = [
    # HM 英文 (merged/composite/lake 块)
    "Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cr_mgkg", "Hg_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg",
    # HM 中文 (HM_CSV 块)
    "镉", "铅", "砷", "铬", "汞", "铜", "锌", "镍",
    # OP (merged/composite/lake 块)
    "Sum_PAH_ngg", "BaP_ngg", "SumOCP_ngg", "SumDDTs_ngg", "SumPCB_ngg", "SumHCHs_ngg",
    "SumPAE_ugkg", "SumPBDE_ngg", "SumPFAS_ngg", "TPH_ngg", "HMWPAH_ngg", "LMWPAH_ngg",
]


def _prep_csv(name, target_col="标签_生产", barrier_only=False):
    """读 imputed train, drop 非特征(经纬度等防泄漏), 双标签防泄漏, 写 tmp csv。

    双标签架构(2026-06-24 Wave E): 仅保留 target_col(重命名'标签'供 prepare),
    删除其余标签列(标签/标签_生产/标签_生态)——防冗余标签进特征致泄漏
    (标签_生产/生态均由浓度派生, 互为代理, 进特征则AUC虚高无泛化意义)。

    barrier_only=True (路径C X_barrier 防泄漏组): 额外 drop 所有污染物浓度列+其__missing,
    特征仅剩土壤理化协变量(SoilpH/OC_pct等)。与含浓度组(full)对照, AUC差距=标签泄漏实证。
    依据: Hu 2026 Nature级 — 障碍因子RF特征应为土壤性质非浓度; plan Wave E修正(裴总2026-06-24科研深问)。
    """
    src = os.path.join(TRAIN_BASE, name, "imputed", "train.csv")
    df = pd.read_csv(src, low_memory=False)
    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    if barrier_only:  # X_barrier: 排除污染物浓度(标签泄漏源), 仅留理化协变量
        pollute = [c for c in POLLUTANT_COLS if c in df.columns]
        pollute += [f"{c}__missing" for c in POLLUTANT_COLS if f"{c}__missing" in df.columns]
        df = df.drop(columns=pollute)
    for c in ["标签", "标签_生产", "标签_生态"]:
        if c in df.columns and c != target_col:
            df = df.drop(columns=c)
    if target_col != "标签" and target_col in df.columns:
        df = df.rename(columns={target_col: "标签"})
    assert "标签" in df.columns, f"{name} 缺标签列({target_col})"
    tmp = os.path.join(TRAIN_BASE, name, "imputed", f"_train_prepared_{target_col}.csv")
    df.to_csv(tmp, index=False)
    return tmp


def _train(name, csv_path):
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
    from sklearn.model_selection import train_test_split
    from datetime import datetime, timezone

    X, y, meta = prepare(csv_path)
    if X.shape[1] == 0:
        # barrier模式: 该块drop浓度后无理化协变量(如HM块仅重金属浓度列) → 0特征不可训
        # 诚实跳过+标注(不伪造模型); 实证"重金属障碍因子识别缺理化协变量"数据局限(plan R3/优先级#2)
        is_bar = "barrier" in name
        reason = ("X_barrier模式该块无理化协变量(仅污染物浓度)→0特征不可训,数据局限实证"
                  if is_bar else "0特征不可训")
        print(f"[{name}] ⚠️ 跳过训练: {reason}")
        _d = datetime.now(timezone.utc).strftime("%Y%m%d")
        _skip = {"block": name, "skipped": True, "skip_reason": reason, "n_features": 0,
                 "feature_strategy": "X_barrier_pure_covariate" if is_bar else "full_with_pollutant",
                 "leakage_warning": reason, "is_real_data": meta.get("is_real_data"),
                 "class_balance": meta.get("class_balance")}
        with open(os.path.join(ARTIFACTS, f"rf_barrier_factor_v0.1_{_d}_{name}.skip.meta.json"),
                  "w", encoding="utf-8") as _f:
            json.dump(_skip, _f, ensure_ascii=False, indent=2)
        return None
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    model = RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                   random_state=42, n_jobs=-1)
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)[:, 1]
    metrics = {
        "accuracy": round(float(accuracy_score(y_te, model.predict(X_te))), 4),
        "f1": round(float(f1_score(y_te, model.predict(X_te))), 4),
        "auc": round(float(roc_auc_score(y_te, proba)), 4),
        "test_size": int(len(y_te))}
    version = "v0.1_" + datetime.now(timezone.utc).strftime("%Y%m%d") + "_" + name
    # lake(数据湖)用 z 前缀使字典序最后(>op) → load_latest 优先用它(裴总: 数据湖完整训练)
    if name == "lake":
        version = "v0.1_" + datetime.now(timezone.utc).strftime("%Y%m%d") + "_zlake_final"
    is_barrier = "barrier" in name  # 路径C对照组标识(name含'barrier'=X_barrier防泄漏组)
    bundle = {"model": model, "model_name": "rf_barrier_factor", "version": version,
              "algorithm": "RandomForestClassifier",
              "params": {"n_estimators": 300, "class_weight": "balanced"},
              "feature_list": meta["feature_list"], "medians": meta["medians"],
              "data_version": meta["data_version"] + "_" + name,
              "is_real_data": meta["is_real_data"], "data_source": meta["data_source"],
              "label_source": meta["label_source"], "metrics": metrics,
              "trained_at": datetime.now(timezone.utc).isoformat(),
              "n_features": int(X.shape[1]), "block": name,
              "feature_strategy": "X_barrier_pure_covariate" if is_barrier else "full_with_pollutant_concentration",
              "leakage_warning": ("X_barrier纯协变量(排除污染物浓度);AUC偏低反映理化协变量覆盖率不足(当前仅SoilpH/OC_pct),需外部协变量增强(ECA/ITM/GSM/TLDA/PFE)提升泛化力"
                                  if is_barrier
                                  else "含污染物浓度特征;标签由浓度派生→标签泄漏;AUC虚高(≈1.0)不可作独立泛化证据(Hu2026铁证,plan§18.4)")}
    path = os.path.join(ARTIFACTS, f"rf_barrier_factor_{version}.joblib")
    joblib.dump(bundle, path)
    with open(os.path.join(ARTIFACTS, f"rf_barrier_factor_{version}.meta.json"), "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in bundle.items() if k != "model"}, f, ensure_ascii=False, indent=2)
    # 特征含有机?
    has_org = any(k in str(meta["feature_list"]) for k in ["PAH", "OCP", "PCB", "PAE", "DDT", "HCH", "PBDE", "PFAS", "TPH"])
    print(f"[{name}] n={len(X)} feat={X.shape[1]} 含有机={has_org} metrics={metrics} → {version}")
    return path


def build_lake():
    """三块 concat → 数据湖(特征并集) → train csv。"""
    lake_rows = []
    for name in ["hm", "op", "composite"]:
        df = pd.read_csv(os.path.join(TRAIN_BASE, name, "imputed", "train.csv"))
        df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
        df["__block"] = name
        lake_rows.append(df)
    lake = pd.concat(lake_rows, ignore_index=True, sort=False)
    # 特征并集的缺失(块间无的列)用中位数 + missing 标记(已在各块; 新缺失补 0/median)
    lake_dir = os.path.join(TRAIN_BASE, "lake", "imputed")
    os.makedirs(lake_dir, exist_ok=True)
    lake.to_csv(os.path.join(lake_dir, "train.csv"), index=False)
    print(f"[lake] 合并: {lake.shape} (三块concat, 特征并集)")


if __name__ == "__main__":
    # 路径C双版本对照(Wave E, 裴总2026-06-25拍板):
    #   full组(含浓度, 标签泄漏, AUC虚高≈1.0) vs barrier组(X_barrier纯协变量, AUC低反映协变量不足)
    #   AUC差距 = 标签泄漏实证(Hu 2026 Commun Earth Environ 7:214 铁证复现)
    #   两组×4块×2轨 = 16 model; 均标 leakage_warning 诚实标注(§18.4不伪造性能)
    build_lake()  # 三块concat→数据湖(含双标签), 双轨共用
    for barrier_only, tag in [(False, "full"), (True, "barrier")]:
        print(f"\n########## 对照组 [{tag}] barrier_only={barrier_only} ##########")
        for target_col, suffix in [("标签_生产", "prod"), ("标签_生态", "eco")]:
            print(f"\n=== [{tag}] 训练 {suffix} 轨 (target={target_col}) ===")
            for name in ["hm", "op", "composite", "lake"]:
                csv = _prep_csv(name, target_col, barrier_only=barrier_only)
                _train(f"{name}_{suffix}_{tag}", csv)
    print("\n完成。16 model(路径C对照: full×8 + barrier×8, 各4块×2轨) → ml/artifacts/")
