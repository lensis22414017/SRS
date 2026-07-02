# Training Protocol v0.8

> Gold Dataset 封包后训练协议。本文件定义 P3 模型训练的边界与评估方式。

## 1. 主任务
**回归任务**:X → OI_prod_formal / OI_eco_formal
- 输入:04_feature_tables 的 108 个 x_* 特征(含污染物浓度,SHAP 不删浓度)
- 目标:05_target_tables 的 OI_prod_formal / OI_eco_formal(连续值,范围[0,1])
- 辅助任务:has_obstacle_*(二分类),仅作辅助,不作主指标

## 2. 目标分布与建模策略
- OI_prod_formal zero_rate ≈ 59.8%(非零 10862)
- OI_eco_formal  zero_rate ≈ 60.9%
- **非零膨胀(< 80%)→ 默认单阶段回归**;若后续发现尾部拟合差,启用 two-stage/hurdle:
  - Stage A:has_obstacle 二分类(是否存在障碍)
  - Stage B:非零样本障碍强度回归
  - Final:两阶段联合报告,不丢弃全样本回归结果

## 3. 模型候选
- RandomForestRegressor
- ExtraTreesRegressor
- HistGradientBoostingRegressor
- 主模型用于 SHAP 解释;子集模型仅在样本充足时训练

## 4. 交叉验证
- **GroupKFold**(group=source_id,严禁随机划分)
- 外层 5 折,内层 3 折超参调优(嵌套 CV)
- region holdout:province=652 类过多,本版不强制,标注为 skipped

## 5. SHAP 解释(模型贡献度 M)
- 全特征 SHAP,**不删除污染物浓度**
- SHAP 称"模型贡献度",不写"障碍高度"/"因果"
- 因子组聚合后输出正向贡献排名

## 6. 子集可训练性判定(由 P0-5 自动生成)
- all: ready=True, train_n=16218, source_groups=696
- hm: ready=True, train_n=12378, source_groups=523
- op: ready=True, train_n=2289, source_groups=128
- hm_op: ready=False, train_n=0, source_groups=0, 原因=X_train 不存在

## 7. 消融实验
- Full:全 108 特征
- MeasuredOnly:仅 x_measured_*
- ContextOnly:仅 x_proxy_gee_* + x_covariate_*
- 目的:分离浓度贡献与背景贡献,验证 M-R 共线性处理

## 8. 评估指标(metrics_config_v0.8.yaml)
- 主指标:Spearman ρ / MAE / R²(回归)
- **不报 AUC/Accuracy 作为主指标**(本任务为回归)
- 分组稳定性:跨 source 组的指标方差
- bootstrap 1000 次置信区间

## 9. 禁止
- 禁止把 OI/has_obstacle/threshold 等目标派生字段放入 X(见 feature_leakage_audit)
- 禁止随机划分
- 禁止在 SHAP 删除污染物浓度
