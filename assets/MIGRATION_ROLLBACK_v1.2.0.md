# SRS v1.2.0 迁移与回退说明

## 升级（v1.1.0 → v1.2.0，覆盖安装）
1. 退出 SRS（托盘图标 → 退出）。
2. **备份**：复制整个 `%APPDATA%\SRS` 目录（含 `srs.db`、`files`、`backups`、密钥文件）到安全位置。也可在“系统管理 → 备份恢复”先做一次手动备份。
3. 运行 `SRS-Setup-1.2.0-Windows-x64.exe`，安装到原目录（无管理员权限时使用默认的当前用户安装）。
4. 启动 SRS。启动时自动执行（幂等，可重复）：
   - 新建表 `recon_import_batches`、`recon_observations`（课题二 28 项指标，等价于 alembic `0008_v12_recon_indicators`）；
   - 旧库补列（v1.1 阶段/来源列，已存在则跳过）；
   - 阈值库更正：按官方 CSV 更新数值，删除非标准替代阈值（多氯联苯旧值、DDT 类、六六六总量、族群匹配项等），补 GB 15618 管制值；
   - 补权限 `file:read`（v1.1 文件页 403 的原因）。
5. 核对：登录后首页版本为 1.2.0；原有场地、导入批次、SSUI 批次与结论均在。

v1.1.0→v1.2.0 覆盖升级已在 Windows runner 上实测（先用 v1.1.0 安装包建库并写入演示数据，再覆盖安装 v1.2.0，验证数据保留、迁移与新功能可用），结果见验收证据 `acceptance_upgrade.json`。

## 便携版
解压 `SRS-Portable-1.2.0-Windows-x64.zip`；`SRS\SRS_PORTABLE.txt` 存在时数据写在 `SRS\SRS_data`。删除该标记文件即改用 `%APPDATA%\SRS`。便携版与安装版数据互不影响。

## 回退到 v1.1.0
1. 退出 SRS，卸载 v1.2.0（卸载**不删除** `%APPDATA%\SRS`）。
2. 用升级前的备份**整体替换** `%APPDATA%\SRS`（推荐），再安装 v1.1.0。
3. 若不恢复备份而直接装回 v1.1.0：v1.2 新增的两张表会被 v1.1 忽略；阈值更正会保留（这是对旧错误值的更正，不建议恢复旧值）。

## 数据库（PostgreSQL 部署）
服务器部署使用 alembic：`alembic upgrade head`（0007 → 0008）；回退 `alembic downgrade 0007_v11_stage_provenance`（删除两张课题二表）。阈值更正由 `scripts/seed_db.py` 执行。
