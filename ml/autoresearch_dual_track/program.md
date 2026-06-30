# autoresearch: 双轨 RF CV AUC 优化 (0.83 → 0.9+)

> karpathy autoresearch 三层架构: L1 prepare.py 锁定 / L2 train.py agent 迭代 / L3 本文件循环策略。

## 目标 (裴总)
mean_cv_auc **0.829 → 0.9+**, 同时测试集 AUC 不显著下降 (防过拟合虚高)。

## 红线 (裴总铁律, 违反即 REVERT)
- 🔴 **防泄漏**: X_barrier 不得引入污染物浓度 (后缀 _mgkg/_ngg/_ugkg); 只能改 RF 超参/特征选择/集成
- 不得改 prepare.py (L1 锁定, 保证评估可比)
- CV 提升不得靠泄漏; 测试集 AUC 作泛化参考 (CV 高但测试集暴跌 = 过拟合, REVERT)

## 探索方向 (按优先级, 每次 1 个假设)
1. **树容量**: n_estimators 500→800→1200; max_depth None→30→50→80
2. **正则化** (防过拟合, 提泛化): min_samples_leaf 1→2→4→8; min_samples_split 2→5→10; max_features sqrt→0.3→0.5→log2→0.2
3. **类不平衡**: class_weight balanced→balanced_subsample→{0:1,1:1.5}→{0:1,1:3}
4. **分裂准则**: criterion gini→entropy→log_loss
5. **特征选择** (去噪声): 去低方差 (<0.01) / 去高相关 (>0.95) / SHAP top-K (需在 build_model 内做, 不引入污染物)
6. **集成** (RF 饱和后): RF + ExtraTrees 软投票 / GradientBoosting

## 保留阈值 (monotonic 改进)
- mean_cv_auc 提升 ≥ 0.005 **且** 测试集 mean AUC 下降 < 0.03 → **KEEP** (新 best)
- 否则 → **REVERT** (恢复 train.py, 记录失败假设防重复)

## 预算
- 最多 **12 次迭代**
- 连续 **3 次无改进** → 收敛停止
- 每次迭代: 改 train.py → 跑 prepare.evaluate() (~3min) → 比对 → keep/revert → 写 EXPERIMENTS.md

## 当前 best (baseline #000)
mean_cv_auc=**0.829** (prod 0.8314 / eco 0.8266) | 测试集 prod 0.66 / eco 0.57
