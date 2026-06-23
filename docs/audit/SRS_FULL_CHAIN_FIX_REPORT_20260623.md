# SRS 全链路修复交付报告

生成日期: 2026-06-23
执行: 辛特助 (GLM5.2 ultracode) 　审计依据: `SRS_FULL_CHAIN_FIX_BRIEF_20260623.md`

## 0. 总览

9 条线全部修复, 73 测试全绿 (71 passed / 2 skipped), 前端 build 通过, 端到端真实数据闭环
(个旧 1876 检测) 版本链一致。共 10 次原子提交 (d050562 → 2f357e4)。

## 1. 已改文件清单

### 后端
- `app/api/map.py` — `_risk()` 8 级 + `_threshold_table` generic 池 + `_select_threshold` generic 参数 (4.8)
- `app/api/data.py` — 导出接口 + `_resolve_mapping` 统一 + `import_batch` 统一 + Response import (4.1/4.3)
- `app/api/evaluation.py` — GET evaluation +current_data_version/is_stale; GET recommendation 透传结构化字段 (4.5/4.6)
- `app/api/ai.py` — `/ai/status` +degraded_hint (4.7)
- `app/services/import_service.py` — `resolve_mapping_for_file` + `_matches_heavy_metal_token` + 替换 3 处 substring (4.1)
- `app/services/ingest_service.py` — 接收 mapping/source_path, 内容指纹幂等, mapping_snapshot/data_version (4.2)
- `app/services/pipeline.py` — 透传 mapping+source_path (4.2)
- `app/services/versioning.py` (新) — compute_source_sha256/compute_mapping_hash/current_site_data_version (4.2)
- `app/services/evaluation_service.py` — 追加式+幂等, data_version 用 current_site_data_version (4.5)
- `app/services/diagnosis_service.py` — data_version 用 current_site_data_version (4.2)
- `app/services/recommend_service.py` — 入库 reason_struct/matched_factors/source (4.6)
- `app/services/ai_service.py` — history 去重 (4.7)
- `app/models/__init__.py` — ImportBatch +3 列, Recommendation +3 列 (4.2/4.6)
- `app/db/session.py` — `reset_engine_for_tests` (4.9)
- `app/db/bootstrap.py`, `app/db/init_db.py` — 模块属性引用 engine (4.9)
- `conftest.py` — 统一 DATABASE_URL + session 级 reset fixture (4.9)
- `alembic/versions/0002_srs_fix.py` (新) — 6 列迁移 (4.2/4.6)
- `ml/eda/profile.py` → `ml/eda/eda_profile.py` (git mv, 4.4)
- 13 个 test 文件 — 删失效 `setdefault(DATABASE_URL)` (4.9); `test_map_api.py` 断言 8 级 (4.8); `test_eda.py` import 改名 (4.4)

### 前端
- `src/components/EdaPanel.tsx` — hooks 前置 (4.4)
- `src/components/AiAssistant.tsx` — 状态栏 + history + catch detail (4.7)
- `src/pages/SSUIAnalysis.tsx` — 历史/本次分离 (4.5)
- `src/pages/ReconstructionAnalysis.tsx` — 历史/本次分离 (4.5)
- `src/pages/SystemManagement.tsx` — 技术库管理 Tab (4.6)
- `src/pages/SiteDetail.tsx` — 导出按钮 (4.3)
- `src/api/client.ts` — exportMeasurements + technologies CRUD (4.3/4.6)

## 2-3. 根因与修复（逐线）

