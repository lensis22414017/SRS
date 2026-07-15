import prepare


def test_every_subset_has_multiple_source_groups_and_features():
    for subset in prepare.SUBSETS:
        data = prepare.load_subset(subset)
        assert data["groups"].nunique() >= 3
        assert len(data["feature_cols"]) > 0


def test_targets_and_forbidden_fields_are_not_features():
    forbidden = ("oi_", "target", "threshold", "obstacle_level", "source_id", "sample_id")
    for subset in prepare.SUBSETS:
        features = [value.lower() for value in prepare.load_subset(subset)["feature_cols"]]
        assert not [value for value in features if any(term in value for term in forbidden)]
