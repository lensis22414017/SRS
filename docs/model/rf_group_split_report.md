# RF 分组切分重训报告

> 本报告用于暴露行级随机切分虚高风险。真实泛化能力以 DOI/Source group split 为准。

- 数据源: `data/model_ready/model_ready_hm.csv`
- 样本数: 29993
- 特征数: 16
- 行级随机 ROC-AUC: 0.9999
- AUC 差值(row - group mean): -0.0001

## 分组切分指标

| 分组键 | ROC-AUC | Balanced Acc | Macro-F1 | 测试样本 | 泄漏检查 |
|---|---:|---:|---:|---:|---|
| id_DOI | 1.0 | 0.9995 | 0.9994 | 6913 | PASS |
| id_Source | 1.0 | 0.9995 | 0.9995 | 5926 | PASS |

## 解释口径

阈值派生标签只用于训练切分和泄漏诊断, 不能替代人工复核或独立实测验证。
若行级随机指标显著高于 group split, 应按虚高风险处理, 不作为主性能证据。
若 row-random 与 group split 均接近 1, 也不能视作模型已可靠; 这通常说明标签由同一批污染物阈值派生, 与特征存在规则绑定。
