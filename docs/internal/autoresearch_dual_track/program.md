# autoresearch: zzv0.3 重训 — 0泄漏 GroupKFold + 保留非派生浓度列 (AUC 冲 0.9+)

> karpathy autoresearch 三层架构: L1 prepare.py 锁定 / L2 train.py agent 迭代 / L3 本文件循环策略。

## 目标 (裴总 2026-07-01)
GroupKFold(0泄漏) 下 mean_cv_auc **冲 0.9+**, 同时 valid/test AUC 不显著下降。
若物理上限达不到 0.9, 如实报告真实数据(不伪造)。

## 红线 (裴总铁律, 违反即 REVERT)
- 🔴 **0泄漏定义(重定)**: group split(DOI/Source 连通分量跨集零重叠) + GroupKFold CV(防同文献跨折)
- 🔴 **不得引入 20 个标签派生列**(HM_COLS 8 + ORG_COLS_MAP 12)
- ✅ **允许**: RF/ET/HGB 超参/集成/特征筛选; 原生NaN
- 不得改 prepare.py (L1 锁定)

## 探索方向 (按优先级)
1. **特征筛选**: 去全空列(282)/低方差
2. **HGB调参**: learning_rate/max_iter/max_leaf_nodes
3. **正则化**: l2_regularization/min_samples_leaf
4. **集成**: RF+HGB 软投票
5. **类不平衡**(eco): class_weight/阈值调优

## 保留阈值 (monotonic 改进)
- mean_cv_auc 提升 ≥ 0.005 **且** valid+test 不暴跌(下降<0.03) → KEEP
- 否则 REVERT

## 预算
- 最多 12 次迭代 / 连续 3 次无改进收敛

## 关键诊断结论 (2026-07-01)
特征组 prod test AUC: 理化(11)=0.53(随机) / GEE(14)=0.67(中等) / 浓度列(455)=0.53(随机,过拟合)
→ 物理上限 test~0.68-0.70, 距0.9有本质差距(特征判别力上限, 非模型问题)
