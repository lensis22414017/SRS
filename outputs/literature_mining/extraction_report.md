# SRS 文献挖掘报告 — OP 与 HM_OP 数据补强

**生成日期**: 2026-07-07 | **执行者**: 辛特助 | **审计**: 裴总

> 本报告遵循裴总铁律: 只用真实文献数据, 防伪复合, 不达门槛不训练。
---

## 一、执行摘要

- **文献库扫描**: G:\文献整理_最终 (11,755 篇) → 中国+OP/HM 候选 **1469** 篇
- **结构化抽取**: 1704 观测 / 53 论文 (v3: 含转置表 PCB/PAH 单体)
- **训练可用 (HM_OP 真配对)**: **63 sample / 11 source**
  - 纯土壤: **41 sample / 10 source**
  - 沉积物 (贵屿电子垃圾河流, 标 sediment_not_soil): 22 sample / 1 source
- **OP-only 补强**: 212 sample / 19 source
- **裴总门槛 (≥100 sample + ≥10 source)**: ❌ **未达** (纯土壤 41/10, 含沉积物 63/11)
- **结论**: 按裴总铁律第 6 条, **不训练模型**, 输出数据补强结果 + 缺口说明

## 二、候选文献筛选 (第一阶段)

分级分布:
| 级别 | 数量 | 定义 |
|------|------|------|
| A | 101 | 同论文有采样点级 HM+OP, 地点中国 |
| B | 313 | 同场地有 HM+OP 但仅统计汇总/图表 |
| C | 1055 | OP-only 中国土壤 |
| D | 0 | 无可抽取数据 (综述/模型) |
| 排除 | 10207 | 非 China / 无 OP / 无 HM |

## 三、数据抽取 (第二阶段)

**抽取观测**: 1704 条 long-format 记录, 53 论文

**证据等级**:
- A_sample_table: 1677
- B_site_summary: 27

**污染物族群分布 (pollutant_name_std top 15)**:
- SumPCB_ngg: 199
- Pb_mgkg: 165
- Zn_mgkg: 158
- SumHCHs_ngg: 150
- Cu_mgkg: 147
- Cd_mgkg: 142
- Sum_PAH_ngg: 125
- Cr_mgkg: 123
- SumDDTs_ngg: 118
- Ni_mgkg: 104
- As_mgkg: 99
- SumPBDE_ngg: 87
- Hg_mgkg: 70
- Mn_mgkg: 10
- Co_mgkg: 7

## 四、训练可用性判定 (第三阶段)

### readiness 分布

- op_only_ready: 212 sample
- hm_only_ready: 107 sample
- training_ready_hm_op: 63 sample
- not_training_ready_duplicate: 60 sample
- not_training_ready_chem_label: 42 sample
- not_training_ready_offtopic: 5 sample
- site_level_hm_op_only: 1 sample

### training_ready_hm_op 详情 (核心目标, 63 sample)

| 论文 | sample 数 | 基质 | 族群 | 说明 |
|------|----------|------|------|------|
| P01244 | 4 | soil | PCBs | A comprehensive assessment of heavy metals, VOCs a |
| P01482 | 3 | soil | PAHs | Impact of co-contamination by PAHs and heavy metal |
| P01492 | 7 | soil | OCPs | Status and fuzzy comprehensive assessment of combi |
| P01524 | 7 | soil | PCBs | Heavy metal and persistent organic compound contam |
| P02317 | 2 | soil | OCPs | Assessment of the soil quality by fuzzy mathematic |
| P02376 | 1 | soil | PBDEs | PBDEs and PCDD/Fs in surface soil taken from the T |
| P04669 | 4 | soil | PCBs | Design, Implementation and Environmental Impact of |
| P06121 | 1 | soil | PAHs | Assessing the combined risks of PAHs and metals in |
| P06579 | 10 | soil | PCBs | Risk assessment of polychlorinated biphenyls and h |
| P08598 | 2 | soil | PAHs | The application of urban anthropogenic background  |
| P10991 | 22 | sediment_not_soil | PAHs,PBDEs,PCBs | Microbial community structure and function in sedi |

## 五、质量门禁 — 6 类陷阱排除 (防伪复合)

苏格拉底追问驱动的 6 轮迭代, 累计排除 **115+ 假阳性 sample**:

