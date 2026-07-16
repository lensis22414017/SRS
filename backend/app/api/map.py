"""地图图层瓦片代理 API。

瓦片优先级:
  1. 本地 MBTiles (离线, 桌面打包版首选)
  2. 高德地图 hybrid (在线, 无 IP 白名单, 中文标注, 推荐默认)
  3. 地图服务 (在线, 需固定 IP 白名单, 可选增强)
"""
from __future__ import annotations

import os
import urllib.error
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import assert_site_access, get_current_user
from app.db.session import get_db
from app.models import FactorDictionary, Measurement, SamplingPoint, Site, ThresholdRule, User

router = APIRouter(prefix=get_settings().api_v1_prefix, tags=["map"])

TILE_LAYERS = {
    "img": {"layer": "img", "media_type": "image/jpeg", "label": "地图服务影像"},
    "cia": {"layer": "cia", "media_type": "image/png", "label": "地图服务影像注记"},
    "vec": {"layer": "vec", "media_type": "image/png", "label": "地图服务矢量"},
    "cva": {"layer": "cva", "media_type": "image/png", "label": "地图服务矢量注记"},
}

# 高德地图瓦片服务器列表 (CDN 负载均衡, 同一 x+y 固定路由以利用 CDN 缓存)
_GAODE_SERVERS = ["webst01", "webst02", "webst03", "webst04"]


def _gaode_tile_url(z: int, x: int, y: int, key: str) -> str:
    """构造高德混合图层(卫星+中文注记) URL。
    style=8: 卫星影像 + 中文地名/道路/村镇注记 (hybrid)
    style=6: 纯卫星影像 (无注记)
    有 key 时走官方配额通道; 无 key 时走公共通道(同样可用, 无 IP 限制)。
    """
    server = _GAODE_SERVERS[(x + y) % 4]
    base = f"https://{server}.is.autonavi.com/appmaptile?style=8&x={x}&y={y}&z={z}"
    return f"{base}&key={key}" if key else base


def _require_site(db: Session, user: User, site_id: int) -> Site:
    site = db.get(Site, site_id)
    if not site:
        raise HTTPException(404, "场地不存在")
    assert_site_access(db, user, site)
    return site


def _tile_url(layer: str, z: int, x: int, y: int, key: str) -> str:
    meta = TILE_LAYERS[layer]
    return (
        f"https://t0.tianditu.gov.cn/{meta['layer']}_w/wmts?"
        "SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
        f"&LAYER={meta['layer']}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles"
        f"&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk={key}"
    )


@router.get("/map/tile/{layer}/{z}/{x}/{y}")
def tianditu_tile(layer: str, z: int, x: int, y: int):
    # 路由顺序:{layer}先于/gaode/声明, 故 /map/tile/gaode/* 会命中此路由; gaode 转发给高德端点
    if layer == "gaode":
        return gaode_tile(z, x, y)
    """后端瓦片代理: 优先读本地 MBTiles(离线), 无则走地图服务在线(需 key)。

    优先级: 本地 MBTiles > 地图服务在线 > 503。
    MBTiles 查找路径: {项目根}/data/geo/tiles/*.mbtiles (所有文件均尝试)。
    """
    if layer not in TILE_LAYERS:
        raise HTTPException(404, "地图图层不存在")
    settings = get_settings()

    # 1) 优先本地 MBTiles(离线影像/矢量, 桌面打包版核心路径)
    tile_data = _read_mbtiles(layer, z, x, y)
    if tile_data is not None:
        return Response(content=tile_data, media_type=TILE_LAYERS[layer]["media_type"])

    # 2) 无本地瓦片 → 走地图服务在线(需固定 IP 白名单; 可选增强)
    if not settings.tianditu_key:
        raise HTTPException(
            503,
            "未配置地图服务 TIANDITU_KEY, 且无本地离线瓦片。"
            "影像底图请改用 /map/tile/gaode/{z}/{x}/{y} (无需 key, 无 IP 限制)。",
        )
    try:
        req = urllib.request.Request(
            _tile_url(layer, z, x, y, settings.tianditu_key),
            headers={"User-Agent": "SRS/0.1"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return Response(content=resp.read(),
                            media_type=TILE_LAYERS[layer]["media_type"])
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code, "地图服务瓦片服务返回错误")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"地图服务瓦片加载失败: {e}")


