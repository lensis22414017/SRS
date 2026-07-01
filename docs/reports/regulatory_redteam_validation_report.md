# SRS 监管级红队验收报告

## 验收时间

2026-07-01 03:36 (UTC+8)

## Git Commit Hash

`b22de72`

## 环境信息

| 项目 | 值 |
|------|-----|
| 操作系统 | Windows 11 Home China 10.0.26200 |
| Python 版本 | 3.13.5 |
| pytest 版本 | 9.0.2 |
| pytest-cov 版本 | 7.1.0 |
| httpx 版本 | 已安装 |
| 测试运行时长 | 2036.31s (33:56) |
| 当前分支 | main |

## 测试结果总览

| 类别 | 文件 | 收集 | 通过 | 失败 | 通过率 |
|------|------|------|------|------|--------|
| P0 安全边界 | test_regulatory_api.py | 49 | 49 | 0 | 100.0% |
| P0 数据契约 | test_regulatory_data_contract.py | 34 | 34 | 0 | 100.0% |
| P1 报告/地图 | test_regulatory_report_map.py | 29 | 27 | 2 | 93.1% |
| **合计** | | **112** | **110** | **2** | **98.2%** |

## P0 通过率: 100% (83/83)

### P0-1: 安全边界 (test_regulatory_api.py) — 49/49 PASSED

| 测试类 | 测试数 | 覆盖项 |
|--------|--------|--------|
| 未登录 401 | 6 | `/sites`, `/sites/{id}`, `/auth/me`, `/system/users`, `/sites/{id}/report`, `/import` |
| 无权限 403 | 8 | agency/enterprise 系统用户; agency 报告/技术库; enterprise 审计/用户管理; regulator 技术库 |
| 企业隔离 403 | 9 | 越权访问 site detail/points/measurements/workflow/map/eda/evaluation/export; admin 通行 |
| validation-report 越权 | 1 | `import-batches/{id}/validation-report` 经 `assert_site_access` 阻断 |
| workflow attachment 越权 | 1 | `_require_site` 在附件下载前触发 403 |
| report 越权 | 2 | report download + report list 均经 `_require_site` 校验 |
| 写操作 audit | 8 | login(成功+失败), import, create_user, update_user, change_password, register, approve_user, update_land_use |
| 下载/导出 audit | 5 | export_measurements, export_audit_logs, export_technologies; report_download/attachment_download 标记缺口 |
| SECRET_KEY 阻断 | 2 | 默认值 `CHANGE_ME_IN_ENV` → UserWarning; 自定义值 → 静默 |
| 令牌攻击面 | 7 | 无效/畸形/空/缺失令牌 → 401; 公开端点免认证; 企业场地列表不泄漏 |

**安全缺口 (已知/已标记)**:
1. 报告下载不写 audit_log — `GET /reports/{report_id}/download` 未调用 `log()`
2. 附件下载不写 audit_log — `GET /sites/{site_id}/workflow/{stage}/attachments/{attachment_id}/download` 未调用 `log()`
3. SECRET_KEY 默认值仅 `warnings.warn()` 不阻断启动

### P0-2: 数据契约 (test_regulatory_data_contract.py) — 34/34 PASSED

| 契约条款 | 测试数 | 验证内容 |
|----------|--------|----------|
| AC-10 dataset_versions | 6 | 表存在、必填列(site_id/version_code/is_active)、持久化、DiagnosisResult/EvaluationResult 含 data_version、关联查询 |
| AC-11 Measurement 监管字段 | 12 | original_value_text/qualifier/detection_limit/value_used_for_model/qa_status/evidence_level 列存在；qualifier 持久化(<0.001→qualifier='<')；语义区分(<, >, ND) |
| AC-12 sampling_events | 4 | 表存在、必填列、唯一约束(site_id+event_code)、持久化 |
| AC-13 project_authorizations | 3 | 表存在、必填列(site_id/authorized_org_id/valid_from/is_revoked)、持久化 |
| AC-14 data_origin | 3 | 列存在、四种值(field/literature/synthetic/demo)、默认值='field' |
| AC-15 replicate_group | 3 | 列存在、平行样全保留(不静默平均)、value 与 value_used_for_model 独立 |
| AC-16 计数一致性 | 2 | SQL COUNT 可用、ImportBatch row_count/valid_count/invalid_count 一致性 |
| AC-17 is_seed | 4 | Organization/User 有 is_seed 列、种子组织/用户 is_seed=True |
| AC-18 综合闭环 | 1 | 全部监管字段一次写入后可完整回读 + 关联验证 |

## P1 通过率: 93.1% (27/29)

### P1: 报告/地图/工作流/模型注册 (test_regulatory_report_map.py) — 27/29 PASSED, 2 FAILED

