# 防泄漏切分清单 v0.1

> 目标: 让模型性能成为**跨 DOI/来源/区域的泛化证据**，而非记忆。当前 AUC 0.9991 来自行级随机切分，视为**虚高风险信号**，必须用本清单纠正。

## 1. 切分顺序(强制)
**先切分、后插补/扩增。** 任何插补、归一化、蒙特卡洛扩增都只能在 `train` 内 fit，再 transform 到 valid/test，杜绝信息回流。
```
原始真实数据 → 锁定 split → (仅在train内) 插补/扩增 → 训练 → 在未污染的 valid/test 评估
```

## 2. 主验证切分(禁止行级随机)
| split | 策略 | 用途 |
|---|---|---|
| `train_real` | 分组训练集 | 训练 |
| `valid_real_group_split` | **DOI group split** | 调参/早停 |
| `test_real_group_split` | **Source group split** | 主泛化指标 |
| `external_literature_holdout` | 整批留出的文献来源 | 跨来源外推 |
附加尝试: **Region holdout**、**Pollution_Type holdout** 评估跨区域/跨污染类型迁移。

## 3. 泄漏检查项(每次切分必查)
1. **DOI 不跨集**: 同一 DOI 的样本不得同时出现在 train 与 valid/test。
2. **Source 不跨集**: 同一 Source 同理。
3. **site_id/SampleID 不跨集**: 同场地同点位不跨集。
4. **synthetic 不入 real 验证**: `is_synthetic=true` 行禁止进入任何 `*_real_*` 集。
5. **标签泄漏**: 风险标签若由单污染物阈值直接决定，该污染物不得既当特征又当标签来源——改用多指标阈值服务判定。
6. **预处理泄漏**: 插补中位数、归一化 min/max、特征选择统计量只能来自 train。
7. **时间泄漏(如适用)**: 用 SamplingYear 做时间留出时，未来年份不得进 train。

## 4. 报告口径
- real 指标与 synthetic-augmented 指标**分开列**;
- 必报 domain shift score、跨组指标差(行级随机 vs 分组切分的 AUC 差值)以暴露记忆程度;
- 对照四套: real-only / real+missing-indicator / real+synthetic / real+synthetic+uncertainty。

## 5. 自动化校验(后续实现)
`dataset_split_registry` 记录每个 split 的 grouping_strategy 与 `leakage_check_result`(7 项逐条 pass/fail);CI 中任一 fail 即阻断训练。
