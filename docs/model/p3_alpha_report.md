# P3-Alpha 双轨障碍指数回归模型验证报告

> 生成时间:2026-07-02
> 数据版本:Gold Dataset v0.8(READY_FOR_P3.flag 已生成)
> 训练脚本:`scripts/run_p3_alpha_training.py`
> 核心模块:`ml/models/p3_regression_trainer.py` + `ml/explain/shap_service.py`
> 规范来源:`training_protocol_v0.8.md` / `metrics_config_v0.8.yaml` / `docs/references/污染场地障碍因子诊断双轨方法学...md` / `docs/acceptance/acceptance_criteria.md`

---

## 一、训练范围与放行口径

| 子集 | production | ecology | 说明 |
|---|---|---|---|
| **all** | ✅ 主模型 | ✅ 主模型 | 放行训练 + 消融 |
| **hm** | ✅ 主模型 | ✅ 主模型 | 放行训练 |
| **op** | ✅ 主模型(信号弱) | ✅ 主模型(信号弱) | split 已修复,但 test 非零样本少 |
| **hm_op** | ❌ 不训练 | ❌ 不训练 | 仅外部案例(244样本) |

消融实验(Full / MeasuredOnly / ContextOnly)仅在 all 子集上执行(节省算力)。

---

## 二、主模型指标(test 集,Full 消融)

主指标:**Spearman ρ / MAE / R²**(回归三件套,不报 AUC/Accuracy 作主指标)。

| 子集 | 轨 | 模型 | 特征数 | n_test | Spearman ρ | 95% CI | MAE | R² | Top-5 入榜率 |
|---|---|---|---|---|---|---|---|---|---|
| all | prod | RF | 110 | 5407 | **0.9616** | [0.959, 0.964] | 0.0516 | 0.7957 | 1.00 |
| all | eco | RF | 110 | 5407 | **0.9651** | [0.962, 0.968] | 0.0424 | 0.7781 | 0.95 |
| hm | prod | RF | 110 | 4126 | **0.9680** | [0.965, 0.971] | 0.0469 | 0.8085 | 1.00 |
| hm | eco | RF | 110 | 4126 | **0.9582** | [0.954, 0.962] | 0.0445 | 0.7372 | 1.00 |
| op | prod | RF | 110 | 796 | **0.7695** | [0.695, 0.834] | 0.0078 | 0.6893 | 0.90 |
| op | eco | RF | 110 | 796 | **0.6616** | [0.603, 0.712] | 0.0148 | 0.7006 | 1.00 |

**模型选择**:3 候选(RF/ExtraTrees/HGB)经 GroupKFold 3 折 CV,RandomForest 在所有组合中 Spearman 均值最高(all/prod: RF 0.934 vs ET 0.797 vs HGB 0.799),故全部主模型选用 RandomForest。

**Top-5 入榜率**:除 all/eco(0.95)和 op/prod(0.90)外均达 1.00,满足方法学要求(≥0.70)。

---

## 三、消融实验(all 子集,验证 M-R 共线性处理)

| 子集/轨 | 消融段 | 特征数 | Spearman ρ | MAE | R² | 解读 |
|---|---|---|---|---|---|---|
| all/prod | **Full** | 110 | 0.9616 | 0.0516 | 0.7957 | 基线 |
| all/prod | MeasuredOnly | 91 | **0.9676** | 0.0461 | **0.8346** | 实测特征已足够,移除 GEE 反而提升 |
| all/prod | ContextOnly | 69 | **0.3110** | 0.1533 | -0.0349 | 仅背景协变量无法预测障碍 |
| all/eco | **Full** | 110 | 0.9651 | 0.0424 | 0.7781 | 基线 |
| all/eco | MeasuredOnly | 91 | **0.9695** | 0.0376 | **0.8149** | 实测特征主导 |
| all/eco | ContextOnly | 69 | **0.3254** | 0.1272 | -0.0155 | 仅背景无法预测 |