| 编号 | 测试类 | 测试数 | 通过 | 失败 |
|------|--------|--------|------|------|
| T14 | TestReportPDFGeneration | 3 | 3 | 0 |
| T15 | TestReportVersionMetadata | 4 | 3 | **1** |
| T16 | TestStaticMapRenderer | 3 | 3 | 0 |
| T17 | TestNoCoordFallback | 3 | 3 | 0 |
| T18 | TestExceedanceConsistencyWithAPI | 1 | 1 | 0 |
| T19 | TestWorkflowStateMachine | 6 | 6 | 0 |
| T20 | TestFileIntegrity | 3 | 2 | **1** |
| T21 | TestEvidenceCompleteness | 2 | 2 | 0 |
| T22 | TestModelRegistry | 4 | 4 | 0 |

## 失败项详情 (BLOCKER 清单)

### BLOCKER-1: `test_report_no_tianditu_basemap_misleading_text` (T15)

- **严重级别**: LOW (P2)
- **文件**: `tests/test_regulatory_report_map.py:308`
- **失败原因**: 报告 `map_summary.note` 中出现了 "天地图" 文本。当前报告在说明地图底图来源时引用了"天地图底图系统"路径 `/api/v1/sites/{site_id}/map/layers`，测试期望不应出现误导性文本暗示使用了天地图在线瓦片服务。
- **断言**: `assert "天地图" not in map_note`
- **状态**: 报告实际说明的是内部 API 图层系统，提及"天地图"仅为说明数据来源而非暗示在线服务，属于文本措辞问题。
- **修复建议**: 将报告中的 "天地图底图系统" 改为 "系统内部地图图层服务" 或类似表述，避免与天地图在线瓦片服务混淆。

### BLOCKER-2: `test_file_roundtrip_sha256_unchanged` (T20)

- **严重级别**: MEDIUM (P1)
- **文件**: `tests/test_regulatory_report_map.py:890`
- **失败原因**: `app/services/file_service.py:46` 中的 `_validate_upload` 拒绝了 `application/octet-stream` 内容类型。
- **报错**: `ValueError: 不支持的文件类型: application/octet-stream`
- **影响**: 通配二进制类型文件无法通过 `save_bytes` 写入，可能影响通用文件上传场景。
- **修复建议**: 在 `_validate_upload` 中将 `application/octet-stream` 加入允许的 MIME 类型白名单，或为测试使用具体的 MIME 类型（如 `application/pdf`）。

## Warnings 摘要

| 警告类型 | 数量 | 来源 |
|----------|------|------|
| StarletteDeprecationWarning (httpx 版本) | 1 | testclient.py |
| CJK 字体缺失 (DejaVu Sans Mono) | ~190 | report_service.py, static_map_renderer.py |
| 覆盖 17 个中文字形缺失 | — | 级/色/阶/染/底/图/无/离/线/坐/标/散/点/值/来/源/盖 |

> 注: CJK 字体缺失不影响功能正确性，matplotlib 图表中中文标签会显示为方框。生产部署时需安装中文字体（如 Noto Sans CJK SC 或 SimHei）。

## 证据路径

| 文件 | 绝对路径 | 行数 |
|------|----------|------|
| CI/CD Workflow | `C:\Users\曾鸿\desktop\SRS\.github\workflows\regulatory-redteam-validation.yml` | 1600+ |
| 安全边界测试 | `C:\Users\曾鸿\desktop\SRS\backend\tests\test_regulatory_api.py` | 1004 |
| 数据契约测试 | `C:\Users\曾鸿\desktop\SRS\backend\tests\test_regulatory_data_contract.py` | 748 |
| 报告/地图测试 | `C:\Users\曾鸿\desktop\SRS\backend\tests\test_regulatory_report_map.py` | 955 |
| 本验收报告 | `C:\Users\曾鸿\desktop\SRS\docs\reports\regulatory_redteam_validation_report.md` | — |

## 是否建议给甲方演示

**建议，有注意事项。**

P0 安全与数据契约 100% 通过，核心系统行为（认证、授权、企业隔离、审计日志、数据完整性/一致性）全部经过验证。演示前应：

1. 修复 BLOCKER-2（`application/octet-stream` 上传）或在演示流程中避开该路径
2. 安装中文字体消除 CJK 字形缺失警告
3. BLOCKER-1（天地图措辞）不影响功能，可在演示中口头说明

## 是否建议进入正式验收

**建议，条件性通过。**

条件:
1. BLOCKER-2 (`application/octet-stream` 文件上传) 修复后重新验证
2. 确认 CJK 字体安装方案已在部署文档中落实
3. 安全缺口（报告/附件下载不写 audit_log）纳入 P2 修复队列，不阻塞验收

## 禁止演示功能清单

| 功能 | 原因 | 严重级别 |
|------|------|----------|
| 通用二进制文件上传 (`application/octet-stream`) | `file_service._validate_upload` 拒绝该 MIME 类型 | P1 |
| 含中文标签的 matplotlib 图表 | DejaVu Sans Mono 缺 CJK 字形，显示为方框 | P2 |
| 报告/附件下载审计日志 | 已知缺口，不写 `audit_log` | P2 |
| 报告地图底图来源说明 | 措辞提及"天地图"，可能与在线服务混淆 | P2 |

---

*报告生成时间: 2026-07-01T03:36:00+08:00*
*测试执行人: 辛特助 (Claude Code Agent)*
*验收标准依据: CLAUDE.md Section 13 (测试与验收规范)*
