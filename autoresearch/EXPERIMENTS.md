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
