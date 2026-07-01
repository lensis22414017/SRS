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

// ── 趋势图演示数据 ───────────────────────────────────────────
const DEMO_TREND_MONTHS = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];

export default function DashboardScreen() {
  const nav = useNavigate();
  const { message } = App.useApp();
  const [loading, setLoading] = useState(true);
  const [sites, setSites] = useState<any[]>([]);
  const [stats, setStats] = useState<any>({});
  const [pendingCount, setPendingCount] = useState(0);
  const [logs, setLogs] = useState<any[]>([]);
  const [now, setNow] = useState(dayjs());
  const [smallScreen, setSmallScreen] = useState(false);

  // 检测小屏
  useEffect(() => {
    const check = () => setSmallScreen(window.innerWidth < 1366);
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
      const [st, d, p, l] = await Promise.all([
        api.siteStatistics().catch(() => null),
        api.sites({ size: 200 }),
        api.pendingApprovals().catch(() => []),
        api.auditLogs({ page: 1, size: 10 }).catch(() => ({ items: [] })),
      ]);
      setStats(st || {});
      setSites((d as any).items || []);
      setPendingCount(Array.isArray(p) ? p.length : 0);
      setLogs((l as any).items || []);
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

  const top10BarOption = useMemo(() => ({
    tooltip: { ...DARK_TOOLTIP, trigger: "axis" as const },
    grid: darkGrid(),
    xAxis: { type: "value" as const, name: "提及次数", nameTextStyle: { color: DARK_TEXT, fontSize: 10 },
      axisLine: { lineStyle: { color: DARK_AXIS_LINE } }, axisLabel: { color: DARK_TEXT, fontSize: 10 },
      splitLine: { lineStyle: { color: DARK_SPLIT } } },
    yAxis: { type: "category" as const, inverse: true,
      data: ["Cd镉","Pb铅","As砷","pH","Cu铜","Zn锌","Ni镍","Cr铬","Hg汞","CEC"],
      axisLabel: { color: DARK_TEXT, fontSize: 10 } },
    series: [{
      type: "bar", data: [14, 12, 11, 9, 8, 7, 6, 5, 4, 3],
      itemStyle: { color: { type: "linear" as const, x: 0, y: 0, x2: 1, y2: 0,
        colorStops: [{offset:0,color:"#b9770e"},{offset:1,color:"#f0b429"}] },
        borderRadius: [0, 3, 3, 0] },
      barMaxWidth: 16,
    }],
  }), []);

  // ── 底部趋势 ──────────────────────────────────────────────
  const trendOption = (title: string, data: number[], color: [string,string]) => ({
    tooltip: { ...DARK_TOOLTIP, trigger: "axis" as const },
    grid: { top: 30, right: 16, bottom: 20, left: 40 },
    title: { text: title, textStyle: { color: "#a0b8d8", fontSize: 12, fontWeight: 400 }, left: 8, top: 4 },
    xAxis: { type: "category" as const, data: DEMO_TREND_MONTHS,
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
  if (smallScreen) {
    return (
      <div className={styles.smallScreen}>
        <div>
          <DashboardOutlined style={{ fontSize: 48, color: "rgba(30,144,255,0.3)", marginBottom: 16 }} />
          <div>请使用更大屏幕或缩放浏览器以查看数字大屏</div>
          <div style={{ fontSize: 13, color: "#4a6785", marginTop: 8 }}>推荐分辨率: 1920×1080，最小: 1366×768</div>
          <Button type="link" onClick={() => nav("/")} style={{ marginTop: 16 }}>返回工作台</Button>
        </div>
      </div>
    );
  }

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
    <div className={styles.screenRoot}>
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
      <div className={styles.kpiRow}>
        {kpiCards.map(k => (
          <div key={k.title} className={styles.kpiCard}>
            <div className={styles.kpiIconWrap} style={{ background: k.bg, color: k.color }}>
              {k.icon}
            </div>
            <div style={{ flex: 1 }}>
              <div className={styles.kpiValue}>
                {k.value}
                {k.suffix && <span className={styles.kpiSuffix}>{k.suffix}</span>}
              </div>
              <div className={styles.kpiLabel}>
                {k.title}
                {(k as any).demo && <span className={styles.demoTag} style={{ marginLeft: 6 }}>演示数据</span>}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── 主体三栏 ────────────────────────────────────── */}
      <div className={styles.bodyRow}>
        {/* 左栏 */}
        <div className={styles.leftCol}>
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
              <span className={styles.demoTag} style={{ marginLeft: "auto" }}>演示数据</span>
            </div>
            <ReactECharts option={top10BarOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 200 }} />
            <Text style={{ color: "#4a6785", fontSize: 10, display: "block", textAlign: "center", marginTop: 4 }}>
              跨场地聚合接口 (P1) 完成后接入真实数据
            </Text>
          </div>
        </div>

        {/* 中央地图 */}
        <div className={styles.centerCol}>
          <div className={styles.mapWrap}>
            <SiteMap sites={mapSites} onMarkerClick={(s) => s.id && nav(`/sites/${s.id}`)} />
            {topAlerts.length > 0 && (
              <div className={styles.mapOverlay}>
                <div className={styles.mapOverlayLabel}>地图概览</div>
                <div className={styles.mapOverlaySite}>
                  共 {sites.length} 个场地，覆盖 {provinces} 个省份
                </div>
                <div className={styles.mapOverlayDetail}>
                  高风险: {highRisk} · 超标记录: {totalExceed} 条
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 右栏 */}
        <div className={styles.rightCol}>
          {/* 预警 TOP10 */}
          <div className={styles.panel} style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
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
          <div className={styles.panel}>
            <div className={styles.panelTitle}>
              <span className={styles.panelTitleBar} style={{ background: "linear-gradient(180deg, #00b894, #55efc4)" }} />
              追溯任务摘要
              <span className={styles.demoTag} style={{ marginLeft: "auto" }}>演示数据</span>
            </div>
            {["调查评估","方案审批","施工监理","效果评估","后期管护"].map(stage => (
              <div key={stage} className={styles.traceItem}>
                <span className={styles.traceStage}>{stage}</span>
                <span className={styles.traceSite}>
                  {stage === "调查评估" ? "3 个场地进行中" : stage === "方案审批" ? "1 个场地待审批" : "暂无"}
                </span>
                <span className={styles.traceStatus} style={{
                  background: stage === "调查评估" ? "rgba(30,144,255,0.15)" : "rgba(107,141,181,0.1)",
                  color: stage === "调查评估" ? "#4da3ff" : "#6b8db5",
                }}>
                  {stage === "调查评估" ? "进行中" : stage === "方案审批" ? "待审批" : "—"}
                </span>
              </div>
            ))}
            <Text style={{ color: "#4a6785", fontSize: 10, display: "block", textAlign: "center", marginTop: 6 }}>
              工作流聚合接口 (P1) 完成后接入真实数据
            </Text>
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

      {/* ── 底部趋势 ──────────────────────────────────────── */}
      <div className={styles.bottomRow}>
        <div className={styles.trendCard}>
          <span className={styles.demoTag} style={{ position: "absolute", top: 6, right: 8, zIndex: 1 }}>演示数据</span>
          <ReactECharts option={trendOption("场地累计趋势",
            [3,5,8,10,12,14,15,16,17,18,18,19],
            ["#1e90ff","#1e90ff"])} theme="srs-light" opts={SVG_OPTS} style={{ height: "100%" }} />
        </div>
        <div className={styles.trendCard}>
          <span className={styles.demoTag} style={{ position: "absolute", top: 6, right: 8, zIndex: 1 }}>演示数据</span>
          <ReactECharts option={trendOption("检测记录累计趋势",
            [320,680,1050,1480,1920,2410,2950,3520,4100,4720,5380,6080],
            ["#00d4ff","#00d4ff"])} theme="srs-light" opts={SVG_OPTS} style={{ height: "100%" }} />
        </div>
        <div className={styles.trendCard}>
          <span className={styles.demoTag} style={{ position: "absolute", top: 6, right: 8, zIndex: 1 }}>演示数据</span>
          <ReactECharts option={trendOption("报告生成累计趋势",
            [1,3,5,8,12,16,21,27,33,40,47,55],
            ["#7b68ee","#7b68ee"])} theme="srs-light" opts={SVG_OPTS} style={{ height: "100%" }} />
        </div>
      </div>
    </div>
  );
}
