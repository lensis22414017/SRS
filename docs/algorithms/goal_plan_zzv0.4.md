# 障碍因子诊断 zzv0.4 重建执行计划 (GOAL)

> 基于: 两份深度报告 + 70篇文献方法学综合 + zzv0.4整改方案
> 日期: 2026-07-02 | 执行: 辛特助 | 审批: 裴总
> 文献支撑: docs/references/障碍因子诊断_方法学综合报告.md

## 任务定义（裴总已确认，不可变）
- **本质**: 因子归因任务（RF+SHAP 识别哪些因子是障碍、障碍高度多少），不是二分类预测
- **用户输入**: 场地实测数据（measurements: 浓度+pH+理化）
- **核心输出**: Top-N 障碍因子排名 + SHAP贡献度 + 影响方向 + 不确定性 + 证据链
- **6 场景**: HM/OP/HM+OP × 生产/生态，每场景主导障碍因子不同（文献依据见综合报告矩阵）

---

## GOAL 执行清单（20项差距 → 可验收任务）

### Phase 0: 任务定义冻结 + 标签体系重建 [P0 方法学地基]
| ID | 任务 | 文件 | 验收标准 | 文献 |
|---|---|---|---|---|
| **P0-1** | 冻结任务定义文档 | 新建 `docs/algorithms/task_definition.md` | 写清: 因子归因非预测/三层分离/6场景矩阵/浓度是合法输入 | [#2 Rudin], 裴总报告 |
| **P0-2** | 标签从0/1→severity化 | `ml/etl/build_training_splits.py:175-204` | 每因子输出 `severity=log2((val+eps)/(thr+eps))`，加权severity，非仅0/1 | [#42 AHP],[#43 模糊] |
| **P0-3** | prod/eco标签差异化公式 | `build_training_splits.py:200-203` | OP生态轨拆分(不再lab_eco=lab_prod)；prod_score/eco_score不同权重组合 | [#26-28 生物可利用] |
| **P0-4** | 规则层/模型层分层呈现 | `diagnosis_service.py:445-453` | all_ranked不再混排，规则解释先行(threshold_exceedance)，SHAP归因次之 | [#2 Rudin] |

### Phase 1: 验证协议升级 [P1 评估严谨性]
| ID | 任务 | 文件 | 验收标准 | 文献 |
|---|---|---|---|---|
| **P1-1** | 嵌套CV(内调参/外评估) | `ml/models/rf_barrier.py:62-63` | train()改嵌套: 外层GroupKFold估泛化, 内层GroupKFold调参 | [#1 Cawley2010] |
| **P1-2** | 四套group切分并列 | 新建 `ml/validation/grouped_cv.py` | LeaveOneSiteOut/LeaveOneRegionOut/time/source 四套各跑一轮报分布 | [#55 GroupKFold] |
| **P1-3** | 预处理全进Pipeline | `build_clean_conc_features.py`拆分 | 清洗(可全量) vs 填充/缩放/筛选(fold内Pipeline)分离 | [#56 pitfalls] |
| **P1-4** | 阈值fold内选 | `rf_barrier.py:71` | 不用默认0.5, 内层valid集PR曲线选F_β最优 | [#57 calibration] |
| **P1-5** | 因子排序核心指标 | 新建 `ml/validation/rank_metrics.py` | top-k precision/recall + rank correlation + SHAP consistency, AUC仅健康指标 | 裴总报告139 |
| **P1-6** | 统计检验带CI | `rank_metrics.py` | 所有指标bootstrap 95%CI, 两轨差异permutation_test | [#64,#65] |

### Phase 2: 可解释性三层 [P2 解释深度]
| ID | 任务 | 文件 | 验收标准 | 文献 |
|---|---|---|---|---|
| **P2-1** | permutation importance | `ml/explain/shap_service.py`扩展 | SHAP旁并排permutation, 对照相关特征误导 | [#58] |
| **P2-2** | ALE(相关特征) | 新建 `ml/explain/ale_export.py` | pH-金属/SOM-金属用ALE非PDP | [#4 Apley2020] |
| **P2-3** | 反事实→修复建议 | 新建 `ml/explain/counterfactual.py` | "降低因子X的SHAP"→映射修复技术T | [#24 Wachter],[#44,#50] |

### Phase 3: 双轨差异化 + 6场景 [P3 场景落地]
| ID | 任务 | 文件 | 验收标准 | 文献 |
|---|---|---|---|---|
| **P3-1** | 双轨路由修复 | `diagnosis_service.py:462-463` | 不依赖land_use_type含"生态"(17场地全null), 改显式track参数 | [#26-28] |
| **P3-2** | 双轨红旗检测 | `diagnosis_service.py` | prod/eco输出异常一致时触发人工复核标记 | 裴总报告19 |
| **P3-3** | 6场景验证矩阵 | `ml/validation/grouped_cv.py` | 每场景(HM/OP/HM+OP×生产/生态)单独报top-k因子排名 | 综合报告矩阵 |

### Phase 4: 数据治理 + 审计 [P4 合规]
| ID | 任务 | 文件 | 验收标准 | 文献 |
|---|---|---|---|---|
| **P4-1** | confident learning标签审计 | 新建 `ml/cleaning/label_audit.py` | 每轮训练前排查疑似错标, 输出候选复核清单 | [#6 Northcutt] |
| **P4-2** | 模型卡+数据卡 | 新建 `artifacts/model_card.json`+`dataset_card.json` | Mitchell/Gebru模板, 含验证策略/局限/性能切片 | [#9,#10] |
| **P4-3** | OOD检测+人工复核触发 | `diagnosis_service.py` | IsolationForest OOD score + 7条复核触发政策落地 | [#59],[#8] |
| **P4-4** | 审计证据链字段补全 | `models/__init__.py` DiagnosisResult | 补 feature_schema_hash/threshold_version/rule_snapshot/shap_snapshot_path/ci_json/ood_score/human_review | [#9], 裴总报告147 |

---

## 执行原则
1. **每个 GOAL 独立可验收**: 完成1个就跑测试+提交, 不堆积
2. **文献可追溯**: 每个改动在代码注释/文档里引用文献编号
3. **诚实标注**: 模型卡写明局限(如生态轨proxy标签), 不伪造性能
4. **不破坏现有诊断**: 每次改动后 diagnosis_service 能正常运行
5. **浓度是合法输入**: 因子归因任务里浓度是用户实测, 不是泄漏

## 验收口径(对甲方)
甲方看到的不是"AI算分", 而是四块信息:
1. **验证方式**: GroupKFold(site_id) + LeaveOneRegionOut
2. **适用边界**: 污染类型/地区/采样年代/数据来源
3. **当前结论**: 双轨top-k障碍因子 + 置信区间
4. **审计证据**: 数据版本/模型版本/规则版本/解释快照

## 优先执行顺序
P0(方法学地基) → P1(验证协议) → P3(双轨差异化) → P2(可解释性) → P4(数据治理)
理由: P0/P1是地基, P3让6场景真正差异化, P2/P4是增强
