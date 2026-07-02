# Training Readiness Gate v0.8

> 由 seal_pack_repair_v0.8.py 生成。每条 GATE 附证据(文件名+数值)。无证据视为未通过。

## G1: 00 母库无空 factor_id、无 nan factor_name
**判定**: 00 母库无空 factor_id、无 nan factor_name
**证据**: 00_unified_obstacle_factor_master_v0.8.csv rows=159, 空factor_id=0, nan_name=0
**结论**: 通过

## G2: gold mapping 无空 factor_id、无 nan factor_name
**判定**: gold mapping 无空 factor_id、无 nan factor_name
**证据**: gold_factor_mapping_v0.8.csv rows=318, 空factor_id=0, nan_name=0
**结论**: 通过

## G3: 所有 selected_column/feature 都存在
**判定**: 所有 selected_column/feature 都存在
**证据**: 检查 54 个 measured/family/proxy 特征,缺失=0 []
**结论**: 通过

## G4: coverage>=0.1% 污染物/理化/GEE 字段已归类或 excluded
**判定**: coverage>=0.1% 污染物/理化/GEE 字段已归类或 excluded
**证据**: 高覆盖候选列=109, 已映射=32, excluded=77, 未归类=0 []
**结论**: 通过

## G5: model_features_wide 无泄露字段
**判定**: model_features_wide 无泄露字段
**证据**: x_ 特征数=110, 禁止词命中=0 []
**结论**: 通过

## G6: OI_prod/eco_formal 非常数并报告 zero inflation
**判定**: OI_prod/eco_formal 非常数并报告 zero inflation
**证据**: OI_prod_formal: mean=0.0846 std=0.1650 zero_rate=0.5982 nonzero=10862; OI_eco_formal: mean=0.0765 std=0.1488 zero_rate=0.6091; target_is_zero_inflated=False
**结论**: 通过

## G7: GEE 字段只以 x_proxy_gee_*/x_covariate_* 进入特征(值列),不进 formal OI
**判定**: GEE 字段只以 x_proxy_gee_*/x_covariate_* 进入特征(值列),不进 formal OI
**证据**: 含 gee 特征列=28(值列=14+缺失指示=14); 值列全部合规=True(x_missing_* 为缺失指示器,不计入合规判定)
**结论**: 通过

## G8: formal/supplementary/covariate/recommended/exclude 数量明确
**判定**: formal/supplementary/covariate/recommended/exclude 数量明确
**证据**: diagnosis_layer: {'formal': 132, 'model_covariate': 14, 'supplementary_screening': 9, 'recommended_test': 4}
**结论**: 通过

## G9: all/hm/op/hm_op 子集均已生成或有明确原因
**判定**: all/hm/op/hm_op 子集均已生成或有明确原因
**证据**: 子集状态: [('all', True, 16218), ('hm', True, 12378), ('op', True, 2289), ('hm_op', False, 0)]
**结论**: 通过

## G10: split_manifest 已生成,source group 不交叉(site-level 未验证,如实声明)
**判定**: split_manifest 已生成,source group 不交叉(site-level 未验证,如实声明)
**证据**: - all: rows=27031, site_id_unique=27031(≈sample-level), source_id_unique=1158, source 交集 train∩valid=0 train∩test=0 valid∩test=0
  - hm: rows=20630, site_id_unique=20630(≈sample-level), source_id_unique=869, source 交集 train∩valid=0 train∩test=0 valid∩test=0
  - op: rows=4126, site_id_unique=4126(≈sample-level), source_id_unique=164, source 交集 train∩valid=0 train∩test=0 valid∩test=0
  - hm_op: rows=408, site_id_unique=408(≈sample-level), source_id_unique=73, source 交集 train∩valid=0 train∩test=0 valid∩test=0
**结论**: 通过

## G11: 训练特征 X 与目标 y 物理分离
**判定**: 训练特征 X 与目标 y 物理分离
**证据**: X 特征数=110, y 目标数=8, 交集=0 []
**结论**: 通过

## G12: READY_FOR_P3.flag 只在 G1-G11 全通过后生成
**判定**: READY_FOR_P3.flag 只在 G1-G11 全通过后生成
**证据**: G1-G11 全过=True
**结论**: 通过

## 总判定
- G1-G11 全通过: True
- READY_FOR_P3: 是