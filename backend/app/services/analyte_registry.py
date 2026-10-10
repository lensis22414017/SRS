"""v1.2.2(T02): 官方分析物身份登记 — 阈值只绑定到同一物质(名称/CAS/标准记录), 不以关键词相似性代替分析身份。

来源: data/standards/gb36600_2018_official.csv(生态环境部官网 PDF 逐行转录, 含 CAS)。
- exact_official(name): 规范化后的 **完整名称** 或 CAS 精确命中 → 官方记录; 子串/关键词不算命中。
- family_of(name): 名称属于某物质族(邻苯二甲酸酯、二甲苯、氯酚、二氯乙烷、二氯苯、有机氯农药、多环芳烃…)
  但不是官方单体名 → 返回族信息; 是否“族总量”由 is_total_label 判断。
  族总量只在存在“该总量本身”的官方限值时才可走正式阈值(如 GB 15618 六六六总量/滴滴涕总量,
  GB 36600 多氯联苯(总量)); 否则为 family_total(无总量限值, 不判定)。非总量的未知成员 → mapping_review_required。
"""
from __future__ import annotations

import csv
import os
import re
import unicodedata
from functools import lru_cache

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _std_path() -> str:
    try:
        from app.core.config import resource_root
        p = os.path.join(resource_root(), "data", "standards", "gb36600_2018_official.csv")
        if os.path.exists(p):
            return p
    except Exception:  # noqa: BLE001
        pass
    return os.path.join(_ROOT, "data", "standards", "gb36600_2018_official.csv")


def norm(s: str | None) -> str:
    """名称规范化: NFKC、去空白、统一括号/撇号/连字符; 只用于整名比较。"""
    if s is None:
        return ""
    t = unicodedata.normalize("NFKC", str(s)).strip().lower()
    t = t.replace("（", "(").replace("）", ")").replace("′", "'").replace("’", "'").replace("‘", "'")
    t = re.sub(r"\s+", "", t)
    t = t.replace("—", "-").replace("–", "-").replace("_", "")
    return t


def _loose(s: str) -> str:
    """同一名称的书写变体(连字符可有可无, 方括号/圆括号互换)。"""
    return norm(s).replace("-", "").replace("[", "(").replace("]", ")")


# 同一物质的常用写法(缩写/全称/英文), 只收录 **一对一** 的同物异名; 不收录族名。
SYNONYMS: dict[str, list[str]] = {
    # 注意: “邻苯二甲酸二异辛酯”(DIOP, CAS 27554-26-3)、“邻苯二甲酸二辛酯/正辛酯”(俗称有歧义) 不作为同物异名
    "邻苯二甲酸二(2-乙基己基)酯": ["DEHP", "邻苯二甲酸双(2-乙基己基)酯", "bis(2-ethylhexyl)phthalate",
                              "di(2-ethylhexyl)phthalate"],
    "邻苯二甲酸丁基苄酯": ["BBP", "邻苯二甲酸苄基丁酯", "邻苯二甲酸苄丁酯", "butylbenzylphthalate", "benzylbutylphthalate"],
    "邻苯二甲酸二正辛酯": ["DnOP", "DNOP", "di-n-octylphthalate"],
    "间-二甲苯+对-二甲苯": ["间二甲苯+对二甲苯", "间/对二甲苯", "间,对-二甲苯", "m,p-xylene", "m+p-xylene"],
    "邻-二甲苯": ["邻二甲苯", "o-xylene"],
    "苯并[a]芘": ["苯并芘", "苯并(a)芘", "BaP", "benzo[a]pyrene"],
    "石油烃(C10-C40)": ["石油烃(C10~C40)", "TPH(C10-C40)"],
    "多氯联苯(总量)": ["多氯联苯", "多氯联苯总量", "PCBs", "PCBs总量"],
    "铬（六价）": ["六价铬", "Cr(VI)", "Cr6+", "铬(六价)"],
}

