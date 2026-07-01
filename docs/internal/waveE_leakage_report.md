# Wave E 路径 C 双版本对照报告 — 标签泄漏实证

> 生成：2026-06-25 | 模式：EXECUTE（项目组拍板路径 C）| 证据：16 模型 meta.json + ΔAUC 量化
> 依据：Hu et al. 2026 *Commun Earth Environ* 7:214（标签泄漏专论）+ plan Wave E 修正（项目组 2026-06-24 科研深问）

## Executive Summary

按项目组 2026-06-25 拍板的**路径 C（双版本对照）**，同时训练含浓度版（full，标签泄漏组）与 X_barrier 纯协变量版（barrier，防泄漏组），以 AUC 差距量化标签泄漏。

**核心结论**：平均 ΔAUC = **0.3053 > 0.15**（plan E3 判据），**标签泄漏实证成立**（Hu 2026 铁证复现）。
- full 组 AUC 全部 0.99+（hm_prod=1.0 完美泄漏）→ **不可作独立泛化证据**
- barrier 组 AUC 暴跌（composite 0.54≈随机、lake 0.59、HM **0 特征跳过**）→ 反映理化协变量覆盖率严重不足
- 唯一例外：op 组 barrier AUC=0.958（Δ仅0.04），有机污染物与 SoilpH/OC_pct 有真实关联信号

**后续刚需**：重金属障碍因子识别在纯协变量框架下**无数据可训**（HM 块 0 理化协变量）。外部协变量增强（ECA/ITM/GSM/TLDA/PFE）是 CLAUDE.md 当前优先级 #2 的硬刚需，非可选项。

## 一、实验设计（路径 C，项目组拍板）

| 组 | 特征策略 | 标签 | 用途 |
|---|---|---|---|
| **full**（含浓度） | 含 20 污染物浓度列（HM 8 + OP 12）+ 协变量 | 双标签派生（浓度>阈值=1） | 标签泄漏虚高组，证泄漏上限 |
| **barrier**（X_barrier） | drop 全部污染物浓度列，仅留理化协变量 | 同上 | 防泄漏组，AUC 低反映协变量不足 |

- 每组 × 4 块（hm/op/composite/lake）× 2 轨（prod/eco）= 16 模型
- 判据：ΔAUC(full−barrier) > 0.15 = 标签泄漏显著（plan E3）
- 诚实标注：每组模型 meta 均写 `leakage_warning`（§18.4 不伪造性能）

## 二、对照数据（16 模型，实证）

| 块 | 轨 | full_AUC | barrier_AUC | ΔAUC | full_feat | barrier_feat | 判定 |
|---|---|---|---|---|---|---|---|
| composite | eco | 0.9935 | 0.5198 | **0.4737** | 42 | 2 | 泄漏显著 |
| composite | prod | 0.9979 | 0.541 | **0.4569** | 42 | 2 | 泄漏显著 |
| hm | eco | 0.9998 | —（跳过） | — | 16 | **0** | 无协变量可训 |
| hm | prod | 1.0 | —（跳过） | — | 16 | **0** | 无协变量可训 |
| lake | eco | 0.9952 | 0.582 | **0.4132** | 59 | 3 | 泄漏显著 |
| lake | prod | 0.9988 | 0.5944 | **0.4044** | 59 | 3 | 泄漏显著 |
| op | eco | 0.9999 | 0.9582 | 0.0417 | 28 | 4 | 真信号 |
| op | prod | 0.9999 | 0.9582 | 0.0417 | 28 | 4 | 真信号 |

**平均 ΔAUC（6 可配对组）= 0.3053 > 0.15 → 标签泄漏实证成立。**

数据源：`ml/artifacts/rf_barrier_factor_v0.1_20260625_*_{full,barrier}.meta.json`（含浓度组 8 + X_barrier 组 6 训练 + HM barrier 2 跳过标注 `.skip.meta.json`）。

## 三、三大科学发现

### 发现 1：full 组 AUC 全 0.99+ = 标签泄漏虚高（Hu 2026 铁证）
hm_prod AUC=**1.0**（完美泄漏，因标签由 HM 浓度>阈值派生，而 HM 浓度又在特征里→模型学到"浓度→标签"恒等式）。op/lake/composite 全 0.99+。**这组模型的 AUC 不可作为独立泛化证据**——它是"浓度>阈值"规则的过拟合，对未采样情形无外推力。

