# 01 模型注册检查

## 结果: ✅ 通过

生成文件: `ml/artifacts/p3_alpha/model_registry_v0.8.json`

## 注册的 6 个模型

| model_id | status | frontend_enabled | spearman | recommended_use |
|---|---|---|---|---|
| all_prod_Full_RandomForest | approved_alpha | true | 0.9616 | 通用生产用途诊断 |
| all_eco_Full_RandomForest | approved_alpha | true | 0.9651 | 通用生态用途诊断 |
| hm_prod_Full_RandomForest | approved_alpha | true | 0.9680 | 重金属生产场景 |
| hm_eco_Full_RandomForest | approved_alpha | true | 0.9582 | 重金属生态场景 |
| op_prod_Full_RandomForest | exploratory | false | 0.7695 | 仅探索参考 |
| op_eco_Full_RandomForest | exploratory | false | 0.6616 | 仅探索参考 |

API 端点: `GET /api/v1/models/registry` (smoke test ✅ 200)
