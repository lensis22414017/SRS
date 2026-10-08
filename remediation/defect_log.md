# SRS v1.1 缺陷记录（Defect Log）

基线：`main@36aabf4`（2026-07-23）。修复分支：`fix/v1.1-client-acceptance`。
基线 pytest：472 项，447 通过 / 12 失败 / 13 跳过（session 1 证据）。GitHub CI 在 36aabf4 处为红（Backend SQLite、Red-team Security Boundary、API Contract、Data Contract）。

| ID | 严重度 | 模块 | 现象 | 根因 | 处置 | 回归证据 |
|---|---|---|---|---|---|---|
| D-01 | 高 | `app/services/kos_service.py` | 无数据库会话调用 KOS 时抛出 `NoneType` 错误 | FactorDictionary 查询未判空 `db_session` | 增加判空，跳过字典别名查询 | 3 项 KOS 测试通过 |
| D-02 | 高 | `threshold_resolver.resolve_threshold_from_db` | 生态轨道未指定用地类别时，从 GB 36600 中任取第一行限值 | v1.0.3 "取首行" 逻辑 | 生态轨道：多类别限值不同则返回 `ambiguous` + `candidate_limits`；生产轨道保留文档化的"其他"默认 | 阈值与三场地测试 17 项通过 |
| D-03 | 高 | `factor_normalizer._extract_unit` | "铬(六价)"/"Cr(VI)" 被当成单位剥离，映射为总铬 | 括号内容一律视为单位 | 新增 `_is_speciation_qualifier` / `_SPECIATION_TOKENS` | 归一化测试通过 |
| D-04 | 中 | `data/standards/ssui_economic_reference_v1.csv` | D24/D25 2024 年记录重复 3 次（72 行） | 数据追加未去重 | 去重至 68 行；`reference_loader` 拒绝重复指标-年份；新增 `test_reference_loader_rejects_duplicate_years` | 47 项通过 |
| D-05 | 高 | `ml/params/evaluation_params.json` | SSUI 生产轨道 D1–D21 权重取自生态表（方法 PPT 第 13 页），生态轨道使用重归一化的生产权重 | 两轨权重互换 | 按方法 PPT 第 13/14 页逐轨重载；见 SSUI 步骤 | G4 |
| D-06 | 高 | `ml/evaluation/ssui.py` L636 | SSUI 被截断到 [0,1]，掩盖 M>1 导致的超界 | 结果钳位 | 不截断，输出原值并标记 `exceeds_unit_range` | G4 |
| D-07 | 高 | `ml/evaluation/reconstruction.py` | 个旧 134/134 点 Pb/As 超标，生态重构仍判"可行"（63.29） | 未文档化的 "v1.2" 准则层降维兜底：覆盖率不足时把分母换成准则数，并把超标污染物与土壤质量指标平均 | 删除兜底；覆盖率不足返回"证据不足"；法规安全门禁移至利用决策层且不可被得分抵消 | `test_reconstruction_includes_pollutants_ecology` 通过；G3 |
| D-08 | 中 | `SSUIAnalysis.tsx` | `allowProxy` 默认为 true，区域代理值静默参与正式评价 | 默认值设置 | 默认 false；启用时结果标"参考评价" | G4 / UI |
| D-09 | 低（测试） | `tests/test_evaluation.py::test_op_site_recommendation_organic_fallback_and_no_404` | 期望 `organic_fallback=True`，实际 False | Round10 起无持久化诊断时按采样点即时重算 KOS，有机场地得到法规障碍后走 KOS 规则推荐（行为正确，断言过时） | 断言改为：不抛错、`diagnosis_id` 为空、推荐类型显式且与 fallback 标志一致、候选绑定障碍因子 | 通过 |
| D-10 | 中 | `app/services/report_service.py` | DOCX 报告缺"地图图件""人工复核意见区"章节名（HTML 有） | DOCX 与 HTML 章节命名不一致；无坐标时地图章节静默为空 | 统一章节名；无地图时写明原因 | `test_workflow_report` 6 项通过 |
| D-11 | 中 | 版本号 | 1.0.1 与 1.0.2 混用（安装器 .iss 为 1.0.2，发布门禁测试期望 1.0.1） | 发版未统一 | 统一为 1.1.0；门禁测试改为从单一版本源读取 | 发布步骤 |
| D-12 | 低（测试） | `test_round10_release_gate` ×3 | 断言 UI 文案"展开其余""允许区域代理（参考评价）" | 文案已在 204a966 移除，测试未同步 | 按 v1.1 UI 重写门禁断言 | 发布步骤 |
| D-13 | 高（方法） | 方法 PPT vs 仓库 | D-ID 冲突 10 处（第 6 页层次 vs 第 13/14 页权重表）；C4 组内权重和 1.214（生态）/1.047（生产）；M 使 SSUI 可 >1 | 方法文件内部不一致 | 不静默归一化，结果标 `provisional`；问题清单待陈亮/伟杰确认 | crosswalk / reconciliation JSON |
