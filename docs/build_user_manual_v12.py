"""SRS v1.2.0 用户操作手册生成器(年度验收版): 同一内容源 → 可编辑 DOCX + PDF。

截图从 --shots 目录读取(capture_v110_screenshots.command 或 Windows CI 生成);
缺失的截图以醒目的"截图位"占位, 绝不复用旧版截图。
用法: python docs/build_user_manual_v11.py --shots <dir> --out <dir>
"""
from __future__ import annotations

import argparse
import html as H
import json
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
TITLE = "污染场地土壤生态-生产功能重构监管系统（SRS）"
SUB = f"用户操作手册 v{VERSION}"
FONT_DIR = "/Applications/Microsoft PowerPoint.app/Contents/Resources/DFonts"
LABEL = "模拟数据——仅供测试/演示"


def _weights():
    return json.load(open(os.path.join(ROOT, "data", "standards", "ssui_weights_pptx_v1.json"), encoding="utf-8"))


def _features():
    import sys
    sys.path.insert(0, os.path.join(ROOT, "ml", "evaluation"))
    import reconstruction_m2025 as M
    return M


def content():
    W = _weights()
    M = _features()
    C = []  # (kind, payload)
    h1 = lambda t: C.append(("h1", t)); h2 = lambda t: C.append(("h2", t))
    p = lambda t: C.append(("p", t)); ul = lambda *xs: C.append(("ul", list(xs)))
    ol = lambda *xs: C.append(("ol", list(xs))); tb = lambda hdr, rows: C.append(("table", (hdr, rows)))
    note = lambda t: C.append(("note", t)); shot = lambda f, cap: C.append(("shot", (f, cap)))

    h1("第一章 系统概述")
    h2("1.1 系统定位")
    p("SRS 面向污染场地修复与再利用监管，支持从修复前调查数据到修复后可持续利用评价的全过程记录、计算与追溯。"
      "系统由生态环境部土壤与农业农村生态环境监管技术中心委托，浙江大学环境与资源学院研制。本手册对应 v" + VERSION +
      "（修复候选版，待甲方验收），界面截图均采集自 Windows（GitHub Actions 虚拟机）实际安装的 v" + VERSION + " 程序，数据为合成演示数据；"
      "较长页面在手册中只截取上部，完整页面见截图包。")
    h2("1.2 三个课题与数据阶段")
    p("修复前数据只进入课题一、课题二的计算；修复后数据只能通过课题三的独立导入功能进入系统。两类数据在数据库中分表存储，不会互相替代，也不会自动复制。")
    tb(["课题", "功能", "数据阶段", "入口", "主要输出"], [
        ["课题一", "障碍因子识别（KOS）", "修复前", "场地管理 → 数据导入；障碍因子分析（课题一）", "关键障碍因子 Top-N、补测建议"],
        ["课题二", "功能重构可行性（28 项指标）", "修复前", "重构指标导入（课题二）；功能重构分析（课题二）", "生产/生态重构可行性、限制性指标、修复前情景判断"],
        ["课题三", "修复后土壤持续利用度（SSUI）", "修复后", "修复后SSUI（课题三）", "SSUI 值与等级；修复后利用方向结论"],
    ])
    h2("1.3 方法版本")
    tb(["模块", "方法版本", "说明"], [
        ["课题二", M.METHOD_VERSION, "《(2025年)…评价方法+年度报告》表2.18–2.23：综合得分 = Σ(F×T)，表2.18 权重原值（Σ=0.9643）不归一；缺测时按表2.19/2.21 准则层权重，土壤质量类与修复潜力类用内梅罗指数计类别分；>50 可行"],
        ["课题三", "SSUI-PPTX-v1（得分录入模式）", "SSUI = f(t)·Σv{_j}·S{_j}·M；D1–D25 由课题组按分级标准给出得分 s（0–1），系统不做原始值到得分的换算"],
        ["法规阈值", "GB 15618-2018 / GB 36600-2018", "由生态环境部官网发布的标准 PDF 逐行转录；GB 36600 表1 45 项、表2 40 项全部可用"],
    ])
    note("课题二、三的部分方法细节（如 C 库因子赋分笔误、SSUI 支持阈值 0.6）仍待陈亮、宋伟杰老师确认，相关结果标注“方法状态：冻结基线/暂定”，系统不静默修改。")
    h2("1.4 用户角色与权限")
    tb(["角色", "可进行的操作"], [
        ["系统管理员（admin）", "全部功能，含用户/角色管理、参数设置、备份恢复、技术库管理"],
        ["企业用户（enterprise）", "本企业场地的数据录入、查询、导出、报告生成、地图、追溯与文件查看"],
        ["第三方机构（agency）", "获授权场地的数据录入、查询、追溯查看、文件查看与下载"],
        ["监管人员（regulator）", "全部场地只读查询、地图、追溯、报告生成、日志审计；不能导入数据或运行利用判定"],
    ])

    h1("第二章 安装与首次启动")
    h2("2.1 运行环境")
    ul("操作系统：Windows 10/11 64 位（验收环境：Windows Server 2025 Datacenter，GitHub Actions）", "内存 8 GB 及以上；可用磁盘 3 GB 及以上",
       "浏览器：系统启动后自动打开默认浏览器（推荐 Edge 或 Chrome）", "网络：核心功能可离线使用；在线底图与 AI 问答需联网")
    h2("2.2 安装版")
    ol(f"双击 SRS-Setup-{VERSION}-Windows-x64.exe，按向导完成安装。安装路径可以包含中文和空格。",
       "可在命令行加 /CURRENTUSER 参数安装到当前用户目录（例：SRS-Setup-" + VERSION + "-Windows-x64.exe /CURRENTUSER）。该参数把程序安装到当前用户目录（%LOCALAPPDATA%\\Programs\\SRS）。v1.2.1 在 GitHub Actions Windows Server 虚拟机上以标准（非管理员）测试账户、计划任务方式执行了该安装并完成启动与导入/评价检查（见发布说明）；尚未在甲方 Windows 10/11 实机上由真人交互验证。无法安装时可使用便携版。",
       "安装完成后，从开始菜单或桌面快捷方式启动“SRS”。",
       "核对安装包完整性：在 PowerShell 中运行 Get-FileHash <安装包> -Algorithm SHA256，与发布页 .sha256 文件一致。")
    h2("2.3 便携版")
    ol(f"解压 SRS-Portable-{VERSION}-Windows-x64.zip 到任意目录（路径可含中文和空格）。",
       "双击 SRS\\SRS.exe。目录中的 SRS_PORTABLE.txt 使所有数据写入同级的 SRS_data 子目录，不写入 %APPDATA%。",
       "删除 SRS_PORTABLE.txt 后，便携版改用与安装版相同的 %APPDATA%\\SRS 数据目录。")
    h2("2.4 首次启动")
    p("首次启动时数据库为空，系统进入“首启设置向导”。按提示设置管理员用户名和密码（至少 8 位，且包含大写字母、小写字母、数字、特殊字符中的至少 3 类），完成后用该账户登录。安装包不包含任何业务数据或测试账户。")
    shot("00_first_run_setup.png", "首次启动：管理员设置向导（空数据库）")
    shot("01_login.png", "登录页面")
    h2("2.5 数据存储位置")
    tb(["内容", "安装版（Windows）", "便携版"], [
        ["数据库", r"%APPDATA%\SRS\srs.db", r"SRS\SRS_data\srs.db"], ["上传文件与报告", r"%APPDATA%\SRS\storage", r"SRS\SRS_data\storage"],
        ["备份", r"%APPDATA%\SRS\backups", r"SRS\SRS_data\backups"], ["启动日志", r"%APPDATA%\SRS\launcher.log", r"SRS\SRS_data\launcher.log"]])
    h2("2.6 从 v1.2.0 / v1.1.0 / v1.0.x 升级")
    ol("升级前在“系统管理 → 备份恢复”中创建一次备份。",
       f"直接运行 SRS-Setup-{VERSION}-Windows-x64.exe 覆盖安装（安装目录不变）。",
       "首次启动时系统自动：新增课题二指标批次表（迁移 0008）；修复旧版把六价铬“VI”误存为单位的记录（迁移 0009）；补充 GB 15618 水田口径筛选值；按官方标准更正内置阈值表并删除旧版的非标准替代阈值；为已有角色补充“文档查看”权限。已有场地、检测数据、课题三批次、结论和已生成的报告全部保留。",
       "v1.2.0 生成的旧报告没有评价快照，系统如实显示“无快照”；请对已有场地重新运行“障碍因子分析”后再生成报告，以获得正式/探索性分层与新的报告格式。",
       "升级后可对已有场地重新运行“功能重构分析”，结果按冻结方法 M-REC-2025 计算并保留历史记录。")
    p("升级路径已在 Windows（GitHub Actions 虚拟机）上实测两条：v1.1.0 → v" + VERSION + "；v1.2.0 → v" + VERSION + "（含课题二/三批次与已出报告保留、六价铬单位修复、重新诊断得到正式/探索性分层）。")
    h2("2.7 卸载")
    p("通过开始菜单“卸载 SRS”或系统“应用和功能”卸载。卸载不删除 %APPDATA%\\SRS 下的数据库和备份；需要彻底清除时请手动删除该目录。")

    h1("第三章 全流程追溯：进入即见的引导")
    p("点击左侧“全流程追溯”，页面顶部立即显示五阶段引导：每个阶段需要上传的资料、可下载的模板，以及对应的课题和数据阶段。查看引导不会创建任何记录。")
    shot("20_trace_guide.png", "全流程追溯引导（未选择场地时即显示）")
    tb(["阶段", "数据阶段 / 课题", "系统操作", "需上传", "可下载"], [
        ["调查评估", "修复前 / 课题一、二", "导入修复前数据 → KOS → 28 项指标导入 → 重构可行性 → 情景判断", "调查报告、布点方案、检测报告", "修复前检测模板、课题二指标模板"],
        ["方案审批", "修复前 / 课题一、二", "技术推荐、方案比选", "修复方案、专家意见、批复", "—"],
        ["施工监理", "—", "记录进度与监理意见", "施工日志、监理报告、二次污染监测", "—"],
        ["效果评估", "修复后 / 课题三", "导入修复后 SSUI → 计算 → 利用结论", "效果评估报告、修复后检测报告", "课题三模板、SSUI 结果"],
        ["后期管护", "修复后 / 课题三", "按年份更新 t 重新导入；生成全流程报告", "管护记录、长期监测数据", "全流程追溯报告"]])
    p("在列表中点击“进入追溯”选择场地后，页面分两部分显示：①“七项软件操作里程碑”（修复前数据导入、障碍因子识别、重构可行性、修复前情景判断、修复后 SSUI 导入、修复后利用结论、全流程报告），记录系统内是否执行过该操作；②“五阶段业务记录”（调查评估、方案审批、施工监理、效果评估、后期管护），只有上传了对应材料并标记完成才显示“已完成”，没有记录或材料的阶段显示“未开展”。")
    note("软件里程碑 7/7 不等于五阶段业务完成。演示数据不含调查、审批、施工、效果评估、管护材料，因此演示场地的五阶段均显示“未开展”，报告中同样如实显示。")
    shot("21_trace_detail.png", "场地追溯详情：软件里程碑、五阶段业务记录与报告")

    h1("第四章 修复前数据准备与导入（课题一）")
    h2("4.1 下载模板")
    p("在全流程追溯引导或“场地管理 → 数据导入”中下载《修复前检测数据导入模板（PRE-v1.1）》。第一张工作表为数据表，每行一个采样点。")
    h2("4.2 填写规则")
    ul("必填：采样点编号；建议填写经纬度、采样深度、土壤类型、pH。",
       "浓度单位以表头括号为准（如“铅_Pb(mg/kg)”）。低于检出限填写“<检出限”（如 <0.01），系统保留原文并按规则处理。缺测留空，缺测不会被当作 0 或达标。",
       "生产门禁需要 GB 15618 基本项目（镉、汞、砷、铅、铬、铜、镍、锌）和 pH；生态门禁需要 GB 36600 表 1 的 45 项基本项目（含六价铬及 VOC/SVOC），可在模板后追加列。",
       f"演示/模拟数据须在备注列或说明页注明“{LABEL}”。系统识别到该标签后，会把该场地及其所有结果标为模拟数据。",
       "场地编号统一显示为纯字母（如 SRS-A）；原始业务编号保存在“原始编号”中。")
    h2("4.3 导入与校验")
    ol("场地管理 → 导入数据 → 选择文件 → 系统自动识别字段（可在向导中调整映射）。",
       "查看校验报告：错误、警告、超标因子统计。同一文件重复导入时按“跳过 / 覆盖 / 新版本”策略处理（按内容指纹判重）。",
       "导入完成后，在场地详情中查看点位地图、检测数据和 EDA 分析。")
    shot("05_import.png", "数据导入页面")
    shot("03_sites.png", "场地管理列表（5 个合成演示场地）")
    shot("04_site_detail.png", "场地详情")

    h1("第五章 课题一：障碍因子识别（KOS）")
    ol("左侧点击“障碍因子分析（课题一）”，选择场地和评价轨道（生产 / 生态）。", "点击“运行诊断”。系统使用修复前检测数据和已验证的 p3_alpha 模型计算；模型文件缺失或损坏时明确报错，不会自动重训或给出替代结果。",
       "生产轨道请选择农用地类型（水田 / 其他），系统按点位 pH 与该类型选取 GB 15618 筛选值，与利用方向结论的法规门禁一致；生态轨道选择第一类 / 第二类用地。",
       "查看结果：①“正式关键障碍因子 Top-N”，只收录本轨官方标准（生产 GB 15618 / 生态 GB 36600）筛选值、单位可证明换算、实测超标且证据等级 A/B 的因子；②“探索性提示（待复核）”，列出用文献参考值、跨路径参考值或启发式区间判定的因子，并标明上限（超标）或下限（不足）方向。")
    p("正式结果不足 3 个因子时标注“部分结果”；没有因子满足条件时标注“证据不足，无正式排名”，不会用文献参考值填补。")
    tb(["情形", "v1.2.1 处理"], [
        ["阳离子交换量、全氮、有机质、有机碳、有效磷、速效钾等肥力指标", "下限指标：低于参考值才是“不足”，高值不构成障碍；参考值来自文献/行业标准，只进入探索性列表"],
        ["有机质（g/kg）与有机碳（%）", "两个独立指标，互不换算（不使用 1.724 系数）；有机质不会被当作有机碳与 0.35% 比较"],
        ["单位", "按导入表头或检测记录单位换算（如 % ↔ g/kg、mg/kg ↔ ng/g）；无法证明换算的单位直接排除并列出，不按原数值参与判定"],
        ["六价铬 Cr(VI)", "“VI”为形态标记，不是单位；总铬与六价铬不互换"],
        ["有机物（苯并[a]芘、萘、石油烃等）", "数值换算到与 GB 36600 阈值相同的单位后再比较"]])
    p("KOS = B ×（0.30R + 0.25W + 0.15M + 0.20S + 0.10E），只在规则判定 B = 1 时计算。R 为规则严重度，W 为用途权重，M 为模型贡献度，S 为稳定性，E 为证据强度（官方标准 A；行业/文献标准 B 或 C）。每个因子取超标最严重的真实采样点，结果中给出判定点、阈值来源行和单位换算记录（证据链）。")
    shot("06_obstacle_S1.png", "障碍因子分析（课题一）")

    h1("第六章 课题二：28 项重构指标导入与功能重构可行性")
    h2("6.1 导入流程")
    ol("左侧点击“重构指标导入（课题二）”，选择场地。",
       "选择数据来源（真实 / 现场实测 / 模拟）、来源核实状态、农用地类型（旱地 / 水田 / 未注明）和生态用地类别（第一类 / 第二类）。",
       "点击“下载模板”（RECON-PRE-v1.2），按 6.2 填写；也可以直接上传子课题提供的宽表（首行为表头、一行一个点位，中英文表头均可）。",
       "点击“上传指标数据”。此步骤只做校验预览，不写入业务数据：显示已映射指标数、未提供的指标、错误（逐格定位）、告警和数值文本清洗记录。",
       "无错误时点击“确认入库”。系统在一个事务中写入点位 × 指标观测值并按 M-REC-2025 计算生产、生态两轨结果；同一场地的旧批次标为“已被新批次替代”。",
       "在“已导入批次”中点击“查看”看计算过程，点击“导出”得到结果摘要、点位 F 值、原始值、清洗记录和方法待确认项。")
    shot("08_recon_import_S2_result.png", "课题二指标导入：已确认批次的结果与计算过程")
    h2("6.2 28 项指标与单位")
    tb(["序号", "指标", "单位/类型", "生产轨道赋分（表2.22）"], [
        [i + 1, M.FEATURES[f]["cn"], M.FEATURES[f]["unit"],
         ("国标三档 10/50/100" if M.FEATURES[f]["kind"] == "pol" else
          ("类别分级" if M.FEATURES[f]["kind"] in ("cat", "cat_or_num") else "数值分档"))]
        for i, f in enumerate(M.RECON_28)])
    p("模板在 28 项之后还提供六价铬和生态轨道补充指标（含盐量、入渗率、水解性氮、有效硫/镁/钙/铁/锰/铜/锌/钼、可溶性氯），均为选填。")
    h2("6.3 类别指标取值")
    tb(["指标", "可填写的取值（中文或英文）", "生产 F"], [
        [M.FEATURES[f]["cn"], k + "（" + " / ".join(al[1:3]) + "）", M.CAT_SCORE["production"].get(f, {}).get(k, "—")]
        for f in ("bulk_density", "biodiversity", "salinization", "irrigation_drainage", "texture", "carbon_factor")
        for k, al in M.CATEGORY_MAP[f].items()])
    p("剖面构型可填写单个构型（如 通体壤、壤/砂/壤、sand/clay/clay）或同一分档内多个构型用“、”连接。")
    h2("6.4 校验规则")
    tb(["情形", "系统处理"], [
        ["数值中带不间断空格、制表符（如“0.64 ”）", "确定性去除并逐格记录原文与清洗结果，保留原文"],
        ["Excel 错误值（#VALUE!、#DIV/0! 等）", "按缺测处理并告警，不当作 0"],
        ["“<0.01” 低于检出限", "按 DL/2 参与计算，保留限定符"],
        ["类别值无法识别、点位编号重复、pH 超出 0–14、浓度为负", "错误，不可确认"],
        ["阶段填写为“修复后”、模板场地编号与所选场地不一致", "错误：修复后数据请使用课题三"],
        ["常数列、只有 1 个点位、全氮 > 10 g/kg 等超出常见范围", "告警（可确认），提示核对单位"],
        ["与已确认批次内容相同", "错误：不重复导入（按内容指纹，另存为文件也能识别）"],
        ["“有机质”列、“六价铬”与“铬”", "有机质不换算为有机碳；总铬与六价铬分别对应各自指标"]])
    shot("09_recon_import_validation_error.png", "课题二导入校验：非法类别逐格报错（不可确认）")
    shot("10_recon_import_preview_ok.png", "课题二导入预览：校验通过，含常数列告警")
    h2("6.5 计算方法（M-REC-2025）")
    ol("点位 → 场地：数值指标取中位数，类别指标取众数（方法 §2.3.2.1）；导出文件同时给出每个点位的 F 值和等级分布。",
       "按表2.22 对每项指标分等赋值 F。污染物：生产轨道按 GB 15618-2018（超管制值 10、超筛选值 50、未超 100；无管制值的铜、镍、锌、六六六、滴滴涕、苯并[a]芘只按 50/100），生态轨道按 GB 36600-2018 第一类用地。",
       "全指标路径：表2.18 的 26 项均有赋分时，综合得分 = Σ(F × T)，T 为表2.18 原值（Σ=0.9643，不归一，理论最高 96.43）。",
       "缺失数据路径：否则按表2.19（生产）/表2.21（生态）准则层权重计算；土壤质量类、修复潜力类用内梅罗指数 P = [(P平均² + P权重²)/2]^½ 计类别分；任一准则无可赋分数据时结果为“证据不足/无法评价”，并列出缺失准则。",
       "综合得分 > 50 为“可行”，≤ 50 为“不可行”。F ≤ 60 的指标列为限制性指标。")
    note("重构可行性得分不能替代法规安全门禁。例如个旧测试表的生产得分可能大于 50，但 Cd、As、Pb 超过 GB 15618 管制值，利用决策仍为“不支持”。")
    shot("07_reconstruction_S2.png", "功能重构分析（课题二）")
    shot("18_decision_pre_A.png", "修复前情景判断（不作为修复后结论）")
    note("修复前情景判断只说明“以当前状态，哪些因子必须修复到什么水平”，结论前缀为【修复前情景判断，非修复后利用结论】。修复完成后，必须用修复后数据（课题三）重新判定。")

    h1("第七章 课题三：修复后 SSUI 独立导入")
    h2("7.1 流程")
    ol("左侧点击“修复后SSUI（课题三）”，选择场地和评价轨道（生产利用 / 生态利用）。",
       "点击“下载模板”。模板已预填场地编号和 25 项指标的编码、名称与权重。",
       "按 7.2 填写后点击“上传已填写的模板”。此步骤只做校验预览，不写入业务数据。",
       "检查预览：错误逐条列出“工作表 / 行 / 列 / 问题”，有错误时不能确认，修正后重新上传。",
       "校验通过后点击“确认入库”。系统在一个事务中写入指标记录、修复后污染物检测值和 SSUI 结果，任一步失败则全部回滚。",
       "在“已导入批次”中导出 SSUI 结果（结果、指标贡献、准则层、修复后污染物）。")
    shot("11_ssui_post_S3.png", "修复后 SSUI 导入（课题三）")
    shot("12_ssui_post_validation_error.png", "课题三导入校验：单位错误定位到工作表/行/列")
    h2("7.2 模板填写（SSUI-POST-v1.1，得分录入模式）")
    tb(["工作表", "内容", "要求"], [
        ["批次信息", "场地编号、评价轨道、评价年份、修复后年数 t、管理强度或 M、数据来源", f"M 须在方法区间内：生产 {W['M_range']['production'][0]}–{W['M_range']['production'][1]}，生态 {W['M_range']['ecology'][0]}–{W['M_range']['ecology'][1]}；数据来源须如实选择"],
        ["指标得分", "D1–D25：原始值（可选）、单位（可选）、得分 s{_i}（必填）", "s{_i} 取值 0–1，由课题组按分级标准赋分。方法文件未给出原始值到得分的换算规则，因此本版是“得分录入模式”，不是原始数据计算流程"],
        ["修复后污染物检测", "点位编号、pH、污染物、浓度、单位", "单位必须为 mg/kg；用于法规安全门禁，缺测项目不视为达标"]])
    h2("7.3 计算方法")
    p("SSUI = f(t) × Σ{_j}(v{_j} × S{_j}) × M，其中 S{_j} = Σ{_i} w{_ij} × s{_i}，f(t) = 1 + 0.03t。权重 v{_j}、w{_ij} 分轨道取自方法 PPT（生产第 14 页，生态第 13 页）。")
    tb(["SSUI", "等级"], [["0.8 – 1.0", "高度可持续"], ["0.6 – 0.8", "中度可持续"], ["0.4 – 0.6", "低度可持续"], ["< 0.4", "不可持续"]])
    note("由于 M ≥ 1.05、f(t) ≥ 1，SSUI 可能超过 1.0。系统不截断，显示原值并标记“超出 0–1 区间，待课题组确认”。方法文件中 C4 组内权重之和（生态 1.214，生产 1.047）不等于 1，系统按原值使用并提示。")
    p("“SSUI参考评价（修复前）”页面仍保留，用于基于修复前检测数据的参考评价；正式 SSUI 以课题三页面为准。")
    shot("19_ssui_reference.png", "SSUI 参考评价（修复前数据，非课题三结论）")

    h1("第八章 修复后利用方向结论（生产 / 生态）")
    h2("8.1 判定规则")
    ol("先过法规安全门禁：生产轨道按 GB 15618-2018（农用地筛选值 / 管制值，按 pH 和水田 / 其他分档），生态轨道按 GB 36600-2018 表 1 的 45 项基本项目（未指定时按第一类用地，标准 5.3.1）。",
       "门禁结果分四种：通过 / 条件通过（超筛选值但不超管制值）/ 未通过（超管制值）/ 证据不足。门禁不能被任何评分抵消。",
       "门禁通过（或生产轨道条件通过）后，再看功能评分：修复后用课题三 SSUI（暂定 ≥ 0.6 为支持），修复前用课题二重构可行性。",
       "必测项目缺测、pH 或农用地类型未知导致无法判定时，一律为“证据不足”，并列出需补充的证据。")
    tb(["结论", "含义", "演示场地"], [
        ["生产与生态均支持", "两轨都支持；两轨权重体系不同，分数差只作参考，最终方向由管理目标确定", "SRS-A"],
        ["支持生产利用", "生产门禁通过或条件通过且功能评分支持；条件通过时附安全利用条件", "SRS-B"],
        ["支持生态利用", "生态门禁通过且功能评分支持", "SRS-C"],
        ["均不支持", "两轨都因门禁未通过或评分不支持而被否定", "SRS-D（砷重度超标）"],
        ["证据不足", "至少一轨无法判定，且没有任何一轨得到支持", "SRS-E（缺测镉、VOC）"]])
    for f, cap in (("13_decision_A_both.png", "结论：两轨均支持（SRS-A）"), ("14_decision_B_production.png", "结论：仅生产支持（SRS-B）"),
                   ("15_decision_C_ecology.png", "结论：仅生态支持（SRS-C）"), ("16_decision_D_neither.png", "结论：重度超标两轨均不支持（SRS-D）"),
                   ("17_decision_E_insufficient.png", "结论：缺测关键项目，证据不足（SRS-E）")):
        shot(f, cap)
    h2("8.2 阈值来源")
    p("GB 36600-2018 表1（45 项）与表2（40 项）、GB 15618-2018 表1–表3 均由生态环境部官网发布的标准 PDF 逐行转录，并与统一障碍因子知识库 V1.0 独立比对。12 项挥发性有机物（氯甲烷、1,1-二氯乙烷等）已全部核实并参与门禁。")
    note("标准中未列出的物质（如荧蒽、芘、蒽、菲、六六六总量）在生态门禁中显示“无 GB 36600 阈值”，只列浓度、不判定达标或超标；需按 HJ 25.3 风险评估推导筛选值。")

    h1("第九章 方案推荐、报告与文件")
    ul("方案推荐：基于 KOS 关键障碍因子匹配技术库，给出排序、匹配度、成本周期和禁用条件。",
       "报告：在场地追溯详情或各分析页生成 PDF、DOCX 或 HTML 报告。三种格式与“评价快照 Excel”来自同一份评价快照（编号印在页眉），首页摘要与正文数字一致；报告记录保存该快照，之后导入的新数据不会改变已生成报告的依据。",
       "报告内容：场地信息；按阶段与批次分列的数据来源（修复后两条轨道重复导入的同一批样品按样品编号去重）；分阶段覆盖率与检测摘要；按阶段的法规门禁与超标统计；课题一正式/探索性结果；课题二重构可行性；课题三修复后 SSUI（修复前旧口径评价只作参考）；利用方向结论；推荐方案；五阶段业务记录与软件里程碑；版本与快照编号。",
       "PDF 由程序直接排版，内嵌中文字体（Windows 上使用微软雅黑/黑体），包含表格、图件、页眉页脚与页码；页脚显示所用字体。",
       f"使用模拟数据的场地，报告封面显示红色“【{LABEL}，不得用于正式报告】”横幅。",
       "文件管理：查看、下载各阶段上传的附件与生成的报告。")
    shot("22_recommend.png", "修复方案推荐")
    shot("23_files.png", "文件管理")

    h1("第十章 备份与恢复")
    ol("系统管理 → 备份恢复 → “立即备份”：生成加密备份文件（%APPDATA%\\SRS\\backups）。系统每天 02:00 自动备份。",
       "恢复：选择备份 → 二次确认。恢复前，系统会自动保存当前数据库快照（文件名含 pre_restore）。",
       "恢复完成后重新登录，核对场地数量、课题二/三批次和利用结论。")
    shot("24_system.png", "系统管理")

    h1("第十一章 模拟数据与演示")
    ul(f"演示数据包 demo/mc_v12 由固定随机种子（20261009）生成 5 个合成场地（SRS-A…E，分别对应五类结论）和 8 个边界/错误夹具；所有文件、场地名和结果均带“{LABEL}”标签。",
       "metadata.json 记录生成器版本、种子、分布、相关结构、约束、阶段假设、单位和文件 SHA-256；expected.json 为独立实现（不调用系统评价代码）的期望门禁、SSUI 与结论。",
       "导入顺序：① 修复前检测数据（场地管理 → 数据导入）→ ② 课题二指标 → ③ 课题三生产、生态 → ④ 利用结论 → ⑤ 报告与追溯。",
       "演示请使用独立的演示数据库或演示安装；正式首启数据库为空，演示数据只有在用户显式导入后才会出现，可随时删除。",
       "模拟数据结果只说明软件流程，不代表任何真实场地，不得用于正式报告或模型训练。")

    h1("第十二章 常见问题与故障排除")
    tb(["问题", "原因与处理"], [
        ["结论显示“证据不足”", "查看“需补充的证据”：通常是缺测必测项目（如 GB 36600 VOC）、缺 pH 或农用地类型、功能评分未计算"],
        ["课题二显示“证据不足/无法评价”", "某个准则（如光温生产潜力、地下水埋深）没有可赋分的数据；按“未赋分指标及原因”补充"],
        ["课题二提示“无法识别的类别”", "按第 6.3 节取值填写；中英文均可，但须与表2.22 分级一致"],
        ["课题三预览报错", "按“工作表/行/列”逐条修正；常见原因：得分超出 0–1、M 超出区间、单位不是 mg/kg、场地编号不一致"],
        ["提示“相同内容已在批次 #n 确认导入”", "相同内容不重复入库；如需更正，修改内容后重新上传"],
        ["SSUI 大于 1", "方法公式中 M ≥ 1.05 所致，按原值显示并标注待确认，不是错误"],
        ["文件管理页提示 403（v1.1 旧版）", "v1.1 未登记“文档查看”权限；升级到 v" + VERSION + " 后首启自动补齐"],
        ["启动后浏览器未打开或端口被占用", "手动访问 http://127.0.0.1:8000；若端口被占用，关闭占用程序或已在运行的 SRS 实例"],
        ["地图无底图", "离线时只显示点位；在线底图需联网"],
        ["监管账户无法导入", "监管角色只读，按设计不能导入数据或运行判定"]])

    h1("附录 A 课题三指标与权重（方法 PPT 第 13/14 页）")
    tb(["编码", "指标", "准则层", "生产权重", "生态权重"],
       [[i["code"], i["name"], i["criterion"], f"{i['w_production']:.4f}", f"{i['w_ecology']:.4f}"] for i in W["indicators"]])
    p(f"准则层权重 v{{_j}}：生产 {W['criterion_weights']['production']}；生态 {W['criterion_weights']['ecology']}。编号以第 13/14 页权重表为准，第 6 页层次图有 10 处编号不一致，已列入待确认。")
    h1("附录 B 课题二权重（表2.18 / 表2.19 / 表2.21）")
    tb(["指标（表2.18 生产）", "权重"], [[M.FEATURES[f]["cn"], f"{w:.4f}"] for f, w in M.T218.items()])
    tb(["准则（表2.19 生产，缺失数据）", "权重"], [[M.FEATURES.get(k, {}).get("cn", k), f"{w:.4f}"] for k, w in M.T219.items()])
    tb(["准则（表2.21 生态，缺失数据）", "权重"], [[{"carbon_factor_grass": "C库变化因子（草地）"}.get(k, M.FEATURES.get(k, {}).get("cn", k)), f"{w:.4f}"] for k, w in M.T221.items()])
    h1("附录 C 已知限制与待确认事项")
    ul("课题三尚无真实修复后数据，目前只用模拟数据演示；真实修复后验证待数据提供。",
       "SSUI 为得分录入模式：D1–D25 原始值到得分的分级规则未提供。",
       "方法笔误与未定义事项 M-01…M-10（C 库因子④档 690→69、生态有效土层④档 00→90、表2.18 未给有机碳/剖面构型权重、区间端点、旱地/水田未注明、六价铬与总铬等）按冻结基线处理，待陈亮、宋伟杰老师确认。",
       "子课题测试表（个旧）来源未核实：BHC/DDT/BaP 与全氮大量取值与权重计算表相同，结果只作软件演示。",
       "Windows 验收在 GitHub Actions 虚拟机的管理员账户上执行；标准（非管理员）账户测试为独立作业（以计划任务身份运行），结果见发布说明，不等同于甲方 Windows 10/11 实机测试。",
       "课题一探索性提示使用的文献参考值（阳离子交换量 10 cmol(+)/kg、全氮 1.0 g/kg、有机质 6 g/kg 等）未经课题组批准为正式限值，只用于复核提示。",
       "经济输入文件（演示包 05_*.json）不参与课题三 SSUI 计算；经济原值到 D18–D25 得分的计算未实现。",
       "课题二演示场景均为“可行”，不可行分支尚未用演示数据覆盖；方法事项 Q01–Q18 见决策登记。")
    return C


