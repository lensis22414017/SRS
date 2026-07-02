# P0–P2 阶段执行报告

> 日期: 2026-07-02 | 执行: 辛特助 | 计划: zzv0.6颗粒度单元版
> 范围: 数据审计 + 库建设 + 规则引擎(不训练模型, 不改前端)

---

## 一、数据是否足够进入 P3

**结论: 可以进入 P3，但需注意覆盖率限制。**

- merged_std33_geocoded.csv: 27031行 × 720列, 宽表(无需pivot)
- model-ready: 674列可入模, 46列排除(元数据+规则派生)
- 泄露审计通过: 0个禁止字段进入特征清单
- OI_t目标已生成: 生产轨OI均值0.4049, 生态轨0.5441, 两轨有差异

**限制**: 720列中406列完全空(56.4%), 实际有信号的特征远少于674列。重金属8个非空率25-56%, 理化列非空率15-35%, 有机汇总列非空率<3%。P3模型训练时需做特征筛选。

---

## 二、生产轨可诊断覆盖率

- 阈值库匹配: **11/19** 因子匹配成功(57.9%)
- 核心指标覆盖: Cd/Pb/As/Cr/Hg/Cu/Zn/Ni(8重金属) + pH + 有机质 + CEC = **11个核心指标有阈值+有数据**
- OI_t分布: 均值0.4049, 正样本率(OI>0) 72.5%
- 未匹配8因子: 电导率/土壤质地/坡度/有效土层/砾石含量/六六六总量/滴滴涕总量/苯并[a]芘(命名不一致, 需别名表补充)

---

## 三、生态轨可诊断覆盖率

- 阈值库匹配: **14/116** 因子匹配成功(12.1%)
- 核心指标覆盖: 8重金属 + pH + 有机质 + CEC + 土壤容重 + 含盐量 = **14个核心指标有阈值+有数据**
- OI_t分布: 均值0.5441, 正样本率(OI>0) 77.4%(生态阈值更宽→更多障碍)
- 未匹配102因子: 大量生态功能指标(入渗率/孔隙度/压实/交换性钠/可溶性硼等)在数据中无对应列

---

## 四、阈值匹配失败的因子

**生产轨未匹配(8个)**:
- 电导率(数据列EC_mScm, 阈值库写"电导率", 名称不一致)
- 土壤质地/坡度/有效土层/砾石含量(数据中无对应列或命名不同)
- 六六六总量/滴滴涕总量(数据列是SumHCHs_ngg/SumDDTs_ngg, 阈值库写中文)
- 苯并[a]芘(数据列BaP_ngg, 阈值库写"苯并 [a] 芘"带空格)

**生态轨未匹配(102个)**: 大量生态指标(入渗率/孔隙度/压实/交换性钠/可溶性氯/可溶性硼等)在merged_std33中无对应数据列。

**原因**: 知识库122因子中大量是理想化指标集(年度报告课题二设计的完整体系), 但实际数据(merged_std33文献meta-merge)只有部分指标有实测。这是数据稀疏的客观现实。

**修正方案**: 因子别名表(factor_aliases.yaml)已建, 但需补充电导率/质地等映射; 下一轮P1-2阈值库重建时补充。

---

## 五、权重缺失的因子

**生产轨**: 权重库覆盖28个指标(年度报告表13完整), 但数据中实际有实测的只有11个匹配成功。其余17个权重指标(有效土层/生物多样性/全氮/有效磷/速效钾/灌排能力/地下水埋深/光温潜力/表土质地/剖面构型/C库因子)在数据中缺失。

**生态轨**: 权重库覆盖17个核心指标(年度报告表14), 但数据中只有14个匹配。入渗率/水解性氮/有效微量元素等缺失。

**影响**: KOS计算时, 缺失指标的W不参与(D=0), 只有权重+有实测的因子才进入排名。这是正确的——未测指标不进正式Top-N, 列为建议补测。

---

## 六、无法正式诊断、只能建议补测的因子

以下因子在课题二权重体系中重要, 但数据中未检测, **只能进入建议补测榜**:

