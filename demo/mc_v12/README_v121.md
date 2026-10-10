# SRS 演示数据包 v1.2.1（模拟数据——仅供测试/演示）

| 内容 | 位置 |
|---|---|
| 场景 A–E（利用方向五类分支，v1.2.0 原文件，哈希未变） | `site_A` … `site_E` |
| 补充场景 F（有机-重金属复合，生态轨）与 G（仅文献参考阈值触发） | `cases_v121/` |
| 边界/错误夹具 F01–F08 | `fixtures/` |
| 生成器 | `scripts/mc_demo_v12.py`（A–E，种子 20261009）、`scripts/mc_demo_v121_cases.py`（F/G） |
| 独立期望值 | `expected.json`（A–E）、`metadata.json → cases_v121`（F/G） |
| 执行器（经 HTTP API） | `scripts/mc_demo_v12.py run --out demo/mc_v12 --db <dir>/srs_demo_x.db` |
| 独立校验器（不导入 SRS 代码） | `scripts/validate_demo_package.py --demo demo/mc_v12` |
| 环境锁定 | `ENVIRONMENT_LOCK.txt` |
| 功能覆盖台账（按课题） | `feature_coverage_v121.csv` |
| 实装输出（报告、快照 Excel/JSON、比较结果） | `actual/`（`comparison.json` 汇总全部比对项） |

## 使用边界
- 课题三 SSUI 为**得分录入模式**：D1–D25 得分由 Beta 分布生成，原始指标值/单位列为空；原始值→得分的计算闭环未实现。
- `05_*_场地经济输入.json` 为独立演示文件，**不参与 SSUI 计算**；不能表述为“经济原值计算 SSUI 已完成”。
- 五阶段业务材料（调查/审批/施工/效果/管护）未包含，报告中显示“未开展”。
- 所有结果带“模拟数据——仅供测试/演示”标签，不得用于正式报告或模型训练。
