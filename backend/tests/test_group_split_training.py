"""RF 行级随机 vs DOI/Source 分组切分测试。"""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, "ml", "models")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_compare_row_random_and_group_split_reports_leakage_checks():
    from group_split_training import compare_row_random_and_group_split

    rows = []
    for g in range(12):
        for i in range(6):
            rows.append({
                "id_DOI": f"10.synthetic/{g}",
                "id_Source": f"source-{g // 2}",
                "measured_Cd_mgkg": float(g + i / 10),
                "measured_As_mgkg": float((g % 4) * 10 + i),
                "measured_Pb_mgkg": float(g * 3 + i),
                "missing_Cd_mgkg": 0,
                "missing_As_mgkg": 0,
                "missing_Pb_mgkg": 0,
                "label_risk": int(g >= 6),
            })
    df = pd.DataFrame(rows)
    result = compare_row_random_and_group_split(
        df, target_col="label_risk", group_cols=("id_DOI", "id_Source"),
        n_estimators=40, random_state=7,
    )

    assert {"row_random", "group_splits", "auc_gap_row_minus_group", "leakage_checks"} <= set(result)
    assert "id_DOI" in result["group_splits"]
    assert result["row_random"]["split_strategy"] == "row_random"
    assert result["leakage_checks"]["id_DOI"]["passed"] is True
    assert result["leakage_checks"]["id_Source"]["passed"] is True
    assert result["row_random"]["roc_auc"] >= 0.5
