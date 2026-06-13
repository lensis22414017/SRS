"""
从《(2025年)污染场地土壤生态-生产功能障碍识别与重构利用的评价方法+年度报告.docx》
提取重构可行性评价与 SSUI 评价的真实参数, 固化为机读 JSON, 供算法模块加载。

可重复运行。所有数值均来源于该方法文件相应表格, 不得手工改值。
来源表:
  - 表2.10/2.11 指标层权重 (table idx 21=生产, 23=生态)
  - 表2.18~2.21 准则层权重 (table idx 22=生产, 24=生态)
  - 表2.22 指标分等赋值 (table idx 25)
  - 表2.23 评分对应等级 (table idx 26): >50 可行
  - 表3.49 管理调节因子M (table idx 75)
  - 表3.50 SSUI等级 (table idx 76)
  - 表3.53/3.54 SSUI指标层/元指标权重 (table idx 79=生产, 80=生态)
  - 正文: SSUI公式, 时间权重函数 f(t)=1+alpha*t, alpha=0.03
"""
import json
import os
import re
import sys
import glob

try:
    import docx
except ImportError:
    sys.exit("需要 python-docx: pip install python-docx --break-system-packages")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE

# 方法文件可能位于 uploads 或 data/raw; 优先环境变量
def find_doc():
    cands = []
    env = os.environ.get("METHOD_DOC")
    if env:
        cands.append(env)
    cands += glob.glob("/sessions/*/mnt/uploads/*评价方法*.docx")
    cands += glob.glob(os.path.join(HERE, "..", "..", "data", "raw", "*评价方法*.docx"))
    for c in cands:
        if os.path.exists(c):
            return c
    sys.exit("未找到方法文件 (*评价方法*.docx), 可用 METHOD_DOC 环境变量指定")


def table_rows(t):
    return [[c.text.strip().replace("\n", " ") for c in r.cells] for r in t.rows]


def pct(s):
    s = s.strip().replace("%", "").replace("％", "")
    try:
        return round(float(s) / 100.0, 6)
    except ValueError:
        return None


def num(s):
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        return None


def parse_pair_weight_table(rows):
    """解析 '指标|权重|指标|权重' 的双列权重表。"""
    out = {}
    for r in rows[1:]:
        if len(r) >= 2 and r[0] and pct(r[1]) is not None:
            out[r[0]] = pct(r[1])
        if len(r) >= 4 and r[2] and pct(r[3]) is not None:
            out[r[2]] = pct(r[3])
    return out


def main():
    doc = find_doc()
    d = docx.Document(doc)
    T = d.tables
    src = os.path.basename(doc)

    # ---- 重构指标层权重 ----
    recon_ind_prod = parse_pair_weight_table(table_rows(T[21]))
    recon_ind_eco = parse_pair_weight_table(table_rows(T[23]))
    # ---- 重构准则层权重 ----
    recon_crit_prod = parse_pair_weight_table(table_rows(T[22]))
    recon_crit_eco = parse_pair_weight_table(table_rows(T[24]))

    # ---- 分等赋值 (表2.22) ----
    scoring = {"production": {}, "ecology": {}}
    for r in table_rows(T[25])[1:]:
        if len(r) < 4 or not r[1]:
            continue
        cat = "production" if "生产" in r[0] else "ecology"
        scoring[cat][r[1]] = {"grades": r[2], "scores": r[3]}

    # ---- 等级 (表2.23) ----
    recon_grade = {"threshold": 50, "rule": ">50 可行, <=50 不可行",
                   "levels": [{"range": "<=50", "label": "不可行"},
                              {"range": ">50", "label": "可行"}]}

    # ---- 管理调节因子 M (表3.49) ----
    m_factor = []
    for r in table_rows(T[75])[1:]:
        if len(r) >= 3 and num(r[2]) is not None:
            m_factor.append({"land_use": r[0], "intensity": r[1],
                             "M": num(r[2]), "note": r[3] if len(r) > 3 else ""})

    # ---- SSUI 等级 (表3.50) ----
    ssui_levels = []
    for r in table_rows(T[76])[1:]:
        if len(r) >= 2 and r[0]:
            ssui_levels.append({"range": r[0], "label": r[1]})

    # ---- SSUI 元指标权重 (表3.53 生产 / 3.54 生态) ----
    def parse_ssui_meta(rows):
        crit = {}
        meta = {}
        for r in rows[1:]:
            if len(r) < 3 or not r[0]:
                continue
            mname = re.match(r"(.+?)（([0-9.]+)）", r[0])
            cname = mname.group(1) if mname else r[0]
            cw = float(mname.group(2)) if mname else None
            if cw is not None:
                crit[cname] = cw
            w = num(r[2])
            if w is not None:
                meta[r[1]] = {"criterion": cname, "weight": w}
        return {"criteria_weights": crit, "meta_weights": meta}

    ssui_prod = parse_ssui_meta(table_rows(T[79]))
    ssui_eco = parse_ssui_meta(table_rows(T[80]))

    params = {
        "_source": src,
        "_note": "数值来源于方法文件, 禁止手工改值; 重新生成请运行 extract_params.py",
        "reconstruction": {
            "method": "改进模糊综合评价法: 综合得分=Σ(F_i×T_i), F=分等赋值, T=指标权重",
            "grade": recon_grade,
            "production": {"criterion_weights": recon_crit_prod,
                           "indicator_weights": recon_ind_prod},
            "ecology": {"criterion_weights": recon_crit_eco,
                        "indicator_weights": recon_ind_eco},
            "scoring": scoring,
        },
        "ssui": {
            "method": "分维度多指标分块赋权: SSUI = (Σ vCi·SCi) · f(t) · M",
            "time_weight_function": {"formula": "f(t)=1+alpha*t", "alpha": 0.03,
                                     "note": "t为相对基准跨度(年); 文件示例 t=2 → f(t)=1.06"},
            "management_factor_M": m_factor,
            "levels": ssui_levels,
            "top_weights_production": {"vC1_limit": 0.431218, "vC2_cost": 0.259357,
                                       "vC3_benefit": 0.309425},
            "top_weights_ecology": {"vC1_limit": 0.446851, "vC2_cost": 0.270695,
                                    "vC3_benefit": 0.282454},
            "production": ssui_prod,
            "ecology": ssui_eco,
            "default_M": {"production": 1.15, "ecology": 1.08},
        },
    }

    path = os.path.join(OUT, "evaluation_params.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)

    # 摘要
    print("写出:", path)
    print("重构-生产 准则层权重数:", len(recon_crit_prod),
          "指标层:", len(recon_ind_prod))
    print("重构-生态 准则层权重数:", len(recon_crit_eco),
          "指标层:", len(recon_ind_eco))
    print("分等赋值 生产指标:", len(scoring["production"]),
          "生态指标:", len(scoring["ecology"]))
    print("管理调节因子 M 行:", len(m_factor), "SSUI等级:", len(ssui_levels))
    print("SSUI 生产元指标:", len(ssui_prod["meta_weights"]),
          "生态元指标:", len(ssui_eco["meta_weights"]))


if __name__ == "__main__":
    main()