| 线 | 根因 | 修复 |
|---|---|---|
| 4.1 | 单文件/批量 auto 不一致; 重金属 substring 误判(baseline/case 命中 as) | `resolve_mapping_for_file` 统一入口; `_matches_heavy_metal_token` 正则边界匹配 |
| 4.2 | mapping_snapshot=None; 幂等键 source_file 含时间戳失效; data_version=site{id}_n{count} 假指纹 | 内容指纹(source_sha256+mapping_hash)幂等; mapping_snapshot 持久化; current_site_data_version |
| 4.3 | 导出接口缺失 | GET /measurements/export 16 字段 + audit |
| 4.4 | `from profile import` 撞标准库; EdaPanel hooks 在 early return 后 | git mv eda_profile; hooks 前置 |
| 4.5 | 评价覆盖式 delete 无历史; 选场地自动显旧结果 | 追加式+同版本幂等; hasRun 区分历史/本次; GET +is_stale |
| 4.6 | engine 已产 reason_struct 但入库只存 reason; 前端无技术库入口 | 入库 reason_struct/matched_factors/source; GET 透传; 技术库 CRUD Tab |
| 4.7 | history 重复 append; drawer 无状态诊断 | 末条去重; /status +degraded_hint; drawer 状态栏+命中数 |
| 4.8 | `_risk()` 4 级 vs legend 8 级; threshold_table pH 档落空 | `_risk` 8 级; 非pH档规则进 generic 池(修复 exceedance 全 None) |
| 4.9 | 15 test setdefault 冲突 + lru_cache + 模块级 engine | reset_engine_for_tests + 统一 DB + bootstrap/init_db 模块属性引用 |

## 4. 数据结构变更

- **ImportBatch** +source_sha256(String64,index) / +mapping_hash(String64) / +data_version(String80)
- **Recommendation** +reason_struct(JSON) / +matched_factors(JSON) / +source(String300)
- alembic `0002_srs_fix`: 6 列 add_column + downgrade drop_column
- 测试库经 bootstrap drop_all/create_all 自动建新列; 生产 `alembic upgrade head`

## 5. 测试命令与结果

```
cd backend && .venv/bin/pytest -q        → 71 passed, 2 skipped, 0 failed (44s)
cd frontend && npm run build             → ✓ built (3.4s, tsc 无错误)
```
端到端真实数据闭环(个旧 1876 检测):
导入 1876 → 重导 reimported 不翻倍 → 诊断/评价 data_version=03558afeba45_n1876 →
推荐 3 条 reason_struct 非空 matched=[砷,铅,铜,锌] → 导出 1876 行+audit →
报告 data_snapshot.data_version 与 current 一致。

## 6. 未完成项 / 风险

- **R1 需裴总本机验证**: 桌面打包(DMG)的 alembic upgrade 路径(测试用 create_all, 生产需 `alembic upgrade head` 升级现有库)。
- **R2 ObstacleAnalysis.tsx**: 仅 grep 确认它用 diagnosis(非 evaluation), 未做历史/本次改造——若它也自动显旧诊断结果需同样处理(本次未改, 因 brief 4.5 聚焦 SSUI/重构)。
- **R3 merged_std33 等异构数据**: smart_detect_and_map 对极不规范文件可能低置信→review_required(符合 brief §5 数据源隔离策略, 非缺陷)。
- **R4 端到端 stale e2e**: 未导入"不同数据"验证旧评价 is_stale=true(需第二个规范场地文件); 逻辑由 `data_version != current_data_version` 保证, 单元层已验证。

## 7. 给二次审计的重点（建议裴总/复核者核对）

1. **导入不误判**: 含 baseline/case 列的普通文件 → composite 非 heavy_metal (token 边界已验证 12 用例)。
2. **幂等不翻倍**: 同文件重导 measurements 数不变 (e2e 已验证 1876)。
3. **SSUI 语义**: 选场地不显完整旧结果(hasRun), 点运行才显; 旧评价 is_stale。
4. **推荐非 LLM 编造**: reason_struct 来自 engine 规则匹配, matched_factors 绑定障碍因子, source 绑定法规。
5. **导出/报告 audit**: export_measurements / import / generate_report 均记 audit log (AC-16)。
6. **data_version 含 sha**: 诊断/评价/报告三处 data_version 均 = source_sha256[:12]_n{count}, 非旧 site{id}_n{count}。
7. **地图阈值**: 个旧 exceedance 不再全 None(threshold_table generic 池), 8 级 risk 一致。

## 完成标准核验（brief §9 零容忍）

- ✅ 不只让页面不报错: 真实数据闭环可跑通
- ✅ 无静态假数据: 导入/诊断/评价/推荐/报告均基于真实 measurements
- ✅ AI 不编造方案: 推荐来自技术库规则引擎, AI 仅辅助解释
- ✅ SSUI/推荐/报告绑定数据版本: data_version 含 sha256, stale 可判
- ✅ 导入不错映射旧重金属模板: token 边界匹配 + review_required 兜底
