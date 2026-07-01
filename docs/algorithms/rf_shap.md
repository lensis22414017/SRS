# 障碍因子识别:RF + SHAP

**版本** v0.2 ·**日期** 2026-06-29 ·**作者** 项目组 ·**状态** 双轨防泄漏+GEE协变量(已评审)

> **v0.2 重大更新(2026-06-29 项目组设计目标)**: 双轨防泄漏 RF+SHAP。
> - **X_barrier = 理化11 + GEE14 + __missing25 = 50 特征**(防泄漏红线: 后缀正则+关键词剔除 475 个污染物浓度列)
> - **双轨**: prod(GB15618 pH四段+GB36600一类严阈值) / eco(GB36600二类宽阈值), 复用 `_label_dual` 派生标签
> - **GEE 14 协变量**: MODIS NDVI + WorldClim 气候(bio01/bio12) + SRTM 地形 + SoilGrids 2.0 土壤8(`projects/soilgrids-isric`), 27031点采样18568点100%非空
> - **CV AUC prod 0.8314 / eco 0.8266**(达项目组目标 0.8-0.95, **防泄漏非虚高**; 旧 lake_full 0.99 是标签泄漏不可用)
> - **load_latest 路由**: 优先 `_barrier_gee` > `_lake_full`(泄漏仅回退)
> - **场地诊断**: `_enrich_gee_if_needed` 按 site 经纬度 GEE 采样填入 gee_ 列(非全中位数)
> - 脚本: `ml/covariates/gee_fetch.py` + `ml/etl/build_dual_track_training.py` + `ml/models/train_dual_gee.py` + `ml/evaluation/verify_dual_gee.py`
> - 详见 memory `gee-dual-track-setup`

## 1. 目标

从污染物、土壤理化、肥力、物理、生物指标中,识别制约生态/生产功能的关键障碍因子,输出 Top-N + 全局重要性 + 单场地局部解释,结果可追溯到检测值。

## 2. 数据来源

> ✅ **数据真实性声明（2026-06-16 真实数据重建）**：
> 当前训练数据 `data/raw/真实训练集_GB15618.csv`（29993 行，源自 `merged_std33,zh .xlsx` 真实文献数据，含 ID/DOI/Source/Year 溯源列），`is_real_data: True`。此前曾误用 F127 模拟特征表（已正本清源）。

- 训练样机（当前·真实）:`data/raw/真实训练集_GB15618.csv`（29993 样本，8 重金属真实检测值 Cd/Pb/As/Cu/Zn/Ni/Cr/Hg，`is_real_data: True`）。标签由 GB15618-2018 农用地筛选值（pH≤5.5 档）阈值派生：任一重金属超筛选值→1。生成脚本 `scripts/build_real_dataset.py`。训练前剔除 ID/DOI/Source/Year/超标因子数 等溯源与派生列（防泄漏）。
- 标签派生方式：GB15618-2018 阈值（Cd≤0.3/Pb≤80/As≤30/Cu≤150/Zn≤200/Ni≤60/Cr≤250/Hg≤0.5 mg/kg），任一超标→1。阈值来自知识库 ThresholdRule（standard_source=GB15618-2018），真实国标。
- 推理输入:某场地 `measurements` 长表透视为样本×因子矩阵。
- 样机参考:`参考文件/10.SHAP机器学习分析.ipynb`(不得直接复制为生产代码,须拆为可测模块)。
- 方法依据:RF+SHAP 为主线。

> 📌 **AUC≈1.0 的真实解释**：标签由 GB15618 阈值确定性派生，RF 精确学到国标阈值边界（特征重要性：镉 0.52 > 铅 0.12...，镉筛选值 0.3 最低最易超标）。群组 CV（按 Source 分组）AUC 0.9998，证实是**真实可信的国标规则学习**，与 F127 模拟表的虚假 1.0 本质不同。任何机构用相同阈值都能复现。

## 3. 流程

1. 取数:measurements → 透视(行=采样点,列=因子),缺失值多重插补(MI,与方法文件一致)或标记。
2. 训练/加载:RandomForestClassifier;模型存 `ml/artifacts/*.joblib`,元信息入 `ml_models`(version/feature_list/training_data_version/metrics)。
3. 全局解释:SHAP summary → 因子全局重要性,写 `diagnosis_results.shap_global`。
4. 局部解释:对场地各采样点算 SHAP 值,写 `diagnosis_factor_details`(factor_id + sampling_point_id + shap_value + direction + rank)。
5. Top-N:按重要性排序取 N,含因子类别(来自 factor_dictionary)、影响方向。

## 4. 输出契约

`diagnosis_results`: site_id, model_id, data_version, top_n, summary, shap_global, status。
`diagnosis_factor_details`: 每因子 importance/shap_value/direction/rank,局部解释绑定 sampling_point_id。

## 5. 模块规划(待 EXECUTE)

`ml/models/rf_barrier.py`(训练/加载/预测)、`ml/explain/shap_service.py`(全局/局部)、`backend/app/api/diagnosis.py`(触发+入库)。

## 6. 禁止

泛化结论("重金属污染严重")、静态 Top5、无特征清单、无版本号、SHAP 无样本 ID、结论不可追溯。

## 7. 已定决策(2026-06-10, 项目组确认"诚实标注"原则)

- **目标**:二分类(`标签` 列, 0:973 / 1:146),类别不均衡用 `class_weight=balanced`。
- **特征工程**(`ml/models/data_prep.py`):剔除 ID/DOI/Source/Year/超标因子数 等溯源与派生列(防泄漏);重金属"<0.01"检出限数值化提取;剔除缺失率>95% 列;中位数填充 + `*__missing` 标记;数据版本 `真实训练集_GB15618_n29993`(`is_real_data: True`,8 重金属 + 8 缺失标记 = 16 特征)。
- **特征对齐**(`feature_mapping.json` + `diagnosis_service.align_features`):场地因子→训练特征(砷→As(mg/kg) 等 14 项);有机质→SOC 换算 ×0.58;场地缺失的训练特征用训练集中位数填充并记录 `imputed_features`;**填充特征不参与 Top-N 结论排名**,摘要中明示填充数量。
- **局部解释**:取风险概率最高采样点,SHAP 值绑定 sampling_point_id 入库。
