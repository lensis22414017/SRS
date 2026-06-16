import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api } from "../api/client";

interface SitePoint {
  id?: number;
  name?: string;
  point_code?: string;
  longitude: number | null;
  latitude: number | null;
  pollution_type?: string;
  status?: string;
  value?: number | null;
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
  sites, layerData, height = 400, zoom = 5, onMarkerClick,
}: {
  sites: SitePoint[]; layerData?: MapLayerData; height?: number; zoom?: number;
  onMarkerClick?: (s: SitePoint) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const adminLayersRef = useRef<{ gl: L.GeoJSON; level: string }[]>([]);
  const loadedAdcodeRef = useRef<Set<string>>(new Set());
  const geoIndexRef = useRef<any>(null);
  const gaodeTileRef = useRef<L.TileLayer | null>(null);

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
    const map = L.map(ref.current, { center: [34, 104], zoom, minZoom: 3, maxZoom: 18 });
    mapRef.current = map;

    // 默认矢量底图: 全国省界, 完全离线, 无需任何 key
    loadBoundaries("province");

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
        tileLayer.on("tileerror", () => setTileError(true));
        tileLayer.on("tileload", () => setTileError(false));
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

    if (layerFeatures.length) {
      layerFeatures.forEach((f) => {
        const [lon, lat] = f.geometry?.coordinates || [];
        if (lon == null || lat == null) return;
        const props = f.properties || {};
        const selected = props.selected || {};
        const ll = L.latLng(lat, lon);
        pts.push(ll);
        const color = STATUS_COLOR[props.risk_level || "unknown"] || "#64748b";
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
        const color = STATUS_COLOR[s.status || "danger"] || "#dc2626";
        const mk = L.circleMarker(ll, { radius: 8, color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.9 })
          .bindPopup(`<b>${esc(s.name || s.point_code || "点位")}</b><br/>${esc(s.pollution_type || "")}<br/>${s.latitude}, ${s.longitude}`)
          .addTo(layer);
        if (onMarkerClick) mk.on("click", () => onMarkerClick(s));
      });
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
    <div style={{ position: "relative", height, width: "100%" }}>
      {/* 地图画布 */}
      <div ref={ref} style={{ height, width: "100%", borderRadius: 8, background: "#e8eef3" }} />

      {/* 遮罩提示 */}
      {!hasCoords && overlay("当前无可用坐标点位：该场地采样点缺少经纬度，无法在地图上展示。")}
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
            {mode === "vector" ? "🗺 矢量" : "🛰 影像"}
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
      {hasCoords && layerData?.legend?.length ? <Legend items={layerData.legend} /> : null}
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
