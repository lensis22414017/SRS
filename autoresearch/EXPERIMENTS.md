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

## Exp #003 ✅ 完成 | GB36600 有机阈值精确化(裴总核对) | 2026-06-23
四路 OCR 交叉验证(GLM/Qwen3.5-9B/4.5v/裴总亲口) → 全部 LLM 对扫描表幻觉。
最终用裴总标准目录原文核对锚定 `data/standards/GB36600_有机阈值_权威.csv`:
  苯并芘0.55/萘25/多氯联苯0.2/石油烃826/DDT1.0/六六六0.4/乙苯7.2(Peizong纠正web搜28错) mg/kg
  factor 精确匹配 ORG_COLS_MAP 中文 key; cat1 ng/g; 幻觉CSV重命名_deprecated。
详见 docs/audit/GB36600_OCR_交叉验证报告_20260623.md。
裁决: KEEP(数据真实性合规, §18.2 不伪造标准)。overall 持平 0.9867(阈值微调不改变 OP 推荐路径)。

## Exp #005 ✅ 完成 | lake model 有机 SHAP 生效 | 2026-06-23
重建三块训练数据(hm/op/composite) + 数据湖(lake), RF 插补有机缺失, 训练 lake model。
lake model `rf_barrier_factor_v0.1_20260623_zlake_final.joblib` feature_list 89 含有机:
  Top15 含 6 有机特征(非 threshold 规则): Sum_PAH#6/DDT#10/PCB#11/BaP#12/HCH#13/OCP#14
  → model 真正学会有机判别, OP 诊断可输出有机 SHAP 解释。
裁决: KEEP(model 有机 SHAP 生效, 裴总"根治 OP"目标达成)。

## 收敛判定 | autoresearch 自主循环收敛 (best=0.9867, Exp#003/#005 已闭环)
核心 OP 系统解决且深化:
- Exp#002: threshold_exceedance 规则路径(诊断+推荐)
- Exp#005: lake model 有机 SHAP 路径(ML 可解释) — 双路径并存
- Exp#003: 阈值精确化(裴总核对权威值)
鲁棒性: 10 场地(5OP+5HM+OP)100% 成功, 有机 SHAP 命中 10/10。
剩余可选(边际小, 非阻塞):
- TPH 重训: OP train 仅 6 行 TPH 超标(0.13%), 权威 CSV 已记录阈值, 按需重训。
- SSUI None(北京/海南 OP): 诚实数据边界(切片无 pH/有机质/氮磷钾), 不伪造。
- PAE/PBDE/PFAS: GB36600 无明确筛选值或单位不同, 标 excluded 不误判。
