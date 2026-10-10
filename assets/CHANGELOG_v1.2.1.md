# SRS v1.2.1 变更记录（相对 v1.2.0-rc.1 / e5a3728）

| 审计项 | 变更 | 提交 |
|---|---|---|
| R01 阈值方向 | 文献参考阈值区分上限/下限（CEC、全氮、有机质、有机碳、磷、钾为下限）；pH 为区间；方向未知不判定 | db64677, a6d26e8 |
| R01 有机质/有机碳 | 新 canonical OM_gkg（g/kg）与 OC_pct（%）分开，不做 SOM↔SOC 换算 | db64677 |
| R01 单位 | 使用 Measurement.unit 与表头单位换算；不可证明换算即排除（unit_unresolved）；阈值单位与数值单位对齐（GB 36600 有机物 mg/kg↔ng/g） | db64677, fe67f17 |
| R01 形态 | 表头 Cr(VI) 中的“VI”不再解析为单位；旧库迁移 0009 修复 | db64677, fe67f17 |
| R01 农用地类型 | 阈值库补 GB 15618 水田口径；KOS 增加 farmland_type / eco_land_class，与法规门禁一致 | 54bce6b, 70958bb |
| R01 最不利点 | R 饱和时按超标倍数选最不利点 | 63a8a16 |
| R02 证据准入 | 正式 Top-N 只收录本轨官方标准、resolved、单位可证、B=1、证据 A/B；其余进入 exploratory_obstacles；official_ranking_status = available / partial / insufficient_evidence；每项附 evidence_chain | db64677, a6d26e8 |
| R03 报告口径 | 评价快照（SHA-256）统一界面/Excel/PDF/DOCX；阶段×批次分列、重复导入样品去重；场地级超标按阶段由法规门禁给出；修复后 SSUI 取课题三批次；五阶段业务记录与七项软件里程碑分开；模拟标签、中文污染类型 | fe67f17, 63a8a16 |
| R03 地图与计数 | 场地地图图层与报告图件改用法规门禁同一口径（GB 15618 筛选值，按点位 pH 与门禁登记的农用地类型）；v1.2.0 中界面地图因中文因子名无阈值规则而全部显示“无阈值”的问题随之修复；场地详情/障碍因子页按阶段显示样品与检测记录数（不再把修复前与修复后点位记录相加称为“采样点”） | 0d01c5d |
| R04 PDF | ReportLab 直接排版：表格、图件、页眉页脚、页码、嵌入中文字体；DOCX 同一内容 | fe67f17 |
| R04 字体/版式 | Linux CI 与 Docker 镜像安装可嵌入的 TrueType 中文字体（fonts-wqy-microhei；noto-cjk 为 CFF 轮廓，ReportLab 无法嵌入）；报告地图经纬度刻度不再使用偏移记号；无水田专项值的因子注明“其他农用地口径” | e5f7a40, 85ac9ec |
| R06 Windows | v1.2.0→v1.2.1 升级测试；标准账户独立作业（无 continue-on-error）；DOCX 渲染作业 | 54bce6b |
| R07/R08 演示 | 补充场景 F（有机-重金属复合）、G（仅文献参考阈值）；独立校验器；覆盖台账；环境锁定；三个原始场地私有回归脚本 | 70958bb |
| R09 测试 | test_v121_kos_semantics（KOS 语义, 参数化后 42 项）、test_v121_report_consistency（跨渠道一致性）；report_invariants 用于演示与 Windows 验收 | 各提交 |
| R10 文本 | “/CURRENTUSER 免管理员”改为如实表述；公开版 PPT 章节连续编号；手册、操作脚本、已知限制更新 | 本提交 |