### 发现 2：barrier 组 AUC 暴跌 + HM 0 特征 = 协变量不足硬实证
排除浓度后：
- **HM 块 0 理化协变量** → 无法训练（跳过）。重金属障碍因子识别在纯协变量框架下**无数据支撑**。
- composite 仅 2 协变量（SoilpH/OC_pct）→ AUC 0.52-0.54 ≈ 随机猜
- lake 3 协变量 → AUC 0.58-0.59 略高于随机
- 重申旧 model `X_no_formula R²=-0.008` 根因：纯协变量特征不足以预测阈值派生标签

### 发现 3：op 组 ΔAUC=0.04 = 有机污染与协变量有真实信号
op 组 barrier AUC=0.958（远高于其他块的随机水平），Δ仅 0.04。**机理解释**：有机污染物（PAH/OCP/PCB）的迁移性与 SoilpH、有机质（OC_pct）强相关——低 OC 土壤对有机污染物吸附弱→迁移性强→超标风险高。这是唯一在 X_barrier 框架下有判别力的块，**暗示有机污染障碍因子可基于理化协变量建模**（与 Hu 2026"OC/pH 为迁移性主驱动"结论一致）。

## 四、诚实标注（每模型 meta.leakage_warning）

- **full 组**：`含污染物浓度特征;标签由浓度派生→标签泄漏;AUC虚高(≈1.0)不可作独立泛化证据(Hu2026铁证,plan§18.4)`
- **barrier 组（训练）**：`X_barrier纯协变量(排除污染物浓度);AUC偏低反映理化协变量覆盖率不足(当前仅SoilpH/OC_pct),需外部协变量增强(ECA/ITM/GSM/TLDA/PFE)提升泛化力`
- **barrier 组（HM 跳过）**：`X_barrier模式该块无理化协变量(仅污染物浓度)→0特征不可训,数据局限实证`

## 五、数据局限硬实证（需项目组重视）

| 块 | 行数 | 理化协变量 | X_barrier 可训？ |
|---|---|---|---|
| hm（真实训练集_GB15618.csv） | 15017 | **0** | ❌ 无任何理化列 |
| op（merged） | 4574 | 4（SoilpH/pH/OC_pct+missing） | ✅ AUC 0.958 |
| composite（merged） | 1361 | 2 | ⚠️ AUC 0.54≈随机 |
| lake（concat） | 20952 | 3 | ⚠️ AUC 0.59 |

**HM 块是最大数据源（15017 行）却 0 理化协变量**——重金属障碍因子识别（plan 核心目标）在当前数据下无法用 plan Wave E 要求的 X_barrier 纯协变量方法学实现。这是**架构性数据缺陷**（CLAUDE.md §3.1 数据代表性思维），算法无法弥补，必须补数据。

## 六、产物清单

| 产物 | 路径 | 说明 |
|---|---|---|
| 训练脚本（改造） | `ml/models/train_three.py` | 加 POLLUTANT_COLS + barrier_only + 0特征守卫 + leakage_warning |
| 对照汇总脚本 | `scripts/waveE_leakage_compare.py` | 扫 meta 配对算 ΔAUC |
| 对照 JSON | `docs/audit/waveE_leakage_compare.json` | 机读对照表 |
| 16 模型 | `ml/artifacts/rf_barrier_factor_v0.1_20260625_*` | full×8 + barrier×6 + HM barrier skip×2 |
| 本报告 | `docs/audit/waveE_leakage_report.md` | 人读结论 |

## 七、需项目组确认与下一步

1. **full 组双轨 8 模型是否可作 Wave F 双用途测试的过渡产物**？（AUC 虚高但双轨诊断可演示，meta 已标 warning）
2. **协变量增强（优先级 #2）是否升为 Wave E 完整化的前置**？HM 块 0 协变量意味着重金属障碍因子识别必须先补 ECA/ITM/GSM/TLDA/PFE 数据。
3. **op 组的真信号是否值得单独深挖**？（有机污染 X_barrier AUC=0.958，可能产出有泛化力的有机障碍因子模型）
4. **下一步 Wave**：B（OCR 交叉验证）/ F（双用途功能测试，用 full 过渡模型）/ 协变量增强（解锁 X_barrier 完整版）？

## Methodology

改 train_three.py 加双组对照 → 16 模型训练（full 重生成 + barrier 新跑 + HM 跳过守卫）→ 汇总脚本配对算 ΔAUC → 对照 plan E3 判据 → 诚实标注 leakage_warning。子问题：HM 块 0 协变量（数据局限）、op 组真信号（机制可释）、标签泄漏量化（ΔAUC=0.3053）。
