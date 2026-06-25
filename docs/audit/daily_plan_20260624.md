# 每日开发计划 — 2026-06-24

[MODE: PLAN]

**辛特助** 巡检报告 | 日期：2026-06-24 | 当前模式：PLAN

---

## 昨日完成（2026-06-23，共 15 次提交）

| 提交 | 内容 |
|---|---|
| d253cfc | feat(data): GB36600有机阈值权威锚定+鲁棒性测试+OCR合规纠正 |
| 23919e2 | docs(audit): 竞品对比+深度完善清单 |
| c1472d5 | feat(eda)+test: 环形图(类别分布)+深度功能测试全通过 |
| 7fbf636 | feat(model): 三块+数据湖RF训练（双轨8模型，AUC>0.9） |
| f24b3a2 | feat(training): 三块训练数据切分+GB36600 OCR脚本 |
| f4688d5 | feat(op): 有机阈值补充，autoresearch overall 0.56→0.99 |
| 8e41698 | test+fix: 同行评审修订（持久单测+评价累积上限+SSUI race） |
| b79e705 | docs: 同行评审报告（全链路修复 Minor Revisions 通过） |
| 更多... | 全链路修复 9 条线全部收尾 |

**今日已产出**（截至巡检时）：
- `docs/audit/SRS_COMPETITIVE_INCREMENT_20260624.md`（双轨能力报告）
- `docs/audit/external_covariate_datasets_20260624.md`（H4 外部协变量数据集检索清单）

---

## 当前仓库状态

### MVP 闭环进度

| 环节 | 状态 | 说明 |
|---|---|---|
| 数据导入 | ✅ 已通 | import_service + 字段映射 + 幂等 + 版本链，brief 4.1 通过 |
| 数据校验 | ✅ 已通 | validation_service + qc_service（RPD/加标回收） |
| 场地详情 | ✅ 存在 | SiteDetail.tsx，但 land_use_type 只展示不可编辑 |
| 障碍因子识别 | ⚠️ 部分 | rf_barrier.py 已通；双轨路由 _track_map 存在但前端无入口设置 |
| RF/SHAP 解释 | ⚠️ 部分 | shap_service.py 已有；HM 块 AUC 虚高已诚实标注，E③待外部数据 |
| 功能重构评价 | ✅ 已通 | reconstruction.py + evaluation_service + 追加式，SSUI race 已修 |
| SSUI 评价 | ⚠️ 缺口 | HM 场地通过；OP(有机)场地 SSUI=None（Exp#004 待修） |
| 方案推荐 | ✅ 已通 | recommend_service + 技术库 + GB36600 有机技术路线 overall=0.99 |
| 全流程追溯 | ✅ 存在 | workflow.py + TraceDetail.tsx，五阶段架构 |
| PDF 报告 | ✅ 存在 | report_service.py + traceability_report.html |
| 操作日志 | ✅ 存在 | audit_service.py，写操作有记录 |

### 已知阻塞项

1. **C 前端双轨 UI**（land_use_type 无选择入口）— 直接影响甲方演示
2. **Exp#004 OP-SSUI**（有机场地 SSUI=None）— MVP 闭环断点
3. **测试环境**（/usr/bin/python 无 pytest）— 需通过 backend/.venv 运行

---

## 今日最重要 3 个目标

---

### 目标 1：前端双轨用地类型选择 UI（C）

**为什么最高优先级：**
双轨（生产/生态）是 SRS 核心差异化能力，后端路由已完成（diagnosis_service 第 271-272 行），但前端无入口让用户设置 land_use_type。甲方演示时用户无法触发双轨切换。

**文件路径：**

