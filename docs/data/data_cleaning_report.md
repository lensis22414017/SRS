# 数据清洗与剖面报告（双数据集，阶段1只读）

> 自动生成: `scripts/run_data_profiling.py` ｜ 真实数据, 未插补、未改原值、未生成模拟数据
> 逐列/分组缺失率明细见 `data/processed/missingness_profile.csv`

## 一、数据资产概览
| 数据集 | 行 | 列 | 数值列 | 整体缺失率 |
|---|---|---|---|---|
| 真实数据集.csv（训练主表） | 1119 | 34 | 31 | 44.48% |
| merged_std33（数据湖） | 41504 | 719 | 622 | 97.55% |

merged_std33 为**宽稀疏数据湖**（719 列、缺失 97.55%），**禁止整表统一插补/训练**，
必须先派生 model_ready 子表（见 `data/model_ready/model_ready_schema.csv`），再做 DOI/Source/Region 分组切分。

## 二、merged_std33 列分组
- 标识/地理: ID/DOI/Source/Year/Journal/Country/Province/City/Region/Latitude/Longitude/LandUse/Pollution_Type/SampleID 等（17）
- 理化协变量: SoilpH/pH/pH_merged/OC_pct/SoilBD/CEC/Sand/Silt/Clay/SoilTexture/SoilType（11）
- 重金属(measured_*): Cd/Pb/As/Cu/Zn/Ni/Cr/Hg/Co/Mn/Fe/Sb… `*_mgkg`（约 28 列）
- 有机物(measured_*): HCH/DDT/PAH/PCB/OCP/PFAS/TPH 族 `*_ngg`/`*_mgkg`（约 142 列）

## 三、关键列覆盖（merged_std33）
DOI 99.2%、Source 100%、Province 63.4%、经纬度 ~57.5%、LandUse 52.6%、SoilpH 21.8%、Region 21.9%。
**Pollution_Type 分布**: HM 24436、OP 5226、HM+OP 2104、PAH 1843、OCP 414…（适合派生 HM/OP/HM+OP 视图）。
**LandUse/Province 取值脏**（中英混杂、392 个 Province 取值），需 `unit_conversion_rules`/标准化映射后才能分组建模。

## 四、高缺失列（> 80%）
- 真实数据集: 共 8 列，如 CEC(99.8%), ClayPerc(93.3%), Fertilization_T(89.7%), P_T(84.1%), K_C(87.5%), EC_T(99.8%), BS_T(100.0%), Aggre_T(95.6%)
- merged_std33: 共 689 列（719 列里绝大多数有机物单指标列高度稀疏，属正常——单篇文献只测部分污染物）

## 五、使用红线（强制）
1. 原始文件 immutable，只读;所有派生写入 cleaned/model_ready/synthetic 分层并带 `source_file_sha256`。
2. 未测污染物**不得当 0**;缺失按真实机制处理，建模用中位数填充+`*_missing` 标记，**绝不补满 719 列**。
3. 模拟/插补数据带 `is_synthetic`/`evidence_level`，**永不进入 real 验证集**。
4. 主验证禁止行级随机切分，必须 DOI/Source group split（见 `docs/validation/leakage_prevention_checklist.md`）。
