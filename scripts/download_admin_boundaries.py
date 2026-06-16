#!/usr/bin/env python3
"""下载全国行政区边界 GeoJSON(离线地图 L1 矢量底图数据源)。

数据来源: 阿里 DataV.GeoAtlas 开放数据(公开免费, 可商用)。
  省级: 100000_full.json(全国)
  地市级: 各省 adcode(如 530000_云南省.json)
  县级: 各地级市 adcode(如 532500_红河州.json, 含个旧市等)

用法:
  python scripts/download_admin_boundaries.py                 # 全量: 省+地市+县
  python scripts/download_admin_boundaries.py --skip-county   # 只省+地市
  python scripts/download_admin_boundaries.py --rebuild-index # 仅重建索引(不下载)
生成:
  data/geo/china_provinces.json     # 全国省级边界
  data/geo/prefectures/             # 各省地级市
  data/geo/counties/                # 各地级市的县(全国~475个文件, ~46MB)
  data/geo/geo_index.json           # 行政区索引(adcode→名称→bbox→文件路径)
说明:
  - 三级金字塔架构: 省(569KB)→地市(3.7MB)→县(46MB), 前端按缩放层级懒加载。
  - 矢量边界数据, 配合 Leaflet 渲染, 不需要任何瓦片/key/外网。
  - 合规: DataV.GeoAtlas 为开放数据, 可用于商业项目。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO_DIR = os.path.join(ROOT, "data", "geo")
PREF_DIR = os.path.join(GEO_DIR, "prefectures")
COUNTY_DIR = os.path.join(GEO_DIR, "counties")

DATAV = "https://geo.datav.aliyun.com/areas_v3/bound"

UA = {"User-Agent": "SRS/0.1 (offline-map-setup)"}


def fetch(url: str, retries: int = 3, timeout: int = 30) -> bytes | None:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                time.sleep(2)
    print(f"  ⚠️ 下载失败 {url}: {last}")
    return None


def save_json(path: str, data: bytes) -> bool:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return True


def feature_bbox(geom: dict) -> list[float] | None:
    """粗算 feature 的 bbox(经纬度范围), 供前端快速查找。"""
    coords = []
    def walk(g):
        if g.get("type") == "GeometryCollection":
            for gg in g.get("geometries", []):
                walk(gg)
            return
        t = g.get("type")
        if t in ("Polygon",):
            coords.extend(g.get("coordinates", [])[0])
        elif t == "MultiPolygon":
            for poly in g.get("coordinates", []):
                coords.extend(poly[0])
    try:
        walk(geom)
        if not coords:
            return None
        lons = [c[0] for c in coords]; lats = [c[1] for c in coords]
        return [round(min(lons), 4), round(min(lats), 4),
                round(max(lons), 4), round(max(lats), 4)]
    except Exception:  # noqa: BLE001
        return None


def download_china_provinces():
    """全国省级边界(含各省 adcode)。"""
    out = os.path.join(GEO_DIR, "china_provinces.json")
    if os.path.exists(out):
        print("[省] 已存在, 跳过下载")
        return json.loads(open(out, encoding="utf-8").read())
    print("[省] 下载全国省级边界...")
    data = fetch(f"{DATAV}/100000_full.json")
    if data:
        save_json(out, data)
        print(f"  ✅ china_provinces.json ({len(data)/1024:.0f} KB)")
        return json.loads(data)
    raise RuntimeError("全国省级边界下载失败, 无法继续")


def download_children(adcode: int, name: str, out_dir: str, label: str,
                      sleep: float = 0.3) -> dict | None:
    """下载某 adcode 的下级行政区(地级市或县级)。返回解析后的 json 或 None。"""
    out = os.path.join(out_dir, f"{adcode}_{name}.json")
    if os.path.exists(out):
        try:
            return json.loads(open(out, encoding="utf-8").read())
        except Exception:  # noqa: BLE001
            pass
    data = fetch(f"{DATAV}/{adcode}_full.json", retries=2, timeout=20)
    if not data:
        return None
    try:
        j = json.loads(data)
        if "features" not in j:
            return None
    except Exception:  # noqa: BLE001
        return None
    save_json(out, data)
    print(f"  ✅ {label}: {name}({adcode}) {len(data)/1024:.0f} KB")
    time.sleep(sleep)
    return j


def download_prefectures(provinces_json: dict):
    """下载全国各省的地级市。"""
    print("[地市] 下载各省地级市...")
    os.makedirs(PREF_DIR, exist_ok=True)
    ok = skip = fail = 0
    for feat in provinces_json.get("features", []):
        p = feat.get("properties", {})
        adcode = p.get("adcode"); name = p.get("name")
        if not adcode:
            continue
        out = os.path.join(PREF_DIR, f"{adcode}_{name}.json")
        if os.path.exists(out):
            skip += 1; continue
        if download_children(adcode, name, PREF_DIR, "地市"):
            ok += 1
        else:
            fail += 1
    print(f"  地市完成: 新下载 {ok}, 已存在 {skip}, 失败 {fail}")


def download_counties():
    """下载全国所有地级市的县级数据。"""
    print("[县] 下载全国县级数据(三级金字塔最底层)...")
    os.makedirs(COUNTY_DIR, exist_ok=True)
    ok = skip = fail = 0
    for fn in sorted(os.listdir(PREF_DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            prov = json.loads(open(os.path.join(PREF_DIR, fn), encoding="utf-8").read())
        except Exception:  # noqa: BLE001
            continue
        for feat in prov.get("features", []):
            p = feat.get("properties", {})
            adcode = p.get("adcode"); name = p.get("name")
            if not adcode:
                continue
            out = os.path.join(COUNTY_DIR, f"{adcode}_{name}.json")
            if os.path.exists(out):
                skip += 1; continue
            if download_children(adcode, name, COUNTY_DIR, "县", sleep=0.15):
                ok += 1
            else:
                fail += 1
    print(f"  县级完成: 新下载 {ok}, 已存在 {skip}, 失败 {fail}")


def build_index():
    """构建行政区索引: adcode → {name, level, parent, bbox, file}。供前端/后端快速查找。"""
    print("[索引] 构建行政区索引 geo_index.json...")
    index: dict = {"provinces": [], "prefectures": {}, "counties": {}}

    def parse(filepath: str) -> list[dict]:
        try:
            d = json.loads(open(filepath, encoding="utf-8").read())
        except Exception:  # noqa: BLE001
            return []
        out = []
        for feat in d.get("features", []):
            p = feat.get("properties", {}) or {}
            out.append({
                "adcode": p.get("adcode"), "name": p.get("name"),
                "center": p.get("center"), "level": p.get("level"),
                "bbox": feature_bbox(feat.get("geometry", {})),
            })
        return out

    # 省
    prov_path = os.path.join(GEO_DIR, "china_provinces.json")
    if os.path.exists(prov_path):
        for item in parse(prov_path):
            item["file"] = "china_provinces.json"
            index["provinces"].append(item)

    # 地市(按省分组)
    if os.path.isdir(PREF_DIR):
        for fn in sorted(os.listdir(PREF_DIR)):
            if not fn.endswith(".json"):
                continue
            parent_adcode = int(fn.split("_")[0])
            for item in parse(os.path.join(PREF_DIR, fn)):
                item["file"] = f"prefectures/{fn}"
                item["parent"] = parent_adcode
                index["prefectures"][item["adcode"]] = item

    # 县(按地市分组)
    if os.path.isdir(COUNTY_DIR):
        for fn in sorted(os.listdir(COUNTY_DIR)):
            if not fn.endswith(".json"):
                continue
            parent_adcode = int(fn.split("_")[0])
            for item in parse(os.path.join(COUNTY_DIR, fn)):
                item["file"] = f"counties/{fn}"
                item["parent"] = parent_adcode
                index["counties"][item["adcode"]] = item

    index["summary"] = {
        "n_provinces": len(index["provinces"]),
        "n_prefectures": len(index["prefectures"]),
        "n_counties": len(index["counties"]),
        "source": "DataV.GeoAtlas (公开开放数据)",
        "note": "三级金字塔离线行政区, 前端按缩放层级懒加载。无 key/无外网依赖。",
    }
    out = os.path.join(GEO_DIR, "geo_index.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)
    s = index["summary"]
    print(f"  ✅ geo_index.json: 省 {s['n_provinces']}, 地市 {s['n_prefectures']}, 县 {s['n_counties']}")


def main():
    skip_county = "--skip-county" in sys.argv
    rebuild_only = "--rebuild-index" in sys.argv
    if rebuild_only:
        build_index()
        return
    provinces = download_china_provinces()
    download_prefectures(provinces)
    if not skip_county:
        download_counties()
    build_index()
    print("\n✅ 离线行政区数据准备完成。")
    print(f"   目录: {GEO_DIR}")


if __name__ == "__main__":
    main()

