# SHAP 三态清洗汇总

| 模型 | measured | family | missing | proxy | measured Top-3 |
|---|---|---|---|---|---|
| all_eco_Full_RandomForest | 36 | 5 | 55 | 14 | ['Cd_mgkg', 'As_mgkg', 'Zn_mgkg'] |
| all_prod_Full_RandomForest | 36 | 5 | 55 | 14 | ['Cd_mgkg', 'As_mgkg', 'Zn_mgkg'] |
| hm_eco_Full_RandomForest | 36 | 5 | 55 | 14 | ['Cu_mgkg', 'Pb_mgkg', 'Cd_mgkg'] |
| hm_prod_Full_RandomForest | 36 | 5 | 55 | 14 | ['Cu_mgkg', 'Pb_mgkg', 'Zn_mgkg'] |
| op_eco_Full_RandomForest | 36 | 5 | 55 | 14 | ['二苯并[a,h]蒽', 'As_mgkg', 'BaP_ngg'] |
| op_prod_Full_RandomForest | 36 | 5 | 55 | 14 | ['As_mgkg', 'BaP_ngg', '苯并[k]荧蒽'] |

**规则**:前端关键障碍只读 measured + family;missing/proxy 只进数据质量提示,不进障碍排名。