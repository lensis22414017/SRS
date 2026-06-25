# SRS ML 模型说明 v1.0

## 模型概述

| 属性 | 值 |
|------|-----|
| 模型名称 | rf_barrier_factor |
| 最新版本 | v0.1_20260616 |
| 算法 | RandomForestClassifier |
| 训练数据 | **真实训练集_GB15618_n29993**（✅ 真实文献数据） |
| **is_real_data** | **True** ✅ |
| 标签来源 | GB15618-2018 农用地筛选值阈值派生 |
| 污染类型 | 重金属 (HM) |
| 训练时间 | 2026-06-16 |

> ✅ **数据真实性声明（2026-06-16 重建）**：
> 当前模型训练数据为 `data/raw/真实训练集_GB15618.csv`（29993 行，源自 `merged_std33,zh .xlsx` 真实文献数据，含 ID/DOI/Source/Year 溯源列），`is_real_data: True`。标签由 **GB15618-2018 农用地土壤污染风险筛选值（pH≤5.5 档）** 阈值派生：任一重金属（Cd/Pb/As/Cu/Zn/Ni/Cr/Hg）超筛选值 → 标签1（污染风险）。阈值来自知识库 ThresholdRule（standard_source=GB15618-2018），真实国标非编造。

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
| Accuracy | 0.999 |
| F1-Score | 0.9989 |
| ROC-AUC | 1.0 |
| Test Size | 5999 |
| 群组CV AUC(按Source) | 0.9998 ± 0.0003 |

> 📌 **AUC 接近 1.0 的真实解释（非虚高）**：
> 标签由 GB15618-2018 阈值**确定性派生**（任一重金属>筛选值→1），RF 精确学到了国标阈值边界（特征重要性：镉 0.52 > 铅 0.12 > 砷 0.10...，因镉筛选值 0.3 最低最易超标）。群组交叉验证（按 Source/文献分组，同文献不跨集）AUC 仍 0.9998，证实这是**真实可信的国标规则学习**，**与 F127 模拟表的虚假 1.0 本质不同**。任何机构用相同 GB15618 阈值都能复现此性能。

> ⚠️ **适用边界**：此模型学的是"国标阈值规则"，适用于**识别重金属是否超 GB15618 筛选值**的场景。若甲方需要识别"实际生态风险/作物超标"等更复杂标签，需用相应标准重派生标签重训。

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

1. **标签阈值派生性（如实标注）**：标签由 GB15618-2018 阈值确定性派生，RF 学到国标阈值边界 → AUC≈1.0 是预期且可复现的真实规则学习（群组 CV 0.9998 证实）。非模拟虚高，但意味着模型本质是"国标阈值识别器"，非独立生态风险预测。
2. **ID 泄漏已修复**：训练前剔除 ID/DOI/Source/Year/超标因子数 等唯一标识与溯源列（见 `dropped_leakage_cols`）。
3. **缺失处理**：重金属列含 "<0.01" 检出限等非数值，已数值化提取；缺失用中位数填充 + `__missing` 标记。
4. **时空代表性**：训练数据为全球文献汇编（merged_std33），地域覆盖广但分布不均，外推特定场地需谨慎。
5. **单标签 (HM)**：当前仅重金属场景（8 种），有机污染/复合污染需重派生标签重训。
6. **特征仅重金属**：当前 8 重金属 + 缺失标记共 16 特征，未含理化肥力/有机物（merged_std33 有但本轮未纳入，可扩展）。