@router.get("/map/tile/gaode/{z}/{x}/{y}")
def gaode_tile(z: int, x: int, y: int):
    """高德卫星+中文注记混合瓦片代理。

    优先级: 本地 MBTiles > 高德在线(无 IP 白名单)。
    无需配置 GAODE_KEY 即可使用; 配置后走官方配额(30万次/天免费)。
    换电脑/换网络不受影响, 适合桌面演示和移动演示场景。
    """
    settings = get_settings()

    # 1) 优先本地 MBTiles(离线演示)
    tile_data = _read_mbtiles("img", z, x, y)
    if tile_data is not None:
        return Response(content=tile_data, media_type="image/jpeg")

    # 2) 高德在线 (有无 key 均可, 无 IP 白名单)
    url = _gaode_tile_url(z, x, y, settings.gaode_key)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SRS/0.1", "Referer": "https://lbs.amap.com/"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            return Response(content=resp.read(), media_type="image/jpeg")
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code, f"高德瓦片服务返回错误 (HTTP {e.code})")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"高德瓦片加载失败: {e}")


def _read_mbtiles(layer: str, z: int, x: int, y: int) -> bytes | None:
    """从本地 MBTiles 读取瓦片(支持 img 影像/vec 矢量)。无文件或无命中返回 None。

    MBTiles 用 TMS 行号(与 XYZ 的 y 反转), 下载脚本已存反转后的 my。
    """
    import glob as _glob
    import sqlite3 as _sqlite3
    tiles_dir = os.path.join(_geo_root(), "tiles")
    if not os.path.isdir(tiles_dir):
        return None
    # 影像层读 *_img.mbtiles, 矢量层读 *_vec.mbtiles
    pattern = os.path.join(tiles_dir, f"*_{layer}.mbtiles")
    # TMS y 反转
    my = (2 ** z - 1) - y
    for mbt in _glob.glob(pattern):
        try:
            conn = _sqlite3.connect(f"file:{mbt}?mode=ro", uri=True)
            row = conn.execute(
                "SELECT tile_data FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                (z, x, my)).fetchone()
            conn.close()
            if row and row[0]:
                return bytes(row[0])
        except Exception:  # noqa: BLE001
            continue
    return None


# ============ GB15618 阈值按 pH 档选择 ============
# GB15618-2018 农用地筛选值: 每个重金属按土壤 pH 分 4 档。
# 旧实现取 min(4档)=最严苛档, 重度污染场地所有点被判 high, 无颜色层次。
# 新实现: 按采样点实测 pH 选对应档阈值(无 pH 时回退最严苛档)。

# pH → 档索引: 0:pH<=5.5  1:5.5<pH<=6.5  2:6.5<pH<=7.5  3:pH>7.5
def _band_index(ph: float | None) -> int | None:
    if ph is None:
        return None
    if ph <= 5.5:
        return 0
    if ph <= 6.5:
        return 1
    if ph <= 7.5:
        return 2
    return 3


def _parse_band(land_type: str | None) -> int | None:
    """从 ThresholdRule.land_type 解析 GB15618 pH 档索引。"""
    if not land_type:
        return None
    s = land_type.replace("≤", "<=")
    if "pH<=5.5" in s:
        return 0
    if "5.5<pH<=6.5" in s:
        return 1
    if "6.5<pH<=7.5" in s:
        return 2
    if "pH>7.5" in s:
        return 3
    return None


def _threshold_table(db: Session, site_id: int) -> dict:
    """返回 {factor_code: {"name":..., "bands": [v0,v1,v2,v3], "generic": [...]}}。

    仅取该场地用到的因子, 不 join measurement(避免 4档×measurement 笛卡尔积)。
    pH 档规则进 bands; 非 pH 档规则(land_type 为用地类型/None)进 generic 池,
    由 _select_threshold 在 pH 档缺失时兜底取 min(最严苛), 避免阈值表整体落空。
    """
    factor_ids = {r[0] for r in db.query(Measurement.factor_id)
                  .filter(Measurement.site_id == site_id).distinct().all()}
    if not factor_ids:
        return {}
    rows = (db.query(FactorDictionary.factor_code, FactorDictionary.factor_name,
                     ThresholdRule.threshold_max, ThresholdRule.land_type)
            .join(ThresholdRule, ThresholdRule.factor_id == FactorDictionary.id)
            .filter(FactorDictionary.id.in_(factor_ids)).all())
    table: dict = {}
    for code, name, tmax, land in rows:
        if tmax is None or float(tmax) <= 0:
            continue
        bidx = _parse_band(land)
        entry = table.setdefault(code, {"name": name, "bands": [None, None, None, None],
                                        "generic": []})
        if bidx is not None:
            entry["bands"][bidx] = float(tmax)
        else:
            # land_type 非 pH 档文本(用地类型/None): 视为不分 pH 的通用阈值, 进 generic 池。
            entry["generic"].append(float(tmax))
    return table


def _select_threshold(bands: list, bidx: int | None, generic: list | None = None) -> float | None:
    """按 pH 档选阈值; 无 pH 或该档缺失时回退最严苛档(min(bands+generic))。"""
    if bidx is not None and bands[bidx] is not None:
        return bands[bidx]
    avail = [b for b in bands if b is not None]
    if generic:
        avail += generic
    return min(avail) if avail else None


def _risk(exceedance: float | None) -> str:
    """超标倍数 → 8 级风险枚举。

    与 legend(:337-346) 和前端 SiteMap.excColor(SiteMap.tsx:34-43) 三者口径一致:
      none<1 / low 1-3 / med1 3-10 / med2 10-30 / high 30-80 /
      severe 80-200 / extreme>=200 / unknown(无阈值/无数据)
    旧实现仅 high/medium/low 三档, 重度场地全部 high 无层次; 统一为 8 级连续分桶。
    """
    if exceedance is None:
        return "unknown"
    if exceedance >= 200:
        return "extreme"
    if exceedance >= 80:
        return "severe"
    if exceedance >= 30:
        return "high"
    if exceedance >= 10:
        return "med2"
    if exceedance >= 3:
        return "med1"
    if exceedance >= 1:
        return "low"
    return "none"


@router.get("/sites/{site_id}/map/layers")
def site_map_layers(site_id: int,
                    factor: str | None = Query(default=None),
                    user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """场地地图图层: 采样点 GeoJSON + 污染物筛选 + 超标倍数分级。"""
    site = _require_site(db, user, site_id)
    points = db.query(SamplingPoint).filter_by(site_id=site_id).order_by(SamplingPoint.id).all()
    rows = (db.query(Measurement, FactorDictionary, SamplingPoint)
            .join(FactorDictionary, Measurement.factor_id == FactorDictionary.id)
            .join(SamplingPoint, Measurement.sampling_point_id == SamplingPoint.id)
            .filter(Measurement.site_id == site_id)
            .all())
    ttable = _threshold_table(db, site_id)
    pollutants = []
    pollutant_seen = set()
    ph_by_point: dict = {}
    meas_by_point: dict = {}
    for m, fd, sp in rows:
        if fd.factor_code not in pollutant_seen:
            pollutants.append({
                "factor_code": fd.factor_code,
                "factor_name": fd.factor_name,
                "unit": m.unit or fd.default_unit,
                "category": fd.level1_category,
            })
            pollutant_seen.add(fd.factor_code)
        if fd.factor_code == "pH":
            try:
                ph_by_point[sp.id] = float(m.value) if m.value is not None else None
            except (TypeError, ValueError):
                ph_by_point[sp.id] = None
            continue
        if factor and factor not in (fd.factor_code, fd.factor_name):
            continue
        meas_by_point.setdefault(sp.id, []).append((m, fd))

    features = []
    for p in points:
        ph = ph_by_point.get(p.id)
        bidx = _band_index(ph)
        pairs = meas_by_point.get(p.id, [])
        selected = None
        measurements_payload = []
        for m, fd in pairs:
            tt = ttable.get(fd.factor_code)
            limit = _select_threshold(tt["bands"], bidx, tt.get("generic")) if tt else None
            try:
                exc = float(m.value) / limit if (limit and m.value is not None) else None
            except (TypeError, ValueError):
                exc = None
            entry = {
                "factor_code": fd.factor_code,
                "factor_name": fd.factor_name,
                "value": m.value,
                "unit": m.unit or fd.default_unit,
                "threshold": limit,
                "exceedance": exc,
                "risk_level": _risk(exc),
            }
            if len(measurements_payload) < 20:
                measurements_payload.append(entry)
            if exc is not None and (selected is None or exc > selected["exceedance"]):
                selected = dict(entry)
        risk_level = selected["risk_level"] if selected else "unknown"
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [
                    float(p.longitude) if p.longitude is not None else None,
                    float(p.latitude) if p.latitude is not None else None,
                ],
            },
            "properties": {
                "id": p.id,
                "point_code": p.point_code,
                "region": p.region,
                "soil_type": p.soil_type,
                "depth_top_cm": p.depth_top_cm,
                "depth_bottom_cm": p.depth_bottom_cm,
                "risk_level": risk_level,
                "selected": selected,
                "ph": ph,
                "measurements": measurements_payload,
            },
        })

    return {
        "site": {
            "id": site.id,
            "site_code": site.site_code,
            "name": site.name,
            "longitude": float(site.longitude) if site.longitude is not None else None,
            "latitude": float(site.latitude) if site.latitude is not None else None,
            "pollution_type": site.pollution_type,
        },
        "tile_proxy": {
            "enabled": bool(get_settings().tianditu_key),
            "base_layers": list(TILE_LAYERS.keys()),
        },
        "pollutants": pollutants,
        "selected_factor": factor,
        "legend": [
            {"risk_level": "none", "label": "未超标(<1倍)", "color": "#16a34a"},
            {"risk_level": "low", "label": "轻度(1-3倍)", "color": "#facc15"},
            {"risk_level": "med1", "label": "中度(3-10倍)", "color": "#f59e0b"},
            {"risk_level": "med2", "label": "偏重(10-30倍)", "color": "#ea580c"},
            {"risk_level": "high", "label": "重度(30-80倍)", "color": "#dc2626"},
            {"risk_level": "severe", "label": "极重(80-200倍)", "color": "#9f1239"},
            {"risk_level": "extreme", "label": "超极重(>200倍)", "color": "#6b0f1a"},
            {"risk_level": "unknown", "label": "无阈值/无数据", "color": "#64748b"},
        ],
        "geojson": {"type": "FeatureCollection", "features": features},
    }