def _runs(par, text):
    import re
    for i, part in enumerate(re.split(r"\{_([a-z]+)\}", text)):
        if part:
            r = par.add_run(part)
            if i % 2 == 1:
                r.font.subscript = True
    return par


def _plain(text):
    import re
    return re.sub(r"\{_([a-z]+)\}", r"\1", text)


def build_docx(C, shots, out_path):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
    doc = Document()
    sec = doc.sections[0]; sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    for m in ("left_margin", "right_margin"):
        setattr(sec, m, Cm(2.2))
    st = doc.styles["Normal"]; st.font.name = "Times New Roman"; st.font.size = Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    for lvl, size in (("Heading 1", 16), ("Heading 2", 13)):
        s = doc.styles[lvl]; s.font.size = Pt(size); s.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        s.font.name = "Times New Roman"; s.element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")
    for _ in range(6):
        doc.add_paragraph()
    for t, sz in ((TITLE, 22), (SUB, 18)):
        pp = doc.add_paragraph(); pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = pp.add_run(t); r.bold = True; r.font.size = Pt(sz)
    for t in ("委托单位：生态环境部土壤与农业农村生态环境监管技术中心", "研制单位：浙江大学环境与资源学院",
              f"版本：v{VERSION}　　日期：{date.today():%Y年%m月}"):
        pp = doc.add_paragraph(); pp.alignment = WD_ALIGN_PARAGRAPH.CENTER; pp.add_run(t).font.size = Pt(12)
    doc.add_page_break()
    missing = []
    for kind, x in C:
        if kind == "h1":
            doc.add_heading(x, level=1)
        elif kind == "h2":
            doc.add_heading(x, level=2)
        elif kind == "p":
            _runs(doc.add_paragraph(), x)
        elif kind in ("ul", "ol"):
            for it in x:
                _runs(doc.add_paragraph(style="List Bullet" if kind == "ul" else "List Number"), it)
        elif kind == "note":
            pp = doc.add_paragraph(); r = pp.add_run("说明：" + _plain(x)); r.font.color.rgb = RGBColor(0x8A, 0x4B, 0x00)
        elif kind == "table":
            hdr, rows = x
            t = doc.add_table(rows=1, cols=len(hdr)); t.style = "Table Grid"
            for i, hh in enumerate(hdr):
                t.rows[0].cells[i].text = hh
                for r in t.rows[0].cells[i].paragraphs[0].runs:
                    r.bold = True
            for row in rows:
                cells = t.add_row().cells
                for i, v in enumerate(row):
                    cells[i].text = _plain(str(v))
            doc.add_paragraph()
        elif kind == "shot":
            f, cap = x
            path = os.path.join(shots, f) if shots else None
            if path and os.path.isfile(path):
                from PIL import Image as PI
                w0, h0 = PI.open(path).size
                if 16.5 * h0 / w0 > 20:
                    doc.add_picture(path, height=Cm(20))
                else:
                    doc.add_picture(path, width=Cm(16.5))
                doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            else:
                missing.append(f)
                pp = doc.add_paragraph(); pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                r = pp.add_run(f"【截图位：{f} —— 待从 v{VERSION} 实机采集，不使用旧版截图】"); r.bold = True
                r.font.color.rgb = RGBColor(0xB9, 0x1C, 0x1C)
            cp = doc.add_paragraph(f"图：{cap}"); cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.save(out_path)
    return missing