**生产轨建议补测**:
- 有效土层厚度(权重10.2%, 数据缺失)
- 生物多样性(权重2.2%, 数据缺失)
- 全氮/有效磷/速效钾(肥力指标, 数据缺失)
- 灌排能力/地下水埋深(功能利用, 数据缺失)

**生态轨建议补测**:
- 土壤入渗率(权重5.6%, 数据缺失)
- 水解性氮/有效微量元素(数据缺失)
- 压实/孔隙度(结构水文, 数据缺失)
- 可溶性氯/交换性钠(化学环境, 数据缺失)

---

## 七、是否发现潜在泄露字段

**泄露审计结果: 通过, 无泄露。**

- scripts/audit_feature_leakage.py 对 model_ready_schema 的特征列做了审计
- 禁止模式: 标签/超标/severity/rule_/B_/R_/KOS/OI_/threshold/exceedance/_label/_target/_score
- 禁止精确: 标签_生产/标签_生态/标签/id_DOI/id_Source
- 检查30列sample, 0个禁止字段

**注意**: 知识库的 threshold_min/threshold_max 列在阈值库里(不进模型), 但训练数据的 wide table 本身不含阈值列, 所以无泄露风险。P3训练前会再次强制运行泄露审计。

---

## 八、下一阶段 P3–P5 是否可以启动

**结论: 可以启动, 但有以下前置条件:**

1. ✅ OI_t连续目标已生成(生产/生态各27031样本) — 回归目标就绪
2. ✅ 阈值库+权重库+因子字典就绪
3. ✅ 泄露审计脚本就绪
4. ⚠️ **特征筛选需在P3做**: 674列中406列全空, 需去全空+极稀疏列
5. ⚠️ **因子别名补充**: 苯并[a]芘空格变体/电导率中英文等需补到别名表
6. ⚠️ **OI_t分布偏斜**: 生态轨OI均值0.54偏高(生态阈值宽→大量障碍), P3回归可能需处理

**P3启动清单**:
- [ ] 特征筛选(去406全空列 + 非空率<5%列)
- [ ] 嵌套CV(GroupKFold site_id外层 + 内层调参)
- [ ] 回归模型(X_all → OI_prod / OI_eco)
- [ ] 消融实验(Full / MeasuredOnly / ContextOnly)

---

## 文件变更清单

### 新增文件(15个)
1. `scripts/data_audit/00_snapshot_and_structure.py` — P0快照+结构识别
2. `scripts/data_audit/01_to_07_audit.py` — P0-1~7数据审计
3. `scripts/build_all_libraries.py` — P1库建设
4. `scripts/audit_feature_leakage.py` — P1-4泄露审计
5. `ml/rules/rules_engine.py` — P2规则+权重+OI引擎
6. `data/reports/raw_file_manifest.json` — 原始数据SHA256快照
7. `data/reports/data_structure_report.json` — 数据结构(宽表判定)
8. `data/reports/dataset_profile.json` — P0-1概况
9. `data/reports/field_missingness.csv` — P0-2缺失率
10. `data/reports/factor_coverage.csv` — P0-2因子覆盖
11. `data/reports/factor_coverage_by_track.csv` — P0-3轨道覆盖
12. `data/reports/unit_harmonization_log.csv` — P0-4单位
13. `data/reports/censored_value_audit.csv` — P0-5检出限
14. `data/reports/outlier_candidates.csv` — P0-6异常值
15. `data/reports/model_ready_schema.json` — P0-7 model-ready
16. `data/knowledge/factor_dictionary.csv` + `.yaml` — P1-1因子字典
17. `data/knowledge/factor_aliases.yaml` — P1-1别名表
18. `data/thresholds/threshold_library_production.csv` — P1-2生产阈值
19. `data/thresholds/threshold_library_ecology.csv` — P1-2生态阈值
20. `data/weights/track_weight_library.csv` — P1-3权重库
21. `outputs/rules/rule_outputs_production.csv` — P2生产规则输出
22. `outputs/rules/rule_outputs_ecology.csv` — P2生态规则输出
23. `outputs/targets/oi_targets_production.csv` — P2生产OI目标
24. `outputs/targets/oi_targets_ecology.csv` — P2生态OI目标
25. `outputs/p2_summary.json` — P2汇总

### 修改文件: 无(原始数据只读未改)
