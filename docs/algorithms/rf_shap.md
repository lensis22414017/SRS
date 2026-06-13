# 障碍因子识别:RF + SHAP

**版本** v0.1 ·**日期** 2026-06-10 ·**作者** 辛特助 ·**状态** 草稿

## 1. 目标

从污染物、土壤理化、肥力、物理、生物指标中,识别制约生态/生产功能的关键障碍因子,输出 Top-N + 全局重要性 + 单场地局部解释,结果可追溯到检测值。

## 2. 数据来源

- 训练样机:`data/raw/真实数据集.csv`(1118 样本,标签=污染风险等级/二分类标签,特征=重金属 Cr/Hg/As/Pb/Cu/Zn/Ni/Cd + 有机物 OCPs/PAHs/PCBs/PAEs + 理化肥力)。
- 推理输入:某场地 `measurements` 长表透视为样本×因子矩阵。
- 样机参考:`参考文件/10.SHAP机器学习分析.ipynb`(不得直接复制为生产代码,须拆为可测模块)。
- 方法依据:年度报告(虚拟+真实数据集 AUC≥0.996,RF/SVM 等五模型对比,RF+SHAP 为主线)。

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

## 7. 已定决策(2026-06-10, 裴总确认"诚实标注"原则)

- **目标**:二分类(`标签` 列, 0:973 / 1:146),类别不均衡用 `class_weight=balanced`。
- **特征工程**(`ml/models/data_prep.py`):剔除缺失率>95% 列(CEC/EC_T/BS_T/Aggre_T),其余中位数填充 + `*__missing` 标记列,共 40 特征;数据版本 `真实数据集_20250731_n1119`。
- **特征对齐**(`feature_mapping.json` + `diagnosis_service.align_features`):场地因子→训练特征(砷→As(mg/kg) 等 14 项);有机质→SOC 换算 ×0.58;场地缺失的训练特征用训练集中位数填充并记录 `imputed_features`;**填充特征不参与 Top-N 结论排名**,摘要中明示填充数量。
- **局部解释**:取风险概率最高采样点,SHAP 值绑定 sampling_point_id 入库。
