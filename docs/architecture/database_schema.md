# 数据库结构设计（Database Schema）

**项目名称**：污染场地土壤生态-生产功能重构监管系统
**文档版本**：v0.1（初稿）
**编写日期**：2026-06-10
**编写人**：辛特助
**数据库**：PostgreSQL 15+ / PostGIS 3+
**状态**：草稿，待裴总评审

> 设计原则：检测数据使用长表，避免污染物宽列无限扩展；阈值、用地类型、风险规则、权重、SSUI 参数、推荐规则、角色权限、报告模板版本、模型版本、标准来源、单位换算全部入库或入配置，不硬编码。

---

## 1. 设计总则

1. **长表优先**：检测值存 `measurements`，一条记录对应一个 (场地, 采样点, 因子)。新增 PFAS、抗生素、微塑料、TPH、PAHs 等无需改表结构。
2. **可追溯**：每条业务数据带来源（source_file / batch / 版本号）、创建/更新时间、操作人。
3. **版本化**：模型、评价参数、推荐规则、报告模板均带版本字段；结果表引用版本，便于回溯当时口径。
4. **软约束 + 字典**：用地类型、因子类别、风险等级、阶段名等用字典/枚举管理，不散落在代码里。
5. **审计**：所有写操作进 `audit_logs`。
6. **多租户隔离**：场地归属 `organization_id`，企业用户只能访问本企业数据（应用层 + 行级过滤）。

---

## 2. 实体分组

| 分组 | 表 |
|---|---|
| 权限与组织 | organizations, users, roles, permissions, user_roles, role_permissions |
| 场地与检测（核心） | sites, sampling_points, factor_dictionary, threshold_rules, measurements |
| 算法与评价 | ml_models, diagnosis_results, diagnosis_factor_details, evaluation_results |
| 推荐与技术库 | technology_library, recommendations |
| 追溯与报告 | workflow_records, workflow_attachments, report_records |
| 系统与文件 | audit_logs, file_objects, import_batches |

---

## 3. ER 关系（文字描述）

```
organizations 1—N users
users N—M roles (user_roles)；roles N—M permissions (role_permissions)
organizations 1—N sites
sites 1—N sampling_points
sampling_points 1—N measurements
factor_dictionary 1—N measurements（factor_id）
factor_dictionary 1—N threshold_rules
sites 1—N import_batches；import_batches 1—N measurements（batch 溯源）
sites 1—N diagnosis_results；diagnosis_results 1—N diagnosis_factor_details
ml_models 1—N diagnosis_results
sites 1—N evaluation_results（type: reconstruction_prod / reconstruction_eco / ssui）
sites 1—N recommendations；recommendations N—1 technology_library；recommendations N—1 diagnosis_factor_details（绑定障碍因子）
sites 1—N workflow_records（stage 五阶段）；workflow_records 1—N workflow_attachments → file_objects
sites 1—N report_records
所有写操作 → audit_logs
```

---

## 4. 核心表定义

> 通用列：`created_at timestamptz default now()`、`updated_at timestamptz`、必要处 `created_by bigint`（→ users.id）。主键统一 `id bigserial`，下文从略。

### 4.1 organizations 企业/机构

| 字段 | 类型 | 说明 |
|---|---|---|
| name | varchar(200) | 名称 |
| org_type | varchar(20) | enterprise / agency / regulator / admin |
| credit_code | varchar(50) | 统一社会信用代码（可空） |
| status | varchar(20) | active/disabled |

### 4.2 users 用户

| 字段 | 类型 | 说明 |
|---|---|---|
| username | varchar(80) unique | 登录名 |
| password_hash | varchar(255) | bcrypt/argon2 哈希，禁止明文 |
| display_name | varchar(120) | 显示名 |
| organization_id | bigint FK | 所属企业/机构 |
| email / phone | varchar | 联系方式（可空） |
| status | varchar(20) | active/locked/disabled |
| last_login_at | timestamptz | 最近登录 |

### 4.3 roles / permissions / user_roles / role_permissions

- `roles`：name（系统管理员/企业用户/第三方机构/监管人员）、code、description。
- `permissions`：code（如 data:import、data:export、report:generate、user:manage、model:manage、tech:manage…）、name、category。
- `user_roles`：user_id, role_id。
- `role_permissions`：role_id, permission_id。

