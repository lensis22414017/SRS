# 半合成数据(蒙特卡洛)生成协议 v0.1

> 状态: 协议(阶段1)。**本阶段不生成任何模拟数据**，仅锁定规则。
> 红线: 模拟数据只用于训练增强/压力测试/演示，**永不进入任何 real 验证集**；所有模拟值带 `is_synthetic=true`、`evidence_level=SIMULATED`、`generation_rule_version`、`simulation_batch_id`。

## 1. 用途边界
| 允许 | 禁止 |
|---|---|
| 训练增强 `synthetic_train_augmented` | 进入 `valid_real_*` / `test_real_*` |
| 压力测试 `synthetic_stress_extreme` | 作为真实泛化性能证据 |
| 报告演示 `report_demo_sites`（显式水印） | 把未测污染物当 0 |
| 50 场地基准 `synthetic_scenario_benchmark_50sites` | 全字段补满 719 列 |

## 2. 分层
按 `Region × Pollution_Type × LandUse × Industry_Source` 分层估计，保持真实场景结构。Region 由 Province 映射 9 大区；Pollution_Type 用 merged 的 HM/OP/HM+OP/PAH/OCP 等真实取值。

## 3. 浓度分布估计
- 重金属/有机物浓度多为右偏，优先 **log-normal**；厚尾用 **gamma** 或 **mixture**；样本足够时用**经验 bootstrap**直接重采样真实值，避免分布假设偏差。
- 分布参数**仅从对应分层的真实子集**估计，记录 `source_dataset_id` 与样本量；样本量 < 30 的分层标记 `low_confidence`，不外推。

## 4. 相关结构保持
- 重金属族 Cd-Pb-Zn-Cu-As-Ni-Cr-Hg、有机族 PAH/OCP/PCB/PFAS/TPH 的**共现相关**用 **Spearman 秩相关 + Gaussian copula** 或 **block bootstrap**（按 DOI 整块重采样）保持，避免破坏元素间地球化学关联。

## 5. 缺失机制
- **按真实缺失率生成 missing mask**（见 `missingness_profile.csv` 的分层缺失率），单篇文献只测部分污染物的稀疏结构必须保留。
- **绝不把未测污染物填 0 或补满**；缺失即缺失，下游建模用中位数填充 + `*_missing` 标记列。

## 6. 标签控制
- 风险等级标签用**标准阈值服务**（GB 15618/36600 + pH 分段）从模拟浓度判定，控制各等级比例接近真实分布；
- 避免单污染物直接决定标签造成的标签泄漏（与防泄漏清单一致）。

## 7. 溯源与水印
每个模拟批次写入 `synthetic_generation_batches`（rule_version、random_seed、输入真实数据版本 sha256、分层定义）。报告中所有模拟图件显式标注「模拟数据 / SIMULATED」水印。

## 8. 验收
模拟产物必须能证明: ①未测污染物未当 0; ②未全字段补满; ③相关结构与真实子集 Spearman 偏差在阈内; ④模拟指标与真实泛化指标**分开报告**。
