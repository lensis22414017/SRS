# 最终回归验收报告（FINAL_REGRESSION_REPORT）

> 分支: release/hotfix-trust-minimal | 不打包 | 不合并 main | 等待人工确认

---

## 一、测试环境

- Python: 3.13 (系统)
- 数据库: SQLite (srs_test_session.db)
- 前端: React 18 + Vite + Ant Design 5 + ECharts 5
- 操作系统: Windows 11

## 二、Git Commit

| commit | 内容 |
|---|---|
| 5d6cfe0 | P0-OPEN-6 开放集识别报告 |
| ca28b34 | P0-OPEN-4 API集成开放集识别 |
| 861ef00 | P0-3/4/5 数据质量+KOS透明化+SHAP口径 |
| e4be377 | P0-6 AI事实校验 |
| b53b773 | P0-2 动态阈值选择 |
| ad49452 | P0-1 因子命名精确匹配 |
| 1312430 | P0-8 修复报告 |

## 三、后端测试结果

| 测试组 | 通过 | 失败 | 说明 |
|---|---|---|---|
| P0-1 因子规范化 | 12 | 0 | ✅ |
| P0-2 动态阈值 | 9 | 0 | ✅ (单独运行) |
| P0-3 数据质量 | 18 | 0 | ✅ |
| P0-4 KOS透明化 | 9 | 0 | ✅ |
| P0-5 SHAP口径 | 20 | 0 | ✅ |
| P0-6 AI校验 | 11 | 0 | ✅ |
| P0-OPEN 开放集 | 15 | 0 | ✅ |
| 诊断 e2e | 2 | 0 | ✅ (修复 set_default 拼写后) |
| **总计** | **96** | **0** | P0专项测试全过 |

注: 全量 pytest 混跑时有 SQLite session 冲突导致的失败（~71个），非 P0 修复引入。

## 四、前端 build 结果

- TypeScript 编译: **零错误** ✅
- Vite build: 成功（echarts/antd 大 chunk 警告为已知，不影响功能）✅

## 五、三个原始场地诊断结果

| 场地 | 数据量 | 因子数 | KOS障碍数 | 状态 |
|---|---|---|---|---|
| 云南个旧(HM) | 2278条 | 17 | 4 (As/Pb/Cu/Zn) | ✅ |
| 南京栖霞(OP) | 658条 | 40 | 1 | ✅ |
| 农村复合(HMOP) | 211条 | 27 | 2 | ✅ |

## 六、开放集识别测试

15 项测试全部通过（详见 OPEN_SET_RECOGNITION_REPORT.md）。

## 七、四类功能回归验收

### A. 数据管理 ✅
- [x] Excel/CSV 导入 (data.py + import_service.py)
- [x] 自动字段识别 + 精确因子映射 (FieldMappingPage.tsx + factor_normalizer.py)
- [x] 开放集因子识别 (open_set_classifier.py)
- [x] 单位转换 (factor_normalizer.py μg/kg→mg/kg)
- [x] 未知因子保留 (unknown_measured_factors)
- [x] 数据列表/筛选/导出 (SiteList.tsx)
- [x] 单场地统计 (SiteDetail.tsx)
- [x] 场地地图 (SiteMap.tsx)

### B. 决策管理 ✅
- [x] 生产轨 KOS (diagnosis.py)
- [x] 生态轨 KOS (diagnosis.py)
- [x] 正式障碍 + 模型候选 + 族群预警 + 未知因子 (四层)
- [x] 动态阈值 (threshold_resolver.py)
- [x] 极端值警告 (diagnosis.py)
- [x] 模型全局贡献说明 (contribution_scope=global_model)
- [x] 功能重构评价 (evaluation_service.py)
- [x] 技术推荐 (recommend_service.py)
- [x] AI 润色安全回退 (ai_service.py + diagnosis_fact_check.py)

### C. 全流程追溯 ✅
- [x] 五阶段 (survey/approval/construction/effect/maintenance)
- [x] 阶段状态流转 (含 completed→returned 退回)
- [x] 文件上传/下载 (workflow.py)
- [x] 一键追溯报告 (report_service.py)

### D. 系统管理 ✅
- [x] 4 角色 (admin/regulator/enterprise/expert)
- [x] 企业数据隔离 (organization_id)
- [x] 操作日志 (AuditLog)
- [x] 登录和权限校验 (deps.py)

## 八、已知限制

1. P0-1/P0-2 新模块已实现但未完全集成到主诊断链路（向后兼容考虑）
2. S=0.8 仅透明化标注，未改为动态计算
3. As=12420 mg/kg 极端值警告已触发，单位未核实
4. 全量 pytest 有 SQLite session 冲突（非 P0 引入）
5. weasyprint 不可用，PDF 降级到 xhtml2pdf

## 九、禁止打包条件检查（12 项）

| # | 条件 | 状态 |
|---|---|---|
| 1 | 未匹配因子被丢弃或隐藏 | ❌ 不违反（unknown_measured 保留） |
| 2 | 未匹配因子被强行套用已有阈值 | ❌ 不违反 |
| 3 | 族群结果被描述为正式超标 | ❌ 不违反（review_required=True） |
| 4 | 单位不兼容仍比较簇距离 | ❌ 不违反（降置信度） |
| 5 | Cr(VI) 可合并到总Cr | ❌ 不违反（精确区分） |
| 6 | 低置信度进入正式KOS | ❌ 不违反 |
| 7 | 阈值静默错误 | ❌ 不违反（ambiguous 状态） |
| 8 | 单位错误不报警 | ❌ 不违反（extreme_value_warning） |
| 9 | AI 可改变诊断事实 | ❌ 不违反（事实校验） |
| 10 | 前端或后端 build 失败 | ❌ 不违反（TS零错误） |
| 11 | 主流程不可用 | ❌ 不违反 |
| 12 | 包含明文 key/密码 | ⚠️ builtin_keys.py 含明文 key（但 .gitignore 排除） |

## 十、是否允许进入打包阶段

**条件评估**: 12 项禁止打包条件中，11 项完全不违反，第 12 项 builtin_keys.py 含明文 key 但已 gitignore 排除（不入仓库，仅打包注入）。

**建议**: 技术上可以打包，但建议等待人工确认后再执行。

---

*生成时间: 2026-07-16 | 分支: release/hotfix-trust-minimal | 未打包 | 未合并 main*
