"""P1 候选文献筛选 (全量脚本)

输入: G:\\文献整理_最终\\文献目录_literature_catalog.csv (11676 篇)
输出:
  - candidate_literature_op_hmop.csv  (A/B/C 级候选)
  - rejected_literature_log.csv       (D 级 + 排除原因)

分级 (裴总任务定义):
  A: HM+OP 采样点级 + 中国 + SI(present) + 采样信号 (或裴总强候选)
  B: HM+OP 复合候选, 但偏综述/汇总/图表级, 需精读确认
  C: OP-only 中国土壤候选
  D: 非中国 / HM-only 无OP / 无信号 / 纯模型/综述 → rejected

注: P1 是摘要级初判, A/B 的精确区分需 P2 精读 paper.md 后修正。
"""
from __future__ import annotations
import sys
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (  # noqa: E402
    OUT_DIR, load_catalog,
    OP_KEYWORDS, HM_KEYWORDS, COMPOUND_KEYWORDS,
    is_strong_candidate,
)

import pandas as pd  # noqa: E402

# ===== 中国地名/区域信号 (region!=China 时的兜底) =====
CHINA_LOCATIONS = [
    # 省会/直辖市
    "北京", "上海", "天津", "重庆", "广州", "深圳", "杭州", "南京", "武汉", "成都",
    "西安", "沈阳", "哈尔滨", "长春", "济南", "郑州", "长沙", "南昌", "合肥", "福州",
    "昆明", "贵阳", "兰州", "太原", "石家庄", "呼和浩特", "银川", "西宁", "乌鲁木齐",
    "拉萨", "海口", "南宁", "香港", "澳门",
    # 典型场地所在城市/区域
    "秦皇岛", "台州", "贵屿", "胜利油田", "大庆", "攀枝花", "金昌", "白云鄂博",
    "三峡", "长江", "太湖", "滇池", "巢湖", "珠江", "黄浦江", "辽河", "海河",
    "Three Gorges", "Yangtze", "Pearl River", "Taihu",
    # 区域泛称
    "South China", "East China", "North China", "Southwest China", "Northeast China",
    "eastern China", "southern China", "northern China", "western China",
    "华北平原", "长江三角洲", "珠江三角洲", "京津冀", "黄土高原",
    # 英文省名 (兜底)
    "Zhejiang", "Jiangsu", "Guangdong", "Shandong", "Liaoning", "Hebei",
    "Shanxi", "Shaanxi", "Sichuan", "Hunan", "Hubei", "Henan", "Anhui",
    "Fujian", "Yunnan", "Guizhou", "Heilongjiang", "Jilin",
]


