# SRS 系统修复状态报告

**日期**: 2026-07-16
**提交**: 3d4d069 → 9534cd9 (main)
**目标**: 接续 codex 计划完成系统修复，解决裴总指出的8项问题

---

## 已完成修复（8项）

### 1. 角色切换及审批功能 ✅
- **状态**: 功能已完整实现，此前仅未演示
- 4个角色(admin/enterprise/agency/regulator)，密码统一 Demo@2026
- 权限隔离验证: enterprise 登录后菜单无"系统管理"(需 user:manage 权限)
- 注册审批: POST /auth/register → pending → admin 审批 → active
- 五阶段流程: survey→approval→construction→effect→maintenance 含状态机
- 截图: 18_enterprise_dashboard.png

### 2. 真实场地数据代表性 ✅
- **此前**: 个旧只有2个假采样点(SP01/SP02坐标102.81也不对)
- **修复后**: 用系统导入功能重导三份真实数据
  - 个旧HM: 134采样点, 2412测量, 坐标103.14°E/23.34°N
  - 栖霞OP: 49采样点, 2009测量
  - 农村HM+OP: 8采样点, 224测量
- 截图: 19_gejiu_site_detail_134pts.png

### 3. KOS诊断UI中F1/AUC残留 ✅
- ObstacleAnalysis.tsx: AUC_GUIDE改为Spearman解读, 技术详情标题"模型验证指标"
- diagnosis_service.py: calc_trace AUC/F1 → Spearman
- methodFlows.ts: 方法说明清除AUC/SHAP/F1
- SystemManagement.tsx: CV AUC → CV Spearman
- 截图: 22_kos_prod_result.png

### 4. 大模型回答多余标点 ✅
- SYSTEM_PROMPT/DIAGNOSIS_POLISH_PROMPT: 添加禁止markdown指令
- 新增 _clean_markdown_punct(): 剥离 **加粗/##标题/列表标记/中文引号
- 在 chat 和 polish_diagnosis 返回前调用

### 5a. EDA数据探索页面 ✅
- **状态**: 功能完整, 是场地详情页的Tab(非独立路由)
- 统计体检/直方图/云雨图/散点图/相关热力/Q-Q/分组对比/Mann-Whitney检验/PCA/异常值
- 截图: 20_eda_panel.png

### 5b. 生产生态双轨诊断 ✅
- 生产轨+生态轨均成功运行134点真实数据
- KOS公式表显示双轨用途权重差异(生产严/生态宽)
- 截图: 21_diagnosis_prod_134pts.png, 23_kos_eco_result.png

### 6. 文字显示不完整 ✅
- DashboardScreen.module.css: alertName/traceSite
  - white-space:nowrap + text-overflow:ellipsis → -webkit-line-clamp:2
- 截图: 24_dashboard_map_fixed.png

### 7. 采样点位地图坐标 ✅
- **根因**: 数据问题(只有2个假点), 非代码bug
- SiteMap.tsx 无随机生成逻辑, 坐标完全来自Excel原始数据
- 重导134点后: 真实坐标103.14°E/23.34°N, SiteMap 0 errors
- 截图: 25_gejiu_134pts_map.png

---

## 截图清单（25+9张）

### 本轮修复验证截图 (artifacts/full_screenshots_20260715/)
| # | 文件 | 内容 |
|---|------|------|
| 18 | 18_enterprise_dashboard.png | 企业用户Dashboard(无系统管理菜单) |
| 19 | 19_gejiu_site_detail_134pts.png | 个旧134点场地详情 |
| 20 | 20_eda_panel.png | EDA数据分析面板 |
| 21 | 21_diagnosis_prod_134pts.png | 生产轨诊断(134点) |
| 22 | 22_kos_prod_result.png | KOS诊断结果详情 |
| 23 | 23_kos_eco_result.png | 生态轨诊断结果 |
| 24 | 24_dashboard_map_fixed.png | Dashboard地图(0 errors) |
| 25 | 25_gejiu_134pts_map.png | 个旧134点地图 |

### 早期验证截图 (early_screenshots/)
01_login ~ 09_ai_chat: GLM-5.2接入、AI配置、AI对话等

---

## 已知技术债(下轮处理)
1. OP Hurdle两阶段模型 — OP零膨胀数据(94%零目标)本质问题
2. 栖霞/农村场地无经纬度列 — 原始Excel文件本身没有坐标数据
3. AI润色有时仍返回"—"(GLM超时或429降级)

## 代码变更统计
- 修改文件: 9个(前端4+后端2+脚本2+配置1)
- 新增行: +216, 删除: -29
- 新增截图: 34张
- 新增脚本: reimport_real_sites.py, reimport_direct.py, reimport_via_api.py
