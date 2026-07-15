"""P7 Step 1: 整理两张训练用清洗表 (wide format, 对齐 SRS x_measured_* 命名)

裴总第一要求: "先把目前挖出来的整理成能训练用的两张表"

输出:
  train_table_op_only.csv  — op_only_ready 采样点 (纯 OP, 每点一行)
  train_table_hm_op.csv    — training_ready_hm_op (HM+OP 同点, 含 co_contamination 标签)

列设计 (对齐 SRS wide format + 老师建议 schema):
  sample_id, source_id (GroupKFold 分组键), paper_id, province, city_or_region,
  site_type, land_use, matrix_flag, evidence_level,
  x_measured_{HM/OP 浓度列},  # 对齐 SRS 规范名
  n_hm_obs, n_op_obs, op_families, hm_elements,
  co_contamination_type (仅 HM_OP 表),
  readiness, qa_flag
"""
from __future__ import annotations
import sys
import re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, HM_RAW, OP_RAW  # noqa: E402

import pandas as pd  # noqa: E402

# 省份/城市 → province (标题关键词提取)
PROVINCE_KW = {
    "浙江": ["浙江", "温岭", "台州", "杭州", "宁波", "温州", "Zhejiang", "Wenling", "Taizhou"],
    "广东": ["广东", "贵屿", "汕头", "广州", "深圳", "珠三角", "Guangdong", "Guiyu", "Shantou"],
    "江苏": ["江苏", "南京", "苏州", "无锡", "长三角", "Jiangsu", "Nanjing"],
    "辽宁": ["辽宁", "沈阳", "大连", "鞍山", "Liaoning", "Shenyang"],
    "上海": ["上海", "Shanghai"],
    "北京": ["北京", "Beijing"],
    "天津": ["天津", "Tianjin"],
    "重庆": ["重庆", "Chongqing"],
    "山东": ["山东", "济南", "青岛", "Shandong"],
    "河北": ["河北", "唐山", "石家庄", "Hebei"],
    "山西": ["山西", "太原", "Shanxi"],
    "湖南": ["湖南", "长沙", "株洲", "Hunan"],
    "湖北": ["湖北", "武汉", "Hubei"],
    "江西": ["江西", "南昌", "Jiangxi"],
    "安徽": ["安徽", "合肥", "Anhui"],
    "福建": ["福建", "福州", "厦门", "Fujian"],
    "四川": ["四川", "成都", "Sichuan"],
    "云南": ["云南", "昆明", "Yunnan"],
    "贵州": ["贵州", "贵阳", "Guizhou"],
    "陕西": ["陕西", "西安", "Shaanxi"],
    "黑龙江": ["黑龙江", "哈尔滨", "Heilongjiang"],
    "吉林": ["吉林", "长春", "Jilin"],
    "河南": ["河南", "郑州", "Henan"],
}


def extract_province(title: str) -> str:
    t = str(title)
    for prov, kws in PROVINCE_KW.items():
        if any(k in t for k in kws):
            return prov
    return ""


SITE_TYPE_KW = [
    ("coking", ["coking", "coke", "焦化", "steel", "钢铁"]),
    ("petrochemical", ["petrochemical", "oilfield", "oil field", "gas station", "石化", "油田", "加油站",
                        "petroleum", "石油烃"]),
    ("e_waste", ["e-waste", "e waste", "electronic waste", "电子垃圾", "电子废弃"]),
    ("mining", ["mine", "mining", "smelter", "矿区", "冶炼", "矿冶"]),
    ("agricultural", ["agricultural", "farmland", "paddy", "农田", "耕地", "农业", "agriculture"]),
    ("urban", ["urban", "city", "green space", "park", "roadside", "城市", "绿地", "交通"]),
    ("industrial", ["industrial", "factory", "plant", "工业", "厂区", "化工厂", "chemical industry"]),
]


def classify_site_type(title: str, land_use: str) -> str:
    t = (str(title) + " " + str(land_use)).lower()
    for label, kws in SITE_TYPE_KW:
        if any(k.lower() in t for k in kws):
            return label
    return "other"


def co_contamination_type(op_families: str) -> str:
    ops = set(str(op_families).split(","))
    if "PAHs" in ops:
        return "HM+PAHs"
    if "PCBs" in ops:
        return "HM+PCBs"
    if "OCPs" in ops:
        return "HM+OCPs"
    if "PBDEs" in ops:
        return "HM+PBDEs"
    if "TPH" in ops:
        return "HM+TPH"
    return "HM+multi-OP"