| 陷阱 | 代表论文 | 排除数 | 机制 |
|------|----------|--------|------|
| 植物浓度 (sorghum/Zea mays) | P11676 | 整篇 | EXP_KEYWORDS: root/stem/leaf/dry weight/CK |
| 土地利用全国汇总 | P03303 | 多表 | is_landuse_aggregate: Arable land (n≥20) |
| 生物修复实验 | P09208 | 整篇 | EXP_KEYWORDS: bioremediation/conditioner/urea |
| 跑题 (大气甲醛 HCHO) | P04902 | 5 | OFFTOPIC_PAT: formaldehyde/GEOS-Chem |
| 重复论文 (同标题) | P05700/P10247 等 5 篇 | 60 | 同标题保留 paper_id 最小 |
| 化学代号当采样点 | P01492/P02317 等 | 42 | CHEM_LABEL_PAT: AS/CR/CU/DDT 作 sample |
| 负值 (物理不可能) | P01301/P02376 等 | 142 | value_std<0 → NaN |

## 六、QA 检查 (第五阶段)

| 检查项 | 结果 |
|--------|------|
| Q1 重复观测 (extracted 全量) | 103 行 (转置表多 Total 行, **site_dataset 已去重**) |
| Q2 负值 | 0 ✅ |
| Q3 conversion_note 缺失 | 0 ✅ |
| Q4 HM_OP 真配对 | 63/63 ✅ |
| Q5 GroupKFold source | 11 source, 最大占比 34.9%, 泄漏风险=高 |
| Q6 规范名白名单 | 0 非白名单 ✅ |
| Q7 可追溯性 | 0 缺 location ✅ |

## 七、Top 10 待人工处理文献

### 1. 图片数字化 (figure_only, A 级, 需 WebPlotDigitizer)

- **P11648** tbl=0 img=2 | Heavy metals and PAHs drive ecological and health risks in C
- **P00411** tbl=1 img=6 | Distribution characteristics and health risk assessment of h
- **P01511** tbl=0 img=23 | Insights into multisource sludge distributed in the Yangtze 
- **P01603** tbl=0 img=23 | Bioremediation of PBDEs and heavy metals co-contaminated soi
- **P01836** tbl=0 img=12 | Source apportionment and source specific health risk assessm
- **P01169** tbl=0 img=17 | Emission of PAHs, PCBs, PBDEs and heavy metals in air, water
- **P11323** tbl=0 img=2 | Cement kiln co-processing promotes the redevelopment of indu
- **P01936** tbl=0 img=13 | Direct Analysis of Soil Composition for Source Apportionment
- **P09544** tbl=0 img=1 | The distribution and dynamic transformation of the speciatio
- **P11241** tbl=0 img=1 | A novel method to analyze the spatial distribution and poten

### 2. 跨表配对潜力 (同论文 HM 表 + OP 表, 共享采样点)

- **P01524 已示范**: tbl#1 HM + tbl#3 PCB → 7 个 HM_OP sample (温岭电子垃圾)
- 待排查: 其他有 HM 表 + 独立 OP 表的论文 (需人工核对采样点编号映射)

### 3. SI 深挖 (si_available, 1 篇 A 级有 SI PDF)

SI PDF 含采样点级原始数据, 但 MinerU 未解析进 paper.md, 需重新解析或人工录入。

## 八、缺口说明与下一步建议

### 当前缺口

- **HM_OP training_ready 仅 41 纯土壤 sample** (裴总门槛 100, 缺 **~59** 个)
- **source_groups 10** (门槛 10, 刚达标但 P06579 占 24% 偏高)
- **经纬度缺失**: 绝大部分 sample 无 lat/lon (GEE 协变量采样受阻, 见 P6)
- **沉积物 22 sample** (P10991 贵屿): 是否计入训练需裴总定夺

### 下一步建议 (按收益排序)

1. **图片数字化** (最高收益): 28 篇 A 级 figure_only 论文, WebPlotDigitizer 可救回 30-80 sample
2. **SI PDF 重解析**: 1 篇 A 级有 SI, 含采样点级原始表
3. **跨表配对扩展**: 程序化扫描同论文 HM+OP 表的采样点编号交集
4. **沉积物定夺**: P10991 贵屿电子垃圾河流, 若计入则 63/11 接近门槛
5. **经纬度提取**: 从 paper 正文/metadata 提取场地坐标, 启用 GEE

## 九、产出文件清单

| 文件 | 规模 | 用途 |
|------|------|------|
| candidate_literature_op_hmop.csv | 1469 行 | 候选文献 A/B/C/D 分级 |
| extracted_observations_long_op_hmop.csv | 1704 行 | long format 观测 (含 canonical/readiness/matrix_flag) |
| site_dataset_summary_op_hmop.csv | 490 行 | 每采样点汇总 + readiness |
| rejected_literature_log.csv | 10207 行 | 排除原因 |
| qa_summary.json | 7 项检查 | QA 结果 |
| extraction_report.md | 本文件 | 审计报告 |

---
**裴总审计建议**: 先看本报告第七/八节, 再抽查 extracted CSV 的 evidence_location 可追溯性, 最后决定沉积物是否计入 + 是否启动图片数字化。
