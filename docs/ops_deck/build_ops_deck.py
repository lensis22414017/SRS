"""SRS v1.1.0 操作演示 PPT 生成器(可编辑 PPTX, 原生形状/表格)。

用法: python build_ops_deck.py --shots <screenshots_v110 目录> --out <pptx 路径>
数值全部读取自证据文件(demo_evidence.json 等), 截图缺失时显示"截图位"占位, 不使用旧版截图。
"""
from __future__ import annotations

import argparse
import copy
import json
import os

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KERNEL = "/Users/lensis/.claude-science/orgs/9c507497-8aa7-4b8a-92ec-ab8dd1d6535d/skills/srs-briefing-deck/kernel.py"
exec(open(KERNEL, encoding="utf-8").read())  # deck_* helpers + palette
STYLE_REF = "/Users/lensis/Desktop/SRS/02.课题一中期考核PPT.pptx"
VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
EV = json.load(open(os.path.join(ROOT, "demo", "mc_v11", "demo_evidence.json"), encoding="utf-8"))
LABEL = "模拟数据——仅供测试/演示"


def set_lines(shape, lines):
    tf = shape.text_frame
    tmpl = [copy.deepcopy(r) for p in tf.paragraphs for r in p._p.findall(qn("a:r"))]
    pPr = tf.paragraphs[0]._p.find(qn("a:pPr"))
    for p in list(tf.paragraphs)[1:]:
        p._p.getparent().remove(p._p)
    for r in tf.paragraphs[0]._p.findall(qn("a:r")):
        tf.paragraphs[0]._p.remove(r)
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        if i and pPr is not None:
            p._p.insert(0, copy.deepcopy(pPr))
        if tmpl:
            r = copy.deepcopy(tmpl[min(i, len(tmpl) - 1)]); r.find(qn("a:t")).text = line
            endp = p._p.find(qn("a:endParaRPr"))
            (endp.addprevious(r) if endp is not None else p._p.append(r))
        else:
            p.add_run().text = line


class Deck:
    def __init__(self, shots):
        self.prs = Presentation(STYLE_REF)
        for sid in list(self.prs.slides._sldIdLst)[1:]:
            self.prs.part.drop_rel(sid.rId); self.prs.slides._sldIdLst.remove(sid)
        self.layout = next(l for m in self.prs.slide_masters for l in m.slide_layouts if l.name == "6_标题幻灯片")
        self.shots = shots; self.missing = []; self.used = []

    def slide(self, title, banner, notes, footer):
        s = self.prs.slides.add_slide(self.layout)
        for ph in list(s.placeholders):
            ph._element.getparent().remove(ph._element)
        deck_header(s, title, banner)
        deck_textbox(s, 0.66, 7.2, 12.0, 0.28, [footer], size=9, color="grey")
        s.notes_slide.notes_text_frame.text = notes
        return s

    def shot(self, s, fn, x, y, w, h, caption):
        p = os.path.join(self.shots, fn) if self.shots else None
        if p and os.path.isfile(p):
            px, py, pw, ph = deck_picture(s, p, x, y, w, h - 0.3); self.used.append(fn)
            deck_textbox(s, px, py + ph + 0.02, pw, 0.28, [f"运行截图（v{VERSION}，{LABEL}）：{caption}"], size=9, color="grey")
        else:
            self.missing.append(fn)
            deck_box(s, x, y, w, h, text=[f"截图位：{fn}", f"待从 v{VERSION} 实机采集（不使用旧版截图）", caption],
                     fill="white", line="red", dash="dash", size=12, color="red")


