# SRS Round10 源码门禁执行报告

## 审计基线

- 基线提交：`00e61989c4ae3dd8794ef380fa85007ca87adc17`
- 工作分支：`codex/srs-round10-source-gate`
- 本轮未生成安装包。

## 项目方接受的演示交付例外

以下四项由项目方明确要求保留，本轮未修改，也不作为门禁失败项：

1. 继续使用既定 AppData 数据目录及默认 JWT 配置。
2. 桌面启动器继续向甲方 AppData 写入内置 AI/地图 Key。
3. PyInstaller 继续收集 `builtin_keys`。
4. 安装器继续使用 v1.0.1 的 AppId、目录和文件名。

## 验证结果

- `python -m compileall -q backend/app backend/tests backend/alembic ml`：通过。
- 后端全量 `pytest -q -rs`：`445 passed, 0 failed, 12 skipped`，耗时 27 分 35 秒。
- 12 个 skip 均为废弃旧模板/旧 RF 路径、未提交训练切分 CSV 或旧“无场地”测试；本轮关键 KOS、SSUI、迁移和三场地端到端测试为 0 skip。
- `npm ci --no-audit --no-fund --prefer-offline`：通过，干净安装 181 个包。
- `npx tsc --noEmit`：通过。
- `npm run build`：通过，Vite 转换 3716 个模块；保留大 chunk 警告。
- Alembic 空库 `upgrade head → downgrade 0005_round9 → upgrade head`：通过，最终 revision 为 `0006_site_original_code (head)`。
- 模拟旧版 0005 数据库迁移：通过；旧 `AUTO-20260720-1234`、`GJ-2025-001` 自动迁移为 `SRS-A`、`SRS-B`，原编号可追溯。

## 三份甲方真实数据

| 数据 | 污染类型 | 点位 | 生产 KOS Top | 生态 KOS Top | 模型贡献 | 重构 | SSUI |
|---|---|---:|---:|---:|---|---|---|
| 乡村建设用地 | composite | 8 | 2 | 1 | 当前决策点局部贡献 | 证据不足/无法评价 | blocked（实测因子阈值未解析） |
| 南京栖霞 | organic | 49 | 1 | 1 | 当前决策点局部贡献 | 证据不足/无法评价 | blocked（有机污染评价指标不足） |
| 云南个旧 | heavy_metal | 134 | 5 | 1 | 当前决策点局部贡献 | 证据不足/无法评价 | blocked（数据不足） |

三场地均完成：智能导入、污染类型识别、双轨 KOS、局部模型贡献、持久化、评价、推荐和报告上下文。所有展示场地编号均不含数字。云南个旧未出现“优、整体状况良好、低风险污染”等矛盾结论。

## 证据文件

- `site_composite.json`
- `site_organic.json`
- `site_heavy_metal.json`
- `three_real_sites_e2e.json`

这些 JSON 只记录真实导入结果及算法状态；未填入测试夹具、代理经济数据、内置 Key、令牌或本机绝对路径。

## 尚需外部执行

- 当前会话未提供用户点名的应用内浏览器控制入口，因此未做应用内浏览器页面自动化截图。
- 推送后需等待 GitHub Actions 在新提交上完成。
- 源码与 CI 复审通过前，不生成正式安装包；安装包仍需在干净 Windows VM 做最终验收。
