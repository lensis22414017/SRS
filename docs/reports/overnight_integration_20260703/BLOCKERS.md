# BLOCKERS — 一夜集成冲刺未完成项

> 诚实记录:本轮完成的 vs 未完成的,不伪造。

## ✅ 本轮已完成(ML 核心链路打穿)

| Step | 内容 | 状态 |
|---|---|---|
| 0 | 运行清单 | ✅ |
| 1 | 模型注册 model_registry_v0.8.json | ✅ 6 模型 |
| 2 | KOS 引擎 kos_engine_v0.8.py + selftest | ✅ |
| 3 | SHAP 三态清洗 shap_contribution_filter.py | ✅ 6 模型四分类 |
| 6 | 未知有机物三道防线 unknown_organic_guardrails.py | ✅ 南京32物质验证 |
| 7 | 后端 KOS 诊断 API (POST /kos-diagnosis + GET /registry) | ✅ |
| 8 | API smoke test | ✅ 6/7(场地0是空DB非缺陷) |
| 场地验证 | 云南个旧端到端 KOS 诊断 | ✅ As>Pb>Zn>Cu 物理合理 |

## ❌ 本轮未完成(BLOCKERS)

### BLOCKER-1: 前端页面接入(Step9)
- **现状**: ObstacleAnalysis.tsx 仍调旧 diagnosis API(二分类 SHAP),未调 kos-diagnosis
- **原因**: 涉及 4 个 TSX 页面重构(ObstacleAnalysis/SiteDetail/Reconstruction/Recommendation),工作量大
- **下一步**: 按 frontend_model_contract_v0.8.md 改前端调用
- **影响**: 后端 API 已就绪,前端改完即可闭环

### BLOCKER-2: 15+3 批量场地验证(Step4-5)
- **现状**: 只跑了云南个旧 1 个场地端到端验证(通过)
- **原因**: 系统空数据库,需先导入场地数据才能批量跑
- **下一步**: 导入演示数据集后批量跑 15 场地

### BLOCKER-3: 报告生成闭环(Step10)
- **现状**: 未生成 6 份报告样例
- **原因**: report_service 需改读 KOS 字段(当前读旧 importance)
- **下一步**: 改 report_service.collect() 的 diag_ctx

### BLOCKER-4: 全流程追溯验证(Step11)
- **现状**: 未跑 3 场地五阶段追溯
- **原因**: 需系统有完整场地+工作流数据
- **下一步**: 导入数据后跑

### BLOCKER-5: E2E 截图(Step13)
- **现状**: 无截图
- **原因**: 前端未接入 KOS,截图无意义
- **下一步**: 前端改完后跑 Playwright

## 判断
ML 核心链路(模型→KOS→API)已打穿,这是系统能用的地基。
前端接入是下一轮工作,后端 API 契约已就绪(frontend_model_contract_v0.8.md)。
不伪造截图、不伪造测试结果。
