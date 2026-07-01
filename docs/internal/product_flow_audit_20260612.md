# 产品流程与前端审计 — 20260612

> 沙箱限制: 无 npm/浏览器, 无法实跑与截图。以下为**代码级审计**结论 + 需本机验证的清单。

## 1. 路由/流程完整性(代码核查 ✅)
登录 → 数据概览 → 地图 → 场地列表 → 场地详情(基本信息/点位地图/采样点宽表/EDA/报告)→ 障碍因子分析 → 功能重构分析 → SSUI 评价 → 推荐 → 全流程追溯(地块列表→阶段→附件上传)→ 报告生成下载 → AI 助手。
- 七项导航与对应页面、路由均存在; 本地 import 自检无缺失引用 ✅。

## 2. 本轮修复
- **#4 报告 UX**: 前端原仅 PDF。已改:
  - `api.generateReport(id, format)` 支持 `pdf|docx`;
  - `TraceDetail` 增"生成 PDF 报告""生成 DOCX 报告"双按钮;
  - 报告列表新增"格式"列, 下载文件名按 `data_snapshot.format` 用正确扩展名。
  - 后端 `/sites/{id}/report?format=docx` 早已支持(Query 校验 `^(pdf|docx|html)$`)。
- **#5 地图可靠性**:
  - 未配 `VITE_TIANDITU_KEY` 时回退 OSM(代码确认);
  - 新增**空坐标覆盖层**("当前无可用坐标点位…")与**瓦片加载失败覆盖层**(提示地图服务 key 域名白名单/网络);
  - 瓦片代理 `/api/v1/map/tile/...` **本轮未实现**, 在 docker/部署文档中说明演示需 key 白名单含 `127.0.0.1`/打包域名(见 `docs/deployment_desktop.md`)。

## 3. 需本机验证(无法在沙箱完成)
- [ ] `bash scripts/run_frontend.sh` 起前端, 逐流程点检 loading/empty/error 态。
- [ ] 窄屏(<768px)侧边栏折叠、地图/宽表横向溢出是否有横向滚动。
- [ ] DOCX 报告实际生成与下载(需后端 `python-docx`)。
- [ ] AI 助手抽屉问答(见 AI/RAG 审计)。
- [ ] 截图留档。
- [ ] Vite 主包 ~2.5MB: 建议后续按路由 `React.lazy` 拆包 + `manualChunks`(echarts/antd 分离), 本轮未改以免引入回归。

## 4. 残留风险
- 前端类型检查/构建仅能在本机 `npm run build` 确认; 沙箱仅做了 import 解析与括号配平 sanity。
