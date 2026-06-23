"""从全国合并数据集 merged_std33 切分单场地测试数据集(可复跑)。

数据源: data/raw/merged_std33,zh .xlsx (41504 真实检测行 × 719 列, soil 项目)
切分维度: 省 × Pollution_Type(HM重金属/OP有机/HM+OP复合)
列处理: 提取 SRS 关心的真实检测因子(8 重金属 + pH + 有机质), 列名标准化为中文,
        匹配 SRS FactorDictionary; 有机质单位 %→g/kg(×10); 其余 700+ 列舍弃。
规模: 每切片抽样 ≤200 真实行(单场地可行规模), 保证有经纬度+重金属测值。
命名: site_{省}_{类型}_{n}点.xlsx

运行: cd backend && .venv/bin/python ../data/test_datasets/_generate_splits.py
"""
import os
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "data", "raw", "merged_std33,zh .xlsx")
OUT_DIR = os.path.join(ROOT, "data", "test_datasets")
os.makedirs(OUT_DIR, exist_ok=True)

PROV_MAP = {  # 统一中英文省份名
    "Guangdong": "广东", "Zhejiang": "浙江", "Beijing": "北京", "Jiangsu": "江苏",
    "Shandong": "山东", "Shanghai": "上海", "Tianjin": "天津", "Chongqing": "重庆",
    "Sichuan": "四川", "Hunan": "湖南", "Hubei": "湖北", "Henan": "河南",
    "Hebei": "河北", "Shanxi": "山西", "Jiangxi": "江西", "Fujian": "福建",
    "Anhui": "安徽", "Yunnan": "云南", "Guizhou": "贵州", "Guangxi": "广西",
    "Xinjiang": "新疆", "InnerMongolia": "内蒙古", "Heilongjiang": "黑龙江",
    "Jilin": "吉林", "Liaoning": "辽宁", "Gansu": "甘肃", "Qinghai": "青海",
    "Ningxia": "宁夏", "Shaanxi": "陕西", "Hainan": "海南", "Tibet": "西藏",
}

# 目标切片(省, 污染类型, 标签) — 覆盖重金属/复合, 系统全链路最支持
SLICES = [
    ("江西", "HM", "江西重金属(有色金属区)"),
    ("广东", "HM", "广东重金属(沿海工业)"),
    ("湖南", "HM", "湖南重金属(有色金属之乡)"),
    ("四川", "HM+OP", "四川复合污染"),
    ("新疆", "HM", "新疆重金属(干旱区)"),
]

HM_COLS = {  # SRS 关心的真实检测因子列映射(英文源列 → 中文标准列)
    "Cd_mgkg": "镉(mg/kg)", "Pb_mgkg": "铅(mg/kg)", "As_mgkg": "砷(mg/kg)",
    "Cr_mgkg": "铬(mg/kg)", "Hg_mgkg": "汞(mg/kg)", "Cu_mgkg": "铜(mg/kg)",
    "Zn_mgkg": "锌(mg/kg)", "Ni_mgkg": "镍(mg/kg)",
}


def main():
    print(f"读取 {SRC} ...")
    df = pd.read_excel(SRC)
    df["省"] = df["Province"].replace(PROV_MAP).fillna(df["Province"])
    print(f"总行数 {len(df)}; 有经纬度 {df['Latitude'].notna().sum()}")

    manifest = []
    for prov, ptype, label in SLICES:
        sub = df[(df["省"] == prov) & (df["Pollution_Type"] == ptype)].copy()
        sub = sub.dropna(subset=["Latitude", "Longitude"])
        # 至少有砷或镉测值(保证重金属可分析)
        sub = sub[sub["As_mgkg"].notna() | sub["Cd_mgkg"].notna()]
        if len(sub) < 30:
            print(f"  ⚠ {label}: 仅 {len(sub)} 行, 跳过"); continue
        if len(sub) > 200:
            sub = sub.sample(200, random_state=42)
        # 构造切片
        out = pd.DataFrame({
            "采样点编号": [f"{prov}-{ptype}-{i+1:03d}" for i in range(len(sub))],
            "经度": sub["Longitude"].values,
            "纬度": sub["Latitude"].values,
            "区域": (sub["省"] + "·" + sub["City"].fillna("")).values,
        })
        # pH(SoilPH 优先, 回退 pH)
        ph = sub["SoilpH"] if "SoilpH" in sub else sub.get("pH")
        out["pH"] = ph.fillna(sub.get("pH")).values if "pH" in sub else ph.values
        # 有机质 % → g/kg (×10), 不改值意义
        if "OC_pct" in sub:
            out["有机质(g/kg)"] = (sub["OC_pct"] * 10).values
        # 8 重金属(真实测值, mg/kg 直接用)
        for src, dst in HM_COLS.items():
            if src in sub:
                out[dst] = sub[src].values
        # 删全空列
        out = out.dropna(axis=1, how="all")
        fname = f"site_{prov}_{ptype}_{len(out)}点.xlsx"
        out.to_excel(os.path.join(OUT_DIR, fname), index=False)
        manifest.append((fname, label, len(out), ptype, prov,
                         int(out["砷(mg/kg)"].notna().sum()) if "砷(mg/kg)" in out else 0))
        print(f"  ✓ {fname}: {len(out)} 点 | 真实{label} | 砷有效 {manifest[-1][5]} 条")

    # 写清单
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write("# 全国数据集切分 — 单场地测试数据集\n\n")
        f.write("来源: `data/raw/merged_std33,zh .xlsx` (soil 项目 41504 真实检测行)\n")
        f.write("切分维度: 省 × Pollution_Type; 每切片 ≤200 真实行(单场地规模)\n")
        f.write("列: 8 重金属 + pH + 有机质(标准化中文, 匹配 SRS FactorDictionary)\n")
        f.write("生成: `_generate_splits.py` (可复跑, random_state=42)\n\n")
        f.write("| 文件 | 标签 | 点数 | 类型 | 省 | 砷有效 |\n|---|---|---|---|---|---|\n")
        for m in manifest:
            f.write(f"| {m[0]} | {m[1]} | {m[2]} | {m[3]} | {m[4]} | {m[5]} |\n")
    print(f"\n清单: {OUT_DIR}/README.md")


if __name__ == "__main__":
    main()