# 物质族: 关键词 → (族编码, 族中文名)。仅用于识别“属于该族但不是官方单体”的情形。
FAMILIES: list[tuple[str, str, str]] = [
    ("邻苯二甲酸", "SumPAE_ugkg", "邻苯二甲酸酯类(PAEs)"), ("塑化剂", "SumPAE_ugkg", "邻苯二甲酸酯类(PAEs)"),
    ("paes", "SumPAE_ugkg", "邻苯二甲酸酯类(PAEs)"),
    ("二甲苯", "Xylenes_total", "二甲苯(异构体合计)"),
    ("氯酚", "Chlorophenols_family", "氯酚类"),
    ("二氯乙烷", "Dichloroethanes_family", "二氯乙烷类"), ("二氯乙烯", "Dichloroethylenes_family", "二氯乙烯类"),
    ("二氯苯", "Dichlorobenzenes_family", "二氯苯类"), ("三氯乙烷", "Trichloroethanes_family", "三氯乙烷类"),
    ("四氯乙烷", "Tetrachloroethanes_family", "四氯乙烷类"),
    ("有机氯", "SumOCP_ngg", "有机氯农药"),
    ("多环芳烃", "PAHs_total(族群)", "多环芳烃(PAHs)"), ("pahs", "PAHs_total(族群)", "多环芳烃(PAHs)"),
    ("多氯联苯", "SumPCB_ngg", "多氯联苯(PCBs)"), ("六六六", "SumHCHs_ngg", "六六六(HCHs)"),
    ("滴滴", "SumDDTs_ngg", "滴滴涕类(DDTs)"), ("二苯并", "Dibenzo_family", "二苯并类"),
    ("茚并", "Indeno_family", "茚并类"),
]

_TOTAL_RE = re.compile(r"(总量|总和|合计|总计|∑|σ|\bsum\b|\btotal\b|^sum|总\)|类$|类\(|族)")
# 习惯上以族名直接表示总量的写法(无单体限定词)
_BARE_FAMILY_TOTAL = {norm(x) for x in ("邻苯二甲酸酯", "邻苯二甲酸酯类", "PAEs", "塑化剂", "二甲苯", "多环芳烃", "PAHs",
                                         "多氯联苯", "六六六", "滴滴涕", "有机氯", "有机氯农药", "OCPs")}


@lru_cache(maxsize=1)
def _registry() -> tuple[dict, dict]:
    by_name, by_cas = {}, {}
    with open(_std_path(), encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            rec = {"official_name": r["pollutant"], "cas": r["cas"], "standard": "GB 36600-2018",
                   "table": r["table"], "item_no": r["item_no"], "unit": r["unit"]}
            for n in [r["pollutant"]] + SYNONYMS.get(r["pollutant"], []):
                by_name[norm(n)] = rec
                by_name.setdefault(_loose(n), rec)
            for c in re.split(r"[,，;/ ]+", r["cas"] or ""):
                if re.fullmatch(r"\d{2,7}-\d{2}-\d", c.strip()):
                    by_cas[c.strip()] = rec
    return by_name, by_cas


def official_names() -> set[str]:
    return {v["official_name"] for v in _registry()[0].values()}


def exact_official(name: str | None) -> dict | None:
    """整名或 CAS 精确命中 GB 36600 官方记录; 否则 None(不做子串/关键词匹配)。"""
    if not name:
        return None
    by_name, by_cas = _registry()
    k = norm(name)
    if k in by_name:
        return by_name[k]
    if _loose(name) in by_name:
        return by_name[_loose(name)]
    m = re.search(r"\b(\d{2,7}-\d{2}-\d)\b", str(name))
    if m and m.group(1) in by_cas:
        return by_cas[m.group(1)]
    return None


def is_total_label(name: str) -> bool:
    k = norm(name)
    return bool(_TOTAL_RE.search(k)) or k in _BARE_FAMILY_TOTAL


def family_of(name: str | None) -> dict | None:
    """名称含物质族关键词 → {family_code, family_name, identity}; identity ∈ family_total / mapping_review_required。"""
    if not name:
        return None
    k = norm(name)
    for kw, code, cn in FAMILIES:
        if norm(kw) in k:
            return {"family_code": code, "family_name": cn,
                    "identity": "family_total" if is_total_label(name) else "mapping_review_required"}
    return None
