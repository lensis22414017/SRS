# 土壤污染文献精读提取 Agent 任务

## 目标
精读论文原文 paper.md，从真实表格提取**采样点级** HM + OP 浓度数据，构建可训练数据集。脚本抽取已被证伪（统计行/标准阈值/浓度值被误当采样点），必须人工精读。

## 裴总铁律（不可违背）
1. **只用真实文献可追溯数值**（表/图/正文明确数值），禁止生成/估算/合成/外推
2. **不把统计汇总当采样点**：剔除 Mean/SD/Max/Min/Median/Range/Skewness/Kurtosis 行（site-level summary）
3. **不把标准阈值当浓度**：剔除 Grade I/II/III、GB 15618/36600 筛选值、Dutch optimum/action 值、背景值
4. **不把全国/全省/区域均值当场地样本**
5. **不把风险指数当浓度**：HQ/TEQ/Nemerow/RI/污染指数全部剔除
6. **不跨论文拼接 HM+OP**（HM 和 OP 必须来自同一论文同一场地，跨表须同采样点标识）
7. **盆栽/实验室/生物修复实验数据剔除**（只要真实场地土壤实测）

## 剔除场景（输出 0 行 + extract_notes 标 skip 原因）
- 盆栽/温室/实验室添加实验（pot/greenhouse/spiked/amber bottle/microcosm）
- 生物修复/植物修复/微生物修复实验（bioremediation/phytoremediation/bioaugmentation）—— 除非有修复前场地本底实测值
- 水淋溶/浸出/吸附实验（leaching/extraction/sorption isotherm）
- 微塑料研究（microplastic）—— 非传统 OP
- 沉积物/污泥/降尘（sediment/sludge/dust）—— 保留但 matrix 标 sediment（裴总定夺）
- 大气/水体/植物组织（atmosphere/water/plant tissue）—— 非土壤，剔除
- 综述/Meta 分析（无原始数据）

## 提取规则

### HM（重金属，8 元素，mg/kg）
Cd / Pb / Cr / As / Hg / Cu / Zn / Ni → {元素}_mgkg

### OP（有机污染物）
- **Sum_PAH_ngg**：16 EPA PAHs 总和（ng/g）。论文给单体(Nap/Acy/Ace/Flu/Phe/Ant/Flt/Pyr/BaA/Chr/BbF/BkF/BaP/IcdP/DahA/BghiP)则求和；给"Total PAHs"直接用
- **BaP_ngg**：苯并[a]芘单体（ng/g）
- **SumPCB_ngg**：PCB 总和。给同系物(Tri/Tetra/Penta/Hexa/Hepta-PCB)求和；给单体(PCB-28/52/...)求和；给"Total PCBs"直接用
- **SumDDT_ngg**：DDT+DDE+DDD 总和（p,p'- + o,p'- 异构体全加）
- **SumHCH_ngg**：HCH 异构体总和（α+β+γ+δ-HCH）
- **SumPBDE_ngg**：PBDE 总和
- **TotalPHC_mgkg**：石油烃总量（mg/kg）

### 单位换算（关键）
- μg/kg = ng/g（数值不变）
- mg/kg = μg/g：若 PAH/PCB 给 mg/kg，×1000 → ng/g
- ppm = mg/kg；ppb = μg/kg = ng/g
- % 不提取（非浓度）
- 论文单位看 Table 脚注（a Unit mg/kg 等）

## 输出 CSV schema（每采样点每污染物一行）
```
paper_id,sample_id,pollutant_std,value,unit,evidence_location,matrix,site_type,province,extract_notes
P01646,S1,Cd_mgkg,2.3,mg/kg,Table 2,soil,coking,Shanxi,采样点S1表2直接读取
P01646,S1,Sum_PAH_ngg,1234.5,ng/g,Table 3,soil,coking,Shanxi,16单体求和(Nap+...+BghiP)
```

### 字段规范
- **sample_id**：论文原始采样点标识（A/B/C/S1/S2/点位名/村庄名），**严禁**用浓度值(5557.4)或统计量名(Mean)做 ID
- **evidence_location**：明确表号/图号（Table 2 / Fig 3 / 正文3.1段），可追溯
- **matrix**：soil / sediment
- **site_type**：coking/petrochemical/e_waste/mining/agricultural/urban/industrial/other
- **province**：从标题/正文提取（浙江/广东/...）
- **extract_notes**：提取方法（直接读/单体求和/同系物求和）+ 可疑标记

## 空输出情况（必须说明）
- 论文只有区域级 Mean/SD（无采样点级）→ 0 行 + notes="仅区域汇总，无采样点级数据"
- 论文是剔除场景 → 0 行 + notes="skip: 盆栽实验/bioremediation/..."
- 论文表格是图片无法解析 → 0 行 + notes="表格为图片，需OCR"

## 质量自检（输出前必查）
1. 每个 sample_id 是否真实采样点（非统计量/非浓度值/非标准名）？
2. HM + OP 是否来自同一场地（同论文同采样点标识）？
3. 单位是否正确（HM=mg/kg, OP Sum/BaP=ng/g）？
4. 是否误抽标准阈值(Grade/GB/Dutch)/统计行(Mean/SD)/风险指数(HQ/TEQ)？
5. value 是否物理合理（非负、非=1伪值、极端值标注）？

## 输出文件
每篇论文一个 CSV：`manual_extract/{hm_op|op_only}/{paper_id}.csv`（UTF-8-sig）
