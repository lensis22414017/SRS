# SRS autoresearch 研究纲领 (program.md, L3 — human 编程)

## 研究对象 (L2, agent 迭代)
`ml/recommend/engine.py` — 方案推荐引擎的有机/复合污染匹配逻辑。
**核心目标**: OP(有机)场地从 baseline 0 推荐提升到 ≥3 条; 复合保持; 重金属不退化。

## 基础设施 (L1, 锁定)
`prepare.py` — 15 真实切片(4HM+5OP+6HM+OP)全链路 evaluate; BUDGET 180s/次。

## Baseline 指标 (Exp #000, 2026-06-23)
| 指标 | 值 |
|---|---|
| overall | **0.5667** |
| recommend_coverage | 0.667 (10/15) |
| op_recommend_avg | 0.0 (OP全0) |
| diagnosis_top_valid | 0.733 |
| ssui_valid | 0.867 |
| pass_rate | 1.0 (15/15 无crash) |

## 目标
- overall ≥ **0.85**
- recommend_coverage ≥ 0.95
- op_recommend_avg ≥ 3
- pass_rate 保持 1.0 (硬约束)

## 根因诊断(已查)
OP 推荐 0 的根因: `engine.ORGANIC_HINT` 只有英文 token(PAHs/PCBs/...),
中文有机因子名(多环芳烃/苯并芘/有机氯农药/DDT/多氯联苯)不匹配 → `_factor_class="other"`
→ 被 `factors=[f for f if _factor_class in (heavy_metal,organic)]` 过滤掉 → 0 推荐。

## 探索方向 (按优先级)
1. **engine.ORGANIC_HINT 加中文 token**(多环/芳烃/苯并芘/有机氯/DDT/多氯联苯/农药) → OP 因子进 organic 类
2. 技术库 applicable_pollutants 补有机适用(若方向1后 matched 仍空) — 改 technology_library_seed.csv 或 engine 匹配放宽
3. FactorDictionary 有机因子 factor_type 登记为 pollutant(诊断层)
4. 有机阈值规则(GB36600 PAH/OCP) → 提 diagnosis_top_valid

## 保留阈值 (monotonic 铁律)
- overall 提升 ≥ 0.01 → **KEEP**, 更新 best
- 退步/持平 → **REVERT**, 记失败假设(避免重复)
- **pass_rate < 1.0 → 强制 REVERT**(不得引入 crash)

## 止损
连续 3 轮无 overall 改进 → 收敛, 停循环。

## 循环协议(每轮)
1. 读 EXPERIMENTS.md: best overall + 已试方向
2. 提出 1 个改动假设(针对指标缺口)
3. 备份 engine.py → 改 → `python prepare.py` 评估
4. 比 best: 改进 KEEP / 退步 REVERT
5. 记 EXPERIMENTS.md
