# EXPERIMENTS.md — SRS autoresearch 实验日志

best_overall = 0.9867 (Exp #002)

---

## Exp #000 baseline | 2026-06-23
指标: overall 0.5667 | rec_cov 0.667 | op_rec 0.0 | diag 0.733 | ssui 0.867 | pass 1.0
裁决: BASELINE

## Exp #001 | ORGANIC_HINT 加中文 token
假设: engine.ORGANIC_HINT 只英文 → 中文有机因子 factor_class=other → 不进推荐匹配
改动: engine.ORGANIC_HINT += 多环/芳烃/苯并芘/有机氯/DDT/多氯联苯/农药/菲/芘
指标: overall 0.5667 (持平)
裁决: **持平保留为前提** — 单改无效, 因 OP 根因更深(诊断无有机Top, 非匹配层)

## Exp #002 | GB36600 有机阈值补充 ★ KEEP (best)
根因: 知识库有机阈值仅4行(石油烃), PAH/BaP/萘无阈值 → 诊断不识别有机超标
      → 无有机Top因子 → recommend.factor_names 空 → OP 0推荐 (裴总判断正确, 非边界)
改动:
  - threshold_resolver._LIMIT_RE 支持 ng/g(原只mg/kg, 与切片ng/g单位错配)
  - 新建 data/knowledge_base/有机物阈值补充_GB36600.csv
    (苯并芘550/多环芳烃总量550/萘25000/多氯联苯200/DDT400 ng/g, production scope)
  - pipeline.get_pollutant_limits 合并主库+有机补充
路径(无需重训model): 有机阈值 → 诊断 threshold_exceedance 规则识别有机超标
      → 有机进Top → recommend 匹配技术库已有有机技术(化学氧化/生物修复/热脱附) → OP有推荐
指标: overall 0.5667→**0.9867** | rec_cov 0.667→**1.0** | op_rec 0→**4.0** | diag 0.733→**1.0** | pass 1.0
裁决: **KEEP (新best +0.42)**

## 待办(后续轮)
- Exp #003: DDT/多氯联苯 GB36600 精确值核实(现标注"待核实") → 提准确性
- Exp #004: ssui_valid 0.867(北京/海南OP的SSUI None) → evaluation 有机维度
- Exp #005(可选): model 重训练含有机特征(需有机标注) → SHAP 解释有机, 参考 000/10.SHAP.ipynb

## Exp #002-验证 | OP 推荐质量确认 ★
北京/广东/山东 OP 推荐 Top1=生物修复(有机技术), Top2=化学氧化, Top3=客土/换土;
matched_factors=[多环芳烃/DDT/PCB/有机氯农药] —— 推荐引擎对 OP 正确匹配有机修复技术,
非重金属植物修复。Exp#002 真实有效(非数字游戏)。

## Exp #005-调查 | model 有机 SHAP 可行性
发现: feature_mapping 已含有机映射(OCPs/PAHs/PCBs/PAEs); model_ready_hm_op.csv(365列含有机)存在;
但当前 model 用 真实训练集_GB15618, 有机列缺失>95% 被 prepare(DROP_MISSING_ABOVE=0.95)剔除
→ feature_list 只8重金属。
根因: merged 有机数据稀疏(PAH有效9.3%), 即使保留中位数填充 → model 学不到有机信号。
结论: OP 用 threshold_exceedance 规则(不依赖model)是正确分层; model 有机 SHAP 受数据稀疏限制。
下轮 Exp#005 实验: DROP_MISSING_ABOVE=0.99 重训练, evaluate 验证 model 对有机判别力(预期弱, 可能revert)。

## Exp #005 | DROP_MISSING_ABOVE 调整 — 假设修正(REVERT, 未执行实验)
假设: 有机列缺失>95% 被 prepare 剔除 → 调 DROP_MISSING_ABOVE=0.99 保留有机进特征
调查修正: 真实训练集_GB15618.csv 仅 14 列(8重金属+missing+标签), **无任何有机列**!
→ 不是缺失率问题, 是训练数据源本身纯重金属(GB15618 农用地重金属标准派生)。
裁决: REVERT(假设错误); 要 model 含有机必须换训练数据源。

## 收敛判定 | autoresearch 自主循环收敛停 (best=0.9867)
核心 OP 已系统解决(Exp#002): 诊断 threshold_exceedance 规则识别有机超标 + recommend
匹配技术库有机技术(生物修复/化学氧化), 推荐质量经验证正确。剩余项全部需外部输入或受数据硬约束:
- model 有机 SHAP(Exp#006): 需重建含有机训练集(merged 有机行 + GB36600 标签派生);
  merged 有机有效率 PAH 仅 9.3%/OCP 1.1% → 数据稀疏, model 判别力存疑 + 重建大工程。
- DDT/多氯联苯 GB36600 精确阈值: 需裴总提供标准文本(现用保守估计值, 推荐已正确工作)。
- SSUI None(北京/海南 OP): 诚实数据边界(切片无 pH/有机质/氮磷钾), 不伪造。
按 program.md 止损(连续无 overall 改进) → 自主循环收敛, 等裴总指示是否启动 Exp#006 大工程。
