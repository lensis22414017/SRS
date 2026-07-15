# 三污染类型双轨 autoresearch 纲领

- L1 `prepare.py`锁定，不得修改；测试集在迭代阶段保持关闭。
- L2仅允许修改`train.py`中的模型和参数。
- 固定预算：HM、OP、HM+OP各自按`source_id`做3折GroupKFold，分别评价生产轨与生态轨。
- 主指标：六任务`mean_cv_spearman`；守门指标：`worst_cv_spearman`不得下降超过0.01；辅助指标：`mean_cv_mae`。
- 每轮仅提出一个改动假设。主指标提升至少0.002且守门指标通过才KEEP，否则REVERT。
- 连续4轮无提升停止；最终模型只运行一次独立test评估。
- 禁止随机行切分，禁止把目标、阈值、超标结果或来源ID作为特征。
