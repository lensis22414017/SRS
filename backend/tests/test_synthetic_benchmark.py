"""蒙特卡洛 50 场地基准测试。"""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, "ml", "synthetic")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_generate_50_site_benchmark_watermarked_and_sparse():
    from monte_carlo import POLLUTION_COUNTS, REGION_COUNTS, generate_benchmark

    real = pd.DataFrame({
        "covariate_Region": ["青藏高原区", "东北平原区", "华南/东南沿海区"] * 12,
        "covariate_LandUse_std": ["农用地", "工矿用地", "建设用地"] * 12,
        "covariate_Pollution_Type_std": ["HM", "OP", "HM+OP"] * 12,
        "measured_Cd_mgkg": [0.2, 0.6, 1.1] * 12,
        "measured_As_mgkg": [10, 30, 80] * 12,
        "measured_BaP_ngg": [None, 12, 40] * 12,
        "missing_BaP_ngg": [1, 0, 0] * 12,
    })
    sites, samples, manifest = generate_benchmark(real, random_seed=123)

    assert len(sites) == 50
    assert sites["region"].value_counts().to_dict() == REGION_COUNTS
    assert sites["pollution_type"].value_counts().to_dict() == POLLUTION_COUNTS
    assert samples["is_synthetic"].eq(True).all()
    assert samples["evidence_level"].eq("SIMULATED").all()
    assert samples["site_id"].nunique() == 50
    assert samples.groupby("site_id").size().between(20, 80).all()
    assert samples.filter(like="missing_").sum().sum() > 0
    assert manifest["recommended_validation_use"] == "synthetic_scenario_benchmark_only"
