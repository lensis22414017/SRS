# SRS ML 模型说明 v1.0

## 模型概述

| 属性 | 值 |
|------|-----|
| 模型名称 | rf_barrier_factor |
| 最新版本 | v0.1_20260616 |
| 算法 | RandomForestClassifier |
| 训练数据 | **模拟特征表_F127_n11690**（⚠️ 模拟数据，非真实） |
| **is_real_data** | **False** ⚠️ |
| 污染类型 | 重金属 (HM) — 字段对齐用 |
| 训练时间 | 2026-06-16 |

> ⚠️ **数据真实性声明（2026-06-15 peer-review 修正）**：
> 当前模型训练数据为 `data/raw/模拟特征表_F127_n11690.csv`（F1-F127 模拟物理特征，11690 行），**并非真实文献检测数据**。此前文件名为"真实数据集.csv"+版本标"真实_n1119"属命名误导，已正本清源。真实训练数据为 `data/raw/merged_std33,zh .xlsx`（41504×719，带 DOI/Source），后续将切换重建模型。

## 超参数

```json
{
  "n_estimators": 300,
  "class_weight": "balanced",
  "random_state": 42
}
```

## 模型指标

| 指标 | 值 |
|------|-----|
| Accuracy | 1.0 |
| F1-Score | 1.0 |
| ROC-AUC | 1.0 |
| Test Size | 2338 |

> 🚨 **AUC=1.0 虚高警告（必须如实告知甲方）**：
> 在模拟特征表（F1-F127）上 AUC=1.0 是**模拟数据的虚高**，原因：①标签由特征确定性派生（模拟生成规则）；②即便已剔除 ID 唯一标识列，AUC 仍为 1.0，证实标签与特征存在确定性关系。**此性能不可外推到真实场地**，真实数据模型 AUC 预期 0.7-0.9。

### 空间分组验证 (group_split)

| 分组策略 | Test N | Balanced Accuracy | Macro F1 | ROC-AUC |
|----------|--------|-------------------|----------|---------|
| id_DOI | 6913 | 0.9995 | 0.9994 | 1.0 |
| id_Source | 5926 | 0.9995 | 0.9995 | 1.0 |

**重要警告**: 行级/分组指标均接近 1，优先解释为阈值派生标签与污染物特征强绑定，不能当作独立真实性能证据。AUC 参考值为主，实际应用关注 SHAP 特征重要性排序的稳定性。

## 特征清单 (16 原始 + 15 缺失指示)

### 污染物特征 (12)
- Cr, Hg, As, Pb, Cu, Zn, Ni, Cd (重金属)
- OCPs, PAHs, PCBs, PAEs (有机污染物)

### 土壤属性特征 (4)
- SoilBD (容重), SoilpH, BackgroundSOC (背景有机碳)
- SandPerc, SiltPerc, ClayPerc (质地)
- Fertilization_T, OC_T, N_T, P_T, K_C, SWC_T (肥力/水分)

### 缺失指示特征 (15)
以 `__missing` 后缀标记对应特征的缺失状态。

## 文件清单

| 文件 | 说明 |
|------|------|
| rf_barrier_factor_v0.1_20260613.joblib | 模型权重文件 (~1MB) |
| rf_barrier_factor_v0.1_20260613.meta.json | 元数据 (特征/指标/参数) |
| rf_group_split_metrics.json | 空间分组验证结果 |

## 加载代码

```python
import joblib
import json

# 加载模型
model = joblib.load("ml/artifacts/rf_barrier_factor_v0.1_20260613.joblib")

# 加载元数据
with open("ml/artifacts/rf_barrier_factor_v0.1_20260613.meta.json") as f:
    meta = json.load(f)

features = meta["feature_list"]
medians = meta["medians"]

# 预测
import numpy as np
X = np.array([[medians.get(f, 0) for f in features]])
proba = model.predict_proba(X)
```

## 模型版本管理

模型文件命名规范: `{model_name}_{version}_{date}.joblib`

- `model_name`: rf_barrier_factor (随机森林障碍因子分类器)
- `version`: v0.1 (原型版本)
- `date`: YYYYMMDD (训练日期)

每次重新训练产生新的 .joblib + .meta.json 文件对，旧版本保留作为历史参考。

## 已知限制

1. **🚨 模拟数据虚高（最关键）**：当前训练数据为 F1-F127 模拟特征表（`is_real_data: False`），AUC=1.0 是模拟生成规则的确定性体现，**不可外推真实场地**。真实数据模型待用 `merged_std33,zh .xlsx` 重建。
2. **ID 泄漏已修复**：训练前已剔除 `ID/污染风险等级/土地利用类型/采样地类型/经度/纬度` 等唯一标识与标签派生列（见 `dropped_leakage_cols`），防 RF 学到伪规则。剔除后 AUC 仍 1.0 进一步证明模拟数据的标签派生性。
3. **标签派生性**：即便用真实数据，标签由阈值规则派生与特征强共线，AUC 仍可能偏高，不能当作独立泛化证据。
4. **缺失率偏高**：非污染物特征覆盖率有限，大量中位数填补。
5. **时空代表性有限**：真实数据以个旧重金属场地为主，外推需谨慎。
6. **单标签 (HM)**：当前仅重金属场景，有机/复合污染需重训。
