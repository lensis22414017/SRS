# 更新日志 (CHANGELOG)

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式,
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-07-01 — v1.0 正式版

### 新增(核心闭环)
- 数据管理: Excel/CSV 导入(单文件/批量/wizard) + 字段映射 + pH感知阈值校验 + 全局指纹判重(skip/overwrite/new_version) + 导出
- 障碍因子诊断: 双轨防泄漏 RF+SHAP(prod=GB15618严 / eco=GB36600宽), X_barrier=理化11+GEE14协变量, CV AUC 0.83(非泄漏虚高)
- GEE 协变量: 17 场地持久化(14 gee_因子, MODIS NDVI/WorldClim气候/SRTM地形/SoilGrids2.0土壤)
- 功能重构评价: 模糊综合评价法 T=Σ(F×W), 生产/生态双 scope
- SSUI 可持续利用评价: C1 限制因子维度(MVP口径)
- 方案推荐: 规则引擎 + 技术库匹配 + 结构化 reason_struct(法规依据+禁用条件)
- 全流程追溯: 五阶段(调查/审批/施工/效果/管护) + 附件 + 审批
- 追溯报告: PDF/DOCX/HTML 三级降级, 嵌 matplotlib 静态图件(SHAP/采样点/EDA)
- 地图: MBTiles离线>高德在线>天地图, 8级pH档超标风险分级, 行政区三级金字塔
- RBAC: 管理员/企业用户/第三方机构/监管人员 + 企业数据隔离 + 审计日志
- AI 助手: SiliconFlow GLM-5.2 RAG 问答(知识库+场地特征)

### 修复
- align_features bug: gee_ 协变量真实值生效(此前走 medians 全中位数)
- .dockerignore 排除 frontend/dist 与 Dockerfile COPY 冲突
- launcher.py emoji 在 Windows GBK 控制台 UnicodeEncodeError
- load_latest 路由: 优先 _barrier_gee 防泄漏模型 > _lake_full(泄漏)

### 已知限制
- SSUI 仅 C1 维度(C2经济/C3社会/C4管理待补)
- 测试集跨文献 group-split AUC 0.66(防泄漏诚实, 非泄漏虚高)
- SQLite 桌面模式(高并发需迁 Postgres)
- QC服务(qc_service RPD/加标回收)已实现但未接 API

---

## 版本规划

### [0.2.0] 计划
- SSUI C2/C3/C4 维度补全
- 模型 manifest.json 治理(取代字典序选模型)
- 双阈值表统一(threshold_rules + standard_thresholds)
- 健康风险评估模块(RBCA 致癌/非致癌)
- 污染物溯源分析(PCA/聚类来源解析)

### [1.0.0] 目标
- 甲方验收通过, 生产部署(Postgres+PostGIS+Redis)
- 名录管理(疑似/污染地块名录)
- 3D 可视化(地层立体刻画)