**关键结论**:实测污染物浓度特征是障碍指数的核心驱动力;GEE 背景协变量单独无法预测(ContextOnly Spearman≈0.31,接近随机)。这证明模型确实在学习污染物-障碍关系,而非地理背景捷径。

---

## 四、SHAP 模型贡献度分析(AC-10)

> ⚠️ **SHAP 是模型贡献度,不是法规判断,不是因果强度,不是天然障碍高度**(方法学行 146)。

### 4.1 关键风险:缺失指示器主导(必须诚实暴露)

| 子集/轨 | SHAP Top-1 | 占比 | 性质 |
|---|---|---|---|
| all/prod | 缺失指示_gee_nitrogen_g_kg | 21.9% | ⚠️ 缺失模式 |
| all/eco | 缺失指示_gee_nitrogen_g_kg | 33.2% | ⚠️ 缺失模式 |
| hm/prod | 缺失指示_gee_soil_pH | 31.7% | ⚠️ 缺失模式 |
| hm/eco | 缺失指示_gee_soil_pH | 40.4% | ⚠️ 缺失模式 |
| op/prod | GEE_gee_soc_g_kg | 95.4% | 背景协变量 |
| op/eco | GEE_gee_soc_g_kg | 85.2% | 背景协变量 |

**问题诊断**:all/hm 模型的 SHAP 贡献度前 1-2 名是"缺失指示器"(`x_missing_*`),而非实测污染物。这意味着模型部分通过"某个测量是否缺失"来推断障碍——**缺失模式本身编码了场地类型/来源信息**,构成隐性捷径。

**污染物真实贡献**(剔除缺失指示器后的实测因子排名):
- all/prod:Cd_mgkg(9.7%)> As_mgkg(7.0%)> Zn_mgkg(4.2%)
- all/eco:Cd_mgkg(6.0%)> As_mgkg(5.1%)
- hm/prod:Cu_mgkg(8.5%)> Pb_mgkg(7.7%)> Zn_mgkg(7.5%)> Cd_mgkg(3.0%)
- op/prod:As_mgkg(2.3%)+ PAHs_total(1.2%)—— OP 信号极弱

### 4.2 OP 子集的特殊性
OP 模型 SHAP 由 GEE_gee_soc_g_kg 主导(85-95%),而非缺失指示器。这是因为 OP 样本少(3330 train)且障碍信号稀疏(9% nonzero),模型退化为依赖土壤有机碳背景。OP 指标参考价值有限。

### 4.3 SHAP 局部解释(AC-10 合规)
所有主模型已生成 `_shap_local.parquet`,**绑定 sample_id**(非行号),每样本 top-15 因子贡献。满足 AC-10"全局重要性 + 绑定样本 ID 的局部解释"。

---

## 五、验证矩阵覆盖(方法学 10 维,P3-Alpha 覆盖 5 维)

| 验证维度 | P3-Alpha 覆盖 | 结果 |
|---|---|---|
| 外层泛化(test 集) | ✅ | Spearman 0.66-0.97 + bootstrap CI |
| 来源泛化(跨 source 组) | ✅ | grouped_stability_std 0.02-0.55 |
| 场景泛化(all/hm/op) | ✅ | all≈hm > op(信号差异) |
| 排名稳定性(bootstrap) | ✅ | Top-5 入榜率 0.90-1.00 |
| 解释对照(SHAP) | ✅ | global + local + 消融对比 |
| 区域泛化(LORO) | ⏳ P4 | province 652 类,本轮 skipped |
| 阈值调优(内层 CV) | ⏳ P4 | 本轮用默认超参 |
| 标签质量(CL) | ⏳ P4 | — |
| OOD 检测 | ⏳ P4 | — |
| 双轨一致性 | ✅ 部分 | prod/eco Top 因子有差异(hm:Cu/Pb/Zn vs 待eco分析) |

---

## 六、诚实声明(不美化)

