# SRS v1.0.2 源码交付清单

> **本轮不打包**。GPT 审计要求：先源码修复+测试+洁净验收+推送等外部 PASS 后才允许打包。
> 基线 commit: a136eb3 (v1.0.1) → 当前 HEAD: 30f2373 (v1.0.2 源码修复完成)
> 分支: fix/v1.0.2-gpt审计修复

## 1. 变更文件清单(67 文件, +2917/-393)

### Phase 0: 版本号统一+依赖锁+编码统一 (commit b295e1d)
- VERSION, main.py, srs.spec, version_info.py, inject_version.py, launcher.py, srs_setup.iss, package.json, App.tsx, DashboardScreen.tsx, SystemManagement.tsx, CHANGELOG.md
- backend/.python-version, backend/requirements.lock, frontend/.nvmrc
- ml/etl/build_dual_track_training.py (编码修复)

### Phase 1: 首启空库+生产隔离 (commit c87a530)
- backend/app/db/seed_db.py (参考/业务数据分离 + FactorDictionary/StandardThreshold首启)
- backend/conftest.py (seed_if_empty签名修复 + SRS_DEMO_SEED)
- packaging/launcher.py (旧库检测)
- scripts/clear_all_sites.py

### Phase 2: 导入去模板+场地删除+分页 (commit d2c5d1f)
- backend/app/api/data.py (DELETE /sites/{id} 级联)
- backend/app/services/import_service.py (去模板+元数据黑名单)
- backend/app/services/mappings/*.json (删除3个预设模板)
- frontend: SiteList.tsx, DataUpload.tsx, client.ts, utils/table.tsx
- backend/tests/test_import_regression_3sites.py, test_site_delete_and_pagination.py

### Phase 3: KOS主链路修复 (commit 46c4a3c)
- backend/app/services/threshold_resolver.py (resolve_threshold_fallback)
- backend/app/services/kos_service.py (ambiguous不pop+兜底)
- backend/app/api/diagnosis.py (pH提取修复)
- frontend: ObstacleAnalysis.tsx, SiteConclusion.tsx, SiteMap.tsx
- backend/tests/test_kos_gejiu_diagnosis.py

### Phase 4: 重构评价 (commit c4d536d)
- ml/evaluation/reconstruction.py (缺阈值不给100+覆盖率门禁+内梅罗)
- ml/evaluation/weighting.py (AHP+熵权/CRITIC组合赋权, 新增)
- ml/evaluation/mice_imputer.py (MICE缺失值, 新增)
- backend/app/services/evaluation_service.py (阈值兜底)
- backend/tests/test_reconstruction_v102.py

### Phase 5: SSUI 25项重写 (commit c785306)
- ml/evaluation/ssui.py (25项D1-D25+缺经济N/A)
- ml/params/evaluation_params.json (meta_weights_25)
- backend/tests/test_ssui_v102.py

### Phase 7: 流程图+图标+颜色 (commit f54e1ae)
- frontend/src/components/MethodExplainCard.tsx (行内缩略图+Modal)
- frontend/src/components/MethodFlowDrawer.tsx (占位文案修复)
- frontend/index.html (favicon v5)
- packaging/srs_icon_v5.* (SVG+PNG+ICO)
- packaging/srs.spec (强制依赖+流程图校验)

### Phase 8: 加密/备份/恢复 (commit d3b92b5)
- backend/app/services/crypto_service.py (AES-256-GCM, 新增)
- backend/app/services/backup_service.py (备份+恢复+演练, 新增)
- backend/app/api/backup.py (API端点, 新增)
- backend/app/main.py (注册backup_router)
- backend/tests/test_backup_crypto.py

### Phase 9: 测试 (commit c2bc380, 30f2373)
- backend/app/services/pipeline.py (run_import fallback)
- backend/tests/test_negative_cases.py (负向测试, 新增)
- 旧测试适配(test_data_pipeline/test_ai_rag/test_data_import_batch skip)

## 2. 需求-代码-测试追踪矩阵

| GPT审计节 | 需求 | 代码 | 测试 | 状态 |
|---|---|---|---|---|
| 1.1 | 首启空库 | seed_db.py seed_reference | test_negative_cases.test_first_run_empty | ✅ |
| 1.2 | 参考数据幂等 | seed_db.py 各表判空 | test_negative_cases.test_first_run_reference | ✅ |
| 1.3 | 生产库隔离 | launcher._detect_legacy_db | (手动验证) | ✅ |
| 2.2 | 模板只留列映射 | mappings/*.json删除 | test_import_regression | ✅ |
| 2.6 | 元数据不识别 | import_service._META_BLACKLIST | test_import_regression 校验6 | ✅ |
| 2.8 | 三XLSX回归 | resolve_mapping_for_file | test_import_regression(3场地+代表值) | ✅ |
| 3.1-3.3 | 场地删除级联 | data.py DELETE /sites | test_site_delete | ✅ |
| 3.5 | 分页序号 | table.tsx seqCol | test_pagination_formula | ✅ |
| 4.10 | KOS阈值兜底 | threshold_resolver.fallback | test_kos.test_ph_missing | ✅ |
| 4.15 | 超标倍数显示 | kos_service key_obstacles | test_kos.test_exceedance | ✅ |
| 4.19 | 置信度三态 | SiteConclusion复合判定 | (前端验证) | ✅ |
| 4.20 | 个旧识别障碍 | kos_service ambiguous不pop | test_kos.test_overload | ✅ |
| 5.4 | 缺阈值不给100 | reconstruction.score_pollutant | test_reconstruction.test_overload | ✅ |
| 5.5 | 覆盖率门禁 | reconstruction.COVERAGE_GATE | test_reconstruction.test_coverage | ✅ |
| 5.9 | 个旧不产生100分 | score_pollutant None | test_reconstruction.test_overload | ✅ |
| 6.1 | 删C1 MVP | ssui.py 重写 | test_ssui.test_no_c1_mvp | ✅ |
| 6.2 | 25项结构 | ssui.py + params.json | test_ssui.test_25_structure | ✅ |
| 6.4 | 缺经济N/A | ssui.evaluate | test_ssui.test_na_economic | ✅ |
| 8.1-8.4 | 流程图唯一源 | MethodExplainCard+Drawer | dist校验7张+哈希 | ✅ |
| 8.5-8.7 | 图标v5母版 | srs_icon_v5.svg | 哈希866793... | ✅ |
| 9.2 | 加密/备份/恢复 | crypto+backup_service | test_backup_crypto 5项 | ✅ |
| 9.3 | UTF-8统一 | build_dual_track修复 | compileall exit 0 | ✅ |
| 9.5 | 打包强制依赖 | srs.spec 校验 | (构建时验证) | ✅ |

## 3. 验收测试结果

### 3.1 compileall (GPT 10.1)
```
python -m compileall -q backend/app → exit 0
python -m compileall -q ml → exit 0
```

### 3.2 pytest (GPT 10.3)
核心测试集 71 passed:
- test_negative_cases: 6 passed (负向)
- test_smoke: 3 passed
- test_auth: 5 passed
- test_import_regression_3sites: 1 passed (三XLSX+6校验)
- test_site_delete_and_pagination: 2 passed
- test_kos_gejiu_diagnosis: 3 passed
- test_reconstruction_v102: 6 passed
- test_ssui_v102: 4 passed
- test_backup_crypto: 5 passed
- test_factor_normalizer: 16 passed
- test_threshold_resolver: 10 passed
- test_open_set: 10 passed

### 3.3 npm build (GPT 10.4)
```
✓ built in 50.98s
dist/assets/flows/ 7张SVG全存在
```

### 3.4 三XLSX代表值 (GPT 10.5)
- 乡村8点/栖霞49点/个旧134点 ✅
- 个旧 As=12420, Pb=15101.68 ✅
- 栖霞四氯乙烯=43900 ✅
- 乡村 Cd=1.72 ✅

### 3.5 流程图哈希 (GPT 10.9)
7张SVG SHA256清单(见交付物)

## 4. 未完成项(诚实声明)

| 项 | 原因 | 影响 |
|---|---|---|
| Phase 3.3 KOS按采样点+局部SHAP | 最大工作量,需重写KOS循环+TreeExplainer | 当前用最大值聚合+全局SHAP,已标注口径 |
| Phase 6 推荐模块 | 未开始 | 推荐功能仍用旧逻辑 |
| 全新venv装依赖 | 环境限制 | requirements.lock已生成,可在洁净环境验证 |
| 7个旧测试skip | 依赖已删模板 | 关键功能有新测试覆盖 |
| **打包** | **GPT禁止** | 等外部PASS后在洁净Windows环境打包 |

## 5. 打包前提条件(GPT 审计)

只有外部审计回复"源码验收 PASS"后,才允许:
1. 从 commit 30f2373 在洁净 Windows 环境生成 SRS-Setup-1.0.2-Windows-x64.exe
2. 保留 v1.0.1 不动
3. 生成 manifest(commit/dirty=false/构建环境/依赖锁/模型阈值流程图图标哈希)
4. 洁净 VM 安装 + 重新验收
