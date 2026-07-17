# SRS v1.0.1 功能测试报告

> 测试时间: 2026-07-17 | 测试环境: Windows 11 x64 | 版本: v1.0.1

## 测试环境

| 项目 | 值 |
|---|---|
| 系统 | Windows 11 x64 |
| SRS 版本 | v1.0.1 |
| 打包方式 | PyInstaller 6.18 + Inno Setup 6 |
| 数据 | 18 场地（3 真实 + 15 训练） |
| AI Key | 智谱 GLM-5.2 已预配 |
| 高德 Key | 已预配 |

## 页面截图清单（11 张）

| # | 页面 | 截图 | 说明 |
|---|---|---|---|
| 1 | 登录页 | 01_login_page.png | admin/Demo@2026 登录 |
| 2 | 首页仪表盘 | 02_dashboard.png | 场地分布/地图/统计 |
| 3 | 数字大屏 | 03_bigscreen.png | 全国场地分布+超标排名 |
| 4 | 场地列表 | 04_sites_list.png | 18 个场地 |
| 5 | 场地详情 | 05_site_detail.png | 个旧 HM 场地详情 |
| 6 | 障碍因子诊断 | 06_obstacle_diagnosis.png | KOS 诊断页面 |
| 7 | 功能重构 | 07_reconstruction.png | 双轨评价 |
| 8 | SSUI 评价 | 08_ssui.png | 可持续性评价 |
| 9 | 方案推荐 | 09_recommendation.png | 技术推荐 |
| 10 | 全流程追溯 | 10_trace.png | 五阶段追溯 |
| 11 | 系统管理 | 11_system.png | 账户/角色/关于 |

## API 功能验证（KOS 诊断）

```
KOS诊断成功: 4障碍因子
  #1 As_mgkg  KOS=0.807 thr=25.0  (pH>7.5档, GB15618-2018)
  #2 Pb_mgkg  KOS=0.777 thr=170.0
  #3 Cu_mgkg  KOS=0.759 thr=100.0
  #4 Zn_mgkg  KOS=0.755 thr=300.0
开放集: 10 formal_eligible / 4 formal_obstacle / 1 model_candidate / 3 family_alert / 3 unknown
动态阈值: 数据库查询(StandardThreshold) ✓
```

## 安装包信息

| 项目 | 值 |
|---|---|
| 文件名 | SRS-Setup-1.0.1-Windows-x64.exe |
| 大小 | 320 MB |
| 位置 | packaging/Output/ |

## 测试结论

- ✅ 登录系统正常
- ✅ 18 场地数据完整
- ✅ KOS 诊断功能正常（4 障碍因子 + 动态阈值）
- ✅ 开放集四层识别正常
- ✅ AI Key + 高德 Key 已预配
- ✅ 所有页面可正常加载
- ✅ 安装包生成成功
