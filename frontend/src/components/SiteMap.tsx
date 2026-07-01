import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../api/client";
import { POLLUTION_TYPE, POLLUTION_LABEL } from "../theme/palette";

interface SitePoint {
  id?: number;
  name?: string;
  point_code?: string;
  longitude: number | null;
  latitude: number | null;
  pollution_type?: string;
  status?: string;
  color?: string;   // 裴总 P1-5a: 直接指定颜色(优先于 status), 与污染类型语义色一致
  value?: number | null;
  ph?: number | null;
  top_factor?: string;
  max_exceedance?: number | null;
  risk_level?: string;
  n_exceed?: number;
  onClick?: () => void;
}

interface MapLayerData {
  geojson: { features: any[] };
  tile_proxy?: { enabled: boolean };
  legend?: { risk_level: string; label: string; color: string }[];
}

type MapMode = "vector" | "satellite";

const STATUS_COLOR: Record<string, string> = {
  danger: "#dc2626", warning: "#f59e0b", success: "#16a34a", info: "#3b82f6",
  high: "#dc2626", medium: "#f59e0b", low: "#16a34a", unknown: "#64748b",
};

// 超标倍数 → 连续色阶(绿→黄→橙→红→深红→暗红)。
// 离散 risk 仅 high/medium/low 三档, 重度污染场地全部 high 无层次;
// 改用 exceedance 值分桶着色, 让 42倍 vs 497倍 的点颜色明显不同。
function excColor(exc: number | null | undefined): string {
  if (exc == null) return "#64748b";   // 灰 无阈值/无数据
  if (exc < 1)   return "#16a34a";      // 绿 未超标
  if (exc < 3)   return "#facc15";      // 黄 轻度
  if (exc < 10)  return "#f59e0b";      // 橙 中度
  if (exc < 30)  return "#ea580c";      // 深橙 偏重
  if (exc < 80)  return "#dc2626";      // 红 重度
  if (exc < 200) return "#9f1239";      // 深红 极重
  return "#6b0f1a";                      // 暗红 超极重
}

// 凸包(Andrew monotone chain) — 输入 [lng,lat][], 返回凸包顶点 [lng,lat][]。
// 用于在采样点最外围画虚线轮廓, 体现采样范围边界。
function convexHull(pts: [number, number][]): [number, number][] {
  if (pts.length < 3) return pts;
  const p = [...pts].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o: [number, number], a: [number, number], b: [number, number]) =>
    (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower: [number, number][] = [];
  for (const pt of p) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pt) <= 0) lower.pop();
    lower.push(pt);
  }
  const upper: [number, number][] = [];
  for (let i = p.length - 1; i >= 0; i--) {
    const pt = p[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pt) <= 0) upper.pop();
    upper.push(pt);
  }
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}

// 高德 hybrid 瓦片 — 卫星影像 + 中文注记, 通过后端代理访问(无 IP 白名单, 换电脑/换网络均可用)
const GAODE_PROXY = "/api/v1/map/tile/gaode/{z}/{x}/{y}";

// 行政区矢量底图样式 — 按模式动态调整
const ADMIN_STYLE_VECTOR: Record<string, L.PathOptions> = {
  province:   { color: "#0f3d6e", weight: 1.2, fillOpacity: 0.04, opacity: 1 },
  prefecture: { color: "#1d6fb8", weight: 0.8, fillOpacity: 0.06, opacity: 1 },
  county:     { color: "#64748b", weight: 0.5, fillOpacity: 0.05, opacity: 1 },
};
const ADMIN_STYLE_SATELLITE: Record<string, L.PathOptions> = {
  province:   { color: "#ffffff", weight: 1.0, fillOpacity: 0, opacity: 0.6 },
  prefecture: { color: "#e2e8f0", weight: 0.7, fillOpacity: 0, opacity: 0.5 },
  county:     { color: "#cbd5e1", weight: 0.4, fillOpacity: 0, opacity: 0.4 },
};

