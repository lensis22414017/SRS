# 更新日志 (CHANGELOG)

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 格式,
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.1] - 2026-07-18 — 甲方验收14项修复 + 重新打包

### 修复(UI/布局)
- 图标替换为重构之盾(v6): 深蓝底板+白盾+双叶+三数据节点
- 数字大屏漏斗图文字跨行修复(单行显示,漏斗条缩短)
- SSUI表头溢出修复(单行布局,SitePicker缩小)
- 数字大屏顶部标题栏删除(与底部重复)
- 左侧导航固定(position:fixed不随主体滚动)
- 系统管理Tab整合(概述/健康/配置三合一)
- 全页面图标文字重叠检查

### 修复(障碍因子诊断)
- 删除"诊断模型与结论"模块
- 诊断方法说明移到页面最底部(优先展示Top-N)
- Top-N去掉实测值列(避免歧义)
- 因子单位标准化显示(Cd_mgkg→Cd (mg/kg), ph→pH)
- 删除"重要说明"Alert, 充实模型贡献度小提示

### 修复(功能逻辑)
- 场地编号格式统一: 湖南-hm+op-89点(开头不要数字,污染类型小写)
- 场地批量删除(rowSelection+batch-delete端点)
- 文件下载/预览/删除(inline预览+删除端点+前端按钮)
- 地图坐标层级(coordPane置于三色点下一层)
- 流程图嵌入修复(onError显示错误提示不静默隐藏)

### 工程
- 打包排除.db文件(开发库残留不打入包)
- 版本号统一为1.0.1
- 模型/Python库/依赖/知识库完整打包(全新机可用)

## [1.0.2] - 2026-07-17 — GPT 审计修复 + 甲方方法严格落地(源码版本,发布回退为1.0.1)

### 修复(阻断"超标严重却评价为优")
- KOS 主链路重做: 按采样点计算(不再全场地压最大值), 阈值兜底用 GB15618 通用档, 模型贡献度改为局部 SHAP, S 用模型层 Top-5 稳定性
- 重构评价: 缺阈值不再给 100 分; 28/25 项指标严格按甲方方法; AHP+熵权/CRITIC 主客观 50/50 组合; MICE 缺失值处理; 改进模糊综合评价(内梅罗指数)
- SSUI 完整重写: 25 项元指标(D1-D25, 安全性 D1-D17 + 经济性 D18-D25); PCA-MDS 降维(累计解释率≥60%); AHP+熵值/CRITIC+博弈论组合赋权; SSUI=ΣWi·Si×f(t)×M

### 新增(工程合规)
- 首启空库: 参考数据与业务数据分离, 生产库不继承开发库
- 场地删除: DELETE API + 12 表事务化级联 + 审计墓碑
- 批量导入去模板: 删除预设模板硬编码, 完全智能识别
- 数据加密/备份/恢复: AES-256 字段级加密 + 定时备份 + 恢复 API
- 流程图行内缩略图: 方法说明区直接显示流程图 + 点击放大
- 图标重做: 蓝盾双层+生态生产双叶+土壤分层+三数据节点
- 版本号统一: 全仓 7+ 处冲突统一为 1.0.2
- 依赖锁: requirements.lock + .python-version + .nvmrc

### 验收(11 项硬验收)
- compileall / 全新 venv / pytest / npm ci / npm build 全过
- 三 XLSX 不可跳过回归测试(乡村 8 点 / 栖霞 49 点 / 个旧 134 点)
- 个旧诊断完整 JSON + 截图(含 TOP-N / 五分量 / 模型贡献)
- 负向测试(缺测/缺阈值/缺模型/低置信度)
- 场地删除 + 分页第 2 页从 11 开始
- 7 张流程图构建产物哈希
- 首启空库数据库计数证明
- 模型工件缺失必须导致测试失败

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
