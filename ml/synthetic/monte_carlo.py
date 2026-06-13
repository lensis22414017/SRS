"""半合成 50 场地区域化 benchmark 生成器。

模拟数据只用于场景适配、压力测试、报告演示、稳健性检验。
严禁进入 real validation/test 指标。
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_REAL = os.path.join(ROOT, "data", "model_ready", "model_ready_hm_op.csv")
OUTDIR = os.path.join(ROOT, "data", "synthetic")
RULE_VERSION = "mc_benchmark_v0.1"

REGION_COUNTS = {
    "青藏高原区": 5,
    "黄土高原/黄河中上游区": 5,
    "黄淮海/黄河平原区": 6,
    "长江中下游区": 7,
    "东北平原区": 5,
    "华北城市群区": 5,
    "西北干旱绿洲区": 5,
    "西南山地/云贵川区": 6,
    "华南/东南沿海区": 6,
}
POLLUTION_COUNTS = {"HM": 18, "OP": 16, "HM+OP": 16}
HM_COLS = ["Cd_mgkg", "Pb_mgkg", "As_mgkg", "Cu_mgkg", "Zn_mgkg", "Ni_mgkg", "Cr_mgkg", "Hg_mgkg"]
OP_COLS = ["BaP_ngg", "Phe_ngg", "Ant_ngg", "Pyr_ngg", "SumDDTs_ngg", "SumPCB_ngg", "TPH_ngg"]

REGION_PROVINCES = {
    "青藏高原区": [("青海", "西宁"), ("西藏", "拉萨")],
    "黄土高原/黄河中上游区": [("陕西", "铜川"), ("山西", "临汾"), ("甘肃", "白银"), ("宁夏", "石嘴山")],
    "黄淮海/黄河平原区": [("河南", "郑州"), ("山东", "淄博"), ("河北", "唐山"), ("天津", "滨海新区")],
    "长江中下游区": [("江苏", "南京"), ("浙江", "杭州"), ("安徽", "铜陵"), ("湖北", "武汉"), ("湖南", "株洲")],
    "东北平原区": [("辽宁", "沈阳"), ("吉林", "吉林"), ("黑龙江", "大庆")],
    "华北城市群区": [("北京", "房山"), ("内蒙古", "包头")],
    "西北干旱绿洲区": [("新疆", "乌鲁木齐"), ("新疆", "克拉玛依")],
    "西南山地/云贵川区": [("云南", "个旧"), ("贵州", "铜仁"), ("四川", "攀枝花"), ("重庆", "万州")],
    "华南/东南沿海区": [("广东", "广州"), ("广西", "河池"), ("福建", "泉州"), ("海南", "儋州")],
}
INDUSTRY_BY_TYPE = {
    "HM": ["矿山", "冶炼", "电镀", "工业周边农田"],
    "OP": ["石化", "焦化", "农药厂", "油污场地"],
    "HM+OP": ["电子拆解", "化工遗留地", "复合工业棕地", "垃圾填埋周边"],
}
LAND_BY_TYPE = {
    "HM": ["农用地", "工矿用地", "生态用地"],
    "OP": ["建设用地", "工矿用地", "农用地"],
    "HM+OP": ["建设用地", "工矿用地", "农用地"],
}


def _sha(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _pollution_sequence(rng: np.random.Generator) -> list[str]:
    seq = []
    for k, n in POLLUTION_COUNTS.items():
        seq.extend([k] * n)
    rng.shuffle(seq)
    return seq


def _site_rows(rng: np.random.Generator) -> pd.DataFrame:
    pollution = _pollution_sequence(rng)
    rows = []
    i = 0
    for region, n in REGION_COUNTS.items():
        for _ in range(n):
            ptype = pollution[i]
            province, city = REGION_PROVINCES[region][i % len(REGION_PROVINCES[region])]
            rows.append({
                "site_id": f"SYN-SITE-{i + 1:03d}",
                "synthetic_site_id": f"SYN-BENCH-{i + 1:03d}",
                "region": region,
                "province": province,
                "city": city,
                "land_use_type": rng.choice(LAND_BY_TYPE[ptype]),
                "pollution_type": ptype,
                "industry_source": rng.choice(INDUSTRY_BY_TYPE[ptype]),
                "sample_points": int(rng.integers(20, 81)),
                "recommended_validation_use": "synthetic_scenario_benchmark_only",
                "generation_rule_version": RULE_VERSION,
                "is_synthetic": True,
                "evidence_level": "SIMULATED",
            })
            i += 1
    return pd.DataFrame(rows)


def _series(real: pd.DataFrame, measured_col: str) -> pd.Series:
    if measured_col in real.columns:
        s = pd.to_numeric(real[measured_col], errors="coerce").dropna()
        s = s[s >= 0]
        if len(s) > 0:
            return s
    return pd.Series(dtype=float)


def _draw_concentration(real: pd.DataFrame, col: str, rng: np.random.Generator) -> float:
    s = _series(real, f"measured_{col}")
    if len(s) >= 30:
        sample = float(rng.choice(s.values))
        jitter = float(rng.lognormal(mean=0, sigma=0.25))
        return round(max(sample * jitter, 0), 5)
    defaults = {
        "Cd_mgkg": 0.6, "Pb_mgkg": 80, "As_mgkg": 35, "Cu_mgkg": 120,
        "Zn_mgkg": 220, "Ni_mgkg": 70, "Cr_mgkg": 150, "Hg_mgkg": 1.0,
        "BaP_ngg": 20, "Phe_ngg": 100, "Ant_ngg": 50, "Pyr_ngg": 80,
        "SumDDTs_ngg": 30, "SumPCB_ngg": 15, "TPH_ngg": 500,
    }
    base = defaults.get(col, 1.0)
    return round(float(rng.lognormal(mean=np.log(base), sigma=0.75)), 5)


def _missing_rate(real: pd.DataFrame, col: str, fallback: float) -> float:
    miss_col = f"missing_{col}"
    measured_col = f"measured_{col}"
    if miss_col in real.columns:
        rate = pd.to_numeric(real[miss_col], errors="coerce").mean()
    elif measured_col in real.columns:
        rate = real[measured_col].isna().mean()
    else:
        rate = fallback
    if pd.isna(rate):
        rate = fallback
    return float(np.clip(rate, 0.15, 0.85))


def _cols_for_type(ptype: str) -> list[str]:
    if ptype == "HM":
        return HM_COLS
    if ptype == "OP":
        return OP_COLS
    return HM_COLS + OP_COLS


def _screening_limits() -> dict[str, float]:
    import sys
    backend = os.path.join(ROOT, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from app.db.load_standard_thresholds import seed_rows

    limits: dict[str, float] = {}
    for item in seed_rows():
        if item["standard_code"] != "GB 15618-2018" or item["screening_value"] is None:
            continue
        factor = item["factor_name"]
        limits[f"{factor}_mgkg"] = min(limits.get(f"{factor}_mgkg", float("inf")),
                                      float(item["screening_value"]))
    return limits


def _risk_label(row: dict, limits: dict[str, float]) -> tuple[int, str]:
    exceed = 0
    for col, limit in limits.items():
        val = row.get(f"measured_{col}")
        if val is not None and not pd.isna(val) and float(val) > limit:
            exceed += 1
    if exceed >= 3:
        return exceed, "high"
    if exceed >= 1:
        return exceed, "medium"
    return exceed, "low"


def generate_benchmark(real: pd.DataFrame, random_seed: int = 42):
    rng = np.random.default_rng(random_seed)
    sites = _site_rows(rng)
    samples = []
    limits = _screening_limits()
    batch_id = f"SIM-{random_seed}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    for _, site in sites.iterrows():
        cols = _cols_for_type(site["pollution_type"])
        for i in range(int(site["sample_points"])):
            row = {
                "site_id": site["site_id"],
                "synthetic_site_id": site["synthetic_site_id"],
                "sample_id": f"{site['site_id']}-P{i + 1:03d}",
                "region": site["region"],
                "province": site["province"],
                "city": site["city"],
                "land_use_type": site["land_use_type"],
                "pollution_type": site["pollution_type"],
                "industry_source": site["industry_source"],
                "is_synthetic": True,
                "evidence_level": "SIMULATED",
                "simulation_batch_id": batch_id,
                "generation_rule_version": RULE_VERSION,
                "recommended_validation_use": "synthetic_scenario_benchmark_only",
            }
            for col in cols:
                fallback = 0.45 if col in HM_COLS else 0.65
                is_missing = bool(rng.random() < _missing_rate(real, col, fallback))
                row[f"missing_{col}"] = int(is_missing)
                row[f"measured_{col}"] = np.nan if is_missing else _draw_concentration(real, col, rng)
            exceed, risk = _risk_label(row, limits)
            row["threshold_exceedance"] = exceed
            row["SBFI_risk"] = {"low": 0.25, "medium": 0.55, "high": 0.85}[risk]
            row["SBFI_prod"] = round(max(0.05, 1 - row["SBFI_risk"] + rng.normal(0, 0.05)), 3)
            row["SBFI_eco"] = round(max(0.05, 1 - row["SBFI_risk"] + rng.normal(0, 0.07)), 3)
            samples.append(row)
    samples_df = pd.DataFrame(samples)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_rule_version": RULE_VERSION,
        "random_seed": random_seed,
        "site_count": int(len(sites)),
        "sample_count": int(len(samples_df)),
        "region_counts": REGION_COUNTS,
        "pollution_counts": POLLUTION_COUNTS,
        "recommended_validation_use": "synthetic_scenario_benchmark_only",
        "warning": "SIMULATED rows are prohibited from real validation/test metrics.",
    }
    return sites, samples_df, manifest


def generate_from_csv(real_csv: str = DEFAULT_REAL, random_seed: int = 42):
    real = pd.read_csv(real_csv, low_memory=False)
    sites, samples, manifest = generate_benchmark(real, random_seed=random_seed)
    manifest["source_real_csv"] = os.path.relpath(real_csv, ROOT)
    manifest["source_real_sha256"] = _sha(real_csv)
    os.makedirs(OUTDIR, exist_ok=True)
    sites_path = os.path.join(OUTDIR, "synthetic_scenario_benchmark_50sites.csv")
    samples_path = os.path.join(OUTDIR, "synthetic_samples_50sites.csv")
    manifest_path = os.path.join(OUTDIR, "synthetic_generation_manifest.json")
    sites.to_csv(sites_path, index=False, encoding="utf-8-sig")
    samples.to_csv(samples_path, index=False, encoding="utf-8-sig")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return {"sites": sites_path, "samples": samples_path, "manifest": manifest_path, **manifest}


if __name__ == "__main__":
    print(json.dumps(generate_from_csv(), ensure_ascii=False, indent=2))
