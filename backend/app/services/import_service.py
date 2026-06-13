"""数据导入: Excel/CSV 解析 + 字段映射。

解析层仅依赖 pandas, 不触 DB, 便于独立测试。
入库由 ingest_service 完成。
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

MAPPINGS_DIR = os.path.join(os.path.dirname(__file__), "mappings")


def load_mapping(mapping_id: str) -> dict:
    """按 mapping_id 或文件名加载映射配置。"""
    path = mapping_id
    if not os.path.exists(path):
        path = os.path.join(MAPPINGS_DIR, mapping_id)
        if not path.endswith(".json"):
            path += ".json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class ParsedMeasurement:
    factor_code: str
    factor_name: str
    value: float | None
    unit: str | None
    level1_category: str | None = None
    factor_type: str | None = None
    in_kb: bool = True


@dataclass
class ParsedPoint:
    point_code: str
    longitude: float | None = None
    latitude: float | None = None
    region: str | None = None
    depth_top_cm: float | None = None
    depth_bottom_cm: float | None = None
    soil_type: str | None = None
    remark: str | None = None
    measurements: list[ParsedMeasurement] = field(default_factory=list)


@dataclass
class ParsedSite:
    site: dict
    points: list[ParsedPoint]
    factor_defs: list[dict]
    source_file: str

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def n_measurements(self) -> int:
        return sum(len(p.measurements) for p in self.points)


def _to_float(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_str(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    s = str(v).strip()
    return s or None


def read_table(path: str, mapping: dict) -> pd.DataFrame:
    sheet = mapping.get("sheet")
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path, sheet_name=sheet if sheet else 0)


def parse(path: str, mapping: dict) -> ParsedSite:
    df = read_table(path, mapping)
    df.columns = [str(c).strip() for c in df.columns]

    pc = mapping["point_columns"]
    factor_cols = mapping["factor_columns"]
    points: list[ParsedPoint] = []
    lons, lats = [], []

    for _, row in df.iterrows():
        pcode = _to_str(row.get(pc["point_code"])) if pc.get("point_code") in df.columns else None
        if not pcode:
            continue
        lon = _to_float(row.get(pc.get("longitude"))) if pc.get("longitude") in df.columns else None
        lat = _to_float(row.get(pc.get("latitude"))) if pc.get("latitude") in df.columns else None
        if lon is not None:
            lons.append(lon)
        if lat is not None:
            lats.append(lat)
        p = ParsedPoint(
            point_code=pcode,
            longitude=lon,
            latitude=lat,
            region=_to_str(row.get(pc.get("region"))) if pc.get("region") in df.columns else None,
            depth_top_cm=_to_float(row.get(pc.get("depth_top_cm"))) if pc.get("depth_top_cm") in df.columns else None,
            depth_bottom_cm=_to_float(row.get(pc.get("depth_bottom_cm"))) if pc.get("depth_bottom_cm") in df.columns else None,
            soil_type=_to_str(row.get(pc.get("soil_type"))) if pc.get("soil_type") in df.columns else None,
            remark=_to_str(row.get(pc.get("remark"))) if pc.get("remark") in df.columns else None,
        )
        for fc in factor_cols:
            col = fc["column"]
            if col not in df.columns:
                continue
            p.measurements.append(ParsedMeasurement(
                factor_code=fc["factor_code"],
                factor_name=fc.get("factor_name", fc["factor_code"]),
                value=_to_float(row.get(col)),
                unit=fc.get("unit"),
                level1_category=fc.get("level1_category"),
                factor_type=fc.get("factor_type"),
                in_kb=fc.get("in_kb", True),
            ))
        points.append(p)

    site = dict(mapping.get("site", {}))
    if lons and lats and site.get("longitude") is None:
        site["longitude"] = round(sum(lons) / len(lons), 6)
        site["latitude"] = round(sum(lats) / len(lats), 6)

    factor_defs = [{
        "factor_code": fc["factor_code"],
        "factor_name": fc.get("factor_name", fc["factor_code"]),
        "level1_category": fc.get("level1_category"),
        "factor_type": fc.get("factor_type"),
        "default_unit": fc.get("unit"),
        "in_kb": fc.get("in_kb", True),
    } for fc in factor_cols]

    return ParsedSite(site=site, points=points, factor_defs=factor_defs,
                      source_file=os.path.basename(path))
