import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

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

const TK = import.meta.env.VITE_TIANDITU_KEY || "";
const STATUS_COLOR: Record<string, string> = {
  danger: "#dc2626", warning: "#f59e0b", success: "#16a34a", info: "#3b82f6",
};

export default function SiteMap({
  sites, height = 400, zoom = 5, onMarkerClick,
}: {
  sites: SitePoint[]; height?: number; zoom?: number;
  onMarkerClick?: (s: SitePoint) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const [tileError, setTileError] = useState(false);
  const hasCoords = sites.some((s) => s.longitude != null && s.latitude != null);

  useEffect(() => {
    if (!ref.current || mapRef.current) return;
    const map = L.map(ref.current, { center: [34, 104], zoom });
    mapRef.current = map;

    let base: L.TileLayer;
    if (TK) {
      base = L.tileLayer(
        `https://t{s}.tianditu.gov.cn/img_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=img&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TK}`,
        { subdomains: ["0", "1", "2", "3", "4", "5", "6", "7"], maxZoom: 18, attribution: "天地图" }
      ).addTo(map);
      L.tileLayer(
        `https://t{s}.tianditu.gov.cn/cia_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=cia&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&tk=${TK}`,
        { subdomains: ["0", "1", "2", "3", "4", "5", "6", "7"], maxZoom: 18 }
      ).addTo(map);
    } else {
      base = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18, attribution: "© OpenStreetMap（未配置天地图 key）",
      }).addTo(map);
    }
    // 瓦片加载失败 -> 显示错误态(天地图 key 域名白名单/网络问题)
    base.on("tileerror", () => setTileError(true));
    base.on("tileload", () => setTileError(false));
    // 容器尺寸在布局完成后才确定, 延迟刷新避免灰屏
    setTimeout(() => map.invalidateSize(), 200);
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const layer = L.layerGroup().addTo(map);
    const pts: L.LatLng[] = [];
    sites.forEach((s) => {
      if (s.longitude == null || s.latitude == null) return;
      const ll = L.latLng(s.latitude, s.longitude);
      pts.push(ll);
      const color = STATUS_COLOR[s.status || "danger"] || "#dc2626";
      const mk = L.circleMarker(ll, { radius: 8, color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.9 })
        .bindPopup(`<b>${s.name || s.point_code || "点位"}</b><br/>${s.pollution_type || ""}<br/>${s.latitude}, ${s.longitude}`)
        .addTo(layer);
      if (onMarkerClick) mk.on("click", () => onMarkerClick(s));
    });
    if (pts.length) {
      map.fitBounds(L.latLngBounds(pts).pad(0.3), { maxZoom: 13 });
      setTimeout(() => map.invalidateSize(), 100);
    }
    return () => { layer.remove(); };
  }, [sites]);

  const overlay = (text: string) => (
    <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center",
      justifyContent: "center", background: "rgba(232,238,243,0.85)", borderRadius: 8,
      color: "#64748b", fontSize: 13, textAlign: "center", padding: 16, zIndex: 500 }}>
      {text}
    </div>
  );
  return (
    <div style={{ position: "relative", height, width: "100%" }}>
      <div ref={ref} style={{ height, width: "100%", borderRadius: 8, background: "#e8eef3" }} />
      {!hasCoords && overlay("当前无可用坐标点位：该场地采样点缺少经纬度，无法在地图上展示。")}
      {hasCoords && tileError && overlay("底图瓦片加载失败：请检查网络，或在天地图控制台为当前域名/127.0.0.1 配置 key 白名单。点位坐标已就绪。")}
    </div>
  );
}