权限维度至少覆盖：数据录入/查询/导出/归档、报告生成、地图查看、全流程查看、文档下载、用户管理、角色管理、日志审计、参数设置、模型管理、技术库管理。

### 4.4 sites 场地

| 字段 | 类型 | 说明 |
|---|---|---|
| site_code | varchar(50) unique | 场地编号（如 A-2024-001） |
| name | varchar(200) | 场地名称 |
| organization_id | bigint FK | 归属企业 |
| pollution_type | varchar(20) | heavy_metal/organic/composite |
| land_use_type | varchar(50) | 用地类型（字典） |
| risk_level | varchar(30) | 污染风险等级（如 Ⅰ类(安全) 等） |
| province / city / district | varchar | 行政区划 |
| geom | geometry(Point,4326) | 场地中心点（PostGIS） |
| longitude / latitude | numeric | 冗余存储便于展示 |
| area | numeric | 面积（可空） |
| description | text | 描述 |
| status | varchar(20) | 数据状态 |

### 4.5 sampling_points 采样点

| 字段 | 类型 | 说明 |
|---|---|---|
| site_id | bigint FK | 所属场地 |
| point_code | varchar(50) | 采样点编号 |
| geom | geometry(Point,4326) | 点位 |
| longitude / latitude | numeric | 经纬度 |
| depth_top_cm / depth_bottom_cm | numeric | 采样深度上下限 |
| soil_type | varchar(80) | 土壤类型 |
| region | varchar(120) | 区域 |
| sampled_at | date | 采样日期 |

唯一约束：(site_id, point_code)。

### 4.6 factor_dictionary 因子字典（来源：统一障碍因子知识库 V1.0）

| 字段 | 类型 | 说明 |
|---|---|---|
| factor_code | varchar(60) unique | 因子代码（如 As、PAHs、pH） |
| factor_name | varchar(120) | 因子名称（中文） |
| level1_category | varchar(40) | 化学性质/物理性质/环境指标/肥力指标/生物指标 |
| factor_type | varchar(30) | pollutant/physical/chemical/fertility/biological |
| default_unit | varchar(30) | 默认单位（mg/kg 等） |
| description | text | 说明 |
| source | varchar(100) | 来源标注 |

### 4.7 threshold_rules 阈值规则（来源：知识库 + 障碍因子集）

| 字段 | 类型 | 说明 |
|---|---|---|
| factor_id | bigint FK | → factor_dictionary |
| application_scenario | varchar(120) | 应用场景（如"水田用地"） |
| applicable_scope | varchar(30) | production/ecology |
| land_type | varchar(60) | 用地类型 |
| threshold_min | numeric | 下限（可空） |
| threshold_max | numeric | 上限（可空） |
| unit | varchar(30) | 单位 |
| threshold_original | text | 原始阈值描述 |
| standard_source | varchar(200) | 标准来源（如 TD/T1036-2013） |
| version | varchar(20) | 规则版本（默认 V1.0） |

> ⚠️ **重要数据事实(经核查知识库 V1.0)**：生产用地污染物行的 `threshold_min/threshold_max` 列实际存的是 **pH 分段断点(5.5/6.5/7.5)**，真正的浓度限值写在 `threshold_original` 文本里(如"pH≤5.5时，≤30mg/kg")，且同一因子分"水田/果园用地"与"其他用地"两套。生态用地行的 min/max 才是直接浓度。因此判定污染物是否超标**不能直接比较 min/max**，必须解析 `threshold_original` + 结合样点实测 pH。该逻辑已实现于 `backend/app/services/threshold_resolver.py`，供数据校验与污染物分等赋值共用。

### 4.8 measurements 检测值（长表，核心）

| 字段 | 类型 | 说明 |
|---|---|---|
| site_id | bigint FK | 场地 |
| sampling_point_id | bigint FK | 采样点 |
| factor_id | bigint FK | 因子 |
| value | numeric | 检测值 |
| unit | varchar(30) | 单位 |
| method | varchar(120) | 检测方法（可空） |
| is_below_detection | boolean | 是否低于检出限 |
| source_file | varchar(300) | 来源文件名 |
| import_batch_id | bigint FK | 导入批次 |
| detected_at | date | 检测/采样时间 |

