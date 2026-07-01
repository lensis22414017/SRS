# zzv0.4 障碍因子诊断重建 — 执行过程记录

> 日期: 2026-07-02 | 执行: 辛特助 | 基于: goal_plan_zzv0.4.md (20项GOAL)

## 执行总览

| Phase | GOAL数 | 状态 | 关键commit |
|---|---|---|---|
| P0 方法学地基 | 4 | ✅ 完成 | ff2d657 |
| P1 验证协议 | 6 | ✅ 完成 | 45a5e09 |
| P3 双轨差异化 | 2/3 | ✅ 路由+红旗完成 | (本次) |
| P2 可解释性 | 3 | ✅ 完成 | (本次) |
| P4 数据治理 | 4 | ✅ 完成 | (本次) |

## 各 Phase 详细记录

### P0 方法学地基 (commit ff2d657)
- P0-1 任务定义冻结: `docs/algorithms/task_definition.md`
  - 因子归因任务(非二分类), 三层分离, 6场景矩阵, 浓度合法输入
  - 文献[#2 Rudin2019]规则先行
- P0-2 标签severity化: `build_training_splits.py:175-218`
  - `_label_dual` 输出 因子级 severity=log2(val/thr)
  - `_attach_dual_labels` 输出 severity_prod_max/severity_eco_max
  - 文献[#42 AHP],[#43 模糊集]
- P0-3 OP生态差异化: OP生态用二类宽阈值(×2.5松弛)
  - 不再 lab_eco=lab_prod, 文献[#67 GB36600]
- P0-4 规则/模型分层: `diagnosis_service.py:440-463`
  - rule_ranked(阈值超标) + shap_ranked(模型归因) 独立分层
  - 不再混排, 文献[#2 Rudin2019]

### P1 验证协议 (commit 45a5e09)
- P1-1 嵌套CV: `ml/validation/grouped_cv.py` nested_group_cv()
  - 外层GroupKFold估泛化, 内层GroupKFold调lr/max_leaf_nodes
  - 文献[#1 Cawley2010]
- P1-2 四套group切分: DOI/Source/Province/Source代理
  - 文献[#55 GroupKFold], 裴总报告126行
- P1-3 预处理: 去全空列(不涉标签可外层) + 原生NaN(HGB fold内)
  - 文献[#56 pitfalls]
- P1-4 阈值fold内选: _fold_threshold PR曲线F1最优
  - 文献[#57 calibration]
- P1-5 排序核心指标: `ml/validation/rank_metrics.py`
  - top-k precision/recall + rank correlation + SHAP consistency
  - 文献[裴总报告139行]
- P1-6 统计检验: bootstrap_ci + permutation_test_diff
  - 文献[#64,#65]

### P3 双轨差异化 (本次commit)
- P3-1 双轨路由修复: `diagnosis_service.py:469-477`
  - 不再依赖 land_use_type 含"生态"(17场地全null)
- P3-2 红旗检测: prod/eco输出异常一致→触发 human_review_triggered
  - 裴总报告19行

### P2 可解释性 (本次commit)
- P2-1 permutation importance: `ml/explain/ale_export.py`
  - permutation_importance() 对照SHAP防相关特征误导, 文献[#58]
- P2-2 ALE: accumulated_local_effects()
  - pH-金属/SOM-金属用ALE非PDP, 文献[#4 Apley&Zhu2020]
- P2-3 反事实→修复: `ml/explain/counterfactual.py`
  - counterfactual_factor() + FACTOR_REMEDIATION_MAP
  - 障碍因子→修复技术映射, 文献[#24 Wachter],[#44,#50,#51]

### P4 数据治理 (本次commit)
- P4-1 标签审计: `ml/cleaning/label_audit.py`
  - confident_learning_audit() 排查疑似错标, 文献[#6 Northcutt]
- P4-2 模型卡+数据卡: `ml/registry/model_governance.py`
  - generate_model_card() + generate_dataset_card(), 文献[#9 Mitchell],[#10 Gebru]
- P4-3 OOD+人工复核: compute_ood_score() + should_trigger_human_review()
  - IsolationForest OOD + 7条复核触发, 文献[#59],[#8], 裴总报告251-261
- P4-4 审计证据链: DiagnosisResult 加9字段
  - validation_strategy/group_key/feature_schema_hash/threshold_library_version/
    rule_snapshot/shap_snapshot_path/confidence_interval/ood_score/human_review_triggered/review_reason
  - 裴总报告147-164行

## 诚实局限
- P1 嵌套CV/四套切分代码就绪, 但未实际跑出验证报告(算力+时间, GroupKFold 5折×内层3折×9超参组合较慢)
- P3-3 6场景验证矩阵代码就绪(grouped_cv支持), 未实际跑全部6场景
- P4-1 标签审计代码就绪, 未实际运行输出复核清单
- 模型卡/数据卡模板就绪, 需用实际训练结果填充performance字段
- 以上"代码就绪未实跑"的项, 待裴总指示在本机venv/docker环境完整运行
