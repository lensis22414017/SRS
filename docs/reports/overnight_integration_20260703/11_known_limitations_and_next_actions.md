# 11 已知限制与明日优先级

## 已知限制(诚实)

1. **P3-Alpha 非最终论文定版** — 工程放行,非科学定版
2. **source-level 验证** — 不宣称 site-level 泛化(site_id≈逐样本)
3. **OP 模型探索性** — Spearman 0.66-0.77,GEE 主导,标 exploratory
4. **HM+OP 不单独训练** — 仅 408 样本
5. **未知有机物走三道防线** — 族群预警 + TEF 降级,不假装识别
6. **GEE/proxy 只做背景** — 不进正式 KOS 排名
7. **缺失指示器只做数据质量** — 经三态清洗分流,不进 Top-N
8. **SHAP 称模型贡献度** — 非因果/非障碍高度
9. **Spearman 0.96 含水** — ContextOnly 0.31 揭示地理混淆,真实泛化估 0.7

## 明日优先级(TOP 3)

### P1: 前端 ObstacleAnalysis 接入 KOS(最高)
- 按 frontend_model_contract_v0.8.md 改 4 个 TSX 页面
- 完成后可甲方演示

### P2: 导入演示数据 + 15 场地批量验证
- 导入云南个旧/南京栖霞/乡村复合 3 个甲方数据
- 批量跑双轨诊断

### P3: 报告生成读 KOS 字段
- 改 report_service.collect() 读 key_obstacles/model_contribution
- 生成 6 份报告样例