索引：(site_id, factor_id)、(sampling_point_id)、(import_batch_id)。
约束：原始检测值禁止 UPDATE 改值（仅追加/标记作废，规则在应用层 + 审计层保障）。

### 4.9 import_batches 导入批次（溯源）

| 字段 | 类型 | 说明 |
|---|---|---|
| site_id | bigint FK | 场地 |
| source_file | varchar(300) | 源文件 |
| mapping_snapshot | jsonb | 字段映射快照 |
| row_count | int | 行数 |
| valid_count / invalid_count | int | 校验通过/失败数 |
| validation_report | jsonb | 校验报告 |
| script_version | varchar(30) | 处理脚本版本 |
| status | varchar(20) | success/partial/failed |
| imported_by | bigint FK | 操作人 |

### 4.10 ml_models 模型版本

| 字段 | 类型 | 说明 |
|---|---|---|
| model_name | varchar(80) | 如 rf_barrier_factor |
| version | varchar(30) | 模型版本 |
| algorithm | varchar(40) | RandomForest |
| feature_list | jsonb | 特征清单 |
| training_data_version | varchar(60) | 训练数据版本 |
| metrics | jsonb | 准确率/F1/AUC 等 |
| artifact_path | varchar(300) | joblib 路径（对象存储/本地） |
| trained_at | timestamptz | 训练时间 |

### 4.11 diagnosis_results 诊断结果

| 字段 | 类型 | 说明 |
|---|---|---|
| site_id | bigint FK | 场地 |
| model_id | bigint FK | 使用模型 |
| data_version | varchar(60) | 输入数据版本 |
| top_n | int | Top-N 数量 |
| summary | text | 结论说明 |
| shap_global | jsonb | 全局重要性数据 |
| status | varchar(20) | 状态 |

### 4.12 diagnosis_factor_details 诊断因子明细

| 字段 | 类型 | 说明 |
|---|---|---|
| diagnosis_id | bigint FK | → diagnosis_results |
| factor_id | bigint FK | 因子 |
| sampling_point_id | bigint FK | 局部解释对应样本（可空=全局） |
| importance | numeric | 重要性 |
| shap_value | numeric | SHAP 值 |
| direction | varchar(10) | positive/negative 影响方向 |
| rank | int | 排名 |

### 4.13 evaluation_results 评价结果（重构可行性 + SSUI 共用）

| 字段 | 类型 | 说明 |
|---|---|---|
| site_id | bigint FK | 场地 |
| eval_type | varchar(30) | reconstruction_prod / reconstruction_eco / ssui |
| data_version | varchar(60) | 输入数据版本 |
| param_version | varchar(30) | 指标体系/权重/参数版本 |
| score | numeric | 综合得分/指数 |
| grade | varchar(40) | 等级 |
| dimensions | jsonb | 维度分（安全/经济等）、指标分项 |
| weights | jsonb | 权重快照（来源可追溯） |
| limiting_factors | jsonb | 关键限制因子 |
| risk_factors | jsonb | 风险因子（SSUI） |
| explanation | text | 解释文本 |

### 4.14 technology_library 重构技术库

| 字段 | 类型 | 说明 |
|---|---|---|
| tech_name | varchar(150) | 技术名称 |
| applicable_pollutants | jsonb | 适用污染物 |
| applicable_soil | text | 适用土壤条件 |
| applicable_land_type | jsonb | 适用用地类型 |
| applicable_stage | varchar(60) | 适用阶段 |
| advantages / limitations | text | 优点 / 局限 |
| cost_level | varchar(20) | 成本等级 |
| duration_level | varchar(20) | 工期等级 |
| secondary_risk | text | 二次风险 |
| forbidden_conditions | text | 禁用条件 |
| source | varchar(200) | 标准/文献/经验来源 |

### 4.15 recommendations 方案推荐

| 字段 | 类型 | 说明 |
|---|---|---|
| site_id | bigint FK | 场地 |
| technology_id | bigint FK | → technology_library |
| diagnosis_factor_id | bigint FK | 绑定的障碍因子明细 |
| rule_version | varchar(30) | 推荐规则版本 |
| match_score | numeric | 匹配度 |
| reason | text | 结构化推荐理由 |
| rank | int | 排序 |

