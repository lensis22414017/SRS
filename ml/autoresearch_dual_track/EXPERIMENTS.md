# autoresearch 实验日志: 双轨 RF CV AUC 优化

> 目标: mean_cv_auc 0.829 → 0.9+ (防泄漏红线 + 测试集不暴跌)

## Exp #000 | baseline (2026-06-29)
假设: 初始 RF (n=300, max_depth=None, min_leaf=1, max_features=sqrt, class_weight=balanced)
指标: mean_cv_auc=0.829 (prod 0.8314 / eco 0.8266) | 测试集 prod 0.66 / eco 0.57
裁决: BASELINE (后续迭代以此为基准)

## Exp #001 | n_estimators 300→500
假设: 树容量提升 CV
改动: PARAMS['n_estimators']=500
指标: mean_cv_auc 0.829→0.8296 (+0.0006 <0.005 阈值) | 测试集 prod0.66/eco0.57 持平
裁决: REVERT (提升不足, 树数量饱和; 后续基准 mean_cv_auc=0.8296)

## Exp #002 | max_features sqrt→0.3
假设: 更多特征/树提升表达
改动: PARAMS['max_features']=0.3
指标: mean_cv_auc 0.8296→0.8311 (+0.0015) | prod0.8332/eco0.8289 | 测试集 prod0.6694/eco0.5709
裁决: KEEP (小幅但 prod/eco/测试集全升, 方向对; 新基准 0.8311)

## Exp #003 | RF→HistGradientBoosting
假设: 梯度提升更强突破 0.9
改动: build_model 用 HistGradientBoostingClassifier
指标: mean_cv_auc 0.8311→0.8294 (-0.0017) | prod降/eco升 | 测试集 prod0.64降
裁决: REVERT (mean 退步; HGB 无显著优势)

## Exp #004 | RF→ExtraTrees(max_features=0.3)
假设: 分裂随机更多样
改动: build_model 用 ExtraTreesClassifier
指标: mean_cv_auc 0.8311→0.8288 (-0.0023) | 测试集 eco 暴跌 0.52
裁决: REVERT (mean+测试集双退)

## Exp #005 | RF+交互项(SelectKBest80)
假设: 理化×GEE 交互捕获非线性
改动: Pipeline(PolynomialFeatures interaction_only + SelectKBest80 + RF)
指标: mean_cv_auc 0.8311→0.8237 (-0.0074) | 交互噪声>信号
裁决: REVERT (交互项退步)

## Exp #006 | RF max_features=0.2
假设: 更少特征/树增多样性
改动: max_features=0.2
指标: mean_cv_auc 0.8311→0.8304 (-0.0007 持平)
裁决: REVERT (#002 max_features=0.3 仍 best 0.8311)

## Exp #007 | RF+ExtraTrees 软投票集成
假设: 多样性互补突破饱和
改动: VotingClassifier(RF+ET, soft, n=200)
指标: mean_cv_auc 0.8311→0.8347 (+0.0036 最大提升) | prod0.8365/eco0.833 | 测试集prod0.67/eco0.56
裁决: KEEP (新基准 0.8347, 集成有效)

## Exp #008 | RF+ExtraTrees+HGB 三集成
假设: 三模型多样性更强
改动: VotingClassifier(RF+ET+HGB, soft)
指标: mean_cv_auc 0.8347→0.8412 (+0.0065 >0.005!) | prod0.8396/eco0.8427 | 测试集prod0.67/eco0.57
裁决: KEEP (新基准 0.8412, 三集成突破)

## Exp #009 | 三集成子模型调优(n=300, mf=0.25, HGB iter=500)
假设: 调优提升
改动: RF/ET n=300 max_features=0.25; HGB max_iter=500 lr=0.03
指标: mean_cv_auc 0.8412→0.8408 (-0.0004 持平)
裁决: REVERT (#008 n=200 mf=0.3 仍 best 0.8412)

## Exp #010 | 三集成+LogisticRegression
假设: 线性模型多样性互补
改动: VotingClassifier(RF+ET+HGB+LR)
指标: mean_cv_auc 0.8412→0.8345 (-0.0067) | LR拖累
裁决: REVERT

## Exp #011 | Stacking(RF+ET+HGB→LR元) | 中断
假设: Stacking 学习最优组合权重
裁决: 中断(裴总决策接受 RF 成绩, 停 autoresearch)

## 最终总结 (裴总 2026-06-29)
- 11 次迭代: 单 RF 0.83 饱和, 集成(#008 三集成 RF+ExtraTrees+HGB) **0.8412 最佳**
- 防泄漏守住红线: 0.83-0.84 是 X_barrier(理化11+GEE14) 的真实上限, 非 0.99 泄漏
- **裴总决策**: 接受 RF 成绩(生产纯 RF CV 0.83), 跟甲方解释真实数据这结果不错
- 转任务: 17 场地 GEE 协变量补充 + site_ 前缀去掉 + 全流程跑通

---
