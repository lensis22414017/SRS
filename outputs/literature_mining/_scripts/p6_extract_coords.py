"""P6 前置: 从 paper.md 扫描经纬度 (GEE 采样的前提)

扫描 candidate A/B 论文的 paper.md + metadata.json, 提取研究区坐标.
输出 site_coordinates.csv (paper_id, lat, lon, coord_source, region).

GEE 采样策略:
  - 有场地中心坐标 → GEE 提取 16 协变量 (soc/cec/ndvi/precip/temp/elevation/clay 等)
  - 无坐标 → 标记 needs_coordinates, 需人工从正文/图1定位
"""
from __future__ import annotations
import sys
import re
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT_DIR, LIT_ROOT  # noqa: E402

import pandas as pd  # noqa: E402

# 坐标正则 (多种格式)
COORD_PATS = [
    # 28.3°N, 121.4°E / 28.3° N, 121.4° E
    (re.compile(r"(\d{1,2}\.?\d{0,4})\s*°?\s*[NSns]\s*[,，]\s*(\d{1,3}\.?\d{0,4})\s*°?\s*[EWew]"), "DMS_degree"),
    # N 28.3, E 121.4 / 28.3 N, 121.4 E
    (re.compile(r"[NSns]\s*(\d{1,2}\.?\d{0,4})\s*[,，]\s*[EWew]\s*(\d{1,3}\.?\d{0,4})"), "NS_prefix"),
    # latitude 28.3, longitude 121.4
    (re.compile(r"lat(?:itude)?\s*(\d{1,2}\.?\d{0,4})\s*[,，]?\s*lon(?:gitude)?\s*(\d{1,3}\.?\d{0,4})", re.I), "latlon_kw"),
    # 28°30'N, 121°24'E (度分秒)
    (re.compile(r"(\d{1,2})\s*°\s*(\d{1,2})\s*['′]\s*[NSns]\s*[,，]\s*(\d{1,3})\s*°\s*(\d{1,2})\s*['′]\s*[EWew]"), "DMS_minute"),
]
# 中国经纬度范围验证
def in_china(lat, lon):
    return 18.0 <= lat <= 53.5 and 73.0 <= lon <= 135.0


def extract_coords(text: str) -> list:
    found = []
    for pat, src in COORD_PATS:
        for m in pat.finditer(text):
            try:
                if src == "DMS_minute":
                    lat = int(m.group(1)) + int(m.group(2)) / 60
                    lon = int(m.group(3)) + int(m.group(4)) / 60
                else:
                    lat = float(m.group(1))
                    lon = float(m.group(2))
                if in_china(lat, lon):
                    found.append((lat, lon, src))
            except (ValueError, IndexError):
                continue
    return found


def main():
    cand = pd.read_csv(OUT_DIR / "candidate_literature_op_hmop.csv", dtype=str, keep_default_na=False)
    ab = cand[cand["candidate_level"].isin(["A", "B"])]
    site = pd.read_csv(OUT_DIR / "site_dataset_summary_op_hmop.csv", dtype=str, keep_default_na=False)
    tr_pids = set(site[site["readiness"] == "training_ready_hm_op"]["paper_id"])
    op_pids = set(site[site["readiness"] == "op_only_ready"]["paper_id"])

    rows = []
    for _, r in ab.iterrows():
        pid, stem = r["paper_id"], r["stem"]
        md = LIT_ROOT / stem / "parsed" / "paper.md"
        meta = LIT_ROOT / stem / "metadata.json"
        text = md.read_text(encoding="utf-8", errors="ignore")[:80000] if md.exists() else ""
        # metadata.json 里也可能有坐标
        if meta.exists():
            try:
                mj = json.loads(meta.read_text(encoding="utf-8", errors="ignore"))
                text += " " + json.dumps(mj, ensure_ascii=False)
            except Exception:
                pass
        coords = extract_coords(text)
        in_tr = pid in tr_pids
        in_op = pid in op_pids
        if coords:
            # 取第一个有效坐标 (研究区中心)
            lat, lon, src = coords[0]
            rows.append({
                "paper_id": pid, "lat": lat, "lon": lon,
                "coord_source": src, "n_coords_found": len(coords),
                "region": r.get("region", "")[:40],
                "in_training_ready": in_tr, "in_op_only": in_op,
            })
    df_c = pd.DataFrame(rows)
    df_c.to_csv(OUT_DIR / "site_coordinates.csv", index=False, encoding="utf-8-sig")

    # 统计
    print(f"=== P6 坐标扫描结果 ===")
    print(f"A/B 候选论文: {len(ab)}")
    print(f"提取到坐标: {len(df_c)} 篇")
    tr_with_coord = df_c[df_c["in_training_ready"]]
    op_with_coord = df_c[df_c["in_op_only"]]
    print(f"\ntraining_ready 论文有坐标: {len(tr_with_coord)} / {len(tr_pids)}")
    if len(tr_with_coord):
        print(f"  覆盖 training_ready sample: 见 site_coordinates.csv")
        for _, r in tr_with_coord.iterrows():
            print(f"    {r['paper_id']}: ({r['lat']:.3f}, {r['lon']:.3f}) [{r['coord_source']}] {r['region']}")
    print(f"\nop_only 论文有坐标: {len(op_with_coord)} / {len(op_pids)}")
    print(f"\nGEE 可行性: {'✅ 有坐标可采样' if len(df_c) else '❌ 无坐标, 需人工提取'}")
    print(f"  建议先人工核验坐标 (场地中心 vs 采样点), 再调 gee_fetch.py")
    print(f"\n输出: {OUT_DIR / 'site_coordinates.csv'}")


if __name__ == "__main__":
    main()
