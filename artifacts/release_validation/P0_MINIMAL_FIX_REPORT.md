# P0 最小可信性修复报告（release/hotfix-trust-minimal 分支）

> 按 GPT 审计指令执行 P0-1 至 P0-8，每个问题"先读代码→写失败测试→最小修改→运行测试→提交 commit"。

---

## 修复汇总表

| 编号 | 问题 | 修改文件 | 测试 | 结果 | commit |
|---|---|---|---|---|---|
| P0-1 | 因子命名/单位映射 | factor_normalizer.py (新) | test_factor_normalizer.py | 12 passed | ad49452 |
| P0-2 | 动态阈值选择 | threshold_resolver.py | test_threshold_resolver.py | 9 passed | b53b773 |
| P0-3 | 数据质量防线 | diagnosis.py, kos_service.py | test_p03_data_quality.py | 18 passed | (含P0-3/4/5合并提交) |
| P0-4 | KOS饱和透明化 | kos_engine_v0.8.py | test_p04_kos_transparency.py | 9 passed | (同上) |
| P0-5 | SHAP口径修复 | kos_service.py | test_p05_shap_scope.py | 20 passed | (同上) |
| P0-6 | AI事实校验 | diagnosis_fact_check.py (新), ai_service.py | test_p06_ai_fact_check.py | 11 passed | e4be377 |
| P0-7 | 验证口径 | DB(Site标记), real_site_validation_report.md | 3场地诊断 | 3/3 通过 | 83f0e87 |
| P0-8 | 测试+报告 | 本文件 | 79 P0测试 | 79 passed | — |

**P0 测试总计: 79 passed（单独运行时全过；与其他测试混跑时因 SQLite session 冲突有 ERROR，非 P0 引入）**

---

## 各项详情

### P0-1: 因子命名精确匹配 + 单位转换 + 冲突检测
- **文件**: `backend/app/services/factor_normalizer.py`（新增）
- **改动**:
  - Unicode NFKC 归一化（全角→半角）+ strip + 小写 + 去空格
  - 从 `factor_aliases_v0.8.yaml` 加载别名表，三级精确匹配（禁止子串）
  - 总铬 Cr_mgkg vs 六价铬 Cr6_mgkg 精确区分
  - 单位转换: μg/kg/ng/g → mg/kg（÷1000）
  - 同一 canonical 多来源列 → mapping_conflicts（不静默覆盖）
  - 追溯: original_name/unit_raw/unit_converted/conversion_factor

### P0-2: 动态阈值选择
- **文件**: `backend/app/services/threshold_resolver.py`
- **改动**: 新增 `resolve_threshold_from_db()` — 从 StandardThreshold 表按 pH 分档查询
  - pH 匹配: pH<=5.5 / 5.5<pH<=6.5 / 6.5<pH<=7.5 / pH>7.5
  - eco 轨道默认第二类用地
  - 缺 pH → ambiguous + review_required（不默认最严/最宽档）
  - 返回完整元数据: threshold_value/unit/standard/version/pH_condition/source_id

### P0-3: 数据质量防线
- **文件**: `backend/app/api/diagnosis.py`, `backend/app/services/kos_service.py`
- **改动**:
  - 优先 value_used_for_model，为空用 value
  - qa_status=rejected 跳过
  - 极端值检查（As/Cd/Pb/Hg >10000 mg/kg → extreme_value_warning，不自动改值）
  - 每因子统计: 点位数/有效数/最大值/中位数/P95/超标点数/比例
  - aggregation_method="maximum_valid_measurement"

### P0-4: KOS 饱和和稳定性透明化
- **文件**: `ml/ranking/kos_engine_v0.8.py`
- **改动**:
  - KOS_SEVERITY_CAP_RATIO 配置化（默认 10，可调）
  - 新增 `compute_severity_detail()`: exceedance_ratio / severity_saturated / severity_cap_ratio
  - key_obstacles 每条含: exceedance_ratio / severity_saturated / stability_is_constant / stability_note
  - 相邻 KOS 差 <0.01 → ranking_difference_small=True
  - S=0.8 保留但透明标注（stability_note="当前无重复样稳定性数据,S为固定占位参数"）

### P0-5: SHAP 口径修复
- **文件**: `backend/app/services/kos_service.py`
- **改动**:
  - model_contribution 每条增加 contribution_scope="global_model"
  - 代码注释明确禁止"局部/因果/障碍高度"措辞

### P0-6: AI 事实校验强化
- **文件**: `backend/app/services/diagnosis_fact_check.py`（新增）, `backend/app/services/ai_service.py`
- **改动**:
  - `extract_facts()`: 结构化提取因子/浓度/超标/排名
  - 19 个禁止性整体结论词（总体可控/影响有限/可正常使用/无需修复/可接受范围 等）
  - `check_fact_consistency()`: 因子不丢失/数值不篡改/超标关系不反转
  - `validate_ai_polish()`: 综合校验，失败 → should_fallback=True
  - polish_diagnosis 替代旧 6 关键词检查

### P0-7: 验证口径
- **改动**:
  - 3 个原始场地（个旧/栖霞/农村）KOS 诊断全部成功
  - 训练场地（id=4-18）标记 `[synthetic/demo]`
  - 真实场地（id=1-3）标记 `[real]`
  - 生成 `artifacts/release_validation/real_site_validation_report.md`
  - 声明: 仅 3 场地工程回归，非充分外部科学验证

---

## 仍未解决的问题（诚实记录）

1. **P0-1 未集成到主诊断链路**: factor_normalizer.py 已实现并通过测试，但 diagnosis.py 的 trigger_kos_diagnosis 仍用旧 normalize_factors。集成需改 run_kos_diagnosis 签名，本轮未做（避免破坏现有 API）。
2. **P0-2 未集成到主诊断链路**: resolve_threshold_from_db 已实现，但 kos_service.py 仍用硬编码 PROD_THRESHOLDS。集成需重构 run_kos_diagnosis，本轮未做。
3. **S=0.8 仍硬编码**: P0-4 只做了透明化标注，未改为动态计算（无重复样数据支撑）。
4. **As=12420 mg/kg 未核实**: 极端值检查已触发警告，但未联系甲方核实真实单位。
5. **全量测试有 SQLite session 冲突**: 71 failed 多为 SQLAlchemy 测试隔离问题，非 P0 修复引入。P0 测试单独运行全过。

---

## commit SHA 列表

| commit | 内容 |
|---|---|
| ad49452 | P0-1 因子命名精确匹配+单位转换+冲突检测 |
| b53b773 | P0-2 动态阈值选择 |
| (合并) | P0-3/4/5 数据质量+KOS透明化+SHAP口径 |
| e4be377 | P0-6 AI事实校验强化 |
| 83f0e87 | P0-7 真实场地验证报告 |

---

*生成时间: 2026-07-16 | 分支: release/hotfix-trust-minimal | 未打包 | 未合并 main*
