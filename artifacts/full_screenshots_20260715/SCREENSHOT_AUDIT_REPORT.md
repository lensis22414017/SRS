# 全页面截图审查报告 — 2026-07-15

## 截图清单（17张）

| # | 截图文件 | 页面 | console错误 |
|---|---------|------|------------|
| 01 | 01_login.png | 登录页 | 0 |
| 02 | 02_dashboard.png | 数据概览（修复前） | 1（_leaflet_pos） |
| 03 | 03_sites_list.png | 场地管理列表 | 0 |
| 04 | 04_site_detail_1.png | 场地详情(个旧) | 0 |
| 05 | 05_obstacle_analysis.png | 障碍因子分析 | 0 |
| 06 | 06_reconstruction.png | 功能重构分析 | 0 |
| 07 | 07_ssui.png | SSUI评价 | 0 |
| 08 | 08_recommend.png | 方案推荐 | 0 |
| 09 | 09_trace.png | 全流程追溯 | 0 |
| 10 | 10_system_tab1_config.png | 系统管理-系统配置 | 0 |
| 11 | 11_system_tab2_ai_config.png | 系统管理-AI模型配置 | 0 |
| 12 | 12_system_tab3_audit_log.png | 系统管理-操作日志 | 0 |
| 13 | 13_obstacle_eco_track.png | 障碍因子-生态轨诊断 | 0 |
| 14 | 14_obstacle_tech_details.png | 障碍因子-技术详情展开 | 0 |
| 15 | 15_export_report.png | 导出诊断报告 | 0 |
| 16 | 16_obstacle_OP_site.png | OP场地诊断 | 0 |
| 17 | 17_dashboard_fixed.png | 数据概览（修复后） | **0** |

## 发现的问题与修复状态

### 已修复
1. **SiteMap.tsx `_leaflet_pos` undefined** — fitBounds在地图未初始化完成时调用。修复：加 `_loaded && _mapPane` 防御检查 + setTimeout兜底。
2. **favicon.ico 404** — index.html 添加内联 SVG emoji favicon。
3. **antd `destroyOnClose` 弃用警告** — 替换为 `destroyOnHidden`。

### 已知保留（非阻塞）
- **`/api/v1/sites/{id}/diagnosis` GET 404** — OP场地无旧诊断记录时的正常空态，前端已正确处理。
- **antd Descriptions span 警告** — 布局列跨度不匹配，不影响功能，建议后续优化。
- **antd message static context 警告** — 已用 App 组件包裹，个别 message 调用仍有警告，不影响功能。

## GLM-5.2 接入验证
- AI配置页：服务商=智谱GLM-5.2(官网·推荐)，状态=已配置+已连通
- 诊断结论AI润色：标注 `glm-5.2`（非旧的 zai-org/GLM-5.2 代理）
- AI对话：返回专业回复，引用GB15618标准+推荐4种修复技术
