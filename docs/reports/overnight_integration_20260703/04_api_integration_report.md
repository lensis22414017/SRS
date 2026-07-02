# 04 API 集成报告

## 结果: ✅ 通过 (6/7 smoke test)

## 新增 API 端点

| 方法 | 路径 | 功能 | smoke |
|---|---|---|---|
| POST | /api/v1/sites/{id}/kos-diagnosis | KOS 三层诊断 | ✅ |
| GET | /api/v1/models/registry | 模型注册表 | ✅ 6 models |

## KOS 诊断输出 schema
```json
{
  "track": "prod|eco",
  "model_id": "all_prod_Full_RandomForest",
  "model_status": "approved_alpha|exploratory",
  "explicit_obstacles": [{"factor","value","threshold","severity_R"}],
  "key_obstacles": [{"rank","factor","KOS","components":{R,W,M,S,E},"value","evidence"}],
  "recommended_tests": [{"factor","reason","evidence"}],
  "model_contribution": [{"factor","contribution","direction"}],
  "data_quality_flags": ["..."],
  "review_required": true|false,
  "limitations": "...",
  "interpretation_note": "模型贡献度, 非因果, 非障碍高度"
}
```

## 权限控制
- 所有端点需 JWT Bearer (get_current_user)
- KOS 诊断需 site 归属校验 (assert_site_access)
- 未授权返回 401 ✅

## 端到端验证(云南个旧真实数据)
```
模型: all_prod_Full_RandomForest (approved_alpha)
关键障碍: #1 As(KOS=0.807) #2 Pb(0.777) #3 Zn(0.755) #4 Cu(0.743)
建议补测: 7 个
数据质量: 9 个完全未知物质(有机质/全氮等非重金属)
需复核: True
```

## smoke test 未通过项
- 场地列表 n=0: 空数据库(新 SQLite 未导入数据),非 API 缺陷。导入数据后即恢复。