// 缩放层级 → 行政区级别(三级金字塔懒加载)
function zoomToLevel(z: number): "province" | "prefecture" | "county" {
  if (z <= 5) return "province";
  if (z <= 8) return "prefecture";
  return "county";
}

export default function SiteMap({
  sites, layerData, height = 400, zoom = 5, onMarkerClick, scope = "overview",
}: {
  sites: SitePoint[]; layerData?: MapLayerData; height?: number; zoom?: number;
  onMarkerClick?: (s: SitePoint) => void;
  scope?: "overview" | "site";  // 裴总 P1-5b: overview=首页全国地图; site=场地详情(不加载全国省界)
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const adminLayersRef = useRef<{ gl: L.GeoJSON; level: string }[]>([]);
  const loadedAdcodeRef = useRef<Set<string>>(new Set());
  const geoIndexRef = useRef<any>(null);
  const gaodeTileRef = useRef<L.TileLayer | null>(null);
  const tileErrorCountRef = useRef(0);

  const [mapMode, setMapMode] = useState<MapMode>("vector");
  const [tileError, setTileError] = useState(false);
  const [curLevel, setCurLevel] = useState(zoomToLevel(zoom));

  const layerFeatures = layerData?.geojson?.features || [];
  const hasCoords = layerFeatures.length
    ? layerFeatures.some((f) => f.geometry?.coordinates?.[0] != null && f.geometry?.coordinates?.[1] != null)
    : sites.some((s) => s.longitude != null && s.latitude != null);

  // ── 行政区矢量底图渲染 ──────────────────────────────────────────
  const renderAdminLayer = (geojson: any, level: string, mode: MapMode) => {
    const map = mapRef.current;
    if (!map || !geojson?.features) return;
    const style = mode === "satellite" ? ADMIN_STYLE_SATELLITE[level] : ADMIN_STYLE_VECTOR[level];
    const gl = L.geoJSON(geojson, {
      style,
      onEachFeature: (feat, lyr) => {
        const name = feat.properties?.name || "";
        if (name) lyr.bindTooltip(name, { sticky: true });
      },
    }).addTo(map);
    adminLayersRef.current.push({ gl, level });
  };

  const loadBoundaries = async (level: "province" | "prefecture" | "county", adcode?: number) => {
    const key = `${level}:${adcode ?? 0}`;
    if (loadedAdcodeRef.current.has(key)) return;
    loadedAdcodeRef.current.add(key);
    try {
      const gj = await api.geoBoundaries(level, adcode);
      renderAdminLayer(gj, level, mapMode);
    } catch { /* 离线数据缺失则跳过 */ }
  };

  const resolveAdcode = async (lon: number, lat: number, level: "province" | "prefecture"): Promise<number | null> => {
    try {
      if (!geoIndexRef.current) geoIndexRef.current = await api.geoIndex();
      const idx = geoIndexRef.current;
      const pool = level === "province" ? idx.provinces : Object.values(idx.prefectures);
      for (const it of pool as any[]) {
        const b = it.bbox;
        if (b && lon >= b[0] && lon <= b[2] && lat >= b[1] && lat <= b[3]) return it.adcode;
      }
    } catch { /* ignore */ }
    return null;
  };

  // ── 地图初始化 ─────────────────────────────────────────────────
  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    // 裴总 P1-5b: site=场地详情聚焦到该场地, 不加载全国省界(避免"全国数据"视觉混淆);
    // overview=首页全国地图才加载全国省界
    const firstPt = sites.find((s) => s.longitude != null && s.latitude != null);
    const initCenter: [number, number] = scope === "site" && firstPt
      ? [firstPt.latitude as number, firstPt.longitude as number]
      : [34, 104];
    const map = L.map(ref.current, { center: initCenter, zoom, minZoom: 3, maxZoom: 18 });
    mapRef.current = map;

    if (scope !== "site") {
      // 默认矢量底图: 全国省界, 完全离线, 无需任何 key
      loadBoundaries("province");
    }

    // 缩放/平移 → 行政区三级懒加载
    const onZoomMove = () => {
      const z = map.getZoom();
      const level = zoomToLevel(z);
      setCurLevel(level);
      if (level === "province") return;
      const ctr = map.getCenter();
      const parentLevel = level === "prefecture" ? "province" : "prefecture";
      resolveAdcode(ctr.lng, ctr.lat, parentLevel).then((ac) => {
        if (ac) loadBoundaries(level, ac);
      });
    };
    map.on("zoomend", onZoomMove);
    map.on("moveend", onZoomMove);

    setTimeout(() => map.invalidateSize(), 200);
    return () => {
      map.remove();
      mapRef.current = null;
      adminLayersRef.current = [];
      gaodeTileRef.current = null;
    };
  }, []);

  // ── 底图模式切换: vector ↔ satellite ──────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (mapMode === "satellite") {
      // 1) 加载高德瓦片(如未加载)
      if (!gaodeTileRef.current) {
        const tileLayer = L.tileLayer(GAODE_PROXY, {
          maxZoom: 18,
          opacity: 1,
          attribution: '高德地图 &copy; AutoNavi',
          // 瓦片插入到 tilePane(最底层), GeoJSON 和标记自动在上方
        });
        tileLayer.on("tileerror", () => {
          tileErrorCountRef.current += 1;
          setTileError(true);
          if (tileErrorCountRef.current >= 3) {
            setMapMode("vector");
            tileErrorCountRef.current = 0;
          }
        });
        tileLayer.on("tileload", () => { tileErrorCountRef.current = 0; setTileError(false); });
        tileLayer.addTo(map);
        gaodeTileRef.current = tileLayer;
      } else {
        gaodeTileRef.current.addTo(map);
      }
      // 2) 行政区边界改为白色轮廓(不遮挡卫星影像)
      adminLayersRef.current.forEach(({ gl, level }) => {
        gl.setStyle(ADMIN_STYLE_SATELLITE[level] ?? ADMIN_STYLE_SATELLITE.county);
      });
    } else {
      // 矢量模式: 移除高德瓦片
      if (gaodeTileRef.current) {
        gaodeTileRef.current.remove();
      }
      setTileError(false);
      tileErrorCountRef.current = 0;
      // 恢复行政区原始彩色样式
      adminLayersRef.current.forEach(({ gl, level }) => {
        gl.setStyle(ADMIN_STYLE_VECTOR[level] ?? ADMIN_STYLE_VECTOR.county);
      });
    }
  }, [mapMode]);

  // ── 采样点/场地标记渲染 ────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const layer = L.layerGroup().addTo(map);
    const pts: L.LatLng[] = [];
    const lngLats: [number, number][] = [];

    if (layerFeatures.length) {
      layerFeatures.forEach((f) => {
        if (f.geometry?.type !== "Point") return;  // 仅采样点Point参与凸包(过滤行政Polygon,防layerData混入致凸包失效,问题1防御)
        const [lon, lat] = f.geometry?.coordinates || [];
        if (lon == null || lat == null) return;
        const props = f.properties || {};
        const selected = props.selected || {};
        const ll = L.latLng(lat, lon);
        pts.push(ll);
        lngLats.push([lon, lat]);
        const color = excColor(selected.exceedance);
        const title = esc(props.point_code || "点位");
        const value = selected.value == null ? "—" : Number(selected.value).toFixed(3);
        const exceed = selected.exceedance == null ? "无阈值" : `${Number(selected.exceedance).toFixed(2)} 倍`;
        L.circleMarker(ll, { radius: 8, color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.92 })
          .bindPopup(
            `<b>${title}</b><br/>` +
            `因子: ${esc(selected.factor_name || selected.factor_code || "—")}<br/>` +
            `浓度: ${value} ${esc(selected.unit || "")}<br/>` +
            `超标倍数: ${exceed}<br/>` +
            `风险: ${esc(props.risk_level || "unknown")}`
          )
          .addTo(layer);
      });
    } else {
      sites.forEach((s) => {
        if (s.longitude == null || s.latitude == null) return;
        const ll = L.latLng(s.latitude, s.longitude);
        pts.push(ll);
        lngLats.push([s.longitude!, s.latitude!]);
        const color = s.color || POLLUTION_TYPE[s.pollution_type || ""] || STATUS_COLOR[s.status || "danger"] || "#dc2626";
        const ptLabel = POLLUTION_LABEL[s.pollution_type || ""] || s.pollution_type || "—";
        const exceedInfo = s.max_exceedance != null ? `${Number(s.max_exceedance).toFixed(1)} 倍` : (s.n_exceed != null ? `${s.n_exceed} 条` : "—");
        const popupHtml = [
          `<b>${esc(s.name || s.point_code || "点位")}</b>`,
          `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};margin-right:4px;"></span> ${ptLabel}`,
          `超标: ${exceedInfo}`,
          s.top_factor ? `主要因子: ${esc(s.top_factor)}` : "",
          s.ph != null ? `pH: ${s.ph}` : "",
          `坐标: ${s.latitude?.toFixed?.(4) ?? "—"}, ${s.longitude?.toFixed?.(4) ?? "—"}`,
          s.id ? `<a href="/sites/${s.id}" style="font-size:12px;">进入场地详情 →</a>` : "",
        ].filter(Boolean).join("<br/>");
        const mk = L.circleMarker(ll, { radius: 8, color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.9 })
          .bindPopup(popupHtml)
          .addTo(layer);
        if (onMarkerClick) mk.on("click", () => onMarkerClick(s));
      });
    }

    // 采样点外围凸包虚线轮廓 + 顶点经纬度标注(体现采样范围边界与坐标)
    if (lngLats.length >= 3) {
      const hull = convexHull(lngLats);
      if (hull.length >= 3) {
        L.polygon(hull.map(([lon, lat]) => [lat, lon] as [number, number]), {
          color: "#0f3d6e", weight: 2, dashArray: "6 6", fillOpacity: 0, opacity: 0.75,
        }).addTo(layer);
        hull.forEach(([lon, lat]) => {
          L.marker([lat, lon], {
            interactive: false,
            icon: L.divIcon({
              html: `<span style="font-size:10px;color:#0f3d6e;background:rgba(255,255,255,.88);padding:1px 4px;border-radius:3px;border:1px solid #0f3d6e55;white-space:nowrap;">${lon.toFixed(3)}, ${lat.toFixed(3)}</span>`,
              className: "hull-vertex", iconSize: [64, 16], iconAnchor: [32, 8],
            }),
          }).addTo(layer);
        });
      }
    }

    if (pts.length) {
      map.fitBounds(L.latLngBounds(pts).pad(0.3), { maxZoom: 13 });
      setTimeout(() => map.invalidateSize(), 100);
    }
    return () => { layer.remove(); };
  }, [sites, layerData]);

  // ── 渲染 ───────────────────────────────────────────────────────
  const overlay = (text: string) => (
    <div style={{
      position: "absolute", inset: 0, display: "flex", alignItems: "center",
      justifyContent: "center", background: "rgba(232,238,243,0.85)", borderRadius: 8,
      color: "#64748b", fontSize: 13, textAlign: "center", padding: 16, zIndex: 500,
    }}>
      {text}
    </div>
  );

  return (
    <div style={{ position: "relative", aspectRatio: "4 / 3", width: "100%" }}>
      {/* 地图画布 — inset:0 填满 4:3 容器; height prop 已弃用, 由 aspectRatio 控制(裴总要求 4:3 比例) */}
      <div ref={ref} style={{ position: "absolute", inset: 0, borderRadius: 8, background: "#e8eef3" }} />

      {/* 遮罩提示 */}
      {!hasCoords && (
  <div style={{
    position: "absolute", inset: 0, display: "flex", alignItems: "center",
    justifyContent: "center", background: "rgba(248,249,251,0.95)", borderRadius: 8,
    zIndex: 500,
  }}>
    <div style={{ textAlign: "center", padding: 32 }}>
      <div style={{ fontSize: 48, color: "#c0c4cc", marginBottom: 12, lineHeight: 1 }}>📍</div>
      <div style={{ fontSize: 15, fontWeight: 600, color: "#475569", marginBottom: 6 }}>无可用坐标</div>
      <div style={{ fontSize: 12, color: "#8899aa", maxWidth: 320, lineHeight: 1.6 }}>
        该场地采样点缺少经纬度信息，无法在地图上展示点位。<br/>
        请在数据导入时正确填写经度(longitude)和纬度(latitude)字段。
      </div>
    </div>
  </div>
)}
      {hasCoords && mapMode === "satellite" && tileError &&
        overlay("卫星影像加载失败（网络不可达或高德服务异常）。已降级为矢量底图，采样点正常显示。")}

      {/* 底图切换器 — 右上角 */}
      <div style={{
        position: "absolute", top: 10, right: 10, zIndex: 500,
        display: "flex", borderRadius: 6, overflow: "hidden",
        boxShadow: "0 2px 8px rgba(0,0,0,.25)", border: "1px solid #d9e2ec",
      }}>
        {(["vector", "satellite"] as MapMode[]).map((mode) => (
          <button
            key={mode}
            onClick={() => setMapMode(mode)}
            title={mode === "vector" ? "矢量行政区底图（离线，默认）" : "卫星影像+中文标注（高德，在线）"}
            style={{
              padding: "5px 12px", fontSize: 12, cursor: "pointer", border: "none",
              background: mapMode === mode ? "#0f3d6e" : "#fff",
              color: mapMode === mode ? "#fff" : "#374151",
              fontWeight: mapMode === mode ? 600 : 400,
              transition: "background 0.15s",
            }}
          >
            {mode === "vector" ? "矢量底图" : "卫星影像"}
          </button>
        ))}
      </div>

      {/* 层级指示 — 右下角 */}
      <div style={{
        position: "absolute", right: 8, bottom: 8,
        background: "rgba(255,255,255,0.88)", padding: "2px 8px",
        borderRadius: 4, fontSize: 11, color: "#64748b", zIndex: 400,
      }}>
        {mapMode === "satellite" ? "高德影像" : "矢量底图"} ·{" "}
        {curLevel === "province" ? "省级" : curLevel === "prefecture" ? "地市级" : "县级"}
      </div>

      {/* 图例 — 左下角 */}
      {hasCoords && layerData?.legend?.length ? (
        <Legend items={layerData.legend} />
      ) : hasCoords ? (
        <Legend items={[
          { risk_level: "heavy_metal", label: "重金属污染", color: POLLUTION_TYPE.heavy_metal },
          { risk_level: "organic", label: "有机污染", color: POLLUTION_TYPE.organic },
          { risk_level: "composite", label: "复合污染", color: POLLUTION_TYPE.composite },
        ]} />
      ) : null}
    </div>
  );
}

function Legend({ items }: { items: { risk_level: string; label: string; color: string }[] }) {
  return (
    <div style={{
      position: "absolute", left: 12, bottom: 12, zIndex: 450,
      background: "rgba(255,255,255,.94)", border: "1px solid #d9e2ec",
      borderRadius: 6, padding: "8px 10px", fontSize: 12,
      boxShadow: "0 2px 8px rgba(15,61,110,.15)",
    }}>
      {items.map((i) => (
        <div key={i.risk_level} style={{ display: "flex", alignItems: "center", gap: 6, margin: "3px 0" }}>
          <span style={{ width: 10, height: 10, borderRadius: 999, background: i.color, display: "inline-block" }} />
          <span>{i.label}</span>
        </div>
      ))}
    </div>
  );
}

function esc(v: any) {
  return String(v ?? "").replace(/[&<>"']/g, (s) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[s] || s));
}
