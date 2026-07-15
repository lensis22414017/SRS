"""Clean铁律违规 + 省名标准化 (skill A1 + D3).

1. P01301: 删 province=Pakistan 行 (铁律#1 非中国点), 保留中国 C1-C5
2. 全CSV省名标准化: 中文省→英文拼音 (skill D3, 利于 province-group split)
   不动 "未指明(South China)" 等非标准标注 (留待人工)
"""
import csv
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = r"C:/Users/曾鸿/Desktop/SRS/outputs/literature_mining/manual_extract"

PROVINCE_MAP = {
    "内蒙古": "InnerMongolia", "山西": "Shanxi", "吉林": "Jilin",
    "四川": "Sichuan", "黑龙江": "Heilongjiang", "辽宁": "Liaoning",
    "广东": "Guangdong", "浙江": "Zhejiang", "甘肃": "Gansu",
    "北京": "Beijing", "河北": "Hebei", "山东": "Shandong",
    "江苏": "Jiangsu", "上海": "Shanghai", "天津": "Tianjin",
    "湖北": "Hubei", "湖南": "Hunan", "河南": "Henan",
    "福建": "Fujian", "安徽": "Anhui", "江西": "Jiangxi",
    "广西": "Guangxi", "海南": "Hainan", "重庆": "Chongqing",
    "贵州": "Guizhou", "云南": "Yunnan", "陕西": "Shaanxi",
    "青海": "Qinghai", "宁夏": "Ningxia", "新疆": "Xinjiang",
    "西藏": "Tibet", "台湾": "Taiwan", "香港": "HongKong", "澳门": "Macau",
}

# ---- 1. P01301 删 Pakistan ----
f = f"{BASE}/hm_op/P01301.csv"
rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
keep = [r for r in rows if "Pakistan" not in (r.get("province", "") or "")]
removed = len(rows) - len(keep)
if removed > 0 and keep:
    with open(f, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(keep)
    print(f"[P01301] {len(rows)}→{len(keep)}行, 删Pakistan {removed}行 (保留中国C1-C5: 广东贵屿/浙江台州)")
else:
    print(f"[P01301] 无Pakistan行或已清理 (现{len(rows)}行)")

# ---- 2. 全CSV省名标准化 ----
changed_files = 0
changed_cells = 0
province_counter = {}
for d in ["hm_op", "op_only"]:
    for f in glob.glob(f"{BASE}/{d}/*.csv"):
        try:
            rows = list(csv.DictReader(open(f, encoding="utf-8-sig")))
        except Exception:
            continue
        if not rows or "province" not in rows[0]:
            continue
        modified = False
        for r in rows:
            prov = (r.get("province", "") or "").strip()
            if prov in PROVINCE_MAP:
                new = PROVINCE_MAP[prov]
                province_counter[new] = province_counter.get(new, 0) + 1
                r["province"] = new
                changed_cells += 1
                modified = True
        if modified:
            with open(f, "w", encoding="utf-8-sig", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=rows[0].keys())
                w.writeheader()
                w.writerows(rows)
            changed_files += 1

print(f"\n[省名标准化] {changed_files} 文件 / {changed_cells} 单元格 中→英")
for prov, n in sorted(province_counter.items(), key=lambda x: -x[1]):
    print(f"  {prov}: {n}")
