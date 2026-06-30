"""L2 研究对象(agent 迭代): 双轨 RF 配置。

agent 改 PARAMS 或 build_model 提升 mean_cv_auc(karpathy: 单对象迭代)。
🔴 防泄漏红线(裴总铁律): 不得引入污染物浓度特征(后缀 _mgkg/_ngg/_ugkg);
   只能改 RF 超参/特征选择/集成方法。X_barrier 已防泄漏, 在此基础上优化。
"""
from sklearn.ensemble import RandomForestClassifier

PARAMS = {
    "n_estimators": 500,
    "max_depth": None,
    "min_samples_leaf": 1,
    "min_samples_split": 2,
    "max_features": 0.3,
    "class_weight": "balanced",
    "bootstrap": True,
    "criterion": "gini",
    "random_state": 42,
    "n_jobs": -1,
}


def build_model(track=None):
    """#011: Stacking(RF+ET+HGB → LR元学习器, 学习最优组合权重, 比#008投票更强?)。"""
    from sklearn.ensemble import (StackingClassifier, RandomForestClassifier,
                                   ExtraTreesClassifier,
                                   HistGradientBoostingClassifier)
    from sklearn.linear_model import LogisticRegression
    rf = RandomForestClassifier(n_estimators=200, max_features=0.3,
                                 class_weight="balanced", random_state=42)
    et = ExtraTreesClassifier(n_estimators=200, max_features=0.3,
                               class_weight="balanced", random_state=42)
    hgb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05,
                                          max_leaf_nodes=31, min_samples_leaf=20,
                                          l2_regularization=1.0, random_state=42)
    return StackingClassifier(
        [("rf", rf), ("et", et), ("hgb", hgb)],
        final_estimator=LogisticRegression(max_iter=1000), cv=3)
