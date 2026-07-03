import { useEffect, useState } from "react";
import {
  App, Card, Col, Row, Statistic, Spin, Skeleton, Button, List, Tag, Space, Alert,
  Badge, Typography, Modal,
} from "antd";
import {
  PlusOutlined, ImportOutlined, FileTextOutlined, WarningOutlined,
  DatabaseOutlined, EnvironmentOutlined, ApartmentOutlined,
  ClockCircleOutlined, ExportOutlined, FundProjectionScreenOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import SiteMap from "../components/SiteMap";
import { POLLUTION_TYPE, POLLUTION_TYPE_BG, POLLUTION_LABEL } from "../theme/palette";
import { SVG_OPTS } from "../theme/echarts";
import styles from "./Dashboard.module.css";

const { Text } = Typography;

const TYPE_LABEL = POLLUTION_LABEL;

export default function Dashboard() {
  const nav = useNavigate();
  const [sites, setSites] = useState<any[]>([]);
  const [stats, setStats] = useState<any>({});
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [pieModalOpen, setPieModalOpen] = useState(false);
  const { message } = App.useApp();

  useEffect(() => {
    Promise.all([
      api.sites({ size: 200 }),
      api.siteStatistics().catch(() => null),
      api.auditLogs({ page: 1, size: 6 }).catch(() => ({ items: [] })),
    ]).then(([d, st, l]) => {
      setSites(d.items || []);
      setStats(st || {});
      setLogs(l.items || []);
    }).catch((err) => {
      message.error(err?.response?.data?.detail || "加载失败");
      setSites([]);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <Space direction="vertical" style={{ width: "100%", padding: "16px 0" }} size={16}>
      <Row gutter={12}>
        {[1, 2, 3, 4, 5].map((i) => (
          <Col span={Math.floor(24 / 5)} key={i}>
            <Card style={{ borderRadius: 8, height: 110 }}><Skeleton active paragraph={{ rows: 1 }} title={false} /></Card>
          </Col>
        ))}
      </Row>
      <Row gutter={16}>
        <Col span={10}><Card style={{ borderRadius: 8, height: 350 }}><Skeleton active paragraph={{ rows: 6 }} /></Card></Col>
        <Col span={14}><Card style={{ borderRadius: 8, height: 350 }}><Skeleton active paragraph={{ rows: 6 }} /></Card></Col>
      </Row>
    </Space>
  );

  const heavy = stats.heavy_metal_count ?? sites.filter((s) => s.pollution_type === "heavy_metal").length;
  const organic = stats.organic_count ?? sites.filter((s) => s.pollution_type === "organic").length;
  const composite = stats.composite_count ?? sites.filter((s) => s.pollution_type === "composite").length;
  const provinces = stats.total_provinces ?? new Set(sites.map((s) => s.province).filter(Boolean)).size;
  const totalExceed = stats.exceedance_count ?? sites.reduce((a, s) => a + (s.n_exceed || 0), 0);
  const highRiskSites = sites.filter((s) => (s.n_exceed || 0) >= 10);

  const byType = ["heavy_metal", "organic", "composite"].map((t) => ({
    key: t,
    name: TYPE_LABEL[t],
    value: sites.filter((s) => s.pollution_type === t).length,
  })).filter((x) => x.value > 0);

  const pieOption = {
    tooltip: {
      trigger: "item",
      formatter: (p: any) =>
        `<b>${p.name}</b><br/>场地数量: <b>${p.value} 个</b><br/>占比: <b>${p.percent}%</b>`,
    },
    legend: { bottom: 0 },
    series: [{
      type: "pie", radius: ["45%", "70%"], data: byType,
      label: { formatter: "{b}: {c}" },
      color: byType.map((d) => POLLUTION_TYPE[d.key]),
      itemStyle: { borderRadius: 4, borderColor: "#fff", borderWidth: 2 },
      emphasis: {
        focus: "self",
        scale: true,
        label: { show: true, fontSize: 14, fontWeight: "bold" },
        itemStyle: { shadowBlur: 12, shadowOffsetX: 0, shadowColor: "rgba(0,0,0,0.3)" },
      },
    }],
  };

  // 超标排行改横向条形图 + 短标签(省份+场地, 同省多场地加序号), 不截断; Round7 扩展 Top8→Top10
  const topExceed = [...sites].filter((s) => (s.n_exceed || 0) > 0)
    .sort((a, b) => (b.n_exceed || 0) - (a.n_exceed || 0)).slice(0, 10);
  const _provCount: Record<string, number> = {};
  const shortName = (s: any) => {
    let prov = s.province || "";
    if (!prov) {
      const m = (s.name || "").match(/site_([^_]+?)_/);
      prov = m ? m[1] : (s.name || "场地").slice(0, 4);
    }
    _provCount[prov] = (_provCount[prov] || 0) + 1;
    return _provCount[prov] > 1 ? `${prov}场地${_provCount[prov]}` : `${prov}场地`;
  };
  const riskBarOption = {
    tooltip: { trigger: "axis", formatter: (p: any) => {
      const s = topExceed[p[0].dataIndex];
      return `<b>${s?.name || ""}</b><br/>场地 #${s?.id} · ${TYPE_LABEL[s?.pollution_type] || "—"}<br/>超标记录: ${p[0].data} 条`;
    } },
    grid: { left: 12, right: 40, top: 16, bottom: 24, containLabel: true },
    xAxis: { type: "value", name: "超标记录数", nameLocation: "middle", nameGap: 24 },
    yAxis: { type: "category", data: topExceed.map(shortName), inverse: true,
      axisLabel: { fontSize: 11, color: "#374151" } },
    series: [{
      type: "bar",
      data: topExceed.map((s) => s.n_exceed || 0),
      itemStyle: {
        color: (p: any) => {
          const v = p.data;
          return v >= 10 ? "#dc2626" : v >= 5 ? "#f59e0b" : "#3b82f6";
        },
        borderRadius: [0, 4, 4, 0],
        shadowBlur: 4,
        shadowColor: "rgba(0,0,0,0.1)",
      },
      label: { show: true, position: "right", fontSize: 10, color: "#374151" },
    }],
  };

  const mapSites = sites.map((s) => ({
    id: s.id, name: s.name, longitude: s.longitude, latitude: s.latitude,
    pollution_type: s.pollution_type,
    color: POLLUTION_TYPE[s.pollution_type] || "#dc2626",  // 地图点位用语义色
  }));

  // Round7 追加: 区域分布横向条形图(按省份统计场地数, 与超标排行并列展示)
  const regionCount: Record<string, number> = {};
  sites.forEach((s) => { const p = s.province || "未知"; regionCount[p] = (regionCount[p] || 0) + 1; });
  const regionSorted = Object.entries(regionCount).sort((a, b) => b[1] - a[1]).slice(0, 10);
  const regionBarOption = {
    tooltip: { trigger: "axis", formatter: (p: any) => `<b>${p[0].name}</b><br/>场地数: <b>${p[0].value} 个</b>` },
    grid: { left: 12, right: 40, top: 16, bottom: 24, containLabel: true },
    xAxis: { type: "value", name: "场地数", nameLocation: "middle", nameGap: 24 },
    yAxis: { type: "category", data: regionSorted.map((r) => r[0]).reverse(),
      axisLabel: { fontSize: 11, color: "#374151" } },
    series: [{
      type: "bar",
      data: regionSorted.map((r) => r[1]).reverse(),
      itemStyle: {
        color: { type: "linear" as const, x: 0, y: 0, x2: 1, y2: 0,
          colorStops: [{ offset: 0, color: "#1a5276" }, { offset: 1, color: "#2e86c1" }] },
        borderRadius: [0, 4, 4, 0],
      },
      label: { show: true, position: "right", fontSize: 10, color: "#374151" },
    }],
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>

      {/* ── 风险预警横幅 ───────────────────────────────────────── */}
      {highRiskSites.length > 0 && (
        <Alert
          type="warning"
          icon={<WarningOutlined />}
          showIcon
          message={
            <Space>
              <Text strong>风险预警</Text>
              <Badge count={highRiskSites.length} style={{ backgroundColor: "#dc2626" }} />
              <Text>
                个场地超标记录 ≥ 10 条（
                {highRiskSites.slice(0, 3).map((s) => s.name).join("、")}
                {highRiskSites.length > 3 ? `…等 ${highRiskSites.length} 个` : ""}
                ），建议优先开展障碍因子诊断
              </Text>
            </Space>
          }
          action={<Button size="small" danger onClick={() => nav("/obstacle")}>前往诊断</Button>}
          style={{ borderRadius: 6 }}
        />
      )}

      {/* ── KPI 指标卡 ────────────────────────────────────────── */}
      <Row gutter={12}>
        {[
          {
            title: "场地总数", value: sites.length,
            icon: <DatabaseOutlined style={{ fontSize: 20, color: "#0f3d6e" }} />,
            color: "#0f3d6e", suffix: "个",
          },
          {
            title: "覆盖省份", value: provinces,
            icon: <EnvironmentOutlined style={{ fontSize: 20, color: "#059669" }} />,
            color: "#059669", suffix: "个",
          },
          {
            title: "重金属污染", value: heavy,
            icon: <WarningOutlined style={{ fontSize: 20, color: POLLUTION_TYPE["heavy_metal"] }} />,
            color: POLLUTION_TYPE["heavy_metal"], bg: POLLUTION_TYPE_BG["heavy_metal"], suffix: "个场地",
          },
          {
            title: "有机污染", value: organic,
            icon: <WarningOutlined style={{ fontSize: 20, color: POLLUTION_TYPE["organic"] }} />,
            color: POLLUTION_TYPE["organic"], bg: POLLUTION_TYPE_BG["organic"], suffix: "个场地",
          },
          {
            title: "复合污染", value: composite,
            icon: <WarningOutlined style={{ fontSize: 20, color: POLLUTION_TYPE["composite"] }} />,
            color: POLLUTION_TYPE["composite"], bg: POLLUTION_TYPE_BG["composite"], suffix: "个场地",
          },
          {
            title: "超标记录", value: totalExceed,
            icon: <ApartmentOutlined style={{ fontSize: 20, color: "#b45309" }} />,
            color: "#b45309", suffix: "条",
          },
        ].map((k) => (
          <Col span={4} key={k.title}>
            <Card
              className={styles.kpiCard}
              style={{ borderRadius: 8, borderTop: `3px solid ${k.color}` }}
              styles={{ body: { padding: "16px 20px" } }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <Statistic
                  title={<span style={{ fontSize: 12, color: "#888" }}>{k.title}</span>}
                  value={k.value}
                  suffix={k.suffix}
                  valueStyle={{ fontSize: 24, color: k.color, fontWeight: 700 }}
                />
                <div style={{
                  width: 40, height: 40, borderRadius: "50%",
                  background: (k as any).bg || k.color + "18",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  {k.icon}
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      {/* ── 图表行 ────────────────────────────────────────────── */}
      <Row gutter={16}>
        <Col span={10}>
          <Card
            className={styles.chartCard}
            title="污染类型分布"
            extra={<Text type="secondary" style={{ fontSize: 12, cursor: "pointer" }} onClick={() => setPieModalOpen(true)}>共 {sites.length} 个场地 · 点击放大 📊</Text>}
            style={{ borderRadius: 8 }}
          >
            {byType.length
              ? <ReactECharts option={pieOption} theme="srs-light" opts={SVG_OPTS}
                  style={{ height: 280, cursor: "pointer" }}
                  onEvents={{ click: () => setPieModalOpen(true) }} />
              : <div style={{ height: 280, display: "flex", alignItems: "center", justifyContent: "center", color: "#ccc" }}>暂无数据</div>
            }
          </Card>
        </Col>
        <Col span={14}>
          <Card
            className={styles.chartCard}
            title="各场地超标记录排行（前10名）"
            extra={
              <Space size={4}>
                <Badge color="#dc2626" text="≥10" />
                <Badge color="#f59e0b" text="5~9" />
                <Badge color="#3b82f6" text="<5" />
              </Space>
            }
            style={{ borderRadius: 8 }}
          >
            {sites.length
              ? <ReactECharts option={riskBarOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 280 }} />
              : <div style={{ height: 280, display: "flex", alignItems: "center", justifyContent: "center", color: "#ccc" }}>暂无数据</div>
            }
          </Card>
        </Col>
      </Row>

      {/* ── Round7 追加: 区域分布条形图 ──────────────────────── */}
      <Card
        title="区域分布（场地数 Top10 省份）"
        extra={<Text type="secondary" style={{ fontSize: 12 }}>展示场地在全国各省份的分布情况</Text>}
        style={{ borderRadius: 8 }}
        data-testid="dashboard-region-bar"
      >
        {regionSorted.length
          ? <ReactECharts option={regionBarOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 260 }} />
          : <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", color: "#ccc" }}>暂无数据</div>
        }
      </Card>

      {/* ── 快捷操作 + 最近活动 ───────────────────────────────── */}
      <Row gutter={16}>
        <Col span={6}>
          <Card title="快捷操作" style={{ borderRadius: 8 }}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Button block icon={<ImportOutlined />} type="primary"
                onClick={() => nav("/sites/import")}
                style={{ background: "#0f3d6e", borderColor: "#0f3d6e" }}>
                批量导入数据
              </Button>
              <Button block icon={<PlusOutlined />} onClick={() => nav("/sites")}>
                场地管理
              </Button>
              <Button block icon={<ApartmentOutlined />} onClick={() => nav("/obstacle")}>
                障碍因子诊断
              </Button>
              <Button block icon={<FileTextOutlined />} onClick={() => nav("/trace")}>
                全流程追溯与报告
              </Button>
            </Space>
          </Card>
        </Col>
        <Col span={10}>
          <Card
            title="最近场地"
            extra={<a onClick={() => nav("/sites")}>全部 →</a>}
            style={{ borderRadius: 8 }}
          >
            <List
              size="small"
              dataSource={sites.slice(0, 6)}
              renderItem={(s: any) => (
                <List.Item
                  style={{ padding: "6px 0" }}
                  actions={[
                    <a key="d" onClick={() => nav(`/sites/${s.id}`)}>详情</a>,
                  ]}
                >
                  <Space size={6}>
                    <Tag color={POLLUTION_TYPE[s.pollution_type] || "#888"} style={{ fontSize: 11 }}>
                      {TYPE_LABEL[s.pollution_type] || s.pollution_type || "—"}
                    </Tag>
                    <Text style={{ fontSize: 13 }}>{s.name}</Text>
                    {(s.n_exceed || 0) >= 10 && (
                      <Badge dot color="#dc2626" title={`${s.n_exceed}条超标`} />
                    )}
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card
            title={<Space><ClockCircleOutlined />最近操作</Space>}
            style={{ borderRadius: 8 }}
            styles={{ body: { padding: "8px 16px" } }}
          >
            {logs.length ? (
              <List
                size="small"
                dataSource={logs}
                renderItem={(l: any) => (
                  <List.Item style={{ padding: "4px 0", borderBottom: "1px solid #f0f0f0" }}>
                    <Space size={6} style={{ width: "100%" }}>
                      <Tag
                        color={l.result === "success" ? "green" : l.result === "fail" ? "red" : "orange"}
                        style={{ fontSize: 10, minWidth: 36, textAlign: "center" }}
                      >
                        {l.action?.slice(0, 6)}
                      </Tag>
                      <Text style={{ fontSize: 11 }}>{l.user}</Text>
                      <Text type="secondary" style={{ fontSize: 10, marginLeft: "auto" }}>
                        {l.time ? new Date(l.time).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—"}
                      </Text>
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <div style={{ color: "#ccc", textAlign: "center", padding: "20px 0", fontSize: 12 }}>
                暂无操作记录（仅管理员可见）
              </div>
            )}
          </Card>
        </Col>
      </Row>

      {/* ── 地图 ──────────────────────────────────────────────── */}
      <Card
        title="场地分布地图"
        extra={
          <Space size={12}>
            <Text type="secondary" style={{ fontSize: 12 }}>点击标记跳转详情；右上角切换矢量/影像底图</Text>
            <Button size="small" type="primary" ghost icon={<FundProjectionScreenOutlined />}
              onClick={() => nav("/dashboard/screen")}>
              进入数字大屏
            </Button>
          </Space>
        }
        style={{ borderRadius: 8 }}
      >
        <SiteMap sites={mapSites} height={480} onMarkerClick={(s) => s.id && nav(`/sites/${s.id}`)} />
      </Card>

      {/* ── 饼图放大 Modal ────────────────────────────────────── */}
      <Modal
        title="污染类型分布（放大查看）"
        open={pieModalOpen}
        onCancel={() => setPieModalOpen(false)}
        footer={null}
        width={720}
      >
        {byType.length
          ? <ReactECharts
              option={{
                ...pieOption,
                series: [{
                  ...pieOption.series[0],
                  radius: ["35%", "75%"],
                  label: { show: true, formatter: "{b}\n{c} 个 ({d}%)", fontSize: 14, fontWeight: "bold" },
                }],
              }}
              theme="srs-light" opts={SVG_OPTS} style={{ height: 480 }}
            />
          : <div style={{ height: 480, display: "flex", alignItems: "center", justifyContent: "center", color: "#ccc" }}>暂无数据</div>
        }
      </Modal>
    </Space>
  );
}
