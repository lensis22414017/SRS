"""从全国合并数据集 merged_std33 切分单场地测试数据集(可复跑, v2 扩展OP/复合)。

数据源: data/raw/merged_std33,zh .xlsx (41504 真实检测行 × 719 列)
三类切片:
  HM  重金属: 8 重金属 + pH + 有机质
  OP  有机:   5 有机因子(PAH/BaP/OCP/DDT/PCB) + pH + 有机质
  HMOP 复合:  8 重金属 + 5 有机因子 + pH + 有机质
规模: 每切片 ≤200 真实行(有经纬度 + 对应有测值), random_state=42 可复现。
命名: site_{省}_{类型}_{n}点.xlsx

运行: cd backend && .venv/bin/python ../data/test_datasets/_generate_splits.py
"""
import os
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "data", "raw", "merged_std33,zh .xlsx")
OUT_DIR = os.path.join(ROOT, "data", "test_datasets")
os.makedirs(OUT_DIR, exist_ok=True)

PROV_MAP = {
    "Guangdong": "广东", "Zhejiang": "浙江", "Beijing": "北京", "Jiangsu": "江苏",
    "Shandong": "山东", "Shanghai": "上海", "Tianjin": "天津", "Chongqing": "重庆",
    "Sichuan": "四川", "Hunan": "湖南", "Hubei": "湖北", "Henan": "河南",
    "Hebei": "河北", "Shanxi": "山西", "Jiangxi": "江西", "Fujian": "福建",
    "Anhui": "安徽", "Yunnan": "云南", "Guizhou": "贵州", "Guangxi": "广西",
    "Xinjiang": "新疆", "Inner Mongolia": "内蒙古", "InnerMongolia": "内蒙古",
    "Heilongjiang": "黑龙江", "Jilin": "吉林", "Liaoning": "辽宁", "Gansu": "甘肃",
    "Qinghai": "青海", "Ningxia": "宁夏", "Shaanxi": "陕西", "Hainan": "海南", "Tibet": "西藏",
}

# (省, 命名类型, 标签, 列集) — 4 HM + 5 OP + 5 HMOP = 14 真实切片
SLICES = [
    # HM 重金属
    ("江西", "HM", "江西重金属(有色金属区)", "HM"),
    ("广东", "HM", "广东重金属(沿海工业)", "HM"),
    ("湖南", "HM", "湖南重金属(有色金属之乡)", "HM"),
    ("新疆", "HM", "新疆重金属(干旱区)", "HM"),
    # OP 有机(取 OP/PAH/OCP 类)
    ("北京", "OP", "北京有机污染(PAH为主)", "OP"),
    ("广东", "OP", "广东有机污染(工业)", "OP"),
    ("山东", "OP", "山东有机污染", "OP"),
    ("江苏", "OP", "江苏有机污染", "OP"),
    ("浙江", "OP", "浙江有机污染", "OP"),
    # HM+OP 复合(候选7省, 因复合数据稀疏取≥15点)
    ("广东", "HM+OP", "广东复合污染", "HMOP"),
    ("江苏", "HM+OP", "江苏复合污染", "HMOP"),
    ("浙江", "HM+OP", "浙江复合污染", "HMOP"),
    ("辽宁", "HM+OP", "辽宁复合污染", "HMOP"),
    ("山西", "HM+OP", "山西复合污染", "HMOP"),
    ("山东", "HM+OP", "山东复合污染", "HMOP"),
    ("海南", "HM+OP", "海南复合污染", "HMOP"),
]

HM_COLS = {  # 重金属(英文源列 → 中文标准列)
    "Cd_mgkg": "镉(mg/kg)", "Pb_mgkg": "铅(mg/kg)", "As_mgkg": "砷(mg/kg)",
    "Cr_mgkg": "铬(mg/kg)", "Hg_mgkg": "汞(mg/kg)", "Cu_mgkg": "铜(mg/kg)",
    "Zn_mgkg": "锌(mg/kg)", "Ni_mgkg": "镍(mg/kg)",
}
ORG_COLS = {  # 有机污染物(英文源列 → 中文, 单位 ng/g 原样保留)
    "Sum_PAH_ngg": "多环芳烃总量(ng/g)", "BaP_ngg": "苯并芘(ng/g)",
    "SumOCP_ngg": "有机氯农药(ng/g)", "SumDDTs_ngg": "DDT类(ng/g)",
    "SumPCB_ngg": "多氯联苯(ng/g)",
}
OP_TYPE_SET = {"OP", "PAH", "OCP", "PAH+OCP"}  # 有机污染统称


