# SRS 继续开发交接说明（v1.2.2-rc.1）

本文件说明如何在 v1.2.2-rc.1 基础上继续工作。它只描述仓库中已经存在的代码、脚本与证据，**不**声称任何未实现的功能（例如“智能体自动审核”“经济原值计算 SSUI”均未实现）。

## 1 版本与位置
| 项 | 值 |
|---|---|
| 仓库 | github.com/lensis22414017/SRS（公开） |
| 分支 / 被测提交 | `fix/v1.2.2-closeout` / `68a52751e8dfa6f6c48b5c20dd8b69b53b54e3b2`（标签 `v1.2.2-rc.1`） |
| 标签后文档提交 | `806a436`（`[skip ci]`，只从公开变更记录/迁移说明中去掉原始场地名称与数值） |
| 上一候选提交 | `6c4d73e`（run 38066944474 全部通过；之后发现 Excel 导出缺 SSUI 状态与用途状态，已被 68a5275 取代，其安装包不发布） |
| 前一版本 | `v1.2.1-rc.1` → e69116c（未改动）；`v1.2.0-rc.1` → e5a3728（未改动）；`main` → 36aabf4（未合并本分支） |
| Windows 构建/验收 | Actions run 38093845656（windows-release.yml）；CI run 38093845658 |
| 收尾目录 | `SRS_CS_Closeout_v122_20261010/`（00_BASELINE … 08_DECISIONS；07_PACKAGES 为交付包） |

## 2 入口
| 目的 | 文件 |
|---|---|
| 课题一 KOS 正式/探索性分层 | `backend/app/services/kos_service.py`、`threshold_resolver.py` |
| 分析物标识（单体↔官方记录、族总量、标记物、异构体） | `backend/app/services/analyte_registry.py`、`factor_normalizer.py:identity_of` |
| 课题二 M-REC-2025 | `ml/evaluation/reconstruction_m2025.py`、`backend/app/services/recon_import_service.py` |
| 课题三 SSUI（定义域、分级） | `ml/evaluation/ssui_v11.py`（`validity_domain`、`grade`、`classify`）、`backend/app/services/ssui_post_service.py:effective_status` |
| 利用结论（用途状态、门禁） | `ml/evaluation/utilization.py:decide/use_states`、`backend/app/services/utilization_service.py` |
| 五阶段追溯 | `backend/app/services/workflow_service.py`、`api/workflow.py`、前端 `pages/TraceDetail.tsx` |
| 评价快照与报告 | `backend/app/services/evaluation_snapshot.py`、`report_document.py`、`report_service.py` |
| 演示数据与验收 | `scripts/mc_demo_v12.py`（A–E，并串联 F/G/H/P）、`scripts/mc_demo_v121_cases.py`、`scripts/mc_demo_v122_workflow.py`、`packaging/ci/demo_runner.py`、`workflow_demo.py`、`windows_acceptance.py`、`scripts/validate_demo_package.py` |
| 真实场地私有回归 | `scripts/real_sites_regression.py`（输出只放 owner_private） |

## 3 常用命令（在仓库根目录）
```
cd backend && python -m pytest -q                                  # 全量测试
python scripts/mc_demo_v12.py generate --out demo/mc_v12           # 重建全部演示数据(A–H, P)
python scripts/mc_demo_v12.py run --out <副本目录> --db <dir>/srs_demo_x.db   # 经 API 执行并与期望比对(含新进程持久化验证)
python scripts/validate_demo_package.py --demo <副本目录>           # 独立校验(不调用 SRS 评价代码)
python scripts/real_sites_regression.py --out <owner_private>/D12 --db <dir>/srs_demo_real.db
```
注意：`generate` 会重写 xlsx 字节（时间戳），数值不变；若只想更新某一案例，单独运行对应生成器。

## 4 约束（继续开发时必须保持）
1. 三个子课题方法互相独立；不得自行新增、修改阈值、权重或等级区间；方法问题记入 Q 列表等待课题组确认（Q01–Q18 未签字，本版未等待签字）。
2. 正式判定只用官方标准记录（GB 15618 / GB 36600）且按名称/CAS 一一绑定；族总量只有在标准给出总量限值时才判定。
3. SSUI 等级只在 [0, 1.0] 内给出；域外保留原值、不分级、不支持。
4. 利用结论必须有明确用途；“非建设用地生态用途”的适用性不推定。
5. 真实场地输入与输出只放 owner_private；公开包与公开仓库新增内容只用合成数据。
6. 发布：标签打在通过 CI 与 Windows 验收的提交上；旧标签不移动；Release 资产经 `release-assets/<tag>` 孤立分支上传（沙箱无法直连 uploads.github.com），单文件 < 100 MB。

## 5 问题状态
见 `01_ISSUES/issue_register.csv`（R01–R10 及 T01–T06、本轮发现的 N01–N07）与 `08_DECISIONS/decision_register.md`。真正的外部事项：甲方 Windows 10/11 实机交互测试；`data/raw` 公开历史处置（`08_DECISIONS/raw_data_exposure_inventory.md`）；课题组对 Q01–Q18 的确认；实测修复后数据；是否增加独立审核权限。

## 6 证据索引
| 证据 | 位置 |
|---|---|
| 修复前复现（e69116c） | `03_TESTS/before_e69116c.json`、`before_tests_e69116c.txt` |
| 本机全量测试（被测提交） | `03_TESTS/local_68a5275/` |
| Windows 验收、标准账户、DOCX 渲染 | `03_TESTS/windows_test_matrix.csv`；public `D11_evidence/` |
| 报告逐页检查 | `04_REPORT_QA/`（A、D、H 取自发布运行；域外夹具；客户汇报 client_deck_T06） |
| 用途状态（T03）端到端 | `03_TESTS/local_68a5275/T03_e2e/`；Windows `03_TESTS/windows_68a5275/t03_ui_checks.json` |
| 演示包比对 | `05_DEMO/`；public `D07_demo_package/` |
| 真实场地回归与 v1.2.1 对比 | owner_private `D09_data_method_pack/real_site_regression/` |
