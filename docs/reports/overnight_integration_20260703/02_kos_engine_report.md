# 02 KOS 引擎报告

## 结果: ✅ 通过

## 实现文件
- 引擎: `ml/ranking/kos_engine_v0.8.py`
- 服务: `backend/app/services/kos_service.py`
- 防线: `ml/rules/unknown_organic_guardrails.py`
- 清洗: `ml/explain/shap_contribution_filter.py`

## 公式
```
KOS_i,t = B_i,t × (0.30×R + 0.25×W + 0.15×M + 0.20×S + 0.10×E)
```

## 强制规则(全部实现)
1. ✅ 只有 B=1 进正式 Top-N
2. ✅ 只有实测因子进正式排名
3. ✅ GEE/proxy 不作正式障碍
4. ✅ x_missing_* 不进 Top-N(三态清洗分流)
5. ✅ family 进 extended(标 supplementary)
6. ✅ 未测因子进 recommended_tests
7. ✅ OP 模型带 exploratory/review_required
8. ✅ SHAP 统一称"模型贡献度"

## selftest 结果
- KOS 引擎自测: ✅ (Cd KOS=0.638 正确排名)
- 云南个旧端到端: ✅ As(0.807)>Pb(0.777)>Zn(0.755)>Cu(0.743) 物理合理

## 未知有机物三道防线(南京栖霞 32 物质)
- 防线1 正式排名: 8 个(已知有阈值)
- 防线2 族群预警: 19 个(萜烯/烷烃/酮酯无国标)
- 防线3 TEF 降级: 2 个(PAH BaP 当量)
- 完全未知: 5 个(送检鉴定)
