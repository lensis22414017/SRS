"""数据导入: Excel/CSV 解析 + 字段映射。

解析层仅依赖 pandas, 不触 DB, 便于独立测试。
入库由 ingest_service 完成。
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

MAPPINGS_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "mappings"))


def load_mapping(mapping_id: str) -> dict:
    """按 mapping_id 或文件名加载映射配置。

    优先级:
    1. mapping_id 本身是绝对路径且存在 → 直接加载
    2. MAPPINGS_DIR/<mapping_id>.json → 标准映射目录
    抛出 FileNotFoundError 时包含绝对路径, 便于诊断。
    """
    # 如果本身是绝对或相对路径且存在
    path = mapping_id
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    # 标准映射目录
    candidate = os.path.join(MAPPINGS_DIR, mapping_id)
    if not candidate.endswith(".json"):
        candidate += ".json"
    if not os.path.exists(candidate):
        raise FileNotFoundError(
            f"映射配置文件不存在: {candidate}\n"
            f"（已检查目录: {MAPPINGS_DIR}，mapping_id={mapping_id}）"
        )
    with open(candidate, encoding="utf-8") as f:
        return json.load(f)


def list_mappings() -> list[tuple[str, dict]]:
    """枚举 MAPPINGS_DIR 下全部预设模板 [(mapping_id, mapping_dict)]。"""
    out: list[tuple[str, dict]] = []
    if not os.path.isdir(MAPPINGS_DIR):
        return out
    for fn in sorted(os.listdir(MAPPINGS_DIR)):
        if fn.endswith(".json"):
            try:
                with open(os.path.join(MAPPINGS_DIR, fn), encoding="utf-8") as f:
                    out.append((fn[:-5], json.load(f)))
            except Exception:  # noqa: BLE001
                continue
    return out


def _file_sheet_columns(path: str) -> dict[str, list[str]]:
    """返回 {sheet名: [列名]}; CSV 返回 {'__csv__': [...]}。仅读表头, 不读数据。"""
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path, nrows=0)
        return {"__csv__": [str(c).strip() for c in df.columns]}
    xl = pd.ExcelFile(path)
    out: dict[str, list[str]] = {}
    for s in xl.sheet_names:
        try:
            out[s] = [str(c).strip() for c in xl.parse(s, nrows=0).columns]
        except Exception:  # noqa: BLE001
            out[s] = []
    return out


def _score_mapping(mapping: dict, sheet_cols: dict[str, list[str]]) -> tuple[int, int]:
    """在文件最匹配的 sheet 上计分: (命中因子列数, 是否命中point_code 0/1)。"""
    factor_cols = [fc["column"] for fc in mapping.get("factor_columns", [])]
    pc = (mapping.get("point_columns") or {}).get("point_code")
    sheet = mapping.get("sheet")
    if sheet and sheet in sheet_cols:
        col_sets = [sheet_cols[sheet]]
    elif "__csv__" in sheet_cols:
        col_sets = [sheet_cols["__csv__"]]
    else:
        col_sets = list(sheet_cols.values())  # sheet 未指定: 取所有 sheet 最佳
    best = (0, 0)
    for cols in col_sets:
        cset = set(cols)
        fmatch = sum(1 for c in factor_cols if c in cset)
        pcmatch = 1 if pc and pc in cset else 0
        best = max(best, (fmatch, pcmatch))
    return best


# 从文件名/场地名推断省份(修复 smart_detect province=None 致覆盖省份=0, 问题7代码根因)
_PROVINCE_MAP = [("北京", "北京市"), ("天津", "天津市"), ("上海", "上海市"), ("重庆", "重庆市"),
    ("河北", "河北省"), ("山西", "山西省"), ("辽宁", "辽宁省"), ("吉林", "吉林省"), ("黑龙江", "黑龙江省"),
    ("江苏", "江苏省"), ("浙江", "浙江省"), ("安徽", "安徽省"), ("福建", "福建省"), ("江西", "江西省"),
    ("山东", "山东省"), ("河南", "河南省"), ("湖北", "湖北省"), ("湖南", "湖南省"), ("广东", "广东省"),
    ("海南", "海南省"), ("四川", "四川省"), ("贵州", "贵州省"), ("云南", "云南省"), ("陕西", "陕西省"),
    ("甘肃", "甘肃省"), ("青海", "青海省"), ("台湾", "台湾省"), ("内蒙古", "内蒙古自治区"),
    ("广西", "广西壮族自治区"), ("西藏", "西藏自治区"), ("宁夏", "宁夏回族自治区"),
    ("新疆", "新疆维吾尔自治区")]


def _infer_province_from_name(name: str) -> str | None:
    for k, v in _PROVINCE_MAP:
        if k in name:
            return v
    return None


def _matches_heavy_metal_token(col_lower: str) -> bool:
    """重金属因子列识别: token 边界匹配, 排除含 as/cd/pb 字母片段的普通词(brief 4.1)。

    允许命中: 英文元素符号 as/pb/cd/hg/cr/cu/zn/ni(前后非小写字母边界) +
              中文单字 砷铅镉汞铬铜锌镍
    不得命中: baseline(含as)/case(含as)/sample/class/ascend/discord 等普通词。
    旧实现用 `kw in col` substring, 'as' 会命中 baseline/case → 误判, 已废弃。
    """
    import re
    if re.search(r"(?<![a-z])(as|pb|cd|hg|cr|cu|zn|ni)(?![a-z])", col_lower):
        return True
    return any(ch in col_lower for ch in "砷铅镉汞铬铜锌镍")


def resolve_mapping_for_file(mapping_id: str, dest: str) -> tuple[str, dict, dict]:
    """统一映射解析: 单文件 /import 与批量 /import/batch 共用(brief 4.1)。

    v1.0.2(+ GPT 2.2): 完全删除预设模板框束。
      - 不再用 detect_mapping 匹配预设(已删除 mappings/*.json)
      - 全部走 smart_detect_and_map 启发式识别任意结构
      - site.name 用文件名, site_code 自动生成, pollution_type 按列内容判定
      - 低置信/缺必需字段 → mapping 仍返回, 但 detection_report.confidence<0.5 +
        warnings 非空, 上层据此转 review_required 引导 Wizard。
    返回 (used_id, mapping, detection_report)。detection_report 含:
      used_id / confidence / source / detected_sheet / point_code_column /
      longitude_column / latitude_column / factor_columns / warnings / template_scores。
    """
    is_auto = mapping_id in ("auto", "", "detect", None)
    if not is_auto:
        # v1.0.2: 预设模板已删除, 非 auto 的 mapping_id 一律回退到 smart
        # (保留参数兼容性, 但不再加载预设 JSON)
        pass
    # v1.0.2: 全部走 smart 通用识别
    used_id, mapping, _smart_detail = smart_detect_and_map(dest)
    pc = (mapping.get("point_columns") or {}).get("point_code")
    n_factors = len([fc for fc in mapping.get("factor_columns", []) if fc.get("factor_code")])
    warnings: list[str] = []
    confidence = 0.6
    if not pc:
        warnings.append("未识别到采样点编号列")
        confidence = 0.2
    if n_factors < 2:
        warnings.append(f"数值因子列过少({n_factors}), 不足以支撑分析")
        confidence = min(confidence, 0.3)
    report = {
        "used_id": used_id, "confidence": confidence, "source": "smart_auto",
        "detected_sheet": mapping.get("sheet"),
        "point_code_column": pc,
        "longitude_column": (mapping.get("point_columns") or {}).get("longitude"),
        "latitude_column": (mapping.get("point_columns") or {}).get("latitude"),
        "factor_columns": [fc.get("column") for fc in mapping.get("factor_columns", [])],
        "warnings": warnings, "template_scores": [],
    }
    return used_id, mapping, report


def detect_mapping(path: str) -> tuple[str | None, dict | None, list[dict]]:
    """按文件 sheet 名与列签名自动匹配最合适的预设模板。

    返回 (mapping_id, mapping_dict, 评分明细)。
    判定可靠: 命中 point_code 且匹配因子列 >= 4。否则返回 (None, None, 明细),
    由上层提示改用『自定义字段映射 Wizard』。指定 sheet 不存在的模板直接判 0,
    从根本上避免"南京文件被套用重金属模板"这类错配。
    """
    sheet_cols = _file_sheet_columns(path)
    detail: list[dict] = []
    best_id = best_mp = None
    best_key = (0, 0)  # (point_code命中, 因子匹配数)
    for mid, mp in list_mappings():
        if (mp.get("sheet") and mp["sheet"] not in sheet_cols
                and "__csv__" not in sheet_cols):
            detail.append({"mapping": mid, "factor_match": 0,
                           "point_code": False, "note": "目标sheet不存在"})
            continue
        fmatch, pcmatch = _score_mapping(mp, sheet_cols)
        detail.append({"mapping": mid, "factor_match": fmatch, "point_code": bool(pcmatch)})
        key = (pcmatch, fmatch)
        if key > best_key:
            best_key, best_id, best_mp = key, mid, mp
    if best_key[0] >= 1 and best_key[1] >= 4:
        # 防误判: heavy_metal 模板(yunnan_gejiu sheet=None+通用土壤因子)易成万能匹配器,
        # 任何"采样点编号+常规土壤因子(pH/有机质/氮磷钾)"数据都会被判 heavy_metal。
        # 校验: 命中 heavy_metal 模板时,文件必须真含重金属特征列,否则降级未识别→引导Wizard。
        if best_mp.get("site", {}).get("pollution_type") == "heavy_metal":
            _all_cols = {c.lower() for cols in sheet_cols.values() for c in cols}
            _has_hm = any(_matches_heavy_metal_token(col) for col in _all_cols)
            if not _has_hm:
                detail.append({"mapping": best_id, "factor_match": best_key[1],
                               "point_code": True,
                               "note": "仅命中通用土壤因子、无重金属特征列,降级未识别(防误判heavy_metal)"})
                return None, None, detail
        return best_id, best_mp, detail
    return None, None, detail



def smart_detect_and_map(path: str) -> tuple[str, dict, list[dict]]:
    """通用导入: 不依赖预设模板, 读取任意结构的污染场地数据文件,
    启发式识别字段(point_code/经纬度/数值因子/场地元信息)并构造标准 mapping。

    识别规则(覆盖中英文列名):
    - point_code: 列名含 编号|点号|点位|采样点|code|sample|点
    - longitude: 含 经度|经|lon|lng|东经
    - latitude:  含 纬度|纬|lat|北纬
    - 因子列: 数值型列(排除 point_code/坐标/时间/纯文本)
    - pollution_type: 因子列含重金属特征(Cd/Pb/As/Cr/Hg/Cu/Zn/Ni/镉铅砷铬汞铜锌镍)→heavy_metal;
                      含有机特征(PAH/OCP/石油/多环/农药/苯)→organic; 否则 composite
    返回 (mapping_id, mapping_dict, 字段识别明细)。始终返回有效 mapping(不报错), 由上层入库。
    """
    import re as _re
    import pandas as _pd

    detail: list[dict] = []
    # 读取: xlsx 取数值列最多的 sheet; csv 直接读
    sheet_name = None
    if str(path).lower().endswith((".xlsx", ".xls")):
        try:
            xls = _pd.ExcelFile(path)
            best_sheet, best_n = None, -1
            for sh in xls.sheet_names:
                try:
                    df = _pd.read_excel(path, sheet_name=sh, nrows=5)
                    n = df.select_dtypes(include="number").shape[1]
                    if n > best_n:
                        best_sheet, best_n = sh, n
                except Exception:
                    continue
            sheet_name = best_sheet
            df = _pd.read_excel(path, sheet_name=sheet_name) if sheet_name else _pd.DataFrame()
        except Exception as e:
            df = _pd.DataFrame(); detail.append({"note": f"xlsx读取失败:{e}"})
    else:
        try:
            df = _pd.read_csv(path)
        except Exception as e:
            df = _pd.DataFrame(); detail.append({"note": f"csv读取失败:{e}"})

    cols = [str(c) for c in df.columns]
    colset = {c.lower(): c for c in cols}

    def _find(patterns):
        for cl, c in colset.items():
            if any(p in cl for p in patterns):
                return c
        return None

    point_code = _find(["编号", "点号", "点位", "采样点", "code", "sample", "点号", "样点"])
    # 退化: 第一列若为字符串且唯一值多, 当作 point_code
    if point_code is None and cols:
        first = cols[0]
        try:
            if df[first].dtype == object and df[first].nunique() > len(df) * 0.5:
                point_code = first
        except Exception:
            pass
    longitude = _find(["经度", "经", "lon", "lng", "东经"])
    latitude = _find(["纬度", "纬", "lat", "北纬"])
    # v1.0.2(GPT 3a): 补充 region/depth/soil_type 元信息列识别
    # (删预设模板后 smart_detect 必须承担原本模板做的采样点元信息映射)
    region = _find(["区域", "分区", "地段", "位置", "region", "area", "zone"])
    depth_top = _find(["深度_上限", "深度上限", "上层深度", "上界", "depth_top", "top_depth"])
    depth_bottom = _find(["深度_下限", "深度下限", "下层深度", "下界", "depth_bottom", "bottom_depth"])
    soil_type = _find(["土壤类型", "土类", "土壤", "质地", "soil_type", "soil"])

    # 重金属识别改用 _matches_heavy_metal_token(token 边界匹配), 旧 _HM substring 已废弃(brief 4.1)
    _ORG = ("pah", "ocp", "石油", "多环", "农药", "苯", "菲", "芘", "pcb", "pbde")

    factor_columns = []
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    # 若数值列不足, 尝试把所有非元信息列转数值
    candidate_cols = numeric_cols or [c for c in cols if c not in (point_code, longitude, latitude)]
    # v1.0.2(GPT 2.6): 元数据黑名单 — 序号/经纬度/深度/上下限/筛选值/管制值等不得识别为污染因子
    _META_BLACKLIST = {
        "序号", "编号", "id", "no", "index", "行号",
        "经度", "纬度", "longitude", "latitude", "lng", "lat", "x", "y",
        "深度", "depth", "depth_top", "depth_bottom", "上层", "下层",
        "上限", "下限", "上限值", "下限值",
        "筛选值", "管制值", "标准值", "限值", "阈值",
        "备注", "说明", "remark", "note", "comment", "描述",
        "土壤类型", "质地", "soil_type", "land_use", "用地",
        "日期", "时间", "date", "time", "采样日期", "检测日期",
    }
    for c in candidate_cols:
        cl = str(c).lower()
        if c in (longitude, latitude):
            continue
        # v1.0.2: 跳过元数据列(GPT 2.6) — 支持包含匹配(如"深度_上限(cm)"含"上限")
        col_name_clean = _re.sub(r"[（(][^)）]*[)）]", "", str(c)).strip().lower()
        # 去除下划线分隔, 得到核心词(深度_上限 → 上限)
        col_core = col_name_clean.split("_")[-1] if "_" in col_name_clean else col_name_clean
        if (cl in _META_BLACKLIST or col_name_clean in _META_BLACKLIST
                or col_core in _META_BLACKLIST
                or any(kw in col_name_clean for kw in ("上限", "下限", "经度", "纬度", "深度", "序号"))):
            continue
        raw = str(c)
        # 提取单位 (xxx)
        m = _re.search(r"[（(]([^)）]*)[)）]", raw)
        unit = m.group(1) if m else None
        name = _re.sub(r"[（(][^)）]*[)）]", "", raw).strip()
        # v1.0.2(GPT 3a): 因子名取下划线前的中文部分(如"铜_Cu"→"铜"),
        # 与知识库/阈值/评价系统的中文因子命名规范一致; 无下划线时取整体
        name = name.split("_")[0].strip() if "_" in name else name
        is_hm = _matches_heavy_metal_token(cl)
        is_org = any(k in cl for k in _ORG)
        if is_hm:
            cat, ftype, ptype_contrib = "环境指标", "pollutant", "hm"
        elif is_org:
            cat, ftype, ptype_contrib = "环境指标", "pollutant", "org"
        elif "ph" == cl.replace("值", ""):
            cat, ftype, ptype_contrib = "化学性质", "chemical", ""
        elif any(k in cl for k in ("有机质", "有机碳", "碳", "氮", "磷", "钾")):
            cat, ftype, ptype_contrib = "肥力指标", "fertility", ""
        else:
            cat, ftype, ptype_contrib = "其他指标", "other", ""
        factor_columns.append({
            "column": raw, "factor_code": name, "factor_name": name,
            "level1_category": cat, "factor_type": ftype, "unit": unit, "in_kb": False,
        })
        detail.append({"factor": raw, "category": cat, "type": ftype})

    # R3 审计第七类 7.3: 污染类型按有效非空实测值判定(不是仅看列名)
    # has_hm/has_org 要求: 列名匹配 AND 至少 1 个有效非空数值
    def _col_has_valid_values(col_name: str) -> bool:
        """检查列是否有至少 1 个有效非空数值。"""
        if col_name not in df.columns:
            return False
        try:
            valid = pd.to_numeric(df[col_name], errors="coerce").dropna()
            return len(valid) >= 1
        except Exception:
            return False

    def _col_valid_count(col_name: str) -> int:
        """返回列中有效非空数值的总数（用于比较 HM/ORG 强度）。"""
        if col_name not in df.columns:
            return 0
        try:
            valid = pd.to_numeric(df[col_name], errors="coerce").dropna()
            return len(valid)
        except Exception:
            return 0

    has_hm = (any(d.get("type") == "pollutant" and d.get("category") == "环境指标" for d in detail)
              and any(_matches_heavy_metal_token(str(fc.get("column","")).lower()) and _col_has_valid_values(fc.get("column",""))
                      for fc in factor_columns))
    has_org = any(any(k in str(fc.get("column","")).lower() for k in _ORG) and _col_has_valid_values(fc.get("column",""))
                  for fc in factor_columns)

    # Round10: 纯数据驱动判定
    # 只有重金属 → heavy_metal | 只有有机物 → organic | 两者都有 → composite | 都没有 → unknown
    if has_hm and has_org:
        pollution_type = "composite"
    elif has_hm:
        pollution_type = "heavy_metal"
    elif has_org:
        pollution_type = "organic"
    else:
        pollution_type = "unknown"

    import os as _os
    import time as _time
    import random as _random
    site_name = _os.path.splitext(_os.path.basename(path))[0]
    # v1.0.2: site_code 加时间戳+随机后缀, 保证每次导入唯一(GPT 2.3 不共用场地身份)
    ts = _time.strftime("%Y%m%d%H%M%S")
    rand_suffix = f"{_random.randint(1000, 9999)}"
    unique_code = f"AUTO-{ts}-{rand_suffix}"
    # Round10: 优先从Excel列读取province（如demo_sites文件含"省份"列）
    detected_province = None
    for col in df.columns:
        if str(col).strip() in ("省份", "province", "Province", "省"):
            vals = df[col].dropna().unique()
            if len(vals) > 0:
                from collections import Counter
                cnt = Counter(str(v) for v in vals)
                detected_province = cnt.most_common(1)[0][0]
            break
    if not detected_province:
        detected_province = _infer_province_from_name(site_name)
    # 标准化省份名（去掉"省""市""自治区"后缀）
    prov_clean = str(detected_province or "")
    for suffix in ["省", "市", "自治区", "壮族自治区", "回族自治区", "维吾尔自治区"]:
        if prov_clean.endswith(suffix):
            prov_clean = prov_clean[:-len(suffix)]
            break
    if not prov_clean:
        prov_clean = None
    mapping = {
        "mapping_id": "smart_auto",
        "description": f"通用智能识别(自动生成): {site_name}",
        "sheet": sheet_name,
        "header_row": 1,
        "site": {
            # v1.0.2: site_code 唯一(时间戳+随机), 避免同文件名多次导入合并到同一场地
            "site_code": unique_code,
            "name": site_name,
            "pollution_type": pollution_type,
            "province": prov_clean, "city": None,
            "land_use_type": None, "sampled_at": None,
        },
        "point_columns": {
            "point_code": point_code, "longitude": longitude, "latitude": latitude,
            "region": region, "depth_top_cm": depth_top, "depth_bottom_cm": depth_bottom,
            "soil_type": soil_type, "remark": None,
        },
        "factor_columns": factor_columns,
        "required_point_fields": [point_code] if point_code else [],
        "required_factors": [fc["factor_code"] for fc in factor_columns[:5]],
        "_smart_generated": True,
    }
    return "smart_auto", mapping, detail

@dataclass
class ParsedMeasurement:
    factor_code: str
    factor_name: str
    value: float | None
    unit: str | None
    level1_category: str | None = None
    factor_type: str | None = None
    in_kb: bool = True
    # v0.2 P0-1: 检测限解析
    original_value_text: str | None = None  # 导入原始文本, 如 "<0.001"
    qualifier: str | None = None            # '<' / '>' / '=' / 'ND'
    detection_limit: float | None = None    # 检出限数值
    method: str | None = None               # 检测方法
    is_below_detection: bool = False        # 是否低于检出限
    # v1.0 P1-1: 监管级数据契约
    replicate_group_id: str | None = None   # 平行样分组标识


@dataclass
class ParsedPoint:
    point_code: str
    longitude: float | None = None
    latitude: float | None = None
    region: str | None = None
    depth_top_cm: float | None = None
    depth_bottom_cm: float | None = None
    soil_type: str | None = None
    remark: str | None = None
    measurements: list[ParsedMeasurement] = field(default_factory=list)


@dataclass
class ParsedSite:
    site: dict
    points: list[ParsedPoint]
    factor_defs: list[dict]
    source_file: str

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def n_measurements(self) -> int:
        return sum(len(p.measurements) for p in self.points)


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# v0.2 P0-1: 检测限解析 — 识别 <0.001, ND, 未检出, <=0.01 等
import re as _re

_DETECTION_LIMIT_PATTERNS = [
    # "<=0.01", "≤0.01", "<0.001", "< 0.5"
    (_re.compile(r'^[<≤]=?\s*([0-9.]+)\s*$'), '<'),
    # ">=50", "≥50", ">100"
    (_re.compile(r'^[>≥]=?\s*([0-9.]+)\s*$'), '>'),
    # "ND", "nd", "N.D.", "n.d."
    (_re.compile(r'^(ND|nd|N\.?D\.?|n\.?d\.?)$'), 'ND'),
    # "未检出", "检出限以下", "低于检出限", "低于检测限", "未达到检出限"
    (_re.compile(r'^(未检出|检出限以下|低于检出限|低于检测限|未达到检出限)$'), 'ND'),
    # "/" 或 "-" 或 "—" 表示无数据
    (_re.compile(r'^[—\-–/]+$'), None),
]

def _parse_detection_limit(raw: str) -> dict:
    """解析检测限标记。返回 {value, qualifier, detection_limit, is_below_detection, original_value_text}。"""
    result = {
        "value": None,
        "qualifier": None,
        "detection_limit": None,
        "is_below_detection": False,
        "original_value_text": raw,
    }
    if not raw:
        return result

    stripped = raw.strip()
    if not stripped:
        return result

    for pattern, qualifier in _DETECTION_LIMIT_PATTERNS:
        m = pattern.match(stripped)
        if m:
            if qualifier == 'ND':
                result["qualifier"] = 'ND'
                result["is_below_detection"] = True
                result["value"] = None  # ND 无法量化
                return result
            elif qualifier == '<':
                result["qualifier"] = '<'
                result["detection_limit"] = float(m.group(1))
                result["is_below_detection"] = True
                # 保守原则: 取检出限的一半
                result["value"] = result["detection_limit"] / 2.0
                return result
            elif qualifier == '>':
                result["qualifier"] = '>'
                result["detection_limit"] = float(m.group(1))
                result["value"] = result["detection_limit"]
                return result
            elif qualifier is None:
                # "/" 或 "-" 表示无数据
                result["value"] = None
                return result

    # 无匹配 → 尝试直接转浮点数
    try:
        result["value"] = float(stripped)
    except (TypeError, ValueError):
        result["value"] = None
    return result


def _to_str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    s = str(v).strip()
    return s or None


def read_table(path: str, mapping: dict) -> pd.DataFrame:
    sheet = mapping.get("sheet")
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path, sheet_name=sheet if sheet else 0)


def parse(path: str, mapping: dict) -> ParsedSite:
    df = read_table(path, mapping)
    df.columns = [str(c).strip() for c in df.columns]

    pc = mapping["point_columns"]
    factor_cols = mapping["factor_columns"]
    points: list[ParsedPoint] = []
    lons, lats = [], []

    for _, row in df.iterrows():
        pcode = _to_str(row.get(pc["point_code"])) if pc.get("point_code") in df.columns else None
        if not pcode:
            continue
        lon = _to_float(row.get(pc.get("longitude"))) if pc.get("longitude") in df.columns else None
        lat = _to_float(row.get(pc.get("latitude"))) if pc.get("latitude") in df.columns else None
        if lon is not None:
            lons.append(lon)
        if lat is not None:
            lats.append(lat)
        p = ParsedPoint(
            point_code=pcode,
            longitude=lon,
            latitude=lat,
            region=_to_str(row.get(pc.get("region"))) if pc.get("region") in df.columns else None,
            depth_top_cm=_to_float(row.get(pc.get("depth_top_cm"))) if pc.get("depth_top_cm") in df.columns else None,
            depth_bottom_cm=_to_float(row.get(pc.get("depth_bottom_cm"))) if pc.get("depth_bottom_cm") in df.columns else None,
            soil_type=_to_str(row.get(pc.get("soil_type"))) if pc.get("soil_type") in df.columns else None,
            remark=_to_str(row.get(pc.get("remark"))) if pc.get("remark") in df.columns else None,
        )
        for fc in factor_cols:
            col = fc["column"]
            if col not in df.columns:
                continue
            raw_val = row.get(col)
            raw_text = str(raw_val).strip() if raw_val is not None else None
            # v0.2 P0-1: 检测限解析
            dl = _parse_detection_limit(raw_text) if raw_text else {"value": None}
            p.measurements.append(ParsedMeasurement(
                factor_code=fc["factor_code"],
                factor_name=fc.get("factor_name", fc["factor_code"]),
                value=dl.get("value") if dl.get("value") is not None else _to_float(raw_val),
                unit=fc.get("unit"),
                level1_category=fc.get("level1_category"),
                factor_type=fc.get("factor_type"),
                in_kb=fc.get("in_kb", True),
                original_value_text=raw_text,
                qualifier=dl.get("qualifier"),
                detection_limit=dl.get("detection_limit"),
                method=fc.get("method"),
                is_below_detection=dl.get("is_below_detection", False),
            ))
        points.append(p)

    site = dict(mapping.get("site", {}))
    if lons and lats and site.get("longitude") is None:
        site["longitude"] = round(sum(lons) / len(lons), 6)
        site["latitude"] = round(sum(lats) / len(lats), 6)

    factor_defs = [{
        "factor_code": fc["factor_code"],
        "factor_name": fc.get("factor_name", fc["factor_code"]),
        "level1_category": fc.get("level1_category"),
        "factor_type": fc.get("factor_type"),
        "default_unit": fc.get("unit"),
        "in_kb": fc.get("in_kb", True),
    } for fc in factor_cols]

    return ParsedSite(site=site, points=points, factor_defs=factor_defs,
                      source_file=os.path.basename(path))