def pick_cols(out, sub, colmap):
    for src, dst in colmap.items():
        if src in sub:
            out[dst] = sub[src].values


def main():
    print(f"读取 {SRC} ...")
    df = pd.read_excel(SRC)
    df = df.copy()  # 去 fragmented 警告
    df["省"] = df["Province"].replace(PROV_MAP).fillna(df["Province"])
    print(f"总行数 {len(df)}; 有经纬度 {df['Latitude'].notna().sum()}")

    manifest = []
    for prov, label_type, label, col_set in SLICES:
        # 按 Pollution_Type 过滤
        if col_set == "OP":
            sub = df[(df["省"] == prov) & (df["Pollution_Type"].isin(OP_TYPE_SET))].copy()
        elif col_set == "HMOP":
            sub = df[(df["省"] == prov) & (df["Pollution_Type"] == "HM+OP")].copy()
        else:  # HM
            sub = df[(df["省"] == prov) & (df["Pollution_Type"] == "HM")].copy()
        sub = sub.dropna(subset=["Latitude", "Longitude"])
        # 按列集要求有对应测值
        if col_set == "OP":
            req = [c for c in ORG_COLS if c in sub]
            sub = sub[sub[req].notna().any(axis=1)] if req else sub.iloc[0:0]
        elif col_set == "HMOP":
            req_h = [c for c in HM_COLS if c in sub]
            req_o = [c for c in ORG_COLS if c in sub]
            # 复合场地数据稀疏(每行可能只测部分因子), 放宽: 重金属 或 有机 任一有值即可
            sub = sub[sub[req_h].notna().any(axis=1) | sub[req_o].notna().any(axis=1)]
        else:
            req = [c for c in HM_COLS if c in sub]
            sub = sub[sub["As_mgkg"].notna() | sub["Cd_mgkg"].notna()] if "As_mgkg" in sub else sub
        if len(sub) < 15:
            print(f"  ⚠ {label}: 仅 {len(sub)} 行, 跳过"); continue
        if len(sub) > 200:
            sub = sub.sample(200, random_state=42)
        out = pd.DataFrame({
            "采样点编号": [f"{prov}-{label_type}-{i+1:03d}" for i in range(len(sub))],
            "经度": sub["Longitude"].values, "纬度": sub["Latitude"].values,
            "区域": (sub["省"] + "·" + sub["City"].fillna("")).values,
        })
        ph = sub["SoilpH"] if "SoilpH" in sub else sub.get("pH")
        out["pH"] = ph.fillna(sub.get("pH")).values if "pH" in sub else ph.values
        if "OC_pct" in sub:
            out["有机质(g/kg)"] = (sub["OC_pct"] * 10).values
        if col_set in ("HM", "HMOP"):
            pick_cols(out, sub, HM_COLS)
        if col_set in ("OP", "HMOP"):
            pick_cols(out, sub, ORG_COLS)
        out = out.dropna(axis=1, how="all")
        fname = f"site_{prov}_{label_type}_{len(out)}点.xlsx"
        out.to_excel(os.path.join(OUT_DIR, fname), index=False)
        manifest.append((fname, label, len(out), label_type, prov, col_set))
        print(f"  ✓ {fname}: {len(out)} 点 | 真实{label} | 列{len(out.columns)}")

    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write("# 全国数据集切分 — 单场地测试数据集\n\n")
        f.write("来源: `data/raw/merged_std33,zh .xlsx` (soil 项目 41504 真实检测行)\n")
        f.write("切分: 省 × Pollution_Type; 每切片 ≤200 真实行(random_state=42)\n")
        f.write("三类: HM(重金属) / OP(有机) / HMOP(复合=重金属+有机)\n\n")
        f.write("| 文件 | 标签 | 点数 | 类型 | 省 | 列集 |\n|---|---|---|---|---|---|\n")
        for m in manifest:
            f.write(f"| {m[0]} | {m[1]} | {m[2]} | {m[3]} | {m[4]} | {m[5]} |\n")
    print(f"\n清单: {OUT_DIR}/README.md  |  共 {len(manifest)} 切片")


if __name__ == "__main__":
    main()