def contains_chinese_location(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(loc.lower() in low for loc in CHINA_LOCATIONS)


# ===== 家族检测 =====
FAMILY_PATTERNS = [
    ("PAHs", r"PAH|多环芳烃"),
    ("PCBs", r"PCB|多氯联苯"),
    ("PBDEs", r"PBDE|多溴联苯醚|多溴二苯醚"),
    ("PFAS", r"PFAS|全氟|perfluoro"),
    ("PAEs", r"\bPAE\b|phthalate|邻苯二甲酸"),
    ("OCPs", r"OCP|有机氯农药|chlorinated pesticide"),
    ("DDT", r"DDT|滴滴涕"),
    ("HCH", r"HCH|六六六|hexachlorocyclohexane"),
    ("TPH", r"\bTPH\b|petroleum hydrocarbon|石油烃|TotalPHC"),
    ("OPFRs", r"OPFR|有机磷阻燃|organophosphate flame"),
    ("HM", r"(?:^|\W)(?:Cd|Pb|As|Hg|Cr|Cu|Zn|Ni|Co|Sb|Mn)(?:\W|$)|重金属|heavy metal"),
]


def detect_families(text: str) -> list:
    fams = []
    for name, pat in FAMILY_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            fams.append(name)
    return fams


# ===== 样本数估计 (摘要线索) =====
SAMPLE_N_PATTERNS = [
    re.compile(r"(\d+)\s*(?:surface soil samples?|soil samples?|samples were collected|sampling sites?)", re.I),
    re.compile(r"(?:collected|analyzed|investigated|obtained)\s+(\d+)\s*(?:soil\s*)?samples?", re.I),
    re.compile(r"(\d+)\s*(?:topsoil|surface soil)"),
    re.compile(r"n\s*=\s*(\d{2,4})\b"),
    re.compile(r"(\d+)\s*(?:个|件)?(?:土壤)?(?:样品|样本|采样点|样点)"),
    re.compile(r"采集(?:了)?\s*(\d+)\s*(?:个)?(?:土壤)?(?:份)?样品"),
    re.compile(r"(\d+)\s*(?:个)?(?:土壤)?样点"),
]


def extract_sample_n(text: str):
    if not text:
        return None
    for p in SAMPLE_N_PATTERNS:
        m = p.search(text)
        if m:
            try:
                n = int(m.group(1))
                if 3 <= n <= 5000:  # 合理范围
                    return n
            except (ValueError, IndexError):
                continue
    return None


# ===== 分级逻辑 =====
REVIEW_PAT = re.compile(r"\b(review|综述|meta-analysis|compiled from|bibliometric|systematic review)\b", re.I)
RISK_PAT = re.compile(r"(risk assessment|health risk|ecological risk|carcinogenic risk|风险评价|健康风险|生态风险|致癌风险)", re.I)
SAMPLE_PAT = re.compile(r"(sample|soil concentration|site|topsoil|surface soil|采样|浓度|场地|表层土壤|土壤样品|测定|含量)", re.I)


def classify(has_op, has_hm, has_compound, is_china, is_strong, si_present, text):
    """返回 (level, reason)。P1 摘要级初判。

    防误判核心: A/B 级要求 has_op AND has_hm (双家族同时出现)。
    has_compound (复合信号词) 仅作加强, 不单独触发 A/B。
    否则会把 Cd+As co-contaminated (都是HM) 误判为复合候选。
    """
    if not is_china:
        return "D", "非中国境内 (region!=China 且无中国地名信号)"

    is_true_compound = has_op and has_hm  # 双家族同时出现才算真复合

    has_review = bool(REVIEW_PAT.search(text))
    has_sample_sig = bool(SAMPLE_PAT.search(text))

    if is_true_compound:
        # HM+OP 双家族复合候选
        if is_strong:
            return "A", "强候选(裴总指定): HM+OP双家族复合 + 中国"
        if has_review and not has_sample_sig:
            return "B", "HM+OP双家族 但偏综述/汇总, 需精读确认数据可抽性"
        if si_present and has_sample_sig:
            return "A", "HM+OP双家族 + SI(present) + 采样信号 + 非纯综述"
        return "B", "HM+OP双家族复合候选, 需精读确认采样点级 vs 图表级"

    # 非双家族
    if has_op:
        # OP-only 中国 (可能含复合信号词但无具体HM家族)
        if is_strong:
            return "A", "强候选(裴总指定): OP-only 中国"
        if has_review and not has_sample_sig:
            return "C", "OP-only 但偏综述, 场地级可能可用"
        return "C", "OP-only 中国候选"

    if has_hm:
        # HM-only (即使有 co-contaminated/combined 信号词, 无OP家族仍非本任务)
        if has_compound:
            return "D", "HM-only + 复合信号词(无具体OP家族), 非OP补强范围"
        return "D", "HM-only 无OP家族信号"

    return "D", "无OP/HM家族信号"


# ===== 主流程 =====
def main():
    print("=" * 60)
    print("P1 候选文献筛选")
    print("=" * 60)
    cat = load_catalog()
    print(f"catalog 总行数: {len(cat)}")

    rows_candidate = []
    rows_rejected = []
    strong_hits = []

    for _, r in cat.iterrows():
        paper_id = str(r.get("序号", "")).strip()
        doi = str(r.get("DOI", "")).strip()
        title_en = str(r.get("英文标题", "")).strip()
        title_cn = str(r.get("中文标题", "")).strip()
        abstract = str(r.get("中文摘要", "")).strip()
        year = str(r.get("年份", "")).strip()
        region = str(r.get("region", "")).strip()
        si_status = str(r.get("SI", "")).strip()
        stem = str(r.get("stem", "")).strip()

        text = " ".join([title_en, title_cn, abstract])

        has_op = bool(OP_KEYWORDS.search(text))
        has_hm = bool(HM_KEYWORDS.search(text))
        has_compound = bool(COMPOUND_KEYWORDS.search(text))
        is_china = (region == "China") or contains_chinese_location(text)
        is_strong = is_strong_candidate(title_en, doi)
        si_present = (si_status == "present")

        families = detect_families(text)
        families_str = "|".join(families)
        est_n = extract_sample_n(abstract) or extract_sample_n(text)

        level, reason = classify(has_op, has_hm, has_compound, is_china,
                                  is_strong, si_present, text)

        row = {
            "paper_id": paper_id,
            "doi": doi,
            "title": (title_en or title_cn)[:200],
            "year": year,
            "region": region,
            "si_status": si_status,
            "candidate_level": level,
            "pollutant_families": families_str,
            "china_site": is_china,
            "estimated_sample_n": est_n,
            "has_hm": has_hm,
            "has_op": has_op,
            "has_compound": has_compound,
            "has_sample_level_table": "Unknown",  # 待 P2 精读
            "needs_si": bool(level in ("A", "B") and not si_present),
            "needs_digitization": (level == "B"),
            "is_strong_candidate": is_strong,
            "stem": stem,
            "reason": reason,
        }

        if is_strong:
            strong_hits.append(row)

        if level == "D":
            rows_rejected.append(row)
        else:
            rows_candidate.append(row)

    df_cand = pd.DataFrame(rows_candidate)
    df_rej = pd.DataFrame(rows_rejected)

    # 排序: A > B > C, 强候选优先
    level_order = {"A": 0, "B": 1, "C": 2}
    df_cand["_order"] = df_cand["candidate_level"].map(level_order).fillna(9)
    df_cand = df_cand.sort_values(["_order", "is_strong_candidate"], ascending=[True, False])
    df_cand = df_cand.drop(columns=["_order"])

    cand_path = OUT_DIR / "candidate_literature_op_hmop.csv"
    rej_path = OUT_DIR / "rejected_literature_log.csv"
    df_cand.to_csv(cand_path, index=False, encoding="utf-8-sig")
    df_rej.to_csv(rej_path, index=False, encoding="utf-8-sig")

    # ===== 统计报告 =====
    print(f"\n候选 (A/B/C): {len(df_cand)}")
    print(f"  A 级: {(df_cand['candidate_level']=='A').sum()}")
    print(f"  B 级: {(df_cand['candidate_level']=='B').sum()}")
    print(f"  C 级: {(df_cand['candidate_level']=='C').sum()}")
    print(f"rejected (D): {len(df_rej)}")

    print(f"\n复合信号命中 (has_compound): {(df_cand['has_compound']==True).sum() + (df_rej['has_compound']==True).sum()}")
    print(f"  其中 A+B 级: {((df_cand['candidate_level'].isin(['A','B'])) & (df_cand['has_compound']==True)).sum()}")

    print(f"\n裴总强候选命中: {len(strong_hits)}")
    for r in strong_hits:
        print(f"  [{r['candidate_level']}] {r['paper_id']} | {r['title'][:70]}")

    # OP 家族分布
    print("\nOP 家族分布 (A+B+C 候选):")
    fam_counts = {}
    for fams in df_cand["pollutant_families"]:
        for f in fams.split("|"):
            f = f.strip()
            if f:
                fam_counts[f] = fam_counts.get(f, 0) + 1
    for f, c in sorted(fam_counts.items(), key=lambda x: -x[1]):
        print(f"  {f}: {c}")

    print(f"\n输出:")
    print(f"  {cand_path}")
    print(f"  {rej_path}")


if __name__ == "__main__":
    main()
