"""地图图层与天地图瓦片代理 API。"""
from __future__ import annotations

import urllib.error
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import assert_site_access, get_current_user
from app.db.session import get_db
from app.models import FactorDictionary, Measurement, SamplingPoint, Site, ThresholdRule, User

router = APIRouter(prefix=get_settings().api_v1_prefix, tags=["map"])

TILE_LAYERS = {
    "img": {"layer": "img", "media_type": "image/jpeg", "label": "天地图影像"},
    "cia": {"layer": "cia", "media_type": "image/png", "label": "天地图影像注记"},
    "vec": {"layer": "vec", "media_type": "image/png", "label": "天地图矢量"},
    "cva": {"layer": "cva", "media_type": "image/png", "label": "天地图矢量注记"},
}


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
    """后端代理天地图瓦片, 避免前端暴露 key 并规避桌面打包 referer 问题。"""
    if layer not in TILE_LAYERS:
        raise HTTPException(404, "地图图层不存在")
    settings = get_settings()
    if not settings.tianditu_key:
        raise HTTPException(503, "未配置天地图 TIANDITU_KEY")
    try:
        req = urllib.request.Request(
            _tile_url(layer, z, x, y, settings.tianditu_key),
            headers={"User-Agent": "SRS/0.1"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return Response(content=resp.read(),
                            media_type=TILE_LAYERS[layer]["media_type"])
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code, "天地图瓦片服务返回错误")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"天地图瓦片加载失败: {e}")


def _threshold_limits(db: Session, site_id: int) -> dict[str, float]:
    """取每个因子的最严格正阈值, 用于地图超标倍数分级。"""
    rows = (db.query(FactorDictionary.factor_code, FactorDictionary.factor_name,
                     ThresholdRule.threshold_max, ThresholdRule.threshold_min)
            .join(ThresholdRule, ThresholdRule.factor_id == FactorDictionary.id)
            .join(Measurement, Measurement.factor_id == FactorDictionary.id)
            .filter(Measurement.site_id == site_id)
            .all())
    limits: dict[str, float] = {}
    for code, name, tmax, tmin in rows:
        vals = [float(v) for v in (tmax, tmin) if v is not None and float(v) > 0]
        if not vals:
            continue
        val = min(vals)
        for key in (code, name):
            if key and (key not in limits or val < limits[key]):
                limits[key] = val
    return limits


def _risk(exceedance: float | None) -> str:
    if exceedance is None:
        return "unknown"
    if exceedance >= 5:
        return "high"
    if exceedance >= 1:
        return "medium"
    return "low"


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
    limits = _threshold_limits(db, site_id)
    pollutants = []
    pollutant_seen = set()
    by_point: dict[int, list[dict]] = {}
    for m, fd, sp in rows:
        if fd.factor_code not in pollutant_seen:
            pollutants.append({
                "factor_code": fd.factor_code,
                "factor_name": fd.factor_name,
                "unit": m.unit or fd.default_unit,
                "category": fd.level1_category,
            })
            pollutant_seen.add(fd.factor_code)
        if factor and factor not in (fd.factor_code, fd.factor_name):
            continue
        limit = limits.get(fd.factor_code) or limits.get(fd.factor_name)
        exceedance = None
        if limit and m.value is not None:
            exceedance = float(m.value) / limit
        by_point.setdefault(sp.id, []).append({
            "factor_code": fd.factor_code,
            "factor_name": fd.factor_name,
            "value": m.value,
            "unit": m.unit or fd.default_unit,
            "threshold": limit,
            "exceedance": exceedance,
            "risk_level": _risk(exceedance),
        })

    features = []
    for p in points:
        measurements = by_point.get(p.id, [])
        if measurements:
            selected = max(measurements, key=lambda x: x["exceedance"] if x["exceedance"] is not None else -1)
            risk_level = selected["risk_level"]
        else:
            selected = None
            risk_level = "unknown"
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
                "measurements": measurements[:20],
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
            {"risk_level": "high", "label": "高风险(超标≥5倍)", "color": "#dc2626"},
            {"risk_level": "medium", "label": "超标(1-5倍)", "color": "#f59e0b"},
            {"risk_level": "low", "label": "未超标", "color": "#16a34a"},
            {"risk_level": "unknown", "label": "无阈值或无数据", "color": "#64748b"},
        ],
        "geojson": {"type": "FeatureCollection", "features": features},
    }
