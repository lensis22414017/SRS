# V2 新增可信 SI 样本建模就绪度

结论：176个新增可信样本可用于外部覆盖与污染物分布验证，但不能诚实地直接并入当前生产/生态双轨监督训练；两类数据都缺少 `OI_prod_formal` 和 `OI_eco_formal` 训练标签，且与既有模型特征空间的逐行覆盖有限。

| subset   | source_id                          |   rows |   model_feature_count |   overlap_feature_count |   mean_row_feature_coverage |   min_row_feature_coverage | has_prod_and_eco_targets   | training_decision           |
|:---------|:-----------------------------------|-------:|----------------------:|------------------------:|----------------------------:|---------------------------:|:---------------------------|:----------------------------|
| op       | PFAS_SURFACE_SOILS_CHINA_SI_TABLE2 |    124 |                   110 |                       4 |                      0      |                     0      | False                      | holdout_external_validation |
| op       | coal_mining_east_china_pah_si      |     27 |                   110 |                       4 |                      0.0091 |                     0.0091 | False                      | holdout_external_validation |
| hm_op    | industrial_sites_hm_pah_si         |      5 |                   110 |                      11 |                      0.0727 |                     0.0727 | False                      | holdout_external_validation |

处置：保留在 canonical V2 原始训练资产中并标记来源；本轮模型选择仍使用 v0.8 gold model-ready 数据，新增样本作为外部验证/后续协变量补齐池，不虚构标签、不用论文均值替代样点标签。