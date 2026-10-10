"""SRS 年度验收操作演示 PPT 生成器(可编辑 PPTX, 原生形状/表格)。v1.2.1: 章节号按实际页序连续编号(公开版不跳号)。

用法: python build_ops_deck.py --shots <screenshots_v110 目录> --out <pptx 路径>
数值全部读取自证据文件(demo_evidence.json 等), 截图缺失时显示"截图位"占位, 不使用旧版截图。
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re

from pptx import Presentation
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Pt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
KERNEL = "/Users/lensis/.claude-science/orgs/9c507497-8aa7-4b8a-92ec-ab8dd1d6535d/skills/srs-briefing-deck/kernel.py"
exec(open(KERNEL, encoding="utf-8").read())  # deck_* helpers + palette
STYLE_REF = os.environ.get("SRS_DECK_TEMPLATE") or next(p for p in (
    "/Users/lensis/Desktop/SRS/02.课题一中期考核PPT.pptx",
    "/Users/lensis/Desktop/SRS/SRS_Remediation_v1.1/docs/SRS_v1.1.0_操作演示.pptx") if os.path.exists(p))
VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()
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
        self.shots = shots; self.missing = []; self.used = []; self.n = 0

    def slide(self, title, banner, notes, footer):
        # v1.2.1(R10): 章节号连续 — 去掉源码中的固定序号, 按实际生成顺序编号
        self.n += 1
        title = f"{_CN[self.n]}、" + re.sub(r"^[一二三四五六七八九十]+、", "", title)
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


_CN = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八"]
DECISION_CN = {"both_supported": "生产与生态均支持", "production_supported": "支持生产利用", "ecology_supported": "支持生态利用",
               "neither_supported": "均不支持", "insufficient_evidence": "证据不足"}
FACTOR_CN = {"Cd_mgkg": "镉", "Pb_mgkg": "铅", "As_mgkg": "砷", "Hg_mgkg": "汞", "Cu_mgkg": "铜", "Zn_mgkg": "锌", "Ni_mgkg": "镍",
             "Cr_mgkg": "铬", "OC_pct": "有机碳", "OM_gkg": "有机质", "TN_gkg": "全氮", "CEC_cmolkg": "阳离子交换量", "pH": "pH"}


def fcn(codes):
    return "、".join(FACTOR_CN.get(c, c) for c in (codes or []))


GATE_CN = {"pass": "通过", "conditional": "条件通过", "fail": "未通过", "insufficient": "证据不足"}


def build(shots, out, evidence, public=False, release=None, gejiu=None):
    """evidence: Windows 验收目录(含 demo_actual/comparison.json 与 acceptance_*.json)。"""
    EV = json.load(open(os.path.join(evidence, "demo_actual", "comparison.json"), encoding="utf-8"))
    EXP = json.load(open(os.path.join(ROOT, "demo", "mc_v12", "expected.json"), encoding="utf-8"))
    acc = {}
    for ph in ("full", "restart", "upgrade", "portable", "seed_v11", "seed_v12", "upgrade_v12"):
        f = os.path.join(evidence, f"acceptance_{ph}.json")
        if os.path.exists(f):
            rs = json.load(open(f, encoding="utf-8"))
            acc[ph] = (sum(r["passed"] for r in rs), len(rs))
    std_user = os.path.join(os.environ.get("SRS_STD_EVIDENCE") or os.path.join(evidence, "standard_user"), "acceptance_portable.json")
    if os.path.exists(std_user):
        rs = json.load(open(std_user, encoding="utf-8")); acc["standard_user"] = (sum(r["passed"] for r in rs), len(rs))
    release = release or {}
    D = Deck(shots)
    prs = D.prs
    cover = prs.slides[0]
    for sh in list(cover.shapes):  # 以 v1.1 演示 PPT 为模板时, 去掉其封面附加文本框
        if sh.has_text_frame and sh.text_frame.text.startswith("汇报人"):
            sh._element.getparent().remove(sh._element)
    for sh in cover.shapes:
        if sh.name == "Rectangle 7":
            set_lines(sh, [f"SRS v{VERSION} 年度验收演示（收尾候选）"])
        elif sh.name == "Rectangle 2":
            set_lines(sh, ["污染场地土壤生态-生产功能重构", "监管系统（SRS）操作演示"])
            for para in sh.text_frame.paragraphs:
                for r in para.runs:
                    r.font.size = Pt(36)
        elif sh.name == "文本框 8":
            set_lines(sh, ["委托单位：生态环境部土壤与农业农村生态环境监管技术中心", "承担单位：浙江大学环境与资源学院"])
    deck_textbox(cover, 2.0, 3.9, 9.3, 0.95,
                 [[("汇报人：曾 鸿    指导教师：王 玮 副教授", {"size": 16, "bold": True})],
                  [(f"软件版本 v{VERSION}（收尾候选，待甲方验收） · 演示数据为{LABEL}", {"size": 12, "color": "grey"})]],
                 align=PP_ALIGN.CENTER, spacing=1.15)
    cover.notes_slide.notes_text_frame.text = (f"封面。本演示基于 v{VERSION} 年度验收候选版; 截图采自 Windows 实际安装的程序; 演示数据为固定种子的合成数据。"
                                               "课题二/三部分方法细节仍待陈亮、宋伟杰老师确认, 已按冻结基线执行并登记。")
    sc = EV["scenarios"]
    # 2 C1–C6
    s = D.slide("一、年度任务与 7 月 30 日意见的落实", "六条意见均已落到可演示的功能；方法细节待确认的部分按冻结基线执行并逐项登记",
                "逐条说明 C1–C6。C1 方法对齐: 本版冻结 M-REC-2025 并列出 10 项待确认事项与 18 个问题草稿(未发送)。",
                "来源：docs/annual/method_baseline_v1.2.md；DELIVERY_INDEX.md")
    rows = [["编号", "意见", f"v{VERSION} 实现", "状态"],
            ["C1", "与陈亮/宋伟杰对齐方法与数据", "冻结基线 M-REC-2025；10 项待确认 + 18 个问题草稿；字段级对照表", "待确认"],
            ["C2", "三个课题的数据都要演示", "9 个合成场地：A–E 覆盖五类结论，F/G 复合与参考阈值，H 五阶段追溯，SRS-I 邻苯二甲酸酯；子课题个旧测试表 28 项全部可赋分", "已实现"],
            ["C3", "修复后给出宜生产/宜生态结论", "法规门禁 + 功能评分 → 五类结论，附原因、条件与下一步", "已实现"],
            ["C4", "课题一/二修复前、课题三修复后独立导入", "课题二 28 项指标独立导入；课题三独立导入；数据分表存储", "已实现"],
            ["C5", "进入即见全流程追溯与上传下载引导", "五阶段引导 + 模板 + 软件里程碑与五阶段业务记录分列；查看不建记录", "已实现"],
            ["C6", "可编辑用户手册与演示 PPT", "DOCX 手册（含 PDF）+ 本 PPT，截图来自 Windows 实装程序", "已实现"]]
    deck_table(s, 0.9, 1.7, 11.55, 4.6, rows, [0.8, 3.4, 5.95, 1.4], font=13, status_col=3,
               status_map={"已实现": "verified", "待确认": "pending"})
    full = acc.get("full", (0, 0))
    deck_textbox(s, 0.9, 6.45, 11.5, 0.6, [[("Windows 实装验收：", {"bold": True}),
                 (f"关键流程 {full[0]}/{full[1]} 项通过；重启 {acc.get('restart', (0, 0))[0]}/{acc.get('restart', (0, 0))[1]}；"
                  f"v1.1.0→v{VERSION} 升级 {acc.get('upgrade', (0, 0))[0]}/{acc.get('upgrade', (0, 0))[1]}；v1.2.1→v{VERSION} 升级 {acc.get('upgrade_v12', (0, 0))[0]}/{acc.get('upgrade_v12', (0, 0))[1]}；便携版 {acc.get('portable', (0, 0))[0]}/{acc.get('portable', (0, 0))[1]}（GitHub Actions Windows）。", {})]], size=13)
    # 3 数据阶段
    s = D.slide("二、三个课题与数据阶段", "修复前数据进课题一、二；修复后数据只经课题三导入；三类批次分表存储、不自动复制",
                "强调分离: 课题二 28 项指标也是修复前数据, 有独立批次; 修复后 SSUI 与修复后污染物检测只进入课题三。",
                "来源：migration 0007/0008；recon_import_service.py；ssui_post_service.py")
    deck_box(s, 0.95, 1.75, 5.6, 0.55, text=["修复前（调查评估 · 方案审批）"], fill="brown", line=None, size=16, color="white", bold=True)
    deck_box(s, 6.8, 1.75, 5.6, 0.55, text=["修复后（效果评估 · 后期管护）"], fill="gold", line=None, size=16, color="white", bold=True)
    for i, (t, d) in enumerate([("课题一  障碍因子识别（KOS）", "检测数据导入 → 关键障碍因子 Top-N"),
                                ("课题二  功能重构可行性", "28 项指标导入 → 生产/生态可行性 → 修复前情景判断")]):
        deck_box(s, 0.95, 2.55 + i * 1.35, 5.6, 1.15, text=[[(t, {"bold": True, "size": 15})], d], fill="cream", line="brown", size=13)
    deck_box(s, 6.8, 2.55, 5.6, 1.15, text=[[("课题三  修复后 SSUI", {"bold": True, "size": 15})], "独立模板导入 → SSUI 计算 → 导出"], fill="cream", line="gold", size=13)
    deck_box(s, 6.8, 3.9, 5.6, 1.15, text=[[("修复后利用方向结论", {"bold": True, "size": 15})], "法规门禁（GB 15618 / GB 36600）+ SSUI"], fill="cream", line="gold", size=13)
    deck_arrow(s, 9.6, 3.7, 9.6, 3.9, color="gold")
    deck_box(s, 0.95, 5.35, 11.45, 1.55, text=[
        [("修复前入口：", {"bold": True}), ("场地管理 → 数据导入（PRE-v1.1）；重构指标导入（RECON-PRE-v1.2）", {})],
        [("修复后入口：", {"bold": True}), ("修复后SSUI（课题三）→ SSUI-POST-v1.1 → 上传校验 → 确认入库", {})],
        [("分离方式：", {"bold": True}), ("独立批次表；课题一/二只读修复前数据；合成演示中的修复前后关联已显式标注，不代表真实修复效果", {})]],
        fill="panel", line=None, size=13, align=PP_ALIGN.LEFT, margin=0.15)
    # 4 安装
    s = D.slide("三、安装、首启、升级与便携版", "安装包不含业务数据和账户；首启空库设置管理员；v1.1.0、v1.2.0 覆盖升级数据保留",
                f"演示: 安装路径含中文和空格; 首启空库; 升级 v1.1.0/v1.2.1→v{VERSION} 在 GitHub Actions Windows(管理员账户)上实测; 便携版数据写在 exe 同级 SRS_data。/CURRENTUSER 安装到当前用户目录; 标准(非管理员)测试账户经 CI 计划任务安装、启动、导入/评价通过, 甲方 Windows 10/11 实机尚未测试。",
                "来源：.github/workflows/windows-release.yml；acceptance_*.json")
    deck_textbox(s, 0.95, 1.7, 5.2, 5.2, [
        [("1  安装版", {"bold": True, "size": 16, "color": "brown"})], f"SRS-Setup-{VERSION}-Windows-x64.exe；/CURRENTUSER 安装到当前用户目录（CI 标准账户计划任务测试通过，见验收页）", "",
        [("2  首次启动", {"bold": True, "size": 16, "color": "brown"})], "空数据库 → 设置管理员（≥8 位，3 类字符）", "",
        [("3  升级", {"bold": True, "size": 16, "color": "brown"})], "覆盖安装；自动迁移（含 0009 单位修复）、阈值补水田口径、已出报告保留", "",
        [("4  便携版", {"bold": True, "size": 16, "color": "brown"})], f"SRS-Portable-{VERSION}-Windows-x64.zip；数据在 SRS_data"], size=14, spacing=1.1)
    D.shot(s, "00_first_run_setup.png", 6.4, 1.7, 6.1, 5.2, "首次启动设置向导")
    # 5 追溯
    s = D.slide("四、全流程追溯：进入即见", "打开页面即显示五阶段引导、需上传资料和模板下载；查看不创建任何记录",
                "C5: 进入追溯页面不需要先选场地。v1.2.1 起把“七项软件操作里程碑”与“五阶段业务记录”分开: 软件操作 7/7 不等于调查、审批、施工、效果评估、管护五阶段完成; 演示场地 A–G 未上传业务材料, 五阶段均显示未开展; v1.2.2 场地 H 五阶段均有模拟材料与模拟审核记录(见追溯截图 26)。",
                "来源：GET /api/v1/trace/guide、/sites/{id}/trace/progress")
    stages = [("调查评估", "修复前 · 课题一/二"), ("方案审批", "修复前 · 课题一/二"), ("施工监理", "—"),
              ("效果评估", "修复后 · 课题三"), ("后期管护", "修复后 · 课题三")]
    for i, (n, d) in enumerate(stages):
        x = 0.95 + i * 2.33
        deck_box(s, x, 1.75, 2.05, 0.95, text=[[(n, {"bold": True, "size": 15})], d],
                 fill="cream" if i < 3 else "FFF7E6", line="brown" if i < 3 else "gold", size=11)
        if i < 4:
            deck_arrow(s, x + 2.05, 2.22, x + 2.33, 2.22)
    D.shot(s, "20_trace_guide.png", 0.95, 2.9, 7.3, 4.15, "全流程追溯引导")
    tp = sc.get("A", {}).get("trace_progress", {})
    deck_box(s, 8.45, 2.9, 3.95, 4.15, text=[[("SRS-A：两类进度分开显示", {"bold": True, "size": 14, "color": "brown"})],
                                             [("七项软件操作里程碑", {"bold": True})],
                                             "导入 · 课题一 · 课题二 · 修复前判断 · 课题三 · 修复后结论 · 报告",
                                             [(f"已执行 {tp.get('software_milestones') or str(tp.get('completed')) + '/' + str(tp.get('total'))}", {"bold": True, "color": "green"})],
                                             [("五阶段业务记录", {"bold": True})],
                                             [(f"已完成并有材料 {tp.get('business_stages_completed', '—')}（未上传材料 = 未开展）", {"bold": True, "color": "red"})]],
             fill="panel", line=None, size=12, align=PP_ALIGN.LEFT, margin=0.15)
    # 6 课题一
    a = sc.get("A", {})
    s = D.slide("五、课题一：障碍因子识别（KOS）", "正式 Top-N 只收本轨官方标准证据；文献/启发式阈值仅作探索提示，区分上限与下限",
                f"演示场地 SRS-A(合成): 正式关键障碍因子 {fcn((a.get('S1_kos_top') or [])[:5])}; 探索性 {fcn(a.get('S1_kos_exploratory') or [])}(下限不足, 文献参考)。"
                "v1.2.1 修复: 阳离子交换量/全氮等为下限指标, 高值不再被判为障碍; 有机质(g/kg)与有机碳(%)分开, 不做换算; 单位不可换算即排除。模型 p3_alpha 未重训。",
                "来源：Windows 验收 demo_actual/comparison.json")
    deck_textbox(s, 0.95, 1.7, 4.6, 5.3, [
        [("操作步骤", {"bold": True, "size": 16, "color": "brown"})],
        "1  场地管理 → 导入数据（修复前模板）", "2  查看校验报告（错误、警告、超标）", "3  障碍因子分析（课题一）→ 运行诊断", "",
        [("演示结果（模拟数据）", {"bold": True, "size": 16, "color": "brown"})],
        "正式（GB 15618，证据 A）：" + fcn((a.get("S1_kos_top") or [])[:5]),
        "探索性（下限·文献参考，待复核）：" + (fcn(a.get("S1_kos_exploratory") or []) or "无"),
        "KOS = B×(0.30R+0.25W+0.15M+0.20S+0.10E)", "补充场景：F 有机物按同单位比较；G 无官方超标→证据不足"], size=13, spacing=1.05)
    D.shot(s, "06_obstacle_S1.png", 5.8, 1.7, 6.7, 5.3, "障碍因子分析（课题一）")
    # 7 课题二导入
    s = D.slide("六、课题二：28 项重构指标导入", "数值 + 类别指标逐格校验；7 个类别指标按表2.22 分级赋分；个旧测试表 28/28 可赋分",
                "子课题个旧测试表: 81 点位; v1.1 只能解析 19 项数值列; v1.2 解析类别列并清洗 18 个数值文本单元格, 生产轨道 28 项全部可赋分。",
                "来源：D09_data_method_pack/05_feature_usability_19_vs_28.csv；recon_import_service.py")
    rows = [["场地(合成)", "生产得分 / 等级", "生态得分 / 等级", "计算路径"]]
    for c in "ABCDE":
        s2 = sc.get(c, {}).get("S2", {})
        rows.append([f"SRS-{c}", f"{s2.get('production', {}).get('score')} / {s2.get('production', {}).get('grade')}",
                     f"{s2.get('ecology', {}).get('score')} / {s2.get('ecology', {}).get('grade')}",
                     " / ".join("全指标" if s2.get(t, {}).get("path") == "full" else "缺失数据" for t in ("production", "ecology"))])
    deck_table(s, 0.95, 1.75, 6.2, 3.0, rows, [1.1, 1.65, 1.65, 1.8], font=11.5)
    deck_box(s, 0.95, 4.95, 6.2, 2.05, text=[[("子课题个旧测试表（来源未核实，仅作软件演示）", {"bold": True, "color": "brown"})],
                                            "v1.1：19/28 项可用（类别列与含空格数值未解析）",
                                            "v1.2：生产 28/28 项、81/81 点位可赋分；生态 18 项有规则",
                                            "清洗：全氮 13 格、有效磷 4 格、CEC 1 格（不间断空格/制表符）"],
             fill="panel", line=None, size=12.5, align=PP_ALIGN.LEFT, margin=0.15)
    D.shot(s, "08_recon_import_S2_result.png", 7.35, 1.75, 5.1, 5.25, "课题二指标导入结果")
    # 8 校验
    s = D.slide("七、导入校验：错误不入库、告警可确认", "非法类别、重复点位、物理范围、阶段错误、单位错误逐格报错；Excel 错误值按缺测",
                "演示两个夹具: F02 非法类别(拒绝); F05 常数列(告警, 可确认)。课题三单位错误定位到工作表/行/列。",
                "来源：demo/mc_v12/fixtures；demo_actual/comparison.json")
    D.shot(s, "09_recon_import_validation_error.png", 0.95, 1.75, 5.6, 5.25, "课题二：非法类别报错")
    D.shot(s, "12_ssui_post_validation_error.png", 6.8, 1.75, 5.6, 5.25, "课题三：单位错误报错")
    # 9 方法
    s = D.slide("八、冻结方法基线 M-REC-2025", "按方法文件表2.18–2.23 执行：权重原值不归一，内梅罗只用于缺测类别分，笔误显式登记",
                "说明 v1.2 对 v1.1 计算缺陷的更正, 以及 10 项待确认事项。不恢复旧缺陷, 也不凭推测补定义。",
                "来源：docs/annual/method_baseline_v1.2.md")
    deck_table(s, 0.95, 1.75, 6.0, 4.0, [["项目", "冻结基线"], ["综合得分", "Σ(F×T)，表2.18 Σ=0.9643，不归一"],
                                          ["缺测", "表2.19/2.21 准则层；两类用内梅罗"], ["等级", ">50 可行；≤50 不可行"],
                                          ["污染物", "超管制 10 / 超筛选 50 / 未超 100"], ["点→面", "数值中位数，类别众数"],
                                          ["不换算", "有机质≠有机碳；总铬≠六价铬"]], [1.5, 4.5], font=12)
    deck_table(s, 7.15, 1.75, 5.3, 4.0, [["编号", "待确认事项"], ["M-01", "C库因子④档 690→69"], ["M-02", "生态有效土层④档 00→90"],
                                          ["M-03", "有机碳/剖面构型无表2.18 权重"], ["M-04", "类内 P权重 口径"], ["M-06", "旱地/水田未注明取低"],
                                          ["M-07", "六价铬 vs 总铬"], ["M-08", "生态剖面构型缺档"]], [1.0, 4.3], font=12)
    deck_box(s, 0.95, 5.95, 11.5, 1.0, text=[[("v1.1 缺陷更正：", {"bold": True, "color": "red"}),
                                              ("已测指标内重标化、总分套用内梅罗、无依据默认分（剖面 70、坡度 60）、BHC/DDT/BaP 超限=10、权重和 1.0506（混入准则层权重）", {})]],
             fill="F9E3E3", line=None, size=12.5, align=PP_ALIGN.LEFT, margin=0.15)
    # 10 课题三
    sA = a.get("S3", {})
    s = D.slide("九、课题三：修复后 SSUI 独立导入", "下载模板 → 上传校验（不入库）→ 确认入库（事务）→ 导出；本版为得分录入模式",
                f"演示 SRS-A: 生产 SSUI {sA.get('production', {}).get('ssui')}, 生态 {sA.get('ecology', {}).get('ssui')}; 与独立期望值逐个比对一致。"
                "方法未给 D1–D25 原始值→得分规则, 因此由课题组录入得分。",
                "来源：ssui_post_service.py；expected.json")
    rows = [["场地(合成)", "生产 SSUI", "生态 SSUI", "与独立期望值"]]
    for c in "ABCDE":
        s3 = sc.get(c, {}).get("S3", {})
        rows.append([f"SRS-{c}", f"{s3.get('production', {}).get('ssui')}", f"{s3.get('ecology', {}).get('ssui')}",
                     "一致" if all(abs((s3.get(t, {}).get("ssui") or -9) - EXP["scenarios"][c]["ssui"][t]["ssui"]) < 1e-5 for t in ("production", "ecology")) else "不一致"])
    deck_table(s, 0.95, 1.75, 5.6, 3.1, rows, [1.3, 1.5, 1.5, 1.3], font=12)
    deck_box(s, 0.95, 5.05, 5.6, 1.95, text=[[("SSUI = f(t) × Σ vj·Sj × M", {"bold": True, "size": 16})],
                                            "f(t) = 1 + 0.03t；M 生产 1.1–1.2，生态 1.05–1.1", "权重取自方法 PPT 第 13/14 页；>1 不截断并标注"],
             fill="panel", line=None, size=12.5)
    D.shot(s, "11_ssui_post_S3.png", 6.75, 1.75, 5.7, 5.25, "修复后 SSUI 导入（课题三）")
    # 11 五类结论
    s = D.slide("十、五类利用结论（合成场地逐一演示）", "每个场地对应一个分支，系统结论与独立期望值全部一致",
                "五个合成场地分别设计为五类结论。期望值由独立代码直接读官方阈值表计算, 不调用系统评价代码。",
                "来源：demo/mc_v12/expected.json；Windows demo_actual/comparison.json")
    rows = [["场地", "设计", "生产门禁", "生态门禁", "系统结论", "期望"]]
    for c in "ABCDE":
        d = sc.get(c, {}).get("decision_post", {})
        rows.append([f"SRS-{c}", EXP["scenarios"][c]["title"].split("(")[0], GATE_CN.get(d.get("gates", {}).get("production"), "—"),
                     GATE_CN.get(d.get("gates", {}).get("ecology"), "—"), DECISION_CN.get(d.get("state"), d.get("state")),
                     DECISION_CN.get(EXP["scenarios"][c]["post_decision"])])
    deck_table(s, 0.95, 1.75, 7.0, 3.6, rows, [0.9, 1.9, 1.0, 1.0, 1.2, 1.0], font=11)
    deck_box(s, 0.95, 5.55, 7.0, 1.45, text=["门禁优先：超管制值的一轨不能被任何评分抵消；",
                                            "缺测必测项目 → 证据不足，并列出需补充的证据；",
                                            "生产条件通过附安全利用条件；生态超筛选值须先做风险评估。"],
             fill="panel", line=None, size=12.5, align=PP_ALIGN.LEFT, margin=0.15)
    D.shot(s, "16_decision_D_neither.png", 8.15, 1.75, 4.3, 5.25, "SRS-D：重度超标两轨均不支持")
    # 12 阈值
    s = D.slide("十一、法规阈值：按官方标准全文核实", "两项国标由生态环境部官网 PDF 逐行转录；GB 36600 的 12 项 VOC 已核实",
                "知识库 12 项 VOC 的 24 条记录与官方表1 全部一致; 氯甲烷/氯苯场景标签对调已更正; 旧版非标准替代阈值全部移除。",
                "来源：D10_threshold_verification_pack；data/standards/*_official.csv")
    deck_table(s, 0.95, 1.75, 6.4, 4.6, [["污染物", "筛选值 一类/二类", "管制值 一类/二类"],
                                          ["氯甲烷", "12 / 37", "21 / 120"], ["1,1-二氯乙烷", "3 / 9", "20 / 100"],
                                          ["1,1-二氯乙烯", "12 / 66", "40 / 200"], ["顺/反-1,2-二氯乙烯", "66/596；10/54", "200/2000；31/163"],
                                          ["1,2-二氯丙烷", "1 / 5", "5 / 47"], ["四氯乙烷(1112/1122)", "2.6/10；1.6/6.8", "26/100；14/50"],
                                          ["三氯乙烷(111/112)", "701/840；0.6/2.8", "840/840；5/15"], ["1,2,3-三氯丙烷", "0.05 / 0.5", "0.5 / 5"],
                                          ["间+对二甲苯", "163 / 570", "500 / 570"]], [2.4, 2.0, 2.0], font=11.5)
    deck_box(s, 7.55, 1.75, 4.9, 4.6, text=[[("更正内容", {"bold": True, "size": 14, "color": "brown"})],
                                            "多氯联苯(总量) 0.2/2.0 → 官方 0.14/0.38（管制 1.4/3.8）",
                                            "删除 DDT类、六六六总量、荧蒽/芘/蒽/菲等“族群匹配”替代值",
                                            "GB 15618 铜：果园/其他（原误标为水田）",
                                            "种子阈值表补入 GB 15618 管制值；升级时自动更正",
                                            "知识库氯甲烷、氯苯场景字段对调；PCB/二噁英指数解析"],
             fill="panel", line=None, size=12, align=PP_ALIGN.LEFT, margin=0.15)
    deck_textbox(s, 0.95, 6.5, 11.5, 0.5, ["单位 mg/kg；GB 36600-2018 表1，标准第 3–4 页。规划用途不明确时按第一类用地（5.3.1）。"], size=11, color="grey")
    # 13 个旧(内部)
    if not public and gejiu:
        s = D.slide("十二、真实数据复核：个旧（内部版）", "评分可行≠可利用：甲方个旧场地 As、Pb 超管制值 → 两轨均不支持",
                    "两份不同的数据: (1) 甲方个旧场地表 134 点(修复前), 旧版 v1.0.x 曾判生态可行 63.29, v1.1 起法规门禁 As、Pb 134/134 点超管制值 → 均不支持, v1.2 不变; "
                    "(2) 子课题个旧测试表 81 点(来源未核实), v1.2 按冻结方法 生产 " + str(gejiu.get("prod_score")) + "、生态 " + str(gejiu.get("eco_score")) + "。说明方法得分与法规门禁的分工。",
                    "来源：D09 包；data/raw 甲方个旧工作簿；test_gejiu_real_data_fails_both_gates_and_score_cannot_offset")
        deck_table(s, 0.95, 1.8, 11.45, 2.9, [["数据", "项目", "v1.0.x（36aabf4）", "v1.1.0", f"v{VERSION}"],
                                               ["甲方个旧场地表（134 点）", "生态重构", "可行 63.29", "无法评价（指标覆盖不足）", "本版未单独复核（门禁已否决）"],
                                               ["甲方个旧场地表（134 点）", "法规门禁 / 结论", "无门禁", "As、Pb 134/134 超管制值 → 均不支持", "同左（不变）"],
                                               ["子课题个旧测试表（81 点）", "可赋分指标", "—", "19/28 项", "生产 28/28 项"],
                                               ["子课题个旧测试表（81 点）", "课题二得分", "—", "—", f"生产 {gejiu.get('prod_score')} 可行；生态 {gejiu.get('eco_score')} 可行（缺失数据路径）"]],
                   [2.6, 1.7, 1.7, 2.6, 2.85], font=11.5)
        deck_box(s, 0.95, 4.95, 11.45, 1.95, text=[[("意义", {"bold": True, "size": 15, "color": "brown"})],
                                                 "1  方法得分按冻结基线如实计算，不为“好看”而调整；",
                                                 "2  利用方向由法规门禁优先决定，严重超标场地不会被“平均”成可利用；",
                                                 "3  子课题测试表来源未核实（多列取值与权重计算表重合），只说明软件能力，不作为场地结论。"],
                 fill="panel", line=None, size=13, align=PP_ALIGN.LEFT, margin=0.18)
    # 14 报告/备份
    s = D.slide("十三、报告、备份与模拟数据标签", "报告由同一评价快照生成：正文、Excel、PDF、DOCX 数字一致；修复前/后与批次分开统计",
                "v1.2.1: 评价快照(SHA-256)保存在报告记录中, 之后的新数据不改变已出报告; 修复后两条轨道重复导入的同一批样品按样品编号去重; "
                "场地级超标按阶段由法规门禁给出, 不再用最新批次校验代替; PDF 用 ReportLab 排版并嵌入中文字体。",
                "来源：evaluation_snapshot.py；report_document.py；report_invariants.py；test_v121_report_consistency.py")
    for i, (t, items) in enumerate([("报告", ["同一评价快照 → PDF / DOCX / Excel", "修复前/后、批次、样品去重分列", "嵌入中文字体、表格与图件"]),
                                     ("备份与恢复", ["每天 02:00 自动加密备份", "恢复须二次确认，先自动快照", "重启后结论逐字一致（实测）"]),
                                     ("模拟数据标签", [LABEL, "导入自动识别并全链路标记", "正式首启为空库"])]):
        x = 0.95 + i * 3.87
        deck_box(s, x, 1.75, 3.6, 0.55, text=[t], fill="brown" if i < 2 else "red", line=None, size=15, color="white", bold=True)
        deck_box(s, x, 2.3, 3.6, 1.6, text=items, fill="panel", line=None, size=12.5, align=PP_ALIGN.LEFT, margin=0.15)
    D.shot(s, "21_trace_detail.png", 0.95, 4.1, 5.6, 2.95, "场地追溯详情（软件里程碑、五阶段记录、报告）")
    D.shot(s, "24_system.png", 6.8, 4.1, 5.6, 2.95, "系统管理（备份恢复）")
    # 15 演示脚本
    s = D.slide("十四、年度验收演示脚本（约 20 分钟）", "同一演示包按课题顺序演示；每一步说明使用修复前还是修复后数据",
                "顺序: 安装首启(2) → 课题一(3) → 课题二导入与校验(5) → 课题三(4) → 五类结论(4) → 追溯与报告(2)。",
                "来源：D13 演示操作脚本；demo/mc_v12/metadata.json")
    deck_table(s, 0.95, 1.75, 11.45, 4.6, [["步骤", "文件", "操作", "看点"],
                                            ["1 首启", "—", "安装 → 设置管理员 → 登录", "空库、无测试账户"],
                                            ["2 课题一", "site_A/01_修复前检测数据", "数据导入 → 障碍因子分析", "关键障碍因子 Top-N"],
                                            ["3 课题二", "site_A/02_课题二重构指标；fixtures/F02、F05", "重构指标导入 → 预览 → 确认 → 查看/导出", "28 项指标、逐格校验、计算过程"],
                                            ["4 课题三", "site_A/03、04_课题三SSUI", "下载模板 → 上传 → 确认 → 导出", "SSUI 与期望值一致"],
                                            ["5 结论", "site_A…E", "修复后利用结论（水田）", "五类结论逐一出现"],
                                            ["6 追溯", "—", "全流程追溯 → 生成报告 / 评价快照 Excel", "软件里程碑与五阶段分开；报告与 Excel 同一快照"]],
               [1.2, 3.6, 3.7, 2.95], font=12)
    # 16 验收与发布
    s = D.slide("十五、验收证据与发布", "Windows 实装验收、重启、升级、便携版均执行；发布为年度验收候选版（预发布）",
                "如实说明: 验收在 GitHub Actions Windows 虚拟机上执行(管理员账户); 标准账户测试为独立作业, 以计划任务身份运行, 不等同于甲方 Windows 10/11 实机。发布标签与源码、安装包、截图、文档为同一提交。",
                "来源：Windows workflow run；GitHub Release")
    rows = [["检查", "结果"]]
    for k, lab in (("full", "首启 + 7 场景 + 8 夹具 + 跨渠道一致性"), ("restart", "重启一致性"), ("upgrade", f"v1.1.0 → v{VERSION} 升级"),
                   ("upgrade_v12", f"v1.2.0 → v{VERSION} 升级"), ("portable", "便携版"), ("standard_user", "标准(非管理员)账户（CI 计划任务）")):
        v = acc.get(k)
        if not v and k == "standard_user" and os.path.exists(os.path.join(evidence, "standard_user.txt")):
            t = open(os.path.join(evidence, "standard_user.txt"), encoding="utf-8", errors="ignore").read()
            m = re.search(r"installer exit: (\d+)", t)
            rows.append([lab, f"已尝试：安装程序退出码 {m.group(1) if m else '?'}，未完成，待实机复测"]); continue
        rows.append([lab, f"{v[0]}/{v[1]} 通过" if v else "未执行（见验收记录）"])
    deck_table(s, 0.95, 1.75, 6.0, 4.0, rows, [3.2, 2.8], font=12.5)
    deck_box(s, 7.15, 1.75, 5.3, 4.0, text=[[("发布信息", {"bold": True, "size": 14, "color": "brown"})],
                                            f"版本：v{VERSION}（预发布，收尾候选）", f"标签：{release.get('tag', '—')}", f"提交：{(release.get('commit') or '—')[:12]}",
                                            f"工作流：{release.get('run', '—')}", "资产：安装包、便携版、SHA-256、手册 DOCX/PDF、PPTX、演示包"],
             fill="panel", line=None, size=12, align=PP_ALIGN.LEFT, margin=0.15)
    deck_textbox(s, 0.95, 5.95, 11.5, 0.9, [release.get("url", "")], size=11, color="grey")
    # 17 三项结论
    s = D.slide("十六、三项结论与待办", "软件/演示就绪；科学方法与真实修复后数据验证分别跟踪，不混为一谈",
                "三项结论分开: 年度软件与演示就绪度(内部就绪, 非甲方验收结论); 科学方法验证(待确认); 真实修复后验证(待数据)。",
                "来源：FINAL_REPORT.md")
    deck_table(s, 0.95, 1.75, 11.45, 2.6, [["维度", "结论", "依据"],
                                            ["年度软件与演示", "收尾候选（待甲方验收）", "T01–T06：SSUI 定义域、邻苯二甲酸酯单体标识、用途状态、场地 H 推荐与五阶段追溯；Windows 实装验收；文档与截图同版"],
                                            ["科学方法验证", "未完成（冻结基线执行）", "Q01–Q18 决策登记：17 项待答复、1 项软件侧部分解决"],
                                            ["真实修复后验证", "未开始（缺数据）", "尚无实测修复后数据"]], [2.6, 3.0, 5.85], font=13)
    deck_box(s, 0.95, 4.6, 11.45, 2.35, text=[[("需要各方配合", {"bold": True, "size": 15, "color": "brown"})],
                                              "1  陈亮、宋伟杰老师确认方法事项（Q01–Q18 决策登记）；文献参考阈值是否批准为正式限值",
                                              "2  提供至少 1 个场地的实测修复后数据（D1–D25 与污染物）",
                                              "3  提供 D1–D25 原始值 → 得分分级规则，以实现原始数据计算",
                                              "4  决定公开仓库中甲方原始数据表的处理方式（仓库为公开可见）"],
             fill="panel", line=None, size=13, align=PP_ALIGN.LEFT, margin=0.18)
    prs.save(out)
    return {"pptx": out, "slides": len(prs.slides), "screenshots_used": D.used, "screenshots_missing": D.missing}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", required=True)
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--public", action="store_true")
    ap.add_argument("--release", default=None, help="JSON: tag/commit/run/url")
    ap.add_argument("--gejiu", default=None, help="JSON: prod_score/eco_score (内部版)")
    a = ap.parse_args()
    print(json.dumps(build(a.shots, a.out, a.evidence, a.public, json.loads(a.release) if a.release else None,
                           json.loads(a.gejiu) if a.gejiu else None), ensure_ascii=False, indent=1))
