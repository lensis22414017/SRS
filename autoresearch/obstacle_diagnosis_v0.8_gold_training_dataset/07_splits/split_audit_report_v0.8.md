# Split Audit Report v0.8

> 由 seal_pack_repair_v0.8.py 生成。
> **诚实声明:本 split 为 source-level GroupKFold,非 site-level。**

## 关键事实
- site_id nunique ≈ 行数(逐样本唯一),**不构成真正场地组**,不能声称 site-level 泛化验证。
- source_id nunique=1158,是真实可用的分组键,train/valid/test 之间 source_id 不交叉(见下)。
- region/province:province 有 652 类,粒度过细;region 列原始数据缺失。本版 region holdout 标注 skipped。

## 各子集 source 交集检查(应为 0)
- all: rows=27031, site_id_unique=27031(≈sample-level), source_id_unique=1158, source 交集 train∩valid=0 train∩test=0 valid∩test=0
- hm: rows=20630, site_id_unique=20630(≈sample-level), source_id_unique=869, source 交集 train∩valid=0 train∩test=0 valid∩test=0
- op: rows=4126, site_id_unique=4126(≈sample-level), source_id_unique=164, source 交集 train∩valid=0 train∩test=0 valid∩test=0
- hm_op: rows=408, site_id_unique=408(≈sample-level), source_id_unique=73, source 交集 train∩valid=0 train∩test=0 valid∩test=0

## 结论
- split_strategy = source_level_groupkfold
- site_level_generalization = NOT_VALIDATED (site_id 粒度 ≈ sample-level)
- 可作为 source 级泛化的基础验证,不可包装为场地级泛化结论。
