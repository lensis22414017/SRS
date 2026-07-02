# 00 运行清单 (Run Manifest)

> 生成时间: 2026-07-03 00:xx

## 环境基线
1. **commit hash**: `59ff61d682fd2ed59e23b93c8348448316cb3585`
2. **分支**: `main`
3. **Python**: 3.13.5 (系统,非 venv)
4. **Node**: v24.11.1
5. **后端启动命令**: `cd backend && uvicorn app.main:app --reload --port 8000`
6. **前端启动命令**: `cd frontend && npm run dev`
7. **数据库**: SQLite (`backend/srs.db`,测试用 `srs_test_session.db`)
8. **模型包位置**: `ml/artifacts/p3_alpha/` (39 文件,10 joblib + SHAP + metrics)
9. **P3-Alpha 模型文件数**: 10 个 joblib + 10 metrics + 12 SHAP + 6 meta + 1 summary
10. **15+3 验证数据来源**: 系统已有样例场地(从 DB 选取)+ 甲方 3 实测(桌面 000/数据集/3.实际样本集/)
11. **数据版本**: Gold Dataset v0.8 (READY_FOR_P3.flag 已生成)

## 本轮脚本入口
- `scripts/build_model_registry.py` — 模型注册
- `scripts/run_kos_engine.py` — KOS 引擎 + selftest
- `scripts/run_shap_filter.py` — SHAP 三态清洗
- `scripts/run_15plus3_validation.py` — 场地验证

## 本轮输出目录
- `ml/artifacts/p3_alpha/model_registry_v0.8.json` — 模型注册表
- `ml/ranking/kos_engine_v0.8.py` — KOS 引擎
- `ml/explain/shap_contribution_filter.py` — SHAP 清洗
- `artifacts/overnight_20260703/` — 全部机器可读结果
- `docs/reports/overnight_integration_20260703/` — 全部报告
- `docs/audit/screenshots_20260703/` — E2E 截图