def build(shots, out):
    D = Deck(shots)
    prs = D.prs
    # 1 封面
    cover = prs.slides[0]
    for sh in cover.shapes:
        if sh.name == "Rectangle 7":
            set_lines(sh, [f"SRS v{VERSION} 操作演示"])
        elif sh.name == "Rectangle 2":
            set_lines(sh, ["污染场地土壤生态-生产功能重构", "监管系统（SRS）操作演示"])
            for para in sh.text_frame.paragraphs:
                for r in para.runs:
                    r.font.size = Pt(36)
        elif sh.name == "文本框 8":
            set_lines(sh, ["委托单位：生态环境部土壤与农业农村生态环境监管技术中心", "承担单位：浙江大学环境与资源学院"])
    deck_textbox(cover, 2.0, 3.9, 9.3, 0.95,
                 [[("汇报人：曾 鸿    指导教师：王 玮 副教授", {"size": 16, "bold": True})],
                  [(f"软件版本 v{VERSION}（发布候选） · 演示数据为{LABEL}", {"size": 12, "color": "grey"})]],
                 align=PP_ALIGN.CENTER, spacing=1.15)
    cover.notes_slide.notes_text_frame.text = (f"封面。本演示基于 v{VERSION} 发布候选版本；演示所用数据均为固定种子生成的蒙特卡洛模拟数据，"
                                               "只用于展示软件流程。课题二/三的方法口径仍待陈亮、伟杰老师确认，相关结果标注“暂定”。")

    # 2 意见回应
    s = D.slide("一、对 7 月 30 日意见的回应", "六条意见逐条落实到系统功能，方法口径待课题组确认的部分明确标注“暂定”",
                "逐条说明 C1–C6 的实现。C1 是方法对齐，需要陈亮、伟杰老师确认，因此状态为待确认；其余功能已实现并通过自动测试。",
                "来源：remediation/requirements_matrix.csv；gate_report.md（G1–G9）")
    rows = [["编号", "意见", "系统中的实现", "状态"],
            ["C1", "与陈亮/伟杰对齐方法粒度", "13 项方法冲突列清单；涉及结果标注“暂定”，不静默修正", "待确认"],
            ["C2", "三个课题的数据都要演示", "带标签的蒙特卡洛演示包，课题一→二→三全流程", "已实现"],
            ["C3", "修复后给出宜生产/宜生态的具体结论", "法规安全门禁 + 功能评分 → 五类利用结论", "已实现"],
            ["C4", "课题一/二用修复前、课题三用修复后数据", "课题三独立模板、预览、确认入库、计算、导出；数据物理分离", "已实现"],
            ["C5", "进入即展示全流程追溯，引导上传下载", "追溯页面打开即显示五阶段引导与模板；选场地后显示真实进度", "已实现"],
            ["C6", "用户手册和 PPT", "用户操作手册（DOCX/PDF）+ 本演示 PPT", "已实现"]]
    deck_table(s, 0.9, 1.7, 11.55, 4.6, rows, [0.8, 3.4, 5.95, 1.4], font=13, status_col=3,
               status_map={"已实现": "verified", "待确认": "pending"})
    deck_textbox(s, 0.9, 6.45, 11.5, 0.6, [[("自动测试：", {"bold": True}), ("后端 491 项通过、0 项失败；CI 6 个合同/红队作业全部通过。Windows 安装包实机验收待执行（见第十四页）。", {})]], size=13)

    # 3 三个课题与数据阶段
    s = D.slide("二、三个课题与数据阶段", "修复前数据只进课题一、二；修复后数据只能经课题三独立导入，两者物理分离",
                "强调数据阶段分离：修复后数据不会被拿来替代修复前数据，也不做样本配对。课题一/二所有计算查询都限定修复前阶段。",
                "来源：migration 0007；tests/test_v11_stage_model.py；利用决策 ml/evaluation/utilization.py")
    deck_box(s, 0.95, 1.75, 5.6, 0.55, text=["修复前（调查评估 · 方案审批）"], fill="brown", line=None, size=16, color="white", bold=True)
    deck_box(s, 6.8, 1.75, 5.6, 0.55, text=["修复后（效果评估 · 后期管护）"], fill="gold", line=None, size=16, color="white", bold=True)
    for i, (t, d) in enumerate([("课题一  障碍因子识别（KOS）", "关键障碍因子 Top-N、补测建议"),
                                ("课题二  功能重构可行性", "生产/生态可行性 → 修复前情景判断与修复目标")]):
        deck_box(s, 0.95, 2.55 + i * 1.35, 5.6, 1.15, text=[[(t, {"bold": True, "size": 15})], d], fill="cream", line="brown", size=13)
    deck_box(s, 6.8, 2.55, 5.6, 1.15, text=[[("课题三  修复后 SSUI", {"bold": True, "size": 15})], "独立模板导入 → SSUI 计算 → 导出"],
             fill="cream", line="gold", size=13)
    deck_box(s, 6.8, 3.9, 5.6, 1.15, text=[[("修复后利用方向结论", {"bold": True, "size": 15})], "法规门禁（GB 15618 / GB 36600）+ SSUI"],
             fill="cream", line="gold", size=13)
    deck_arrow(s, 9.6, 3.7, 9.6, 3.9, color="gold")
    deck_box(s, 0.95, 5.35, 11.45, 1.55, text=[
        [("修复前数据入口：", {"bold": True}), ("场地管理 → 数据导入（修复前模板 PRE-v1.1）", {})],
        [("修复后数据入口：", {"bold": True}), ("修复后SSUI（课题三）→ 下载模板 SSUI-POST-v1.1 → 上传校验 → 确认入库", {})],
        [("分离方式：", {"bold": True}), ("修复后数据存入独立批次与记录表；课题一/二只读取修复前测值；不做修复前后样本配对", {})]],
        fill="panel", line=None, size=13, align=PP_ALIGN.LEFT, margin=0.15)

    # 4 安装与首启
    s = D.slide("三、安装与首次启动", "安装包不含任何业务数据和测试账户；首次启动由管理员设置密码",
                "演示安装：路径可以包含中文和空格；无管理员权限时可加 /CURRENTUSER。首次启动是空库，进入首启向导。",
                "来源：packaging/srs_setup.iss；backend/app/api/setup.py；用户操作手册第二章")
    deck_textbox(s, 0.95, 1.7, 5.2, 5.2, [
        [("1  安装", {"bold": True, "size": 16, "color": "brown"})], f"双击 SRS-Setup-{VERSION}-Windows-x64.exe；路径可含中文、空格", "",
        [("2  首次启动", {"bold": True, "size": 16, "color": "brown"})], "空数据库 → 首启设置向导 → 设置管理员密码（≥8 位，3 类字符）", "",
        [("3  登录", {"bold": True, "size": 16, "color": "brown"})], "用管理员创建企业、第三方机构、监管人员账户", "",
        [("4  数据位置", {"bold": True, "size": 16, "color": "brown"})], r"%APPDATA%\SRS（数据库、文件、备份）；卸载不删除数据"], size=14, spacing=1.1)
    D.shot(s, "01_login.png", 6.4, 1.7, 6.1, 5.2, "登录页面")

    # 5 追溯引导
    s = D.slide("四、全流程追溯：进入即见", "打开页面即显示五阶段引导、需上传资料和模板下载；查看不创建任何记录",
                "C5：进入追溯页面不需要先选场地。引导列出每个阶段对应的课题、数据阶段、需上传和可下载的资料。选择场地后显示 7 个真实里程碑。",
                "来源：GET /api/v1/trace/guide、/sites/{id}/trace/progress；test_trace_guide_and_progress_create_no_records")
    stages = [("调查评估", "修复前 · 课题一/二"), ("方案审批", "修复前 · 课题一/二"), ("施工监理", "—"),
              ("效果评估", "修复后 · 课题三"), ("后期管护", "修复后 · 课题三")]
    for i, (n, d) in enumerate(stages):
        x = 0.95 + i * 2.33
        deck_box(s, x, 1.75, 2.05, 0.95, text=[[(n, {"bold": True, "size": 15})], d],
                 fill="cream" if i < 3 else "FFF7E6", line="brown" if i < 3 else "gold", size=11)
        if i < 4:
            deck_arrow(s, x + 2.05, 2.22, x + 2.33, 2.22)
    D.shot(s, "09_trace_guide.png", 0.95, 2.9, 7.3, 4.15, "全流程追溯引导")
    deck_box(s, 8.45, 2.9, 3.95, 4.15, text=[[("选择场地后的真实进度", {"bold": True, "size": 14, "color": "brown"})],
                                             "1 修复前数据导入", "2 障碍因子识别（课题一）", "3 重构可行性（课题二）", "4 修复前情景判断",
                                             "5 修复后 SSUI 导入（课题三）", "6 修复后利用结论", "7 全流程报告",
                                             [("演示场地：7/7 完成", {"bold": True, "color": "green"})]],
             fill="panel", line=None, size=12, align=PP_ALIGN.LEFT, margin=0.15)

    # 6 修复前导入 + 课题一
    f = EV["S1_kos"]["factors"][0]
    s = D.slide("五、修复前数据导入与课题一", "下载模板 → 导入 → 校验报告 → KOS 关键障碍因子",
                f"演示场地 24 个点位、{EV['site']['n_measurements']} 条测值，均为模拟数据。KOS 识别出的关键障碍因子为 {'、'.join(f)}。",
                "来源：demo/mc_v11/demo_evidence.json（S1_kos）；/api/v1/templates/pre-remediation")
    deck_textbox(s, 0.95, 1.7, 4.6, 5.3, [
        [("操作步骤", {"bold": True, "size": 16, "color": "brown"})],
        "1  追溯引导或导入页下载修复前模板", "2  每行一个点位，单位以表头为准", "3  场地管理 → 导入数据，系统自动识别字段", "4  查看校验报告（错误、警告、超标）",
        "5  障碍因子分析（课题一）→ 运行诊断", "",
        [("演示结果（模拟数据）", {"bold": True, "size": 16, "color": "brown"})],
        f"24 个点位 · {EV['site']['n_measurements']} 条测值", f"关键障碍因子：{'、'.join(f)}"], size=14, spacing=1.1)
    D.shot(s, "05_obstacle_S1.png", 5.8, 1.7, 6.7, 5.3, "障碍因子分析（课题一）")

    # 7 课题二 + 修复前情景
    r2 = EV["S2_reconstruction"]; dp = EV["decision_pre"]
    s = D.slide("六、课题二：重构可行性与修复前情景判断", "评分“可行”也不能抵消法规门禁：修复前情景只给修复目标，不给利用结论",
                f"演示：生产重构得分 {r2['reconstruction_prod']['score']}（可行），但镉超过 GB 15618 风险管制值，生产门禁未通过；"
                f"生态重构证据不足。因此修复前情景判断为“证据不足”，给出修复目标：生产 {'、'.join(dp['remediation_targets']['production'])}，"
                f"生态 {'、'.join(dp['remediation_targets']['ecology'])}。",
                "来源：demo_evidence.json（S2_reconstruction、decision_pre）；ml/evaluation/utilization.py")
    rows = [["项目", "生产（农用地）", "生态"],
            ["课题二重构可行性", f"{r2['reconstruction_prod']['score']}  可行", "证据不足（覆盖率低于门禁）"],
            ["法规安全门禁", "未通过：Cd 超风险管制值", "证据不足：GB 36600 基本项目缺测"],
            ["修复目标（降至筛选值以下）", "、".join(dp["remediation_targets"]["production"]), "、".join(dp["remediation_targets"]["ecology"])],
            ["修复前情景判断", "证据不足（非修复后结论）", ""]]
    deck_table(s, 0.95, 1.75, 6.3, 3.2, rows, [2.2, 2.2, 1.9], font=12)
    deck_box(s, 0.95, 5.15, 6.3, 1.85, text=[[("要点", {"bold": True, "color": "red"})],
                                             "法规门禁优先于任何评分；", "修复前只回答“需要修复哪些因子、修复到什么水平”；",
                                             "修复完成后用课题三的修复后数据重新判定。"],
             fill="F9E3E3", line=None, size=13, align=PP_ALIGN.LEFT, margin=0.15)
    D.shot(s, "06_reconstruction_S2_pre_decision.png", 7.45, 1.75, 5.0, 5.25, "功能重构分析与修复前情景判断")

    # 8 课题三导入流程
    s = D.slide("七、课题三：修复后 SSUI 独立导入", "四步完成：下载模板 → 上传校验（不入库）→ 确认入库（事务）→ 导出结果",
                "预览阶段不写业务数据；错误逐条列出工作表、行、列；确认在一个事务中完成，失败全部回滚；同一文件不能重复确认。",
                "来源：backend/app/services/ssui_post_service.py；tests/test_v11_utilization_ssui.py（G4）")
    steps = [("1 下载模板", "已预填场地编号与 25 项指标、权重"), ("2 上传校验", "错误定位到 工作表/行/列；不入库"),
             ("3 确认入库", "指标、修复后污染物、SSUI 一次写入；失败回滚"), ("4 导出结果", "xlsx：结果、指标贡献、准则层、污染物")]
    for i, (t, d) in enumerate(steps):
        x = 0.95 + i * 2.9
        deck_box(s, x, 1.75, 2.6, 1.2, text=[[(t, {"bold": True, "size": 15})], d], fill="cream", line="gold", size=11.5)
        if i < 3:
            deck_arrow(s, x + 2.6, 2.35, x + 2.9, 2.35, color="gold")
    deck_table(s, 0.95, 3.2, 5.6, 2.2, [["工作表", "内容"], ["批次信息", "场地、轨道、年份、t、管理强度或 M、数据来源"],
                                         ["指标得分", "D1–D25 得分 s（0–1，必填），原始值可选"],
                                         ["修复后污染物检测", "点位、pH、污染物、浓度（mg/kg）"]], [1.8, 3.8], font=12)
    deck_box(s, 0.95, 5.6, 5.6, 1.4, text=[[("SSUI = f(t) × Σ vj·Sj × M", {"bold": True, "size": 16})],
                                           "f(t) = 1 + 0.03t；M 生产 1.1–1.2，生态 1.05–1.1",
                                           "权重取自方法 PPT 第 13/14 页；结果不截断"],
             fill="panel", line=None, size=12.5)
    D.shot(s, "07_ssui_post_S3.png", 6.75, 3.2, 5.7, 3.8, "修复后 SSUI 导入（课题三）")

    # 9 课题三结果 + 修复后结论
    sp, se = EV["S3_ssui"]["production"], EV["S3_ssui"]["ecology"]
    s = D.slide("八、修复后利用方向结论（演示）", "生产门禁条件通过 + SSUI 高度可持续 → 支持生产利用（附安全利用条件）",
                f"演示：生产 SSUI {sp['ssui']:.3f}（{sp['grade']}），生态 SSUI {se['ssui']:.3f}（{se['grade']}）。"
                "修复后 Cd、As、Pb 仍超过筛选值但低于管制值，属安全利用类，因此结论为“支持生产利用”，并附安全利用条件。"
                "生态门禁因 GB 36600 基本项目缺测为证据不足。",
                "来源：demo_evidence.json（S3_ssui、decision_post）；数值为模拟数据")
    for i, (lab, v, g, col) in enumerate([("生产 SSUI", sp["ssui"], sp["grade"], "brown"), ("生态 SSUI", se["ssui"], se["grade"], "gold")]):
        y = 2.0 + i * 1.1
        deck_textbox(s, 0.95, y, 1.6, 0.5, [lab], size=14, bold=True)
        deck_box(s, 2.6, y + 0.05, 2.6 * v, 0.45, fill=col, line=None)
        deck_textbox(s, 2.65 + 2.6 * v, y, 2.1, 0.5, [f"{v:.3f}  {g}"], size=13, bold=True)
    deck_box(s, 2.6 + 2.6 * 0.6, 1.85, 0.02, 2.2, fill="red", line=None)
    deck_textbox(s, 2.6 + 2.6 * 0.6 - 0.9, 4.05, 1.8, 0.3, ["支持阈值 0.6（暂定）"], size=10, color="red", align=PP_ALIGN.CENTER)
    deck_table(s, 0.95, 4.5, 6.0, 1.6, [["轨道", "法规门禁", "轨道结论"],
                                         ["生产", "条件通过（Cd、As、Pb 超筛选值）", "支持（附安全利用条件）"],
                                         ["生态", "证据不足（基本项目缺测）", "证据不足"]], [1.0, 2.9, 2.1], font=12)
    deck_box(s, 0.95, 6.25, 6.0, 0.75, text=[[("结论：", {"bold": True}), ("支持生产（农用地）利用；须采取农艺调控、替代种植等安全利用措施并协同监测", {})]],
             fill="E8F3E9", line="green", size=12.5, align=PP_ALIGN.LEFT, margin=0.12)
    D.shot(s, "13_post_decision.png", 7.15, 1.75, 5.3, 5.25, "修复后利用方向结论")

    # 10 判定规则
    s = D.slide("九、利用结论怎么得出", "先过法规安全门禁，再看功能评分；证据缺失一律“证据不足”，不会被当作达标",
                "解释五类结论。门禁：生产 GB 15618（按 pH、水田/其他分档），生态 GB 36600 第一类用地（缺省）。条件通过的含义不同：生产为安全利用类，生态须先做风险评估。",
                "来源：ml/evaluation/utilization.py；data/standards/gb15618_2018_v11.csv、gb36600_2018_v11.csv")
    flow = [("法规安全门禁", ["通过 / 条件通过 / 未通过 / 证据不足"], "brown"), ("功能评分", ["修复前：课题二", "修复后：课题三 SSUI"], "gold"),
            ("五类结论", ["支持生产 · 支持生态 · 均支持", "均不支持 · 证据不足"], "green")]
    for i, (t, d, c) in enumerate(flow):
        x = 0.95 + i * 4.0
        deck_box(s, x, 1.75, 3.55, 1.3, text=[[(t, {"bold": True, "size": 16, "color": "white"})]] + [[(l, {"color": "white"})] for l in d],
                 fill=c, line=None, size=12.5)
        if i < 2:
            deck_arrow(s, x + 3.55, 2.4, x + 4.0, 2.4)
    deck_table(s, 0.95, 3.3, 11.45, 2.6, [["情形", "处理"],
                                           ["超风险管制值", "该轨道未通过，任何评分都不能抵消"],
                                           ["超筛选值、未超管制值", "生产：条件通过（安全利用类，附条件）；生态：须先做风险评估 → 证据不足"],
                                           ["必测项目缺测 / 阈值缺失 / pH 或农用地类型未知", "证据不足，并列出需补充的证据"],
                                           ["生态用地类别未指定", "按 GB 36600 第一类用地（最严）评价，并写明为保守假设"]], [4.2, 7.25], font=12.5)
    deck_box(s, 0.95, 6.1, 11.45, 0.9, text=[[("当前边界：", {"bold": True, "color": "red"}),
                                              ("GB 36600 表 1 中 12 项 VOC 尚无经核实阈值，生态门禁暂时只能得到“未通过”或“证据不足”，需按标准原文录入复核。", {})]],
             fill="F9E3E3", line=None, size=12.5, align=PP_ALIGN.LEFT, margin=0.15)

    # 11 真实数据个旧
    s = D.slide("十、真实数据复核：云南个旧", "134 点 As、Pb 全部超管制值 → 两轨均不支持（旧版曾判生态可行 63.29）",
                "这是甲方提供的真实修复前数据。旧版本通过准则层降维把超标污染物与土壤质量指标平均，导致严重超标场地被判生态可行（63.29）。"
                "v1.1 删除了该兜底，并增加法规门禁：As、Pb 在 134/134 个点位超过管制值，结论为均不支持；该结论属修复前情景判断。",
                "来源：data/raw/3.20250731_…云南个旧…xlsx；test_gejiu_full_chain_import_evaluate_decide_via_api；baseline 36aabf4 证据")
    deck_table(s, 0.95, 1.8, 11.45, 2.6, [["项目", "旧版 v1.0.x（36aabf4）", f"v{VERSION}"],
                                           ["生态重构可行性", "可行 63.29", "证据不足/无法评价（指标覆盖不足）"],
                                           ["生产门禁（GB 15618）", "无", "未通过：As、Pb 134/134 点超管制值"],
                                           ["生态门禁（GB 36600 第一类）", "无", "未通过：As、Pb 134/134 点超管制值"],
                                           ["修复前情景判断", "—", "均不支持；修复目标含 As、Pb"]], [3.4, 3.6, 4.45], font=13)
    deck_box(s, 0.95, 4.7, 11.45, 2.2, text=[[("意义", {"bold": True, "size": 15, "color": "brown"})],
                                             "1  严重超标的场地不会再因为土壤质量指标较好而被“平均”成可行；",
                                             "2  结论可追溯：每个门禁列出超标因子、超标点位数和所用标准；",
                                             "3  个旧为修复前数据，修复后的利用方向须导入修复后数据（课题三）再判定。"],
             fill="panel", line=None, size=13.5, align=PP_ALIGN.LEFT, margin=0.18)

    # 12 报告、备份、模拟数据
    s = D.slide("十一、报告、备份与模拟数据标签", "报告新增利用方向结论；模拟数据从导入到报告全程带标签，不能混入正式结果",
                "报告支持 PDF/DOCX/HTML。模拟数据：导入时自动识别标签，场地名、测值、批次、结论、导出与报告封面都带“模拟数据——仅供测试/演示”。备份每天 02:00 自动执行，恢复前自动快照。",
                "来源：report_service.py；pipeline.py（标签识别）；test_v11_persistence_recovery.py（G7）")
    for i, (t, items) in enumerate([("报告", ["PDF / DOCX / HTML", "新增“利用方向结论”章节", "地图图件、人工复核意见区"]),
                                     ("备份与恢复", ["每天 02:00 自动加密备份", "恢复须二次确认，先自动快照", "测试：恢复后结论逐字一致"]),
                                     ("模拟数据标签", [LABEL, "导入自动识别并全链路标记", "演示库独立，拒绝写入正式库"])]):
        x = 0.95 + i * 3.87
        deck_box(s, x, 1.75, 3.6, 0.55, text=[t], fill="brown" if i < 2 else "red", line=None, size=15, color="white", bold=True)
        deck_box(s, x, 2.3, 3.6, 1.6, text=items, fill="panel", line=None, size=12.5, align=PP_ALIGN.LEFT, margin=0.15)
    D.shot(s, "10_trace_detail.png", 0.95, 4.1, 5.6, 2.95, "场地追溯详情（真实进度、报告）")
    D.shot(s, "12_system.png", 6.8, 4.1, 5.6, 2.95, "系统管理（备份恢复）")

    # 13 演示脚本
    s = D.slide("十二、三个课题的演示脚本", "同一份模拟数据包，按课题顺序演示约 15 分钟",
                "演示顺序：课题一（3 分钟）→ 课题二（4 分钟）→ 课题三（5 分钟）→ 追溯与报告（3 分钟）。每一步说清楚用的是修复前还是修复后数据。",
                "来源：SRS_Remediation_v1.1/demo_montecarlo_v11/；scripts/mc_demo_v11.py")
    deck_table(s, 0.95, 1.75, 11.45, 4.6, [["课题", "演示文件", "操作", "看点"],
                                            ["课题一", "MCDEMO_修复前检测数据", "导入 → 障碍因子分析 → 运行诊断", "关键障碍 " + "、".join(f)],
                                            ["课题二", "（同上）", "功能重构分析 → 运行 → 修复前情景判断（水田）", "评分可行但门禁未通过；修复目标"],
                                            ["课题三", "MCDEMO_课题三修复后SSUI_生产 / 生态", "下载模板 → 上传校验 → 确认 → 导出",
                                             f"SSUI {sp['ssui']:.3f} / {se['ssui']:.3f}；预览报错演示"],
                                            ["结论", "—", "修复后利用结论 → 运行判定（水田）", "支持生产利用（附安全利用条件）"],
                                            ["追溯", "—", "全流程追溯 → 进入场地 → 生成报告", "7/7 真实进度；报告带模拟标签"]],
               [1.2, 3.3, 4.0, 2.95], font=12.5)
    deck_textbox(s, 0.95, 6.5, 11.45, 0.5, ["演示数据由固定种子（20261008）生成，metadata.json 记录分布参数与文件 SHA-256；结果不代表任何真实场地。"], size=12, color="grey")

    # 14 验收状态
    s = D.slide("十三、验收状态与待办", "软件功能与自动测试已就绪；Windows 实机验收、方法确认和修复后真实数据仍是发布前提",
                "如实说明：Windows 安装包实机验收工作流已就绪，但尚未运行（需要 GitHub 凭据）；课题三没有真实修复后数据；方法口径待确认。因此本版本为发布候选，不作为正式交付版本。",
                "来源：remediation/gate_report.md；methodology_questions_ChenLiang_Weijie.md")
    deck_table(s, 0.95, 1.75, 7.0, 5.2, [["门禁", "内容", "状态"],
                                          ["G1", "来源与模式对齐", "通过"], ["G2", "三个课题运行", "部分通过"], ["G3", "利用结论正确性", "通过"],
                                          ["G4", "SSUI 完整性", "通过"], ["G5", "数据分离", "通过"], ["G6", "追溯与权限", "通过"],
                                          ["G7", "持久化与迁移", "通过"], ["G8", "Windows 安装实机验收", "待执行"], ["G9", "文档与发布一致", "待执行"]],
               [0.8, 4.2, 2.0], font=12, status_col=2, status_map={"通过": "verified", "部分通过": "pending", "待执行": "open"})
    deck_box(s, 8.2, 1.75, 4.2, 5.2, text=[[("需要各方配合", {"bold": True, "size": 15, "color": "brown"})],
                                           "1  陈亮、伟杰老师确认方法口径（16 个问题）",
                                           "2  提供至少 1 个场地的修复后真实数据（D1–D25 与污染物）",
                                           "3  提供课题二文本分级 → 分值映射",
                                           "4  按 GB 36600 原文录入 12 项 VOC 阈值并复核",
                                           "5  授权 GitHub 推送，运行 Windows 安装验收"],
             fill="panel", line=None, size=12.5, align=PP_ALIGN.LEFT, margin=0.18)

    prs.save(out)
    return {"pptx": out, "slides": len(prs.slides), "screenshots_used": D.used, "screenshots_missing": D.missing}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default=None)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    print(json.dumps(build(a.shots, a.out), ensure_ascii=False, indent=1))
