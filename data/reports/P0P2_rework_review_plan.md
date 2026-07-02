# P0-P2 返工 REVIEW + PLAN（待裴总确认后EXECUTE）

> 日期: 2026-07-02 | 基于: 裴总第二轮指令(15节) + 障碍因子集盘点结果

---

## 一、当前 P0-P2 的问题清单（REVIEW）

### 问题1: 生产轨因子宇宙过窄
- 当前: 只用终版V1.7的19个生产因子(实际匹配11个)
- 问题: 不含有机污染(PAH/DDT/HCH/BaP)和复合污染的生产用途障碍
- 裴总要求: 生产轨必须三层(A正式诊断/B扩展筛查/C建议补测)

### 问题2: 生态轨14/116匹配被误判为"充分可诊断"
- 当前: 报告写"14/116因子匹配"
- 问题: 14个匹配只占12.1%，大量生态指标(入渗率/孔隙度/压实/发芽指数等)数据缺失
- 应改为: "数据覆盖不足，不代表生态轨充分可诊断"

### 问题3: 因子别名不足导致误判"数据缺失"
- EC_mScm(数据列) vs 电导率/含盐量/盐渍化程度(阈值库) 未映射
- SumHCHs_ngg vs 六六六总量 未映射
- SumDDTs_ngg vs 滴滴涕总量 未映射
- BaP_ngg vs 苯并[a]芘/苯并 [a] 芘(带空格) 未映射
- 实际有数据但被当成"未匹配"

### 问题4: GEE协变量被误报为"已补充"
- 当前数据(merged_std33_geocoded.csv 720列)中 **0列有gee_前缀**
- 有的是原始气候/地形字段(Altitude/Slope/Climate/Temperature)不是GEE栅格采样
- GEE协变量在另一个文件(merged_std33_gee_covariates.csv)，未merge进主表
- 裴总要求: 不允许写"GEE已补充完整"除非审计证明

### 问题5: 阈值库来源单一
- 当前: 直接用统一障碍因子知识库V1.0(403条)生成
- 问题: 没有利用V1.6合并版(123因子/12列最全元数据)的标准化单位/标准层级/风险等级
- 裴总要求: V1.6合并版作为master，多源融合

### 问题6: 权重库删了课题二没有的污染物
- 当前: 权重库只有课题二表13(生产28指标)/表14(生态17指标)里有权重的因子
- 问题: PAH/TPH/OCP/PCB等有机污染物被排除在权重库外
- 裴总要求: 不能因课题二没权重就删污染物，用功能层fallback补

---

## 二、障碍因子集版本盘点结果

详见 data/reports/obstacle_factor_source_manifest.md（下一步生成）

核心结论:
- **V1.6合并版(20251015)**: 123因子/1149行/12列(元数据最全) → 作为master factor universe
- **V1.6生产单独(20251028)**: 21因子/691行/11列 → 补强生产轨规则
- **V1.7生态终版**: 116因子/220行/7列 → 补强生态轨
- **V1.7生产终版**: 19因子/183行/7列 → 规范化参考，不作为删减依据
- 所有版本因子并集 = 177个，V1.6合并版覆盖123/177

---

## 三、推荐采用的建模阈值库来源

按裴总指令第三节优先级:
1. V1.6合并版(123因子) → master factor universe主源
2. V1.6生产单独版(21因子) → 补强生产轨(比V1.7多2因子)
3. V1.7生态终版(116因子) → 补强生态轨(新增25种有机氯/挥发性)
4. V1.7生产/生态终版 → 规范化参考
5. 统一知识库V1.0(403条) → 补factor_id/分类/证据等级
6. 所有来源保留source_file/source_version/source_row_id

---

## 四、生产轨扩展方案

### A层: 正式诊断因子(formal, 有国标阈值+有实测)
Cd/Pb/As/Cr/Hg/Cu/Zn/Ni(8重金属) + pH + 有机质/SOC + CEC + 土壤容重 + 土壤质地 + 坡度 + 有效土层 + 含盐量/EC + 六六六总量 + 滴滴涕总量 + 苯并[a]芘

### B层: 扩展污染筛查因子(supplementary_screening, 有实测但生产标准不完整)
PAHs总量及单体 + TPH/石油烃 + OCPs + PCBs + PBDEs + PFAS + VOCs/SVOCs + 农药残留 + 邻苯二甲酸酯

### C层: 建议补测因子(recommended_test, 对生产重要但未测)
全氮 + 有效磷 + 速效钾 + 灌排能力 + 有效耕作层厚度 + 地下水埋深 + 光温/气候生产潜力 + 生物多样性

---

## 五、生态轨保留与分层方案

生态轨116因子不删减，分4类输出:
1. 已测可诊断因子(有阈值+有数据列匹配)
2. 有阈值但未测因子(有阈值但数据无对应列)
3. GEE/协变量可代理因子
4. 必须补测因子(无法代理且生态功能重要)

重点关注: 土壤入渗率/孔隙度/压实/发芽指数/微生物酶活性/生物多样性/有效土层/土壤粒径/含盐量/可溶性硼/可溶性氯/交换性钠/钠吸附比

---

## 六、因子别名与字段映射方案