def build_wide(df_long: pd.DataFrame, site: pd.DataFrame, readiness_filter: str,
               pollutant_list: list, is_hm_op: bool, title_map: dict) -> pd.DataFrame:
    # 1. pivot 浓度到 wide (每 canonical 一行)
    sub = df_long[(df_long["readiness"] == readiness_filter) &
                  (df_long["pollutant_name_std"].isin(pollutant_list))].copy()
    sub["value_std"] = pd.to_numeric(sub["value_std"], errors="coerce")
    sub = sub[sub["value_std"].notna() & (sub["value_std"] >= 0)]
    if sub.empty:
        return pd.DataFrame()
    wide = sub.pivot_table(index="canonical_sample_id", columns="pollutant_name_std",
                           values="value_std", aggfunc="first").reset_index()
    wide.columns = ["sample_id" if c == "canonical_sample_id" else f"x_measured_{c}" for c in wide.columns]
    # 2. join site 汇总
    site_sub = site[site["readiness"] == readiness_filter][[
        "sample_id", "source_id", "paper_id", "site_name", "land_use", "province",
        "n_hm_obs", "n_op_obs", "hm_elements", "op_families",
        "matrix_flag", "evidence_level", "readiness", "qa_flag"]].copy()
    wide = wide.merge(site_sub, on="sample_id", how="left")
    # 3. 加 province (从标题) + site_type
    wide["province"] = wide["paper_id"].map(lambda pid: extract_province(title_map.get(pid, "")))
    wide["site_type"] = wide.apply(
        lambda r: classify_site_type(title_map.get(r["paper_id"], ""), r["land_use"]), axis=1)
    # 4. co_contamination (仅 HM_OP)
    if is_hm_op:
        wide["co_contamination_type"] = wide["op_families"].apply(co_contamination_type)
    return wide


def main():
    df = pd.read_csv(OUT_DIR / "extracted_observations_long_op_hmop.csv", dtype=str, keep_default_na=False)
    # site_dataset 优先读 v2 (P3 在原文件被 Excel 占用时写 v2)
    sd_path = OUT_DIR / "site_dataset_summary_op_hmop_v2.csv"
    if not sd_path.exists():
        sd_path = OUT_DIR / "site_dataset_summary_op_hmop.csv"
    site = pd.read_csv(sd_path, dtype=str, keep_default_na=False)
    cand = pd.read_csv(OUT_DIR / "candidate_literature_op_hmop.csv", dtype=str, keep_default_na=False)
    title_map = cand.set_index("paper_id")["title"].to_dict()

    ALL_POLLUTANTS = HM_RAW + OP_RAW

    # 表 1: OP-only
    op_wide = build_wide(df, site, "op_only_ready", OP_RAW, is_hm_op=False, title_map=title_map)
    op_out = OUT_DIR / "train_table_op_only.csv"
    op_wide.to_csv(op_out, index=False, encoding="utf-8-sig")

    # 表 2: HM+OP
    hmop_wide = build_wide(df, site, "training_ready_hm_op", ALL_POLLUTANTS, is_hm_op=True, title_map=title_map)
    hmop_out = OUT_DIR / "train_table_hm_op.csv"
    hmop_wide.to_csv(hmop_out, index=False, encoding="utf-8-sig")

    # 统计
    print(f"=== 两张训练表生成完成 ===\n")
    print(f"[表1] train_table_op_only.csv")
    print(f"  样本数 (行): {len(op_wide)}")
    print(f"  source_groups: {op_wide['source_id'].nunique() if len(op_wide) else 0}")
    print(f"  OP 浓度列: {[c for c in op_wide.columns if c.startswith('x_measured_')]}")
    if len(op_wide):
        filled = op_wide[[c for c in op_wide.columns if c.startswith('x_measured_')]].notna().sum()
        print(f"  各列有效值: {filled.to_dict()}")
        print(f"  site_type 分布: {op_wide['site_type'].value_counts().to_dict()}")
        print(f"  province 覆盖: {op_wide['province'].replace('', pd.NA).dropna().count()}/{len(op_wide)}")

    print(f"\n[表2] train_table_hm_op.csv")
    print(f"  样本数 (行): {len(hmop_wide)}")
    print(f"  source_groups: {hmop_wide['source_id'].nunique() if len(hmop_wide) else 0}")
    hm_cols = [c for c in hmop_wide.columns if c.startswith('x_measured_')]
    print(f"  浓度列 ({len(hm_cols)}): {hm_cols}")
    if len(hmop_wide):
        print(f"  co_contamination_type: {hmop_wide['co_contamination_type'].value_counts().to_dict()}")
        print(f"  site_type: {hmop_wide['site_type'].value_counts().to_dict()}")
        print(f"  matrix_flag: {hmop_wide['matrix_flag'].value_counts().to_dict()}")
        print(f"  province 覆盖: {hmop_wide['province'].replace('', pd.NA).dropna().count()}/{len(hmop_wide)}")

    print(f"\n输出:")
    print(f"  {op_out}")
    print(f"  {hmop_out}")
    print(f"\n注: province 从标题关键词提取 (粗粒度); site_type 按标题分类; "
          f"缺失浓度列=NaN (SRS 按missing处理). Step 2 深挖 C 级后 sample 数将显著增.")


if __name__ == "__main__":
    main()