### 6.1 site-level 泛化未验证
本阶段验证为 **source-level**(按文献来源 GroupKFold)。site_id 在本数据中≈逐样本唯一,不构成真正场地组。**不宣称 site-level 场地泛化**。site-level 验证需后续真实场地数据接入。

### 6.2 分布漂移
all 子集 test 集 OI mean(0.15)显著高于 train(0.07)——test source 群体障碍率系统性更高。Spearman 指标不受均值漂移影响(秩相关),但 MAE 绝对值需结合此背景解读。

### 6.3 OP 子集局限
- OP test 非零样本仅 47 个(<50),test 指标参考价值有限
- OP SHAP 由 GEE 背景主导,非污染物因果
- OP 模型建议仅作探索,不作为 OP 场地的正式诊断依据

### 6.4 缺失指示器泄露风险(最重要)
**all/hm 模型的 SHAP Top-1 是缺失指示器**,暗示模型利用了"测量缺失模式"这一隐性特征。这在 KOS 引擎构建时必须处理:
- P4 建议:对缺失指示器做 M-R 共线性审计,或从 M(模型贡献度)中分离缺失贡献
- 或:KOS 的 M 仅取实测因子的 SHAP,缺失指示器不计入 Top-N(符合证据等级 A/B 才进 Top-N 的规则)

### 6.5 持久化合规(红线 #4)
全部产物已持久化到 `ml/artifacts/p3_alpha/`:
- 10 个 `_metrics.json`(指标)
- 6 个 `_shap_global.parquet` + 6 个 `_shap_local.parquet`(SHAP)
- 6 个 `.joblib`(模型)
- `p3_alpha_summary.csv`(汇总)
不伪造性能,所有指标真实可复现。

---

## 七、产物清单

```
ml/artifacts/p3_alpha/
├── {subset}_{track}_{ablation}_{model}.joblib       # 模型(10个)
├── {subset}_{track}_{ablation}_{model}_metrics.json # 指标(10个)
├── {subset}_{track}_Full_RandomForest_shap_global.parquet  # SHAP global(6个主模型)
├── {subset}_{track}_Full_RandomForest_shap_local.parquet   # SHAP local(6个)
├── {subset}_{track}_Full_RandomForest_shap_meta.json       # SHAP meta(6个)
└── p3_alpha_summary.csv                              # 汇总
```

---

## 八、下一步(P4)

1. **KOS 引擎**:基于本轮 SHAP 的 M(模型贡献度),结合 B(规则)/R(严重度)/W(权重)/S(稳定性)/E(证据等级),实现 `KOS = B·(0.30R+0.25W+0.15M+0.20S+0.10E)`
2. **缺失指示器处理**:M-R 共线性审计,决定缺失贡献是否计入 KOS
3. **三层输出**:明确障碍(规则)+ 关键障碍(KOS 排序)+ 建议补测
4. **前端集成**:生产/生态独立页面接入 SHAP 解释

---

## 九、规范合规检查

| 规范 | 状态 | 证据 |
|---|---|---|
| 主指标 spearman/mae/r2 | ✅ | 本报告 §二 |
| 不报 AUC 作主指标 | ✅ | 无 AUC 主指标 |
| GroupKFold(source_id)不随机 | ✅ | trainer CV + split_audit |
| SHAP 全特征含浓度 | ✅ | 未删任何浓度特征 |
| SHAP 称"模型贡献度" | ✅ | §四标题与声明 |
| SHAP local 绑 sample_id | ✅ | _shap_local.parquet |
| 消融 Full/MeasuredOnly/ContextOnly | ✅ | §三 |
| bootstrap CI | ✅ | §二 95% CI |
| Top-5 入榜率 ≥0.70 | ✅ | 0.90-1.00 |
| 产物持久化(红线#4) | ✅ | §七 |
| site-level 不宣称 | ✅ | §6.1 |
| 不伪造性能(红线#10) | ✅ | 全部真实可复现 |