重建 factor_aliases.yaml，覆盖裴总指令第七节的25+映射组:
- pH组: SoilpH/pH/pH_merged
- 有机质组: OC_pct/SOC/SOM/有机质/有机碳含量
- CEC组: CEC_cmolkg/阳离子交换量/CEC
- 容重组: SoilBD_gcm3/BD/bulk_density/土壤容重/压实
- 电导率组: EC_mScm/EC/电导率/含盐量/盐渍化程度
- 苯并芘组: BaP_ngg/BaP_mgkg/苯并[a]芘/苯并 [a] 芘
- 六六六组: SumHCHs_ngg/HCHs/六六六总量/各异构体
- 滴滴涕组: SumDDTs_ngg/DDTs/滴滴涕总量/各代谢物
- PAHs组: Sum_PAH_ngg/PAHs总量/各单体
- OCPs/PCBs/PBDEs/PFAS/TPH组
- 8重金属组(含Cr6+/六价铬变体)

输出:
- factor_to_data_column_map.csv(因子→数据列匹配+match_type+coverage)
- unmatched_threshold_factors.csv(阈值库有但数据没有的因子)
- unmapped_data_columns.csv(数据有但阈值库没有的列)
- data_columns_without_threshold.csv(有数据无阈值的列)

---

## 七、GEE/协变量审计方案

扫描720列，分类输出 covariate_inventory.csv:
- DEM/Altitude: Elevation_m/Altitude_m等
- Slope/Aspect: Slope_pct
- NDVI/EVI: 当前数据中无(0列) → 需从merged_std33_gee_covariates.csv merge
- Temperature/Precipitation: Climate/Temperature_C/MeanAnnualTemperature等
- SoilGrids: CEC/Sand/Silt/Clay等(原始实测，非GEE栅格)
- MODIS: 无(0列)

结论: 当前主表无GEE栅格协变量(gee_前缀0列)，有的是原始实测气候/地形。
GEE扩展协变量(merged_std33_gee_covariates.csv)需merge进主表才能用。
报告只能写"当前已有部分地形/气候/土壤背景字段，GEE扩展待补充"。

---

## 八、v0.7阈值库和权重库设计

### 阈值库v0.7
- 来源: V1.6合并版(主) + V1.6生产单独(补) + V1.7生态(补) + 知识库V1.0(factor_id)
- 新增字段: diagnosis_layer(formal/screening/recommended_test/background)/threshold_role(direct/screening/literature/expert/proxy)
- 生产轨: A层formal + B层screening + C层recommended_test
- 生态轨: 116因子全保留，标diagnosis_layer

### 权重库v0.7
- 来源: 课题二表13/14(有则用) + 功能层fallback(课题二没有的用领域默认)
- weight_source: topic2_direct/topic2_mapped/domain_fallback/expert_default/not_weighted_recommended_test
- 生产轨功能层fallback: 污染安全/生产适宜/肥力/根系结构/水盐酸碱/地形土层
- 生态轨功能层fallback: 污染生态毒性/植被恢复/结构水文/化学环境/生物活性/生态服务
- 不删任何污染物(有机物用domain_fallback补权重)

---

## 九、需要修改的脚本和输出文件

### 新增脚本
1. scripts/build_factor_master.py — 从多源xlsx构建master factor universe
2. scripts/audit_covariates.py — GEE/协变量审计
3. scripts/rebuild_aliases_v0.7.py — 重建因子别名系统
4. scripts/rebuild_threshold_v0.7.py — 重建双轨阈值库
5. scripts/rebuild_weights_v0.7.py — 重建权重库

### 新增输出
- data/reports/obstacle_factor_source_manifest.md — 版本盘点
- data/knowledge/factor_master_raw.csv + dedup.csv + track_applicability.csv
- data/knowledge/factor_aliases.yaml(重建) + data/reports/factor_alias_audit.md
- data/reports/factor_to_data_column_map.csv + unmatched + unmapped + without_threshold
- data/reports/covariate_inventory.csv + gee_covariate_audit.md
- data/thresholds/threshold_library_production_v0.7.csv + ecology_v0.7.csv
- data/weights/track_weight_library_v0.7.csv

### 修改脚本
- ml/rules/rules_engine.py — 改为读v0.7库

### 重跑输出
- outputs/rules/rule_outputs_production_v0.7.csv + ecology_v0.7.csv
- outputs/targets/oi_targets_production_v0.7.csv + ecology_v0.7.csv
- data/reports/track_coverage_v0.7.md
- data/reports/P0_P2_execution_report.md(修正结论)

---

## 十、P3是否仍需暂停

**是，P3继续暂停。**

P3-P5启动条件: v0.7阈值库通过 + 字段映射完成 + GEE协变量审计明确 + OI目标重算通过。
当前: 条件未满足，不得直接训练。

---

## 十一、等待确认后再EXECUTE

以上为PLAN，待裴总确认后按以下顺序EXECUTE:
1. 因子源盘点文档
2. master factor universe(V1.6合并版123因子)
3. 因子别名系统(25+映射组)
4. 字段映射(因子→数据列)
5. GEE/协变量审计
6. v0.7阈值库(A/B/C三层)
7. v0.7权重库(含fallback)
8. 重跑P2规则层+OI
9. 覆盖率报告v0.7
10. 修正P0-P2报告
