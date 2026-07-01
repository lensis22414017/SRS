# SRS PR 就绪审计 — 20260612

审计人: Fable 5。目标: 让数据/模型/报告/UI/工作流/AI/Docker/追溯链可辩护、可复现、可评审。**不为刷分。**

## 9 项问题状态总览
| # | 问题 | 状态 | 说明 |
|---|---|---|---|
| 1 | 数据切分泄漏 | ✅ 已修+已验证 | 连通分量切分, 双键零泄漏; 强化测试; 重建 splits/registry。详见 data_split_leakage_audit。 |
| 2 | PR 清洁 | ✅ 沙箱可做部分完成 | .gitignore 补生成态大文件/.env.local/scratch; 分支策略见下。 |
| 3 | 数据库迁移 | ✅ 基线迁移已加 | `0001_baseline.py`(create_all 落当前 schema, 可回滚); Postgres 干净卷初始化命令见 docker 日志。 |
| 4 | 报告 UX(PDF/DOCX) | ✅ 已修 | 前端补 DOCX 按钮 + 真实格式列 + 正确扩展名下载; 后端早支持三格式。 |
| 5 | 地图可靠性 | ✅ 部分修+文档 | OSM 回退确认; 新增空坐标/瓦片失败覆盖层; 瓦片代理未做(文档化)。 |
| 6 | 报告专业质量 | ⚠️ 审计+缺陷记录 | 主要章节齐备; 发现编号重复缺陷、缺人工复核区与静态图表, 记录带测试修法, 本轮不盲改。 |
| 7 | AI/RAG | ✅ 代码核查 | RAG 对"砷超标修复技术"可命中(技术库含固化/植物修复); test_ai 不打印密钥; 限流降级已实现。模型实调需本机。 |
| 8 | 前端/产品流程 | ⚠️ 代码审计 | 路由/页面完整、import 无缺失; loading/empty/error 与窄屏需本机点检+截图。 |
| 9 | Docker 验证 | ⏳ 待本机 | 沙箱无 Docker/外网; 命令与预检见 docker_validation_log, 需本机执行回填。 |

## 沙箱限制(诚实声明)
本审计运行在隔离沙箱: **无法 pip 安装 sqlalchemy/fastapi/sklearn、无法 npm 安装/构建、无法 Docker、无外网**。
因此: 完整 pytest、`npm run build`、Docker 流程、AI 模型实调、浏览器截图**均需项目组本机执行**。
沙箱内**已真实执行并验证**的: 切分泄漏审计与修复(pandas)、强化切分测试前 3 项、字段标准化映射、model_ready 派生、本地 import 解析、报告模板章节核查、技术库/案例库存在性。

## #2 PR 分支策略
SRS 目录在 `/Users/lensis` 这个父 git 根下显示为 untracked。两种干净方案:
- **方案A(推荐): 独立仓库**。`cd /Users/lensis/大语言模型/Projects/SRS && git init && git add -A && git commit -m "feat: SRS MVP + 验证体系"`。`.gitignore` 已覆盖 .env/db/storage/node_modules/dist/生成态数据。
- **方案B: 父仓库内 pathspec 暂存**。`git -C /Users/lensis add -- '大语言模型/Projects/SRS'` 并确认 `git status` 不含 `backend/.env`、`frontend/.env.local`、`*.db`、`storage/`、`node_modules/`、大 CSV。
提交前自检: `git status --ignored` 确认机密与本地产物在 ignored 列表。

## 已改文件(本轮)
- `ml/models/dataset_splits.py`(连通分量零泄漏切分)
- `backend/tests/test_dataset_splits.py`(全配对双键泄漏测试)
- `data/splits/*`(重建, 零泄漏; 大 CSV 已加入 .gitignore)
- `frontend/src/api/client.ts`(generateReport 带 format)
- `frontend/src/pages/TraceDetail.tsx`(PDF/DOCX 双按钮 + 格式列 + 扩展名)
- `frontend/src/components/SiteMap.tsx`(空坐标/瓦片失败覆盖层)
- `.gitignore`(生成态大文件 / .env.local / scratch)
- `backend/alembic/versions/0001_baseline.py`(基线迁移)
- `docs/audit/*`(6 份审计文档)

## 剩余风险(优先级)
1. **泛化指标**: 用零泄漏分组切分重训后, AUC 预计显著低于 0.9991 行级随机值——这是**正确的**, 应以分组指标为准, 旧高分不得作为泛化证据。
2. 报告静态图表/人工复核区缺失(#6), 建议下个 PR 带测试补。
3. Docker/前端构建/AI 实调结果待本机回填。
4. 前端主包 2.5MB, 建议路由级懒加载。