# ============ 离线行政区边界(三级金字塔) ============
# 数据源: data/geo/ (阿里 DataV.GeoAtlas 开放数据), 离线读取, 无 key/无外网。
# 层级: province(全国省) / prefecture(省内地市) / county(地市内县)。

import json as _json  # noqa: E402


def _geo_root() -> str:
    """data/geo 目录绝对路径(兼容打包后 .app 与开发模式)。

    打包后资源落在 Contents/Resources, 旧的 dirname/../../.. 会错到 Contents,
    统一改用 resource_root() 解析(见 app.core.config)。
    """
    from app.core.config import resource_root
    return os.path.join(resource_root(), "data", "geo")


@router.get("/map/geo/index")
def geo_index():
    """返回行政区索引(轻量, 仅 adcode/name/bbox, 不含几何)。前端用于按缩放/范围查找要加载的层级。"""
    idx_path = os.path.join(_geo_root(), "geo_index.json")
    if not os.path.exists(idx_path):
        raise HTTPException(503, "离线行政区索引未安装, 请先运行 scripts/download_admin_boundaries.py")
    with open(idx_path, encoding="utf-8") as f:
        data = _json.load(f)
    return Response(content=_json.dumps(data, ensure_ascii=False), media_type="application/json",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/map/geo/boundaries")
def geo_boundaries(level: str = Query("province", pattern="^(province|prefecture|county)$"),
                   adcode: int | None = Query(None, description="上级 adcode; province 级忽略")):
    """按层级返回行政区边界 GeoJSON(含几何)。

    - level=province: 全国省界(无需 adcode)
    - level=prefecture&adcode=530000: 云南省下辖地市
    - level=county&adcode=532500: 红河州下辖县
    全部离线读取, 无 key/无外网依赖。
    """
    geo = _geo_root()
    if level == "province":
        path = os.path.join(geo, "china_provinces.json")
    else:
        if not adcode:
            raise HTTPException(400, f"{level} 级需提供 adcode 参数")
        # 在 prefectures/ 或 counties/ 目录按 adcode_* 匹配
        subdir = "prefectures" if level == "prefecture" else "counties"
        d = os.path.join(geo, subdir)
        match = None
        if os.path.isdir(d):
            for fn in os.listdir(d):
                if fn.startswith(f"{adcode}_") and fn.endswith(".json"):
                    match = os.path.join(d, fn); break
        if not match:
            raise HTTPException(404, f"未找到 adcode={adcode} 的 {level} 级离线数据")
        path = match
    if not os.path.exists(path):
        raise HTTPException(503, "离线行政区数据未安装, 请先运行 scripts/download_admin_boundaries.py")
    with open(path, encoding="utf-8") as f:
        data = _json.load(f)
    return Response(content=_json.dumps(data, ensure_ascii=False), media_type="application/json",
                    headers={"Cache-Control": "public, max-age=86400"})
