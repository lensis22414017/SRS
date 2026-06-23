# SRS 全链路修复 — 同行评审报告

评审日期: 2026-06-23
评审对象: 9 线修复 (12 提交 d050562→8e41698, 40+ 文件, +1800/−220)
评审方法: 对抗性自查 — 不假设修复正确, 读 diff + 验证怀疑点 + 边界分析

---

## 一、Summary Statement

**总体评价**: 修复整体可靠 — 端到端真实数据闭环通过(版本链 `03558afeba45_n1876` 四环节一致)、全量 80 单测全绿、前端 build 通过。9 条线的根因诊断准确(file:line 证据), 修复方向符合 brief 与甲方验收优先级。

**推荐**: **Minor Revisions** — 严苛审查发现 3 项 Major(已当场修订) + 若干 Minor(记录), 修订后可进入甲方验收。

**关键优点**:
- 内容指纹(source_sha256)贯穿导入→诊断→评价→报告, 真正消除"假指纹"与重复导入翻倍。
- 重金属 token 边界匹配根治了 substring 误判, 12 用例验证。
- 测试隔离三重锁定修复 + 13 处失效 setdefault 清理, 根除串库隐患。

**关键弱点(本次评审发现并处理)**:
- 新增功能最初无持久单测(M1, 已补 9 用例)。
- 评价追加式无累积上限(M4, 已加每类保留 10)。
- SSUI/重构 run 后存在 race(M5, 已清旧数据)。

---

## 二、Major Comments(均已修订)

### M1 [已修] 新增功能无持久单测 — 回归保护缺口
- **问题**: 导出/幂等/stale/token/resolve_mapping/current_site_data_version 仅靠临时 e2e 脚本验证(删库即逝), 无持久单测。未来重构零保护, 违反 brief §7。
- **修复**: 新增 `tests/test_full_chain_fix.py`(9 用例, 全绿), 覆盖 token 边界/统一映射/幂等/版本/导出/stale/8 级风险/generic 兜底。
- **验证**: 全量 71→80 passed。

### M4 [已修] 评价追加式无限累积
- **问题**: D1 改追加式保留历史, 同 data_version 幂等, 但不同 data_version 无上限累积。反复导入+评价会使 EvaluationResult 膨胀。
- **修复**: `evaluation_service` 新增评价后每 eval_type 保留最近 10 个, 删除更旧。
- **权衡**: 保留 10 个历史足够支撑"历史结果区 + stale 对比", 不影响 brief 4.5 验收。

### M5 [已修] SSUI/重构 run 后 race 显旧
- **问题**: run 成功后 `setHasRun(true)` + `load()`(async), load 完成前 hasRun=true 但 data 是旧的 → 短暂显旧评价结果。
- **修复**: run 成功后先 `setData(null)` 清旧, race 期间显 Empty 直到新数据到达。SSUI + Reconstruction 同步修。

---

## 三、Minor Comments(记录, 多为设计权衡不强制修)

### M3 推荐覆盖式 vs 评价追加式不一致
- `recommend_service.py:53` 仍 `delete()`(覆盖式), 评价是追加式。不一致。
- **判断**: 推荐语义是"当前最优方案集", 覆盖合理; 不修。

### M6 `_threshold_table` generic min 可能高估超标
- 多条通用阈值(非 pH 档)取 `min`(最严苛), 可能对边缘值误报超标。
- **判断**: 保守高估符合"风险管控"原则(brief 优先级 数据真实性>可验收), 且根因是知识库 ThresholdRule 的 land_type 存用地类型而非 pH 档(数据侧问题); 不修, 建议裴总核查知识库 ETL。

### M7 重金属 token 漏判英文全称
- `_matches_heavy_metal_token` 对 `nickel/chromium/mercury/lead` 全称不匹配(要求前后非字母, 但全称后跟字母)。
- **判断**: 实际数据用 `Ni/As/砷/铅` 符号或中文, 不用全称; 不修, 若未来出现全称列名再扩展正则。

### M8 同文件不同 mapping 重导可能累积冲突 measurements
- 同物理文件用 mapping A 导入再用 B: sha 同但 mapping_hash 不同 → 不 reimported → 新批次; 而 `delete by source_file`(canonical 含时间戳)删不掉旧 → A+B measurements 叠加, 可能同 point+factor 不同值。
- **判断**: 场景罕见(同文件反复换 mapping), brief 未明确; 建议长期给 Measurement 加唯一约束或改 `delete by source_sha256`。本次不修。

### M9 batch.data_version 的 n 语义
- `batch.data_version` 用本批次写入数, `current_site_data_version` 用全场地 count。多批次场地两者 n 不同。
- **判断**: 两者用途不同(批次存档 vs stale 判定), stale 判定统一用 current(全场地), 一致; 不修, 建议注释说明。

### M10 evaluation POST 返回结构 reused/正常分支不一致
- 幂等复用分支返回摘要, 正常分支含完整 details。前端改用 GET 完整结果(F 阶段), 不直接依赖 POST 结构; 不修。

---

## 四、逐线评审结论

| 线 | 结论 |
|---|---|
| 4.1 导入 | ✓ 统一入口 + token 边界, 12 用例+普通文件验证不误判 |
| 4.2 版本/幂等 | ✓ sha 指纹幂等, e2e 1876 不翻倍; M8/M9 为边缘语义, 已记录 |
| 4.3 导出 | ✓ 16 字段 + 行数一致 + audit; 已补持久单测(M1) |
| 4.4 EDA | ✓ 模块重命名 + hooks 前置; test_eda 13 passed |
| 4.5 SSUI | ✓ 追加式 + 历史/本次 + stale; M4/M5 已修; ObstacleAnalysis 未改(R2) |
| 4.6 推荐 | ✓ reason_struct 透传 + 技术库 CRUD; 推荐覆盖式(M3 记录) |
| 4.7 AI | ✓ history 去重 + 状态诊断; 降级逻辑后端已完善 |
| 4.8 地图 | ✓ 8 级 + generic 兜底(修复 exceedance 全 None); M6 记录 |
| 4.9 测试隔离 | ✓ 三重锁定修复; 全量串库隐患消除 |

---

## 五、剩余风险(需裴总本机确认)

- **R1 生产 alembic upgrade**: 0002 迁移加 6 列; 测试库用 create_all 自动建, 生产/打包版需 `alembic upgrade head`。**请裴总本机验证升级路径**。
- **R2 ObstacleAnalysis.tsx**: 用 diagnosis(非 evaluation), 未做历史/本次改造。若它也自动显旧诊断结果, 需同样处理(brief 4.5 聚焦 SSUI/重构)。
- **R3 端到端手工验收**: brief §8 的 15 步演示(前端交互)需裴总本机跑一次。

## 六、Questions for 裴总

1. 生产库 `alembic upgrade head` 是否已验证(0002 迁移)?
2. ObstacleAnalysis 是否需要同步历史/本次分离?
3. `_threshold_table` generic min 的保守高估是否可接受, 还是需核查知识库 land_type 存储?
4. 同文件换 mapping 重导(M8)是否为真实业务场景, 需加 measurement 唯一约束?

---

## 七、最终推荐

**Minor Revisions(已完成 M1/M4/M5) → 可进入甲方验收**。
建议裴总: ① 本机跑 alembic upgrade + brief §8 手工闭环; ② 决定 M3/M6/M7/M8 是否需进一步处理。辛特助待命。