def _sub_html(t):
    import re
    return re.sub(r"\{_([a-z]+)\}", r'<font size="7">\1</font>', H.escape(t))  # CJK 字体下 <sub> 不显示


def build_pdf(C, shots, out_path):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,
                                    SimpleDocTemplate, Spacer, Table, TableStyle)
    pdfmetrics.registerFont(TTFont("Deng", os.path.join(FONT_DIR, "Deng.ttf")))
    pdfmetrics.registerFont(TTFont("DengB", os.path.join(FONT_DIR, "Dengb.ttf")))
    pdfmetrics.registerFont(TTFont("SimHei", os.path.join(FONT_DIR, "SimHei.ttf")))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("Deng", normal="Deng", bold="DengB", italic="Deng", boldItalic="DengB")
    base = dict(fontName="Deng", fontSize=10.5, leading=16, wordWrap="CJK")
    sty = {"p": ParagraphStyle("p", **base, spaceAfter=4),
           "h1": ParagraphStyle("h1", keepWithNext=1, fontName="SimHei", fontSize=16, leading=22, textColor=colors.HexColor("#1F3A5F"),
                                spaceBefore=10, spaceAfter=8, wordWrap="CJK"),
           "h2": ParagraphStyle("h2", keepWithNext=1, fontName="SimHei", fontSize=12.5, leading=18, textColor=colors.HexColor("#1F3A5F"),
                                spaceBefore=8, spaceAfter=4, wordWrap="CJK"),
           "cell": ParagraphStyle("cell", fontName="Deng", fontSize=9, leading=12.5, wordWrap="CJK"),
           "th": ParagraphStyle("th", fontName="DengB", fontSize=9, leading=12.5, wordWrap="CJK"),
           "note": ParagraphStyle("note", **{**base, "fontSize": 10}, textColor=colors.HexColor("#8A4B00"),
                                  backColor=colors.HexColor("#FFF7E6"), borderPadding=5, spaceBefore=4, spaceAfter=8),
           "ph": ParagraphStyle("ph", **base, alignment=TA_CENTER, textColor=colors.HexColor("#B91C1C"),
                                borderColor=colors.HexColor("#B91C1C"), borderWidth=1, borderPadding=10, spaceBefore=18, spaceAfter=16),
           "cap": ParagraphStyle("cap", fontName="Deng", fontSize=9, leading=12, alignment=TA_CENTER,
                                 textColor=colors.HexColor("#555555"), spaceAfter=8),
           "cv1": ParagraphStyle("cv1", fontName="SimHei", fontSize=22, leading=32, alignment=TA_CENTER, wordWrap="CJK"),
           "cv2": ParagraphStyle("cv2", fontName="SimHei", fontSize=17, leading=26, alignment=TA_CENTER),
           "cv3": ParagraphStyle("cv3", fontName="Deng", fontSize=12, leading=20, alignment=TA_CENTER)}
    width = A4[0] - 4 * cm
    story = [Spacer(1, 6 * cm), Paragraph(H.escape(TITLE), sty["cv1"]), Spacer(1, 0.4 * cm),
             Paragraph(H.escape(SUB), sty["cv2"]), Spacer(1, 3 * cm)]
    for t in ("委托单位：生态环境部土壤与农业农村生态环境监管技术中心", "研制单位：浙江大学环境与资源学院",
              f"版本：v{VERSION}　　日期：{date.today():%Y年%m月}"):
        story.append(Paragraph(t, sty["cv3"]))
    story.append(PageBreak())
    for kind, x in C:
        if kind in ("h1", "h2"):
            story.append(Paragraph(_sub_html(x), sty[kind]))
        elif kind == "p":
            story.append(Paragraph(_sub_html(x), sty["p"]))
        elif kind == "note":
            story.append(Paragraph("说明：" + _sub_html(x), sty["note"]))
        elif kind in ("ul", "ol"):
            items = [ListItem(Paragraph(_sub_html(i), sty["p"]), leftIndent=14) for i in x]
            story.append(ListFlowable(items, bulletType="bullet" if kind == "ul" else "1", start=None if kind == "ul" else 1,
                                      bulletFontName="Deng", bulletFontSize=9, leftIndent=14))
        elif kind == "table":
            hdr, rows = x
            n = len(hdr)
            lens = [max([len(str(hdr[i]))] + [len(str(r[i])) for r in rows]) for i in range(n)]
            tot = sum(min(l, 40) + 4 for l in lens)
            cw = [width * (min(l, 40) + 4) / tot for l in lens]
            data = [[Paragraph(_sub_html(h), sty["th"]) for h in hdr]] + \
                   [[Paragraph(_sub_html(str(v)), sty["cell"]) for v in r] for r in rows]
            t = Table(data, colWidths=cw, repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                                   ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF5")),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            story += [t, Spacer(1, 8)]
        elif kind == "shot":
            f, cap = x
            path = os.path.join(shots, f) if shots else None
            if path and os.path.isfile(path):
                from PIL import Image as PI
                w0, h0 = PI.open(path).size
                w1 = width; h1 = w1 * h0 / w0
                if h1 > 18 * cm:
                    h1 = 18 * cm; w1 = h1 * w0 / h0
                block = [Image(path, width=w1, height=h1)]
            else:
                block = [Paragraph(f"【截图位：{H.escape(f)} —— 待从 v{VERSION} 实机采集，不使用旧版截图】", sty["ph"])]
            story.append(KeepTogether(block + [Paragraph("图：" + H.escape(cap), sty["cap"])]))

    def footer(canvas, doc):
        canvas.saveState(); canvas.setFont("Deng", 8); canvas.setFillColor(colors.HexColor("#777777"))
        canvas.drawCentredString(A4[0] / 2, 1.0 * cm, f"SRS 用户操作手册 v{VERSION} · 第 {doc.page} 页")
        canvas.restoreState()
    doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm,
                            bottomMargin=2 * cm, title=f"{TITLE} {SUB}", author="浙江大学环境与资源学院")
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=footer)
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    C = content()
    base = os.path.join(a.out, f"SRS_用户操作手册_v{VERSION}")
    miss = build_docx(C, a.shots, base + ".docx")
    ok = build_pdf(C, a.shots, base + ".pdf")
    print(json.dumps({"docx": base + ".docx", "pdf": base + ".pdf", "pdf_ok": ok, "missing_screenshots": miss},
                     ensure_ascii=False, indent=1))
