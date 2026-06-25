#!/usr/bin/env python3
"""从 merged_std33,zh .xlsx 真实文献数据构建 RF 训练数据集。

用 GB15618-2018 农用地土壤污染风险筛选值(pH≤5.5 档)派生二分类标签:
  任一重金属 > 筛选值 → 标签1(污染风险), 否则标签0
阈值来源: 知识库 ThresholdRule(standard_source=GB15618-2018), 真实国标非编造。

产物: data/raw/真实训练集_GB15618.csv
  列: ID, DOI, Source, Year, 8重金属_mgkg, 标签, 超标因子数
用法: backend/.venv/bin/python scripts/build_real_dataset.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "data", "raw", "merged_std33,zh .xlsx")
OUT = os.path.join(ROOT, "data", "raw", "真实训练集_GB15618.csv")

# merged_std33 列名 → 因子名映射(8 种重金属, 真实检测值 mg/kg)
HM_COLS = {
    "Cd_mgkg": "镉", "Pb_mgkg": "铅", "As_mgkg": "砷", "Cu_mgkg": "铜",
    "Zn_mgkg": "锌", "Ni_mgkg": "镍", "Cr_mgkg": "铬", "Hg_mgkg": "汞",
}

# GB15618-2018 农用地筛选值(pH≤5.5 档, mg/kg) — 知识库真实国标值
GB15618_SCREENING = {
    "镉": 0.3, "铅": 80, "砷": 30, "铜": 150,
    "锌": 200, "镍": 60, "铬": 250, "汞": 0.5,
}


def build():
    print(f"读取真实数据: {SRC}")
    df = pd.read_excel(SRC, sheet_name="china")
    print(f"  原始: {len(df)} 行 × {len(df.columns)} 列")

    # 提取元信息 + 重金属列
    keep_meta = ["ID", "DOI", "Source", "Year"]
    meta_present = [c for c in keep_meta if c in df.columns]
    hm_present = {col: name for col, name in HM_COLS.items() if col in df.columns}
    print(f"  重金属列命中: {list(hm_present.keys())}")

    if not hm_present:
        raise RuntimeError("未找到重金属列, 检查 merged_std33 列名")

    sub = df[meta_present + list(hm_present.keys())].copy()
    # 重命名为中文因子名
    rename = {col: name for col, name in hm_present.items()}
    sub = sub.rename(columns=rename)

    # 强制数值转换: 重金属列可能含 "<0.01"(检出限)等非数值字符串
    # 用正则提取数值部分, 无法转换的置 NaN(后续中位数填充)
    import re
    hm_names = list(hm_present.values())
    for name in hm_names:
        if name in sub.columns:
            raw = sub[name].astype(str)
            # 提取数值(支持 <0.01 → 0.01, 1.2e-3 等)
            extracted = raw.str.extract(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)")[0]
            sub[name] = pd.to_numeric(extracted, errors="coerce")
    print(f"  重金属数值化完成, 各列有效值:")
    for name in hm_names:
        if name in sub.columns:
            print(f"    {name}: {sub[name].notna().sum()}/{len(sub)}")

    # 只保留至少有 1 个重金属有效值的行(剔除全空行)
    before = len(sub)
    sub = sub.dropna(subset=hm_names, how="all")
    print(f"  剔除重金属全空行: {before} → {len(sub)}")

    # 派生标签: 任一重金属 > GB15618 筛选值 → 1
    exceed_counts = pd.Series(0, index=sub.index, dtype=int)
    label = pd.Series(0, index=sub.index, dtype=int)
    for name in hm_names:
        thr = GB15618_SCREENING[name]
        val = pd.to_numeric(sub[name], errors="coerce")
        is_exceed = val > thr
        exceed_counts += is_exceed.astype(int)
        label = label | is_exceed.astype(int)

    sub["超标因子数"] = exceed_counts
    sub["标签"] = label.astype(int)

    print(f"  标签分布: {sub['标签'].value_counts().to_dict()}")
    print(f"  超标样本(标签1): {(sub['标签']==1).sum()} / {len(sub)} ({(sub['标签']==1).mean()*100:.1f}%)")

    # 数据真实性标记
    sub.attrs["is_real_data"] = True
    sub.attrs["label_source"] = "GB15618-2018 农用地筛选值(pH≤5.5)阈值派生"
    sub.attrs["source_file"] = "merged_std33,zh .xlsx"

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sub.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"\n✅ 真实训练集已生成: {OUT}")
    print(f"   {len(sub)} 行 × {len(sub.columns)} 列")
    print(f"   标签派生: GB15618-2018 任一重金属超筛选值→1")
    print(f"   含溯源列: {meta_present}")


if __name__ == "__main__":
    build()
