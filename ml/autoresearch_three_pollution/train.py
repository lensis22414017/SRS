"""L2唯一研究对象：三污染类型双轨表格回归模型。"""
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from lightgbm import LGBMRegressor


PARAMS = {
    "n_estimators": 240,
    "max_features": 1.0,
    "min_samples_leaf": 1,
    "max_depth": None,
    "n_jobs": -1,
    "random_state": 42,
}

HM_PARAMS = {
    "n_estimators": 250, "learning_rate": 0.04, "num_leaves": 31,
    "min_child_samples": 20, "subsample": 0.85, "colsample_bytree": 0.8,
    "reg_lambda": 1.0, "n_jobs": -1, "random_state": 42, "verbosity": -1,
}
def build_model(subset: str, track: str):
    if subset == "hm":
        return Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("model", LGBMRegressor(**HM_PARAMS)),
        ])
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("model", ExtraTreesRegressor(**PARAMS)),
    ])
