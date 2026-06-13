# 方案推荐与技术库匹配

**版本** v0.1 ·**日期** 2026-06-10 ·**作者** 辛特助 ·**状态** 草稿

## 1. 输入

障碍因子识别结果(`diagnosis_factor_details`)+ 功能重构可行性评价 + SSUI 评价。

## 2. 方法(MVP)

规则引擎 + 技术库匹配 + 结构化推荐理由。**不让 LLM 直接编方案**。

匹配逻辑:
1. 取场地 Top-N 障碍因子及其类别(污染物/理化/肥力)。
2. 在 `technology_library` 中按 `applicable_pollutants` / `applicable_land_type` / `applicable_stage` 匹配。
3. 应用 `forbidden_conditions` 过滤(禁用条件命中则剔除)。
4. 打分:因子覆盖度 + 用地类型匹配 + 成本/工期偏好,得 `match_score`。
5. 生成 `reason`:绑定具体障碍因子,说明为何推荐、优缺点、二次风险、禁用判断。

## 3. 技术库

来源 `data/knowledge_base/technology_library_seed.csv`(辛特助按工程实际构建,10 条:固化稳定化、土壤淋洗、植物修复、化学氧化 ISCO、生物修复、热脱附、阻隔填埋、农艺调控、客土换土、有机质改良)。来源字段如实标注为"通用导则/工程经验",非伪造标准条文。字段:适用污染物/土壤/用地/阶段、优点、局限、成本等级、工期等级、二次风险、禁用条件、来源。

## 4. 输出契约

`recommendations`:site_id、technology_id、diagnosis_factor_id(绑定障碍因子)、rule_version、match_score、reason、rank。

## 5. 模块规划(待 EXECUTE)

`ml/recommend/engine.py`:`recommend(site)` → 排序后的推荐列表 + 理由;入库 `recommendations`。

## 6. 禁止

无技术库就推荐;无禁用条件;无解释依据;方案不绑定障碍因子;LLM 直接编方案/编标准。

## 7. 已实现(2026-06-10)

`ml/recommend/engine.py`(纯 python)+ `recommend_service.py`(入库,绑定 `diagnosis_factor_details`)。匹配逻辑:适用污染物(重金属/有机物大类 + 元素名)∩ 用地类型,禁用条件过滤,打分=覆盖度0.6+成本0.25+工期0.15。

个旧实证(基于诊断 Top 因子 铜/锌/砷/铅,生产用地):推荐 植物修复(0.955)、农艺调控(0.955)、固化稳定化(0.95)、客土换土(0.95)、土壤淋洗(0.878),每条绑定障碍因子并附禁用条件与来源。结果已入 `recommendations`。

待确认:技术库当前为通用最小集(10 条),如有甲方指定技术清单与本地化成本数据可扩展 `technology_library_seed.csv`。
