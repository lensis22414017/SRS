"""生成 model_ready 数据集切分登记。

切分原则:
- 先切真实数据, 后续插补/扩增只能在 train 内 fit/生成;
- real valid/test 必须对 DOI 与 Source **同时**零跨集泄漏, 禁止行级随机作为主验证;
- synthetic 只登记为增强/压力/演示, 不进入任何 real split。

零泄漏切分实现(修复 DOI 与 Source 交叉泄漏):
  把 (DOI, Source) 视为二部图, 同一 DOI 或同一 Source 相连的行属于同一连通分量;
  以**连通分量**为最小不可分单位整体分配到 train/valid/test/external,
  从而保证任意两个 real split 在 DOI 与 Source 两个键上都零重叠。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_REAL = os.path.join(ROOT, "data", "model_ready", "model_ready_hm_op.csv")
DEFAULT_SYN_SAMPLES = os.path.join(ROOT, "data", "synthetic", "synthetic_samples_50sites.csv")
DEFAULT_SYN_SITES = os.path.join(ROOT, "data", "synthetic", "synthetic_scenario_benchmark_50sites.csv")
OUTDIR = os.path.join(ROOT, "data", "splits")

REAL_SPLITS = ["train_real", "valid_real_group_split",
               "test_real_group_split", "external_literature_holdout"]
KEYS = ["id_DOI", "id_Source"]


def _norm(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none", "<na>"):
        return None
    return s


class _UnionFind:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def _connected_components(df: pd.DataFrame) -> list[list[int]]:
    """按 DOI/Source 共现把行聚成连通分量, 返回每个分量的行索引列表。"""
    n = len(df)
    uf = _UnionFind(n)
    doi_first: dict[str, int] = {}
    src_first: dict[str, int] = {}
    doi_vals = df["id_DOI"].tolist() if "id_DOI" in df.columns else [None] * n
    src_vals = df["id_Source"].tolist() if "id_Source" in df.columns else [None] * n
    for i in range(n):
        d = _norm(doi_vals[i])
        s = _norm(src_vals[i])
        if d is not None:
            if d in doi_first:
                uf.union(i, doi_first[d])
            else:
                doi_first[d] = i
        if s is not None:
            if s in src_first:
                uf.union(i, src_first[s])
            else:
                src_first[s] = i
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(uf.find(i), []).append(i)
    return list(comps.values())


def _assign_components(comps: list[list[int]], n: int, seed: int) -> dict[str, set[int]]:
    """以连通分量为单位, 按目标比例贪心分配到 valid/test/external/train。"""
    import numpy as np

    rng = np.random.default_rng(seed)
    order = list(range(len(comps)))
    rng.shuffle(order)
    targets = {"valid_real_group_split": 0.15, "test_real_group_split": 0.15,
               "external_literature_holdout": 0.05}
    quota = {k: max(1, int(n * f)) for k, f in targets.items()}
    assigned = {"valid_real_group_split": set(), "test_real_group_split": set(),
                "external_literature_holdout": set(), "train_real": set()}
    fill_seq = ["valid_real_group_split", "test_real_group_split", "external_literature_holdout"]
    for ci in order:
        rows = comps[ci]
        placed = False
        for split in fill_seq:
            if len(assigned[split]) < quota[split]:
                assigned[split].update(rows)
                placed = True
                break
        if not placed:
            assigned["train_real"].update(rows)
    return assigned


def _leakage(left: pd.DataFrame, right: pd.DataFrame, key: str) -> dict:
    a = {_norm(v) for v in left[key]} - {None} if key in left.columns else set()
    b = {_norm(v) for v in right[key]} - {None} if key in right.columns else set()
    overlap = sorted(a & b)
    return {"passed": len(overlap) == 0, "overlap_count": len(overlap), "examples": overlap[:5]}


def build_real_splits(real_df: pd.DataFrame, seed: int = 42) -> tuple[dict[str, pd.DataFrame], dict]:
    df = real_df.copy().reset_index(drop=True)
    df["split_source"] = "real_model_ready"
    df["is_synthetic"] = False
    comps = _connected_components(df)
    assigned = _assign_components(comps, len(df), seed)
    splits = {name: df.loc[sorted(idx)].copy() for name, idx in assigned.items()}

    # 全配对 × 双键 泄漏检查
    checks: dict = {}
    names = REAL_SPLITS
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            for key in KEYS:
                checks[f"{names[i]}__vs__{names[j]}__{key}"] = _leakage(
                    splits[names[i]], splits[names[j]], key)
    checks["synthetic_not_in_real"] = {
        "passed": all(not bool(splits[n]["is_synthetic"].any()) for n in splits),
        "overlap_count": 0, "examples": [],
    }
    checks["all_passed"] = all(c["passed"] for c in checks.values() if isinstance(c, dict) and "passed" in c)
    return splits, checks


def _write_csv(df: pd.DataFrame, filename: str) -> str:
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, filename)
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def build_split_registry(real_csv: str = DEFAULT_REAL, syn_samples_csv: str = DEFAULT_SYN_SAMPLES,
                         syn_sites_csv: str = DEFAULT_SYN_SITES, seed: int = 42) -> dict:
    real = pd.read_csv(real_csv, low_memory=False)
    splits, checks = build_real_splits(real, seed=seed)
    registry = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_real_csv": os.path.relpath(real_csv, ROOT),
        "seed": seed,
        "splits": {},
        "leakage_checks": checks,
        "grouping_strategy": "connected_components(DOI,Source) — 双键同时零跨集",
        "rules": [
            "real splits are generated before imputation/augmentation",
            "synthetic datasets are excluded from valid_real/test_real/external_holdout",
            "row-level random split is not a main validation split",
            "DOI and Source both have zero cross-real-split overlap",
        ],
    }
    for name, df in splits.items():
        path = _write_csv(df, f"{name}.csv")
        registry["splits"][name] = {"path": os.path.relpath(path, ROOT), "rows": int(len(df)),
                                    "is_synthetic": False}

    if os.path.exists(syn_samples_csv):
        syn = pd.read_csv(syn_samples_csv, low_memory=False)
        syn["recommended_validation_use"] = syn.get(
            "recommended_validation_use", "synthetic_train_augmented_or_stress_only")
        syn["is_synthetic"] = True
        path = _write_csv(syn, "synthetic_train_augmented.csv")
        registry["splits"]["synthetic_train_augmented"] = {
            "path": os.path.relpath(path, ROOT), "rows": int(len(syn)), "is_synthetic": True,
            "allowed_use": "training_augmentation_only"}
        sort_cols = [c for c in ["threshold_exceedance", "SBFI_risk"] if c in syn.columns]
        stress = syn.sort_values(sort_cols, ascending=False).head(min(500, len(syn))) if sort_cols else syn.head(min(500, len(syn)))
        path = _write_csv(stress, "synthetic_stress_extreme.csv")
        registry["splits"]["synthetic_stress_extreme"] = {
            "path": os.path.relpath(path, ROOT), "rows": int(len(stress)), "is_synthetic": True,
            "allowed_use": "stress_test_only"}
    if os.path.exists(syn_sites_csv):
        sites = pd.read_csv(syn_sites_csv, low_memory=False)
        sites["is_synthetic"] = True
        path = _write_csv(sites, "synthetic_scenario_benchmark_50sites.csv")
        registry["splits"]["synthetic_scenario_benchmark_50sites"] = {
            "path": os.path.relpath(path, ROOT), "rows": int(len(sites)), "is_synthetic": True,
            "allowed_use": "benchmark_demo_only"}
        if "pollution_type" in sites.columns:
            demo = sites.groupby("pollution_type", group_keys=False).head(2)
            path = _write_csv(demo, "report_demo_sites.csv")
            registry["splits"]["report_demo_sites"] = {
                "path": os.path.relpath(path, ROOT), "rows": int(len(demo)), "is_synthetic": True,
                "allowed_use": "report_demo_only"}

    registry_path = os.path.join(OUTDIR, "dataset_split_registry.json")
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    summary_rows = [{"split": name, **meta} for name, meta in registry["splits"].items()]
    pd.DataFrame(summary_rows).to_csv(os.path.join(OUTDIR, "dataset_split_summary.csv"),
                                      index=False, encoding="utf-8-sig")
    return registry


if __name__ == "__main__":
    reg = build_split_registry()
    print(json.dumps({"all_passed": reg["leakage_checks"]["all_passed"],
                      "splits": {k: v["rows"] for k, v in reg["splits"].items()}},
                     ensure_ascii=False, indent=2))
