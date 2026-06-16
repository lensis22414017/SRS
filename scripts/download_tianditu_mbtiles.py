#!/usr/bin/env python3
"""下载天地图影像瓦片并打包成 MBTiles(离线地图 L2 影像底图, 按需导入)。

适用场景: 桌面打包版默认用 L1 矢量底图; 甲方需要某区域卫星影像时,
用本脚本下载该区域到指定缩放层级, 生成 .mbtiles 放入应用数据目录即可启用。

用法:
  # 下载个旧周边到 10 级(经纬度范围 + key)
  python scripts/download_tianditu_mbtiles.py \
      --key 你的天地图key \
      --bbox 102.8,22.9,103.5,23.7 \
      --zoom-min 5 --zoom-max 10 \
      --out data/geo/tiles/gejiu_img.mbtiles

  # 或按行政区(用已下载的 geo_index 反查 bbox)
  python scripts/download_tianditu_mbtiles.py \
      --key 你的key --adcode 532501 --zoom-max 10 \
      --out data/geo/tiles/gejiu_img.mbtiles

说明:
  - 体积: bbox 越大、zoom-max 越高, 体积指数级增长。建议区域 ≤ 1°×1°, zoom-max ≤ 12。
  - 礼貌限速: 默认每瓦片 0.1s, 避免触发天地图限流。
  - MBTiles 格式: SQLite 单文件, 后端 /map/tile 优先读本地 MBTiles, 无则走在线。
  - 合规: 请确认您的天地图 key 授权范围; 瓦片仅供本项目离线使用, 不得再分发。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO_DIR = os.path.join(ROOT, "data", "geo")
UA = {"User-Agent": "SRS/0.1 (offline-tile-setup)"}


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    """经纬度 → 瓦片坐标(Web Mercator)。"""
    import math
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def tile_to_lonlat(x: int, y: int, z: int) -> tuple[float, float]:
    """瓦片左上角 → 经纬度。"""
    import math
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * y / n)))
    lat = math.degrees(lat_rad)
    return lon, lat


def init_mbtiles(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (name text, value text);
        CREATE TABLE IF NOT EXISTS tiles (
            zoom_level integer, tile_column integer, tile_row integer,
            tile_data blob, PRIMARY KEY (zoom_level, tile_column, tile_row));
        CREATE INDEX IF NOT EXISTS idx_tiles ON tiles (zoom_level, tile_column, tile_row);
    """)
    return conn


def mbtiles_y(x: int, y: int, z: int) -> int:
    """天地图/XYZ 用 TMS 反转 y 行号。"""
    return (2 ** z - 1) - y


def fetch_tile(layer: str, z: int, x: int, y: int, key: str, retries: int = 2) -> bytes | None:
    url = (f"https://t0.tianditu.gov.cn/{layer}_w/wmts?SERVICE=WMTS&REQUEST=GetTile"
           f"&VERSION=1.0.0&LAYER={layer}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles"
           f"&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk={key}")
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.5)
    print(f"    ⚠️ 瓦片失败 z={z} x={x} y={y}: {last}")
    return None


def bbox_from_adcode(adcode: int) -> list[float] | None:
    idx_path = os.path.join(GEO_DIR, "geo_index.json")
    if not os.path.exists(idx_path):
        return None
    idx = json.loads(open(idx_path, encoding="utf-8").read())
    for pool in (idx.get("provinces", []),
                 idx.get("prefectures", {}).values(),
                 idx.get("counties", {}).values()):
        for it in pool:
            if it.get("adcode") == adcode and it.get("bbox"):
                return it["bbox"]
    return None


