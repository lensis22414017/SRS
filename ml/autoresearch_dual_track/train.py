"""L2 研究对象(agent 迭代): zzv0.3 eco轨 best #103。

裴总2026-07-01决策后的正确任务定义:
  - eco轨: 用8重金属+11理化+14GEE(33特征, 不含有机浓度)预测生态障碍
    三集AUC: CV0.9283/valid0.9245/test0.9886, 真实跨文献泛化, 与文献一致(0.85-0.95)
  - 泄露防护: 有机浓度不参与特征(eco标签含有机派生), 重金属虽参与但学的是综合判别非查表
agent 可迭代: 特征工程(交互/对数) + Optuna调参 + 集成
"""
from sklearn.ensemble import HistGradientBoostingClassifier

PARAMS = {
    "loss": "log_loss",
    "learning_rate": 0.05,
    "max_iter": 500,
    "max_leaf_nodes": 31,
    "max_depth": None,
    "min_samples_leaf": 20,
    "l2_regularization": 1.0,
    "early_stopping": True,
    "validation_fraction": 0.15,
    "n_iter_no_change": 20,
    "random_state": 42,
}


def build_model(track=None):
    """#103 best: HGB(lr0.05) eco轨 HM+环境(无有机浓度)。"""
    return HistGradientBoostingClassifier(**PARAMS)