```
1. [frontend/src/pages/SiteDetail.tsx] 将 land_use_type 展示改为可编辑 Select
   - 原因：第 57 行只有展示，需加内联编辑（Ant Design Descriptions + Select）
   - 具体改动：
     · 增加 land_use_type 枚举值：["生产", "生态", "生产/生态复合"]
     · 展示改为 Editable Select，onChange 时调用后端接口
     · 修改后立即重触发诊断按钮提示（"用地类型已更新，建议重新运行诊断"）
   - 影响范围：SiteDetail 页面 UI，不影响后端逻辑
   - 验证方式：改为"生产"→点诊断→确认 diagnosis_service 输出 track=prod；改为"生态"→输出 track=eco
   - 失败回滚：仅改前端展示，不影响后端，可直接 revert

2. [backend/app/api/data.py] 确认或新增 PATCH /sites/{site_id} 接口
   - 原因：前端 onChange 需要 API 保存 land_use_type，当前 data.py 无 PATCH 接口
   - 具体改动：
     · 添加 @router.patch("/sites/{site_id}") 接口，接受 {land_use_type: str}
     · 校验枚举值（生产/生态/生产生态复合）
     · 写入 audit_log（"更新用地类型"）
   - 影响范围：data.py API 层 + audit_log
   - 验证方式：curl PATCH /sites/1 {"land_use_type":"生产"}，DB 中 site.land_use_type 更新
   - 失败回滚：删除新增 PATCH 路由，不影响其余接口

3. [frontend/src/pages/DataUpload.tsx] 导入时增加用地类型选择
   - 原因：场地新建时应能设置 land_use_type，否则所有新导入场地初始为 None（路由失败）
   - 具体改动：
     · 在导入配置表单里增加 Select "用地类型"（默认"生产"，可选"生态"/"复合"）
     · 导入后调用 PATCH 接口写入 site.land_use_type
   - 验证方式：上传真实数据 xlsx → 选"生产" → 诊断 → SHAP 使用 prod 模型
   - 失败回滚：移除该 Select，不影响导入主流程
```

**风险：**
- data.py 可能已有类似接口但命名不同，执行前先 grep 确认
- SiteDetail 需要确认是否已有内联编辑模式，避免重复实现

---

### 目标 2：有机场地 SSUI 修复（Exp#004）

**为什么高优先级：**
autoresearch 发现北京/海南 OP(有机污染)场地 SSUI=None，导致 ssui_valid=0.867（未满分）。有机场地是真实数据集之一（`2.20250731_有机污染场地数据表(南京栖霞)`），必须完成全链路。

**文件路径：**

```
1. [ml/evaluation/ssui.py] 补充有机污染物的 C1 安全性降级逻辑
   - 原因：C1_META_TO_FACTORS 只有物理化学指标（pH/有机质/CEC等），
     OP 场地检测数据无这些指标 → minmax 返回 None → SSUI=None
   - 具体改动：
     · 在 C1_META_TO_FACTORS 新增有机污染物条目（苯并芘/多环芳烃/DDT/PCB 等），
       或新增 _organic_penalty_score(series) 函数：
       基于 threshold_exceedance 超标比率计算 0-1 惩罚分（超标越多→安全性越低）
     · 在 evaluate() 中：若 series 含有机因子（ORG_COLS_MAP），
       用有机惩罚分替代 C1 物理化学分（避免 None）
     · 在解释字段 explanation 中标注 "有机安全性基于阈值超标比率，非物理化学测量"
   - 影响范围：ssui.py evaluate()，不影响 HM 场地现有逻辑
   - 验证方式：
     · 本地单测：用南京栖霞 OP 数据运行 ssui.evaluate()，SSUI 应为非 None 值
     · e2e：有机场地完整链路，evaluation 表 ssui 字段非 None
   - 失败回滚：在 evaluate() 入口加 pollution_type 判断，OP 走新分支，其余不变

2. [backend/app/services/evaluation_service.py] 传递 pollution_type 给 ssui.evaluate
   - 原因：当前 ssui.evaluate(series, scope="production") 未传 pollution_type 信息
   - 具体改动：
     · run_evaluation() 中读取 site.pollution_type（heavy_metal/organic/composite）
     · 传入 ssui.evaluate(series, ..., pollution_type=site.pollution_type)
     · 更新 ssui.evaluate 签名：增加可选参数 pollution_type="heavy_metal"
   - 验证方式：site.pollution_type="organic" → ssui.evaluate 走有机分支 → 返回非 None
   - 失败回滚：参数默认值为 "heavy_metal"，不改变现有 HM 行为
```