def main():
    ap = argparse.ArgumentParser(description="下载天地图影像 → MBTiles")
    ap.add_argument("--key", required=True, help="天地图 key")
    ap.add_argument("--bbox", help="经纬度范围 minlon,minlat,maxlon,maxlat")
    ap.add_argument("--adcode", type=int, help="行政区 adcode(从 geo_index 反查 bbox)")
    ap.add_argument("--zoom-min", type=int, default=5)
    ap.add_argument("--zoom-max", type=int, default=10)
    ap.add_argument("--layer", default="img", choices=["img", "vec"],
                    help="img=卫星影像(默认), vec=矢量地图")
    ap.add_argument("--out", default="data/geo/tiles/region_img.mbtiles")
    ap.add_argument("--sleep", type=float, default=0.1, help="每瓦片间隔(秒)")
    args = ap.parse_args()

    # 解析 bbox
    if args.bbox:
        bbox = [float(v) for v in args.bbox.split(",")]
    elif args.adcode:
        bbox = bbox_from_adcode(args.adcode)
        if not bbox:
            print(f"❌ adcode {args.adcode} 在 geo_index 中未找到 bbox")
            sys.exit(1)
        print(f"行政区 {args.adcode} bbox: {bbox}")
    else:
        print("❌ 必须提供 --bbox 或 --adcode")
        sys.exit(1)
    minlon, minlat, maxlon, maxlat = bbox

    # 预估瓦片数
    total = 0
    for z in range(args.zoom_min, args.zoom_max + 1):
        x0, y0 = lonlat_to_tile(minlon, maxlat, z)
        x1, y1 = lonlat_to_tile(maxlon, minlat, z)
        total += (abs(x1 - x0) + 1) * (abs(y1 - y0) + 1)
    print(f"区域 {bbox}, 缩放 {args.zoom_min}-{args.zoom_max}, 预估瓦片 {total} 个")
    print(f"预估体积: ~{total * 25 / 1024:.0f} MB (影像平均 25KB/瓦片)")
    if total > 50000:
        ans = input(f"瓦片数 {total} 较大, 确认继续? (y/N) ")
        if ans.lower() != "y":
            print("已取消"); sys.exit(0)

    conn = init_mbtiles(args.out)
    conn.execute("INSERT OR REPLACE INTO metadata VALUES ('name', ?)", (f"SRS offline {args.layer}",))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES ('format', ?)", ("jpg" if args.layer == "img" else "png",))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES ('minzoom', ?)", (str(args.zoom_min),))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES ('maxzoom', ?)", (str(args.zoom_max),))
    conn.execute("INSERT OR REPLACE INTO metadata VALUES ('bounds', ?)",
                 (f"{minlon},{minlat},{maxlon},{maxlat}",))

    done = skipped = failed = 0
    for z in range(args.zoom_min, args.zoom_max + 1):
        x0, y0 = lonlat_to_tile(minlon, maxlat, z)
        x1, y1 = lonlat_to_tile(maxlon, minlat, z)
        xs = range(min(x0, x1), max(x0, x1) + 1)
        ys = range(min(y0, y1), max(y0, y1) + 1)
        z_total = len(xs) * len(ys)
        print(f"[z={z}] {z_total} 瓦片 ...")
        for x in xs:
            for y in ys:
                my = mbtiles_y(x, y, z)
                # 已存在则跳过(断点续传)
                if conn.execute("SELECT 1 FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                                (z, x, my)).fetchone():
                    skipped += 1; continue
                data = fetch_tile(args.layer, z, x, y, args.key)
                if data:
                    conn.execute("INSERT OR REPLACE INTO tiles VALUES (?,?,?,?)",
                                 (z, x, my, sqlite3.Binary(data)))
                    done += 1
                else:
                    failed += 1
                if (done + skipped + failed) % 50 == 0:
                    conn.commit()
                    print(f"    进度: 下载 {done}, 跳过 {skipped}, 失败 {failed}")
                time.sleep(args.sleep)
        conn.commit()
    conn.close()
    size_mb = os.path.getsize(args.out) / 1024 / 1024
    print(f"\n✅ 完成: 下载 {done}, 跳过 {skipped}, 失败 {failed}")
    print(f"   输出: {args.out} ({size_mb:.1f} MB)")
    print(f"   将该文件放入应用数据目录的 tiles/ 子目录, 后端 /map/tile 会自动优先读取。")


if __name__ == "__main__":
    main()
