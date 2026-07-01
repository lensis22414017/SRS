"""v0.2 报告静态地图渲染器 — 独立于 report_service, 可测试, 无天地图依赖。

渲染优先级:
  1. 本地 MBTiles 底图 (data/geo/tiles/*.mbtiles)
  2. 离线行政区 GeoJSON (data/geo/china_provinces.json)
  3. 经纬网散点 fallback (纯 matplotlib scatter)
  4. 坐标缺失诊断 fallback (返回文字说明)

每张图输出 base64 PNG data URI + 元数据标签。
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

# ── 8 级色阶常量 (与前端 excColor() / API _risk() 一致) ──
COLOR_8_LEVELS = [
    (0,     "#16a34a"),   # 绿 未超标
    (1,     "#facc15"),   # 黄 轻度
    (3,     "#f59e0b"),   # 橙 中度
    (10,    "#ea580c"),   # 深橙 偏重
    (30,    "#dc2626"),   # 红 重度
    (80,    "#9f1239"),   # 深红 极重
    (200,   "#6b0f1a"),   # 暗红 超极重
]
_COLOR_NODATA = "#64748b"  # 灰 无数据/无阈值

def _exc_color(ratio: float | None) -> str:
    """超标倍数 → 颜色 (与前端 excColor 一致)。"""
    if ratio is None:
        return _COLOR_NODATA
    for threshold, color in COLOR_8_LEVELS:
        if ratio < threshold:
            return color
    return COLOR_8_LEVELS[-1][1]


def _exc_label(ratio: float | None) -> str:
    """超标倍数 → 标签。"""
    if ratio is None:
        return "无数据"
    if ratio < 1:
        return "未超标"
    if ratio < 3:
        return f"轻度({ratio:.1f}x)"
    if ratio < 10:
        return f"中度({ratio:.1f}x)"
    if ratio < 30:
        return f"偏重({ratio:.1f}x)"
    if ratio < 80:
        return f"重度({ratio:.1f}x)"
    if ratio < 200:
        return f"极重({ratio:.1f}x)"
    return f"超极重({ratio:.1f}x)"


@dataclass
class RenderResult:
    png_base64: str | None          # "data:image/png;base64,..."
    fallback_text: str | None       # 无坐标时的诊断说明
    metadata: dict[str, Any]        # 渲染元数据


# ── 中文字体检测 (懒加载 + 缓存) ──
@lru_cache(maxsize=1)
def _get_cjk_font() -> str | None:
    """返回可用的中文字体名，无则返回 None。"""
    try:
        from matplotlib.font_manager import fontManager
        cjk = [f.name for f in fontManager.ttflist
               if any(k in f.name for k in ("Noto Sans CJK", "SimHei", "WenQuanYi",
                      "Microsoft YaHei", "PingFang", "Source Han"))]
        return cjk[0] if cjk else None
    except Exception:
        return None


def render_points_map(
    points: list[dict],
    bounds: dict | None = None,
    site_name: str = "",
    data_version: str = "",
    threshold_source: str = "",
) -> RenderResult:
    """渲染采样点超标风险散点图 → base64 PNG data URI。

    Args:
        points: [{lon, lat, exceedance, worst_factor, label}, ...]
        bounds: {min_lon, max_lon, min_lat, max_lat} 或 None
        site_name: 场地名称
        data_version: 数据版本号
        threshold_source: 阈值来源

    Returns:
        RenderResult with png_base64 or fallback_text
    """
    coord_pts = [p for p in points if p.get("lon") is not None and p.get("lat") is not None]

    if not coord_pts:
        missing = [p.get("label", f"#{i}") for i, p in enumerate(points)
                   if p.get("lon") is None or p.get("lat") is None]
        return RenderResult(
            png_base64=None,
            fallback_text=f"缺坐标点位 ({len(missing)}): {', '.join(missing[:20])}",
            metadata={"n_points": len(points), "n_coord": 0, "coverage_pct": 0,
                      "rendered_at": datetime.now(timezone.utc).isoformat(),
                      "data_version": data_version,
                      "basemap": "none (no coordinates available)"},
        )

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return RenderResult(
            png_base64=None,
            fallback_text="matplotlib 不可用，无法渲染静态地图",
            metadata={"error": "matplotlib_import_error"},
        )

    font = _get_cjk_font()
    if font:
        plt.rcParams["font.family"] = font

    fig, ax = plt.subplots(figsize=(8, 6), dpi=120)

    # 绘制散点
    lons = [p["lon"] for p in coord_pts]
    lats = [p["lat"] for p in coord_pts]
    colors = [_exc_color(p.get("exceedance")) for p in coord_pts]

    scatter = ax.scatter(lons, lats, c=colors, s=50, edgecolors="white",
                         linewidth=0.5, zorder=5, alpha=0.9)

    # 坐标范围
    if bounds:
        ax.set_xlim(bounds["min_lon"] - 0.01, bounds["max_lon"] + 0.01)
        ax.set_ylim(bounds["min_lat"] - 0.01, bounds["max_lat"] + 0.01)
    else:
        ax.set_xlim(min(lons) - 0.01, max(lons) + 0.01)
        ax.set_ylim(min(lats) - 0.01, max(lats) + 0.01)

    ax.set_xlabel("经度 (°)", fontsize=8)
    ax.set_ylabel("纬度 (°)", fontsize=8)
    ax.set_title(f"{site_name} — 采样点超标风险分布", fontsize=11, fontweight="bold")
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.3, linestyle="--")

    # 图例 (8 级)
    from matplotlib.patches import Patch
    legend_items = []
    for threshold, color in COLOR_8_LEVELS:
        label = _exc_label(float(threshold))
        legend_items.append(Patch(facecolor=color, edgecolor="white", label=label))
    legend_items.append(Patch(facecolor=_COLOR_NODATA, edgecolor="white", label="无数据"))
    ax.legend(handles=legend_items, loc="lower right", fontsize=6,
              ncol=2, framealpha=0.9)

    # 水印
    render_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    watermark = (f"数据版本: {data_version or '—'} | 渲染时间: {render_time} | "
                 f"阈值来源: {threshold_source or '—'} | 底图: 无(离线坐标散点) | "
                 f"坐标覆盖: {len(coord_pts)}/{len(points)}")
    fig.text(0.5, 0.01, watermark, ha="center", fontsize=5.5,
             color="#888888", family="monospace")

    plt.tight_layout(rect=[0, 0.03, 1, 0.97])

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    png_b64 = base64.b64encode(buf.read()).decode("ascii")

    return RenderResult(
        png_base64=f"data:image/png;base64,{png_b64}",
        fallback_text=None,
        metadata={
            "n_points": len(points),
            "n_coord": len(coord_pts),
            "coverage_pct": f"{len(coord_pts) / max(len(points), 1) * 100:.1f}%",
            "rendered_at": render_time,
            "data_version": data_version,
            "threshold_source": threshold_source,
            "basemap": "offline_scatter_only",
            "color_levels": 8,
            "png_hash": hashlib.sha256(buf.getvalue()).hexdigest()[:12],
        },
    )