**风险：**
- evaluation_params.json 第 245 行有"污染物"维度但未在 ssui.py 使用，需确认是否用于此处还是 SSUI 其他维度
- 有机安全性的标准化方法（超标比率 → 0-1）需裴总确认权重设计，执行前可先用简单公式：score = max(0, 1 - 超标因子数/总因子数)

---

### 目标 3：全链路回归测试（双轨+有机场地验证）

**为什么高优先级：**
昨天有 15 次提交，包括模型重训、阈值库替换、diagnosis_service 路由改动、GB36600 OCR 纠正等大改。需要确认系统在最新代码上仍然稳定，并补充双轨路由专项测试。

**文件路径：**

```
1. [backend/e2e_full_chain.py] 用 venv 运行，记录结果
   - 原因：验证昨天 15 次提交后系统完整性
   - 具体改动（不改代码，只执行）：
     cd backend && .venv/bin/python e2e_full_chain.py
   - 验证方式：脚本输出 PASSED / 保存测试报告到 docs/audit/regression_20260624.md
   - 失败条件：任何断言失败 → 停止，进 PLAN 分析根因

2. [backend/.venv/bin/python -m pytest tests/ -q] 运行单测
   - 原因：昨日同行评审已补 80 单测，验证仍全绿
   - 具体改动：执行测试，不改代码
   - 验证方式：输出 80 passed（或新增数量 passed，0 failed）
   - 失败条件：任何 failed → 记录到回归报告，不声称完成

3. [scripts/robustness_test.py] 运行有机/重金属/复合三类场地
   - 原因：验证双轨新模型对三类场地路由正确
   - 具体改动：执行测试，记录结果
   - 验证方式：HM 场地走 prod+eco 双轨，OP 场地走 organic 诊断路径，composite 走 HM+OP

4. [docs/audit/regression_20260624.md] 输出回归报告
   - 原因：记录每日回归状态，可追溯
   - 具体改动：新建 markdown，包含 e2e 结果 + 单测结果 + 双轨验证截图/日志
```

**风险：**
- pytest 需通过 backend/.venv/bin/python -m pytest，不能直接 /usr/bin/python -m pytest
- srs_dev.db 可能需要先迁移：`backend/.venv/bin/alembic upgrade head`
- 双轨路由测试需要场地已有 land_use_type 值，若为 None 则路由失败

---

## 今日建议不动的文件

- `ml/models/rf_barrier.py`（昨日刚完成双轨训练，不动）
- `data/knowledge_base/` 下所有原始阈值文件（昨日已 OCR 锚定，不动）
- `backend/alembic/versions/0002_srs_fix.py`（迁移脚本，不改）
- `reporting/templates/traceability_report.html`（报告模板，不改）

---

## 阻塞项与风险

| 风险 | 级别 | 说明 |
|---|---|---|
| venv pytest 不可用 | 中 | 执行前先确认 backend/.venv/bin/python -m pytest --version |
| land_use_type PATCH 接口缺失 | 高 | data.py 可能无此接口，需先 grep 确认再决定新增 |
| OP-SSUI 有机权重待确认 | 中 | 可用简单公式先行，后续裴总核定 |
| E③ 外部协变量接入 | 低（今日不做）| external_covariate_datasets_20260624.md 已检索，但接入工期长，今日不纳入 |

---

## 下一次任务建议

1. 若目标 1-2 完成，下一优先级为：**E③ 接入 FAO HWSD 协变量增强 HM 块训练数据**
2. 若目标 3 发现回归问题，优先 PLAN 修复，不进新功能
3. 长期：M8 同文件不同 mapping 重导冲突（建议 Measurement 唯一约束），M6 知识库 ThresholdRule pH档路由审查

---

裴总确认后，可另开 Cowork 任务发送 `ENTER EXECUTE MODE` 执行。
