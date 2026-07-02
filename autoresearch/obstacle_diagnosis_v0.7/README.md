# 障碍因子诊断 v0.7 — 干净建模工作区

> 本目录是障碍因子诊断模型重建的独立工作区。
> 从因子库/阈值库/数据清洗/GEE/特征/model-ready/split/训练/SHAP/验证全流程留痕。
> 每个阶段输出带时间戳(YYYYMMDD_HHMM)，保证可追溯。

## 目录结构

| 目录 | 阶段 | 内容 |
|---|---|---|
| 00_project_schema | 项目定义 | project/feature/target/track/split/artifact schema |
| 01_factor_threshold_library | 因子+阈值库 | master因子库/双轨阈值库/权重库/别名/字段映射 |
| 02_raw_manifest | 原始数据 | SHA256快照/列清单/只读声明 |
| 03_data_cleaning | 数据清洗 | 单位统一/检出限/异常值/重复样/别名归一 |
| 04_eda_qa | EDA+QA | 缺失率/因子覆盖/轨道覆盖/QA检查清单 |
| 05_gee_covariates | GEE审计 | 协变量清单/merge报告/enriched数据 |
| 06_feature_engineering | 特征工程 | 特征清单/泄露审计/engineered数据 |
| 07_model_ready_dataset | model-ready | 最终训练集/数据卡/目标分布报告 |
| 08_splits | 数据拆分 | GroupKFold/LeaveOneRegion/split manifest |
| 09_training_configs | 训练配置 | 模型搜索空间/指标/实验协议 |
| 10_experiments | 实验记录 | 每次训练的完整产物 |
| 11_models | 模型产物 | joblib/模型卡 |
| 12_shap_explainability | SHAP解释 | 全特征SHAP/因子组贡献/局部贡献 |
| 13_validation | 验证 | M-R共线性/消融/KOS_noM/bootstrap/OOD |
| 14_reports | 报告 | 方法学/训练总结/局限/执行汇总 |
| 15_frontend_exports | 前端导出 | 三层榜JSON/模型元数据 |
| logs | 日志 | 执行日志 |

## 核心原则

1. 规则判障碍，模型解释障碍指数，KOS综合五维
2. 主模型用全量真实特征拟合OI_t回归(含污染物浓度)
3. 共线性靠泄露控制+消融+M-R审计+KOS_noM敏感性，不删浓度
4. 未检测指标不进正式Top-N，列建议补测
5. 10个GATE全通过才允许P3训练

## GATE检查清单

- GATE_1: v0.7阈值库存在且生产/生态可读取
- GATE_2: factor_to_data_column_map已生成
- GATE_3: GEE/协变量审计完成
- GATE_4: model_ready_dataset已生成
- GATE_5: 泄露审计0个禁止字段
- GATE_6: OI_prod/OI_eco非常数
- GATE_7: split_manifest已生成
- GATE_8: 每个group split的group数满足最低要求
- GATE_9: 生产轨和生态轨非脚本错误导致完全相同
- GATE_10: P0-P2报告已修正
