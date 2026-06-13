"""字段标准化: 省份(中/英混杂)→标准省→9大区; LandUse/污染类型/单位归一。

纯 python, 可独立测试。未识别值归 Unknown, 不臆造、不丢弃(保留原值另存)。
"""
from __future__ import annotations

# 英文省名 -> 中文标准省
_EN2CN = {
    "guangdong": "广东", "zhejiang": "浙江", "jiangsu": "江苏", "beijing": "北京",
    "shandong": "山东", "liaoning": "辽宁", "hunan": "湖南", "hubei": "湖北",
    "henan": "河南", "sichuan": "四川", "jiangxi": "江西", "xinjiang": "新疆",
    "shaanxi": "陕西", "shanxi": "山西", "gansu": "甘肃", "ningxia": "宁夏",
    "hebei": "河北", "tianjin": "天津", "shanghai": "上海", "anhui": "安徽",
    "heilongjiang": "黑龙江", "jilin": "吉林", "neimenggu": "内蒙古",
    "inner mongolia": "内蒙古", "chongqing": "重庆", "yunnan": "云南",
    "guizhou": "贵州", "guangxi": "广西", "fujian": "福建", "hainan": "海南",
    "qinghai": "青海", "tibet": "西藏", "xizang": "西藏",
    "hong kong": "香港", "macau": "澳门", "taiwan": "台湾",
}

# 标准省 -> 9 大区(与 benchmark_50sites_design 一致)
_PROV2REGION = {
    "西藏": "青藏高原区", "青海": "青藏高原区",
    "陕西": "黄土高原/黄河中上游区", "山西": "黄土高原/黄河中上游区",
    "甘肃": "黄土高原/黄河中上游区", "宁夏": "黄土高原/黄河中上游区",
    "河南": "黄淮海/黄河平原区", "山东": "黄淮海/黄河平原区",
    "河北": "黄淮海/黄河平原区", "天津": "黄淮海/黄河平原区",
    "江苏": "长江中下游区", "浙江": "长江中下游区", "安徽": "长江中下游区",
    "江西": "长江中下游区", "湖北": "长江中下游区", "湖南": "长江中下游区",
    "上海": "长江中下游区",
    "黑龙江": "东北平原区", "吉林": "东北平原区", "辽宁": "东北平原区",
    "北京": "华北城市群区", "内蒙古": "华北城市群区",
    "新疆": "西北干旱绿洲区",
    "四川": "西南山地/云贵川区", "重庆": "西南山地/云贵川区",
    "云南": "西南山地/云贵川区", "贵州": "西南山地/云贵川区",
    "广东": "华南/东南沿海区", "广西": "华南/东南沿海区",
    "福建": "华南/东南沿海区", "海南": "华南/东南沿海区",
    "香港": "华南/东南沿海区", "澳门": "华南/东南沿海区", "台湾": "华南/东南沿海区",
}

_CN_PROVS = list(_PROV2REGION.keys())

# LandUse 关键词 -> 标准 5 类
_LANDUSE_RULES = [
    ("农用地", ["农", "耕", "farm", "agricul", "paddy", "园", "cropland", "orchard", "茶", "猕猴桃", "菜", "果"]),
    ("工矿用地", ["矿", "mining", "mine", "industr", "工", "冶炼", "smelt", "厂"]),
    ("建设用地", ["建设", "urban", "城", "residential", "居", "construct", "市政"]),
    ("生态用地", ["林", "forest", "草", "grass", "湿地", "wetland", "生态", "绿地", "水源", "river", "sediment", "park"]),
]


def normalize_province(raw) -> str:
    if raw is None:
        return "Unknown"
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", "未标注", "未知"):
        return "Unknown"
    low = s.lower().replace(" province", "").strip()
    if low in _EN2CN:
        return _EN2CN[low]
    for cn in _CN_PROVS:
        if cn in s:
            return cn
    return "Unknown"


def province_to_region(std_prov: str) -> str:
    return _PROV2REGION.get(std_prov, "Unknown")


def normalize_region(raw) -> str:
    return province_to_region(normalize_province(raw))


def normalize_landuse(raw) -> str:
    if raw is None:
        return "Unknown"
    s = str(raw).strip().lower()
    if not s or s in ("nan", "none", "未标注", "未知", "其他用地", "其他", "other"):
        return "其他/未标注" if s else "Unknown"
    for label, kws in _LANDUSE_RULES:
        if any(k in s for k in kws):
            return label
    return "其他/未标注"


def normalize_pollution_type(raw) -> str:
    """污染类型归一为 HM / OP / HM+OP / Unknown。"""
    if raw is None:
        return "Unknown"
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", "未知", "未标注"):
        return "Unknown"
    low = s.lower()
    composite_markers = ["hm+op", "hm/op", "composite", "复合", "重金属-有机", "重金属+有机"]
    if any(m in low for m in composite_markers):
        return "HM+OP"
    if any(m in low for m in ["hm", "heavy", "metal", "重金属", "矿冶"]):
        return "HM"
    op_markers = ["op", "organic", "pah", "ocp", "pcb", "pfas", "tph", "btex", "有机"]
    if any(m in low for m in op_markers):
        return "OP"
    return "Unknown"


def normalize_unit(raw) -> str:
    """常见土壤浓度单位归一。仅标准化写法, 不在这里做数值换算。"""
    if raw is None:
        return "Unknown"
    s = str(raw).strip()
    if not s or s.lower() in ("nan", "none", "未知"):
        return "Unknown"
    low = (s.lower().replace("μ", "u").replace("µ", "u")
           .replace(" ", "").replace("·", "").replace("_", ""))
    low = low.replace("kg-1", "/kg").replace("g-1", "/g")
    aliases = {
        "mg/kg": "mg/kg", "mgkg": "mg/kg", "mg/kgdw": "mg/kg",
        "mgkgdw": "mg/kg", "mg/kgdryweight": "mg/kg",
        "ng/g": "ng/g", "ngg": "ng/g", "ng/gdw": "ng/g",
        "ug/kg": "ug/kg", "μg/kg": "ug/kg", "ugkg": "ug/kg",
        "g/kg": "g/kg", "gkg": "g/kg",
        "%": "%",
        "cmol/kg": "cmol/kg", "cmolkg": "cmol/kg", "cmol(+)/kg": "cmol/kg",
    }
    return aliases.get(low, s)
