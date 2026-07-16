import { useEffect, useState, useMemo, useCallback } from "react";
import { App, Button, Tag, Spin, Typography, Tooltip, Empty } from "antd";
import {
  RollbackOutlined, DatabaseOutlined, WarningOutlined,
  ApartmentOutlined, FileTextOutlined, ClockCircleOutlined,
  EnvironmentOutlined, CheckCircleOutlined, DashboardOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import dayjs from "dayjs";
import { api } from "../api/client";
import SiteMap from "../components/SiteMap";
import { POLLUTION_TYPE, POLLUTION_LABEL, POLLUTION_TYPE_BG } from "../theme/palette";
import { SVG_OPTS } from "../theme/echarts";
import styles from "./DashboardScreen.module.css";

const { Text } = Typography;

// ── 暗色图表通用配置 ─────────────────────────────────────────
const DARK_TEXT = "#8899bb";
const DARK_AXIS_LINE = "rgba(255,255,255,0.06)";
const DARK_SPLIT = "rgba(255,255,255,0.06)";
const DARK_TOOLTIP_BG = "rgba(12, 24, 48, 0.95)";

function darkGrid() {
  return { top: 10, right: 20, bottom: 24, left: 16, containLabel: true };
}

const DARK_TOOLTIP = {
  backgroundColor: DARK_TOOLTIP_BG,
  borderColor: "rgba(30,144,255,0.2)",
  textStyle: { color: "#c8d6e5", fontSize: 12 },
};

// ── 趋势图示例数据(接口待接入) ───────────────────────────────────────────
const PLACEHOLDER_TREND_MONTHS = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];

