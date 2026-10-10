# SRS v1.2.1-rc.1 发布说明（修复候选版 / 预发布）

**状态：修复候选版（prerelease），不是最终验收版。** 本版针对 2026-10-10 交付审计（R01–R10）修复，被测提交 `e69116c6490483985b37983f6575946da5b9cc60`（分支 `fix/v1.2.1-remediation`）。v1.2.0-rc.1（e5a3728）保持不变。

## 主要修复
| 审计项 | 内容 |
|---|---|
| R01 | 阈值方向（上限/下限/区间）；有机质 OM_gkg 与有机碳 OC_pct 分开、不换算；单位按表头/检测记录换算，不可证明即排除；“Cr(VI)”中的 VI 不再当作单位；GB 36600 有机物阈值单位对齐；KOS 农用地类型与法规门禁一致（补 GB 15618 水田口径）；严重度饱和时取真实最不利点 |
| R02 | 正式 Top-N 只收本轨官方标准（生产 GB 15618-2018 / 生态 GB 36600-2018）、单位可证、B=1、证据 A/B 的因子；文献参考、交叉轨、最严档兜底、pH 区间等进入探索性提示；`official_ranking_status` = available / partial / insufficient_evidence；每项附证据链 |
| R03 | 版本化评价快照（SHA-256）统一界面、Excel、PDF、DOCX；修复前/修复后按阶段与批次分列，重复导入样品去重；修复后 SSUI 取课题三批次；五阶段业务记录与软件里程碑分开；界面地图与报告地图使用法规门禁同一口径；场地详情分阶段计数 |
| R04 | 报告 PDF 由 ReportLab 直接排版（表格、图件、页眉页脚、页码、嵌入中文字体）；DOCX 同一内容 |
| R05–R10 | 交付包重组（public / owner_private + 清单 + 哈希）；标准账户安装测试独立作业；演示场景 F/G 与独立校验器；语义级测试；文字表述统一 |

## 验证（自动化，2026-10-10）
| 测试 | 环境 | 结果 |
|---|---|---|
| 后端全量 pytest | 本机沙箱（macOS），提交 5ea4bb8（与 e69116c 后端/测试相同） | 591 passed, 12 skipped, 0 failed |
| CI 后端 pytest（SQLite） | GitHub Actions ubuntu，run 38046495186 | 590 passed, 13 skipped |
| CI PostgreSQL 并发测试 / 前端构建 | 同上 | 通过 |
| Windows 门禁测试 | GitHub Actions Windows Server 2025，run 38046495198 | 139 passed, 1 skipped |
| Windows 实装验收（安装路径含中文与空格） | 同上，管理员账户 | 全流程 221/221；重启 26/26；评价快照 15/15；v1.1.0→v1.2.1 升级 11/11；v1.2.0→v1.2.1 升级 13/13；便携版 7/7 |
| 标准（非管理员）账户 | 同上，本地账户 srsstd，计划任务方式，`/CURRENTUSER` | 安装 exit 0；进程属主 srsstd；数据库位于该账户 %APPDATA%；检查 7/7 |
| 演示包（A–G） | Windows 实装程序 | 209/209 比对项；独立校验器 20/20 |
| DOCX 渲染 | Windows 上 LibreOffice | A–E 报告均转换成功，逐页查看 |

**未执行：** 甲方 Windows 10/11 实机上的真人交互测试；Microsoft Word 中打开 DOCX 的核查。通过 `Start-Process -Credential` 从运行器会话直接以标准账户启动安装程序失败（exit 1，无日志），判断为跨会话凭据启动限制；改用计划任务方式后成功。

## 资产
- `SRS-Setup-1.2.1-Windows-x64.exe`、`SRS-Portable-1.2.1-Windows-x64.zip`（取自 run 38046495198，发布流程逐字节核对）及 `.sha256`
- 用户手册（DOCX/PDF）、公开版演示 PPT、演示数据包（模拟数据）、本说明、变更记录、已知限制、迁移与回退说明、`SHA256SUMS.txt`

## 升级
升级前请备份 `%APPDATA%\SRS`。v1.2.0 及更早生成的报告没有评价快照，升级后显示“无快照”，需重新诊断并生成报告。详见 `MIGRATION_ROLLBACK_v1.2.1.md`。

## 已知限制（摘要）
课题二冻结基线 M-REC-2025 与 Q01–Q18 待课题组确认；KOS 权重与模型 p3_alpha 未重训；文献参考阈值未获批准为正式限值；SSUI 为得分录入模式；尚无实测修复后数据；五阶段业务材料未演示；安装包未签名；`data/raw` 历史中的甲方工作簿是否移除由所有者决定。完整列表见 `KNOWN_LIMITATIONS_v1.2.1.md`。