### 4.16 workflow_records 五阶段追溯记录

| 字段 | 类型 | 说明 |
|---|---|---|
| site_id | bigint FK | 场地 |
| stage | varchar(30) | survey/approval/construction/effect/maintenance |
| status | varchar(20) | not_started/in_progress/completed/returned |
| operator_id | bigint FK | 操作人 |
| operated_at | timestamptz | 操作时间 |
| review_comment | text | 审批意见/记录 |
| version | varchar(20) | 版本号 |
| data_source | varchar(200) | 数据来源 |
| is_completed | boolean | 是否完成 |
| is_returned | boolean | 是否退回 |
| advanced_to_next | boolean | 是否进入下一阶段 |
| payload | jsonb | 阶段专属字段（施工单位/进度/检测数据等） |

### 4.17 workflow_attachments 阶段附件

| 字段 | 类型 | 说明 |
|---|---|---|
| workflow_record_id | bigint FK | → workflow_records |
| file_object_id | bigint FK | → file_objects |
| file_role | varchar(60) | 材料类型（调查报告/台账/检测数据等） |

### 4.18 report_records 报告记录

| 字段 | 类型 | 说明 |
|---|---|---|
| site_id | bigint FK | 场地 |
| report_type | varchar(40) | traceability/diagnosis |
| version | varchar(20) | 报告版本号 |
| data_snapshot | jsonb | 生成时数据版本快照 |
| template_version | varchar(20) | 模板版本 |
| file_object_id | bigint FK | 生成的 PDF 文件 |
| generated_by | bigint FK | 生成人 |
| generated_at | timestamptz | 生成时间 |

### 4.19 file_objects 文件对象

| 字段 | 类型 | 说明 |
|---|---|---|
| storage_key | varchar(400) | MinIO/本地存储 key |
| original_name | varchar(300) | 原始文件名 |
| content_type | varchar(120) | MIME |
| size_bytes | bigint | 大小 |
| sha256 | varchar(64) | 校验和 |
| organization_id | bigint FK | 归属（权限） |

### 4.20 audit_logs 审计日志

| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | bigint FK | 操作人 |
| action | varchar(80) | 操作行为（login/import/export/generate_report…） |
| resource_type / resource_id | varchar/bigint | 操作对象 |
| result | varchar(20) | success/fail/denied |
| ip / user_agent | varchar | 来源 |
| detail | jsonb | 详情 |
| created_at | timestamptz | 时间 |

---

## 5. 枚举与字典（入库/配置，不硬编码）

- pollution_type：heavy_metal / organic / composite
- eval_type：reconstruction_prod / reconstruction_eco / ssui
- workflow.stage：survey / approval / construction / effect / maintenance
- workflow.status：not_started / in_progress / completed / returned
- factor_dictionary.level1_category：化学性质 / 物理性质 / 环境指标 / 肥力指标 / 生物指标
- risk_level、land_use_type、单位换算规则：单独字典表或配置文件（待确认取值口径）

---

## 6. 迁移与初始化

- 使用 Alembic 管理迁移；PostGIS 扩展 `CREATE EXTENSION postgis`。
- 初始化脚本导入：factor_dictionary + threshold_rules（来自知识库 V1.0 CSV）、roles/permissions 基础数据、4 个演示角色账号。
- 真实样本导入走 import_batches → measurements 流程，原始 Excel 仅入 /data/raw 留档，不改值。

## 7. 待确认问题

1. SSUI 与重构评价的指标分项/权重是否进 `evaluation_results.dimensions/weights` 的 jsonb，还是需要独立指标体系表（更利于配置管理）？
2. 是否两周内启用 PostGIS/MinIO，还是 MVP 先用 numeric 经纬度 + 本地文件存储（降低部署复杂度）？
3. `risk_level`、`land_use_type` 的标准取值清单来源（甲方/国标）？
4. 原始检测值"禁止改值"是否需要数据库触发器强约束，还是应用层 + 审计即可？

## 8. 变更记录

| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-06-10 | 初稿，核心 20 表 + 长表设计 | 辛特助 |