export default function DashboardScreen() {
  const nav = useNavigate();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [sites, setSites] = useState<any[]>([]);
  const [stats, setStats] = useState<any>({});
  const [pendingCount, setPendingCount] = useState(0);
  const [logs, setLogs] = useState<any[]>([]);
  const [topObstacles, setTopObstacles] = useState<any[]>([]);
  const [trend, setTrend] = useState<any>(null);
  const [wfStages, setWfStages] = useState<any[]>([]);
  const [now, setNow] = useState(dayjs());
  const [screenTier, setScreenTier] = useState<"small" | "compact" | "full">("full");

  // 三级断点: <1024 小屏提示; 1024-1366 压缩预览; >=1366 正常大屏
  useEffect(() => {
    const check = () => {
      const w = window.innerWidth;
      setScreenTier(w < 1024 ? "small" : w < 1366 ? "compact" : "full");
    };
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // 实时时钟
  useEffect(() => {
    const t = setInterval(() => setNow(dayjs()), 1000);
    return () => clearInterval(t);
  }, []);

  const load = useCallback(async () => {
    try {
      const [st, d, p, l, to, tr, wf] = await Promise.all([
        api.siteStatistics().catch(() => null),
        api.sites({ size: 200 }),
        api.pendingApprovals().catch(() => []),
        api.auditLogs({ page: 1, size: 10 }).catch(() => ({ items: [] })),
        api.topObstacles(10).catch(() => ({ items: [] })),
        api.monthlyTrend().catch(() => null),
        api.workflowStages().catch(() => ({ items: [] })),
      ]);
      setStats(st || {});
      setSites((d as any).items || []);
      setPendingCount(Array.isArray(p) ? p.length : 0);
      setLogs((l as any).items || []);
      setTopObstacles((to as any)?.items || []);
      setTrend(tr);
      setWfStages((wf as any)?.items || []);
    } catch (e: any) {
      message.error("数据加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // 30 秒自动刷新
  useEffect(() => {
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [load]);

  // ── 派生数据 ──────────────────────────────────────────────
  const heavy = stats.heavy_metal_count ?? sites.filter(s => s.pollution_type === "heavy_metal").length;
  const organic = stats.organic_count ?? sites.filter(s => s.pollution_type === "organic").length;
  const composite = stats.composite_count ?? sites.filter(s => s.pollution_type === "composite").length;
  const provinces = stats.total_provinces ?? new Set(sites.map(s => s.province).filter(Boolean)).size;
  const totalExceed = stats.exceedance_count ?? sites.reduce((a, s) => a + (s.n_exceed || 0), 0);
  const totalMeasurements = stats.total_measurements;
  const totalReports = stats.total_reports;
  const activeWorkflows = stats.active_workflows;
  const highRisk = sites.filter(s => (s.n_exceed || 0) >= 10).length;
  const topAlerts = [...sites].filter(s => (s.n_exceed || 0) > 0)
    .sort((a, b) => (b.n_exceed || 0) - (a.n_exceed || 0)).slice(0, 10);

  // 省份分布
  const provMap: Record<string, number> = {};
  sites.forEach(s => { const p = s.province || "未知"; provMap[p] = (provMap[p] || 0) + 1; });
  const provData = Object.entries(provMap).sort((a, b) => b[1] - a[1]).slice(0, 9);

  // 污染类型分布
  const typeData = [
    { name: "重金属污染", value: heavy, color: POLLUTION_TYPE.heavy_metal },
    { name: "有机污染", value: organic, color: POLLUTION_TYPE.organic },
    { name: "复合污染", value: composite, color: POLLUTION_TYPE.composite },
  ].filter(d => d.value > 0);

  // 地图数据
  const mapSites = sites.map((s: any) => ({
    id: s.id, name: s.name, longitude: s.longitude, latitude: s.latitude,
    pollution_type: s.pollution_type, n_exceed: s.n_exceed,
    color: POLLUTION_TYPE[s.pollution_type] || "#dc2626",
  }));

  // ── 左侧图表 ──────────────────────────────────────────────
  const pieOption = useMemo(() => ({
    tooltip: { ...DARK_TOOLTIP, trigger: "item" as const,
      formatter: (p: any) => `<b>${p.name}</b><br/>场地: <b>${p.value} 个</b> (占 ${p.percent}%)` },
    series: [{
      type: "pie", radius: ["48%", "72%"], center: ["50%", "50%"],
      data: typeData.map(d => ({ name: d.name, value: d.value })),
      color: typeData.map(d => d.color),
      label: { color: DARK_TEXT, fontSize: 10, formatter: "{b}\n{d}%" },
      itemStyle: { borderRadius: 3, borderColor: "rgba(10,16,36,0.8)", borderWidth: 2 },
      emphasis: {
        focus: "self", scale: true,
        label: { fontSize: 13, fontWeight: "bold" as const, color: "#e0ecff" },
        itemStyle: { shadowBlur: 16, shadowColor: "rgba(0,212,255,0.4)" },
      },
    }],
  }), [typeData]);

  const provBarOption = useMemo(() => ({
    tooltip: { ...DARK_TOOLTIP, trigger: "axis" as const },
    grid: darkGrid(),
    xAxis: { type: "value" as const, axisLine: { lineStyle: { color: DARK_AXIS_LINE } },
      axisLabel: { color: DARK_TEXT, fontSize: 10 }, splitLine: { lineStyle: { color: DARK_SPLIT } } },
    yAxis: { type: "category" as const, inverse: true, data: provData.map(d => d[0]),
      axisLine: { lineStyle: { color: DARK_AXIS_LINE } }, axisLabel: { color: DARK_TEXT, fontSize: 10 } },
    series: [{
      type: "bar", data: provData.map(d => d[1]),
      itemStyle: { color: { type: "linear" as const, x: 0, y: 0, x2: 1, y2: 0,
        colorStops: [{offset:0,color:"#1a5276"},{offset:1,color:"#2e86c1"}] },
        borderRadius: [0, 3, 3, 0] },
      barMaxWidth: 16,
    }],
  }), [provData]);

  const top10BarOption = useMemo(() => {
    const items = topObstacles.length ? topObstacles : [];
    return {
      tooltip: { ...DARK_TOOLTIP, trigger: "axis" as const,
        formatter: (p: any) => `<b>${p[0].name}</b><br/>出现场地: <b>${items[p[0].dataIndex]?.freq || 0} 个</b><br/>平均贡献: ${items[p[0].dataIndex]?.avg_importance?.toFixed(3) || "—"}` },
      grid: darkGrid(),
      xAxis: { type: "value" as const, name: "出现场地数", nameTextStyle: { color: DARK_TEXT, fontSize: 10 },
        axisLine: { lineStyle: { color: DARK_AXIS_LINE } }, axisLabel: { color: DARK_TEXT, fontSize: 10 },
        splitLine: { lineStyle: { color: DARK_SPLIT } } },
      yAxis: { type: "category" as const, inverse: true,
        data: items.length ? items.map((d: any) => d.factor) : ["暂无诊断数据"],
        axisLabel: { color: DARK_TEXT, fontSize: 10 } },
      series: [{
        type: "bar", data: items.length ? items.map((d: any) => d.freq) : [0],
        itemStyle: { color: { type: "linear" as const, x: 0, y: 0, x2: 1, y2: 0,
          colorStops: [{offset:0,color:"#b9770e"},{offset:1,color:"#f0b429"}] },
          borderRadius: [0, 3, 3, 0] },
        barMaxWidth: 16,
      }],
    };
  }, [topObstacles]);

  // Round7 追加: 追溯阶段漏斗
  const funnelOption = useMemo(() => {
    const stages = wfStages.length ? wfStages : [];
    const data = stages.map((s: any) => ({ name: s.name, value: s.n_sites || s.n_in_progress || 0 }));
    return {
      tooltip: { trigger: "item" as const },
      series: [{
        type: "funnel", left: "10%", right: "10%", top: 4, bottom: 4,
        width: "80%", minSize: "30%", maxSize: "100%", sort: "descending", gap: 2,
        label: { color: DARK_TEXT, fontSize: 10, formatter: "{b} {c}" },
        labelLine: { length: 8, lineStyle: { color: DARK_AXIS_LINE } },
        itemStyle: { borderColor: "rgba(10,16,36,0.6)", borderWidth: 1 },
        data: data.length ? data : [{ name: "暂无工作流数据", value: 0 }],
        color: ["#00b894", "#55efc4", "#4da3ff", "#7b68ee", "#f0b429"],
      }],
    };
  }, [wfStages]);

  // Round7 追加: 用地类型分布
  const landUseDist = useMemo(() => {
    const p = sites.filter((s) => (s.land_use_type || "").includes("生产")).length;
    const e = sites.filter((s) => (s.land_use_type || "").includes("生态")).length;
    const o = sites.length - p - e;
    const t = sites.length || 1;
    return { p, e, o, pp: p / t * 100, ep: e / t * 100, op: o / t * 100 };
  }, [sites]);

  // ── 底部趋势 ──────────────────────────────────────────────
  const trendMonths = trend?.months?.length ? trend.months : PLACEHOLDER_TREND_MONTHS;
  const trendOption = (title: string, data: number[], color: [string,string]) => ({
    tooltip: { ...DARK_TOOLTIP, trigger: "axis" as const },
    grid: { top: 30, right: 16, bottom: 20, left: 40 },
    title: { text: title, textStyle: { color: "#a0b8d8", fontSize: 12, fontWeight: 400 }, left: 8, top: 4 },
    xAxis: { type: "category" as const, data: trendMonths,
      axisLine: { lineStyle: { color: DARK_AXIS_LINE } }, axisLabel: { color: DARK_TEXT, fontSize: 9 } },
    yAxis: { type: "value" as const, splitLine: { lineStyle: { color: DARK_SPLIT } },
      axisLabel: { color: DARK_TEXT, fontSize: 9 } },
    series: [{
      type: "line", data, smooth: true, symbol: "circle", symbolSize: 4,
      lineStyle: { color: color[0], width: 1.5 },
      itemStyle: { color: color[0] },
      areaStyle: { color: { type: "linear" as const, x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [{offset:0,color:color[1]+"33"},{offset:1,color:color[1]+"05"}] } },
    }],
  });

  // ── KPI 卡片配置 ──────────────────────────────────────────
  const kpiCards = [
    { title: "场地总数", value: sites.length, suffix: "个", icon: <DatabaseOutlined />, color: "#1e90ff", bg: "rgba(30,144,255,0.12)" },
    { title: "高风险场地", value: highRisk, suffix: "个", icon: <WarningOutlined />, color: "#ff6b6b", bg: "rgba(255,107,107,0.12)" },
    { title: "检测记录", value: totalMeasurements ?? "—", suffix: totalMeasurements ? "条" : "", icon: <ApartmentOutlined />, color: "#00d4ff", bg: "rgba(0,212,255,0.12)",
      demo: totalMeasurements == null },
    { title: "报告数量", value: totalReports ?? "—", suffix: totalReports ? "份" : "", icon: <FileTextOutlined />, color: "#7b68ee", bg: "rgba(123,104,238,0.12)",
      demo: totalReports == null },
    { title: "在管流程", value: activeWorkflows ?? "—", suffix: activeWorkflows ? "项" : "", icon: <CheckCircleOutlined />, color: "#00b894", bg: "rgba(0,184,148,0.12)",
      demo: activeWorkflows == null },
    { title: "待处理", value: pendingCount, suffix: "项", icon: <ClockCircleOutlined />, color: "#f0b429", bg: "rgba(240,180,41,0.12)" },
  ];

  // ── 渲染 ──────────────────────────────────────────────────
  if (screenTier === "small") {
    return (
      <div className={styles.smallScreen}>
        <div>
          <DashboardOutlined style={{ fontSize: 48, color: "rgba(30,144,255,0.3)", marginBottom: 16 }} />
          <div>请使用更大屏幕或缩放浏览器以查看数字大屏</div>
          <div style={{ fontSize: 13, color: "#4a6785", marginTop: 8 }}>推荐分辨率: 1920×1080，最小: 1024×768</div>
          <Button type="link" onClick={() => nav("/")} style={{ marginTop: 16 }}>返回工作台</Button>
        </div>
      </div>
    );
  }

  const compactMode = screenTier === "compact";

  if (loading) {
    return (
      <div className={styles.screenEmpty}>
        <Spin size="large">
          <div style={{ padding: 60, color: "#6b8db5" }}>正在加载数字大屏...</div>
        </Spin>
      </div>
    );
  }

  if (!sites.length) {
    return (
      <div className={styles.screenEmpty}>
        <div className={styles.screenEmptyCard}>
          <div className={styles.screenEmptyIcon}><DatabaseOutlined /></div>
          <div style={{ fontSize: 18, marginBottom: 8 }}>暂无场地数据</div>
          <div style={{ fontSize: 13, marginBottom: 16 }}>请先导入场地数据后再查看数字大屏</div>
          <Button onClick={() => nav("/sites/import")} style={{ marginRight: 8 }}>导入数据</Button>
          <Button onClick={() => nav("/")}>返回工作台</Button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.screenRoot} data-testid="digital-screen-root">
      {/* 压缩预览模式警告条 */}
      {compactMode && (
        <div style={{
          background: "rgba(245,158,11,0.15)", borderBottom: "1px solid rgba(245,158,11,0.3)",
          color: "#f0b429", fontSize: 12, padding: "4px 16px", textAlign: "center", flexShrink: 0,
        }}>
          ⚠ 当前为压缩预览模式（{typeof window !== "undefined" ? window.innerWidth : 0}px），推荐 1920×1080 查看完整大屏
        </div>
      )}
      {/* ── 顶部标题栏 ──────────────────────────────────── */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <DashboardOutlined style={{ color: "#4da3ff", fontSize: 20 }} />
          <span className={styles.headerTitle}>污染场地土壤生态-生产功能重构监管系统</span>
        </div>
        <div className={styles.headerMeta}>
          <span className={styles.clock}>{now.format("YYYY-MM-DD HH:mm:ss")}</span>
          <span className={styles.dataVersion}>数据版本 v1.0.0</span>
          <Button type="text" className={styles.backBtn} icon={<RollbackOutlined />}
            onClick={() => nav("/")}>返回工作台</Button>
        </div>
      </div>

      {/* ── KPI 行 ──────────────────────────────────────── */}
      <div className={styles.kpiRow} data-testid="screen-kpi-row">
        {kpiCards.map(k => (
          <div key={k.title} className={styles.kpiCard}>
            <div className={styles.kpiIconWrap} style={{ background: k.bg, color: k.color }}>
              {k.icon}
            </div>
            <div style={{ flex: 1 }}>
              <div className={styles.kpiValue}>
                {k.demo ? (
                  <Tooltip title="后端接口未提供此数据，当前显示为演示占位">
                    <span className={styles.kpiPlaceholder}>待接入</span>
                  </Tooltip>
                ) : (
                  <>{k.value}{k.suffix && <span className={styles.kpiSuffix}>{k.suffix}</span>}</>
                )}
              </div>
              <div className={styles.kpiLabel}>
                {k.title}
                {k.demo && <span className={styles.demoTag} style={{ marginLeft: 6 }}>示例数据</span>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── 主体三栏 ────────────────────────────────────── */}
      <div className={styles.bodyRow}>
        {/* 左栏 */}
        <div className={styles.leftCol} data-testid="screen-left-panels">
          <div className={styles.panel}>
            <div className={styles.panelTitle}><span className={styles.panelTitleBar} />污染类型分布</div>
            {typeData.length
              ? <ReactECharts option={pieOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 170 }} />
              : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />
            }
          </div>
          <div className={styles.panel}>
            <div className={styles.panelTitle}><span className={styles.panelTitleBar} />省份/区域分布</div>
            {provData.length
              ? <ReactECharts option={provBarOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 200 }} />
              : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无数据" />
            }
          </div>
          <div className={styles.panel}>
            <div className={styles.panelTitle}>
              <span className={styles.panelTitleBar} />障碍因子 TOP10
              {!topObstacles.length && <span className={styles.demoTag} style={{ marginLeft: "auto" }}>待接入</span>}
            </div>
            <ReactECharts option={top10BarOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 200 }} />
            {!topObstacles.length && (
              <Text style={{ color: "#4a6785", fontSize: 10, display: "block", textAlign: "center", marginTop: 4 }}>
                各场地诊断结果聚合后显示(需先运行诊断)
              </Text>
            )}
          </div>
        </div>

        {/* 中央：地图(70%) + 风险等级矩阵(30%) */}
        <div className={styles.centerCol}>
          <div className={styles.mapWrap} style={{ flex: "0 0 70%" }} data-testid="screen-map">
            <SiteMap sites={mapSites} onMarkerClick={(s) => s.id && nav(`/sites/${s.id}`)} />
            {topAlerts.length > 0 && (
              <div className={styles.mapOverlay}>
                <div className={styles.mapOverlayLabel}>全国场地分布总览</div>
                <div className={styles.mapOverlaySite}>
                  共 {sites.length} 个场地，覆盖 {provinces} 个省份
                </div>
                <div className={styles.mapOverlayDetail}>
                  高风险: {highRisk} · 超标记录: {totalExceed} 条
                </div>
              </div>
            )}
          </div>
          {/* 地图下方：风险等级矩阵 */}
          <div style={{ display: "flex", gap: 8, flex: "0 0 30%", marginTop: 8 }}>
            <div className={styles.panel} style={{ flex: 1 }}>
              <div className={styles.panelTitle}><span className={styles.panelTitleBar} />风险等级矩阵</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, fontSize: 11 }}>
                {[
                  { label: "重金属", count: heavy, color: POLLUTION_TYPE.heavy_metal, bg: "rgba(215,48,39,0.15)" },
                  { label: "有机污染", count: organic, color: POLLUTION_TYPE.organic, bg: "rgba(27,120,55,0.15)" },
                  { label: "复合污染", count: composite, color: POLLUTION_TYPE.composite, bg: "rgba(224,130,20,0.15)" },
                  { label: "高风险", count: highRisk, color: "#ff6b6b", bg: "rgba(255,107,107,0.15)" },
                  { label: "超标记录", count: totalExceed, color: "#f0b429", bg: "rgba(240,180,41,0.15)" },
                  { label: "覆盖省份", count: provinces, color: "#1e90ff", bg: "rgba(30,144,255,0.15)" },
                ].map(m => (
                  <div key={m.label} style={{ background: m.bg, borderRadius: 4, padding: "8px 10px", textAlign: "center", border: "1px solid rgba(255,255,255,0.05)" }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: m.color }}>{m.count}</div>
                    <div style={{ color: "#8899bb", fontSize: 10, marginTop: 2 }}>{m.label}</div>
                  </div>
                ))}
              </div>
              {/* Round7 追加: 用地类型分布(生产/生态) */}
              <div data-testid="screen-land-use-dist" style={{ marginTop: 8, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 6 }}>
                <div style={{ color: DARK_TEXT, fontSize: 10, marginBottom: 4 }}>修复后用地类型分布</div>
                <div style={{ display: "flex", height: 14, borderRadius: 3, overflow: "hidden", fontSize: 9 }}>
                  <div style={{ width: landUseDist.pp + "%", background: "#722ed1", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }} title={"生产用地 " + landUseDist.p + " 个"}>生产{landUseDist.p}</div>
                  <div style={{ width: landUseDist.ep + "%", background: "#52c41a", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }} title={"生态用地 " + landUseDist.e + " 个"}>生态{landUseDist.e}</div>
                  {landUseDist.o > 0 && <div style={{ width: landUseDist.op + "%", background: "#6b8db5", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff" }} title={"未指定 " + landUseDist.o + " 个"}>未定{landUseDist.o}</div>}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* 右栏 — 扩展为 320px */}
        <div className={styles.rightCol}>
          {/* 预警 TOP10 */}
          <div className={styles.panel} data-testid="screen-alert-top10" style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <div className={styles.panelTitle}>
              <span className={styles.panelTitleBar} style={{ background: "linear-gradient(180deg, #ff6b6b, #ee5a24)" }} />
              重点场地预警 TOP10
            </div>
            <div style={{ flex: 1, overflow: "auto" }}>
              {topAlerts.length ? topAlerts.map((s, i) => (
                <div key={s.id} className={styles.alertItem} onClick={() => nav(`/sites/${s.id}`)}>
                  <span className={styles.alertRank} style={{ color: i < 3 ? ["#ff6b6b","#f0b429","#f39c12"][i] : "#6b8db5" }}>
                    {i + 1}
                  </span>
                  <span className={styles.alertName} title={s.name}>{s.name}</span>
                  <span className={styles.alertBadge} style={{
                    background: (s.n_exceed||0) >= 10 ? "rgba(220,38,38,0.25)" : "rgba(245,158,11,0.2)",
                    color: (s.n_exceed||0) >= 10 ? "#ff7675" : "#fdcb6e",
                  }}>
                    {s.n_exceed || 0}条超标
                  </span>
                </div>
              )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无预警" />}
            </div>
          </div>

          {/* 追溯摘要 */}
          <div className={styles.panel} data-testid="screen-trace-summary">
            <div className={styles.panelTitle}>
              <span className={styles.panelTitleBar} style={{ background: "linear-gradient(180deg, #00b894, #55efc4)" }} />
              追溯任务摘要
              {!wfStages.length && <span className={styles.demoTag} style={{ marginLeft: "auto" }}>待接入</span>}
            </div>
            {(wfStages.length ? wfStages : [
              { code: "survey", name: "调查评估", n_in_progress: 0, n_completed: 0 },
              { code: "approval", name: "方案审批", n_in_progress: 0, n_completed: 0 },
              { code: "construction", name: "施工监理", n_in_progress: 0, n_completed: 0 },
              { code: "effect", name: "效果评估", n_in_progress: 0, n_completed: 0 },
              { code: "maintenance", name: "后期管护", n_in_progress: 0, n_completed: 0 },
            ]).map((s: any) => (
              <div key={s.code} className={styles.traceItem}>
                <span className={styles.traceStage}>{s.name}</span>
                <span className={styles.traceSite}>
                  {s.n_in_progress > 0 ? `${s.n_in_progress} 个场地进行中` : s.n_completed > 0 ? `${s.n_completed} 个已完成` : "暂无"}
                </span>
                <span className={styles.traceStatus} style={{
                  background: s.n_in_progress > 0 ? "rgba(30,144,255,0.15)" : "rgba(107,141,181,0.1)",
                  color: s.n_in_progress > 0 ? "#4da3ff" : "#6b8db5",
                }}>
                  {s.n_in_progress > 0 ? "进行中" : s.n_completed > 0 ? "已完成" : "—"}
                </span>
              </div>
            ))}
            {!wfStages.length && (
              <Text style={{ color: "#4a6785", fontSize: 10, display: "block", textAlign: "center", marginTop: 6 }}>
                工作流记录接入后显示真实数据
              </Text>
            )}
            {/* Round7 追加: 阶段流转漏斗 */}
            <div data-testid="screen-trace-funnel" style={{ marginTop: 8, borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 6 }}>
              <div style={{ color: DARK_TEXT, fontSize: 10, marginBottom: 2 }}>阶段场地流转漏斗</div>
              <ReactECharts option={funnelOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 130 }} />
            </div>
          </div>

          {/* 最近操作 */}
          <div className={styles.panel}>
            <div className={styles.panelTitle}><span className={styles.panelTitleBar} />最近操作</div>
            {logs.length ? logs.slice(0, 6).map((l: any, i: number) => (
              <div key={i} className={styles.traceItem}>
                <Tag color={l.result === "success" ? "green" : l.result === "fail" ? "red" : "orange"}
                  style={{ fontSize: 10, marginRight: 6 }}>
                  {(l.action || "").slice(0, 6)}
                </Tag>
                <span style={{ flex: 1, fontSize: 11, color: "#7b9cc4", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {l.user || "—"}
                </span>
                <span style={{ fontSize: 10, color: "#4a6785", flexShrink: 0 }}>
                  {l.time ? dayjs(l.time).format("MM-DD HH:mm") : "—"}
                </span>
              </div>
            )) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无操作记录" />}
          </div>
        </div>
      </div>
    </div>
  );
}
