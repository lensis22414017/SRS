"""数据集切分登记测试: 真实切分必须对 DOI 与 Source 双键零跨集泄漏。"""
import itertools
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "ml", "models"))

REAL_SPLITS = ["train_real", "valid_real_group_split",
               "test_real_group_split", "external_literature_holdout"]
KEYS = ["id_DOI", "id_Source"]


def _fixture():
    """构造 Source 跨多个 DOI、DOI 跨多个 Source 的交叉场景(旧逻辑会泄漏)。"""
    rows = []
    for g in range(40):
        for i in range(3):
            rows.append({
                "id_DOI": f"10.x/{g}",
                # 关键: Source 每 2 个 DOI 复用一次 → DOI 与 Source 交叉
                "id_Source": f"src-{g // 2}",
                "row_uid": f"r{g}-{i}",
                "measured_As_mgkg": g + i,
                "is_synthetic": False,
            })
    return pd.DataFrame(rows)


def _keyset(df, k):
    if k not in df.columns:
        return set()
    return {str(v).strip() for v in df[k].dropna()} - {"", "nan", "None"}


def test_zero_cross_split_leakage_both_keys():
    from dataset_splits import build_real_splits
    splits, checks = build_real_splits(_fixture(), seed=9)
    assert set(REAL_SPLITS) <= set(splits)
    # 任意两个 real split, DOI 与 Source 都必须零重叠
    for a, b in itertools.combinations(REAL_SPLITS, 2):
        for k in KEYS:
            ov = _keyset(splits[a], k) & _keyset(splits[b], k)
            assert not ov, f"{a} vs {b} 在 {k} 上泄漏: {sorted(ov)[:5]}"
    assert checks["all_passed"] is True
    assert checks["synthetic_not_in_real"]["passed"] is True
    assert all(not df["is_synthetic"].any() for df in splits.values())


def test_all_rows_partitioned_no_loss():
    from dataset_splits import build_real_splits
    df = _fixture()
    splits, _ = build_real_splits(df, seed=3)
    total = sum(len(s) for s in splits.values())
    assert total == len(df)  # 不丢行、不重复


def test_leakage_helper_detects_planted_overlap():
    """负对照: 故意制造重叠, 检查器必须报 fail。"""
    from dataset_splits import _leakage
    a = pd.DataFrame({"id_DOI": ["d1", "d2"]})
    b = pd.DataFrame({"id_DOI": ["d2", "d3"]})
    res = _leakage(a, b, "id_DOI")
    assert res["passed"] is False and res["overlap_count"] == 1


def test_committed_real_splits_are_clean():
    """若仓库已生成 real split CSV, 校验其零泄漏(无文件则跳过)。"""
    import pytest
    sd = os.path.join(ROOT, "data", "splits")
    paths = {n: os.path.join(sd, f"{n}.csv") for n in REAL_SPLITS}
    if not all(os.path.exists(p) for p in paths.values()):
        pytest.skip("尚未生成 real split CSV")
    dfs = {n: pd.read_csv(p, low_memory=False) for n, p in paths.items()}
    for a, b in itertools.combinations(REAL_SPLITS, 2):
        for k in KEYS:
            ov = _keyset(dfs[a], k) & _keyset(dfs[b], k)
            assert not ov, f"已提交切分 {a} vs {b} 在 {k} 泄漏 {len(ov)}"
