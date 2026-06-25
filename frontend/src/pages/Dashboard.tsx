import { useEffect, useState } from "react";
import {
  Card, Col, Row, Statistic, Spin, Button, List, Tag, Space, message, Alert,
  Badge, Typography, Divider,
} from "antd";
import {
  PlusOutlined, ImportOutlined, FileTextOutlined, WarningOutlined,
  DatabaseOutlined, EnvironmentOutlined, ApartmentOutlined,
  ClockCircleOutlined, ArrowUpOutlined, ArrowDownOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import SiteMap from "../components/SiteMap";
import { CATEGORICAL, POLLUTION_TYPE, POLLUTION_LABEL } from "../theme/palette";  // 全局配色(裴总精品案例莫兰迪对齐, 问题4/10政府化)

const { Text } = Typography;

/** 污染类型 → AntD Tag 颜色名(语义同 POLLUTION_TYPE) */
const TYPE_COLOR: Record<string, string> = {
  heavy_metal: "red", organic: "purple", composite: "orange",
};
const TYPE_LABEL = POLLUTION_LABEL;

export default function Dashboard() {
  const nav = useNavigate();
  const [sites, setSites] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.sites({ size: 200 }),
      api.auditLogs({ page: 1, size: 6 }).catch(() => ({ items: [] })),
    ]).then(([d, l]) => {
      setSites(d.items || []);
      setLogs(l.items || []);
    }).catch((err) => {
      message.error(err?.response?.data?.detail || "加载失败");
      setSites([]);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ textAlign: "center", paddingTop: 120 }}><Spin size="large" /></div>
  );

  const points = sites.reduce((a, s) => a + (s.n_points || 0), 0);
  const heavy = sites.filter((s) => s.pollution_type === "heavy_metal").length;
  const provinces = new Set(sites.map((s) => s.province).filter(Boolean)).size;
  const totalExceed = sites.reduce((a, s) => a + (s.n_exceed || 0), 0);
  const highRiskSites = sites.filter((s) => (s.n_exceed || 0) >= 10);

  const byType = ["heavy_metal", "organic", "composite"].map((t) => ({
    key: t,
    name: TYPE_LABEL[t],
    value: sites.filter((s) => s.pollution_type === t).length,
  })).filter((x) => x.value > 0);

  const pieOption = {
    tooltip: { trigger: "item", formatter: "{b}: {c} 个场地 ({d}%)" },
    legend: { bottom: 0 },
    series: [{
      type: "pie", radius: ["45%", "70%"], data: byType,
      label: { formatter: "{b}: {c}" },
      // 裴总 P1-5a: 污染类型语义色(红/紫/橙), 与场地详情 Tag/地图点位同源
      color: byType.map((d) => POLLUTION_TYPE[d.key]),
      emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: "rgba(0,0,0,0.3)" } },
    }],
  };

  // 裴总 P1-5b: 超标排行改横向条形图 + 短标签(省份+场地, 同省多场地加序号), 不截断
  const topExceed = [...sites].filter((s) => (s.n_exceed || 0) > 0)
    .sort((a, b) => (b.n_exceed || 0) - (a.n_exceed || 0)).slice(0, 8);
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
        borderRadius: [0, 3, 3, 0],
      },
      label: { show: true, position: "right", fontSize: 10, color: "#374151" },
    }],
  };

  const mapSites = sites.map((s) => ({
    id: s.id, name: s.name, longitude: s.longitude, latitude: s.latitude,
    pollution_type: s.pollution_type,
    color: POLLUTION_TYPE[s.pollution_type] || "#dc2626",  // 裴总 P1-5a: 地图点位用语义色
  }));

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
            title: "重金属污染场地", value: heavy,
            icon: <WarningOutlined style={{ fontSize: 20, color: "#dc2626" }} />,
            color: "#dc2626", suffix: "个",
          },
          {
            title: "采样点总数", value: points,
            icon: <EnvironmentOutlined style={{ fontSize: 20, color: "#0f766e" }} />,
            color: "#0f766e", suffix: "个",
          },
          {
            title: "超标记录总数", value: totalExceed,
            icon: <ApartmentOutlined style={{ fontSize: 20, color: "#b45309" }} />,
            color: "#b45309", suffix: "条",
          },
          {
            title: "覆盖省份", value: provinces,
            icon: <EnvironmentOutlined style={{ fontSize: 20, color: "#1d6fb8" }} />,
            color: "#1d6fb8", suffix: "个",
          },
        ].map((k) => (
          <Col span={Math.floor(24 / 5)} key={k.title}>
            <Card
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
                  background: k.color + "18",
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
            title="污染类型分布"
            extra={<Text type="secondary" style={{ fontSize: 12 }}>共 {sites.length} 个场地</Text>}
            style={{ borderRadius: 8 }}
          >
            {byType.length
              ? <ReactECharts option={pieOption} style={{ height: 280 }} />
              : <div style={{ height: 280, display: "flex", alignItems: "center", justifyContent: "center", color: "#ccc" }}>暂无数据</div>
            }
          </Card>
        </Col>
        <Col span={14}>
          <Card
            title="各场地超标记录排行（前8名）"
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
              ? <ReactECharts option={riskBarOption} style={{ height: 280 }} />
              : <div style={{ height: 280, display: "flex", alignItems: "center", justifyContent: "center", color: "#ccc" }}>暂无数据</div>
            }
          </Card>
        </Col>
      </Row>

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
                    <Tag color={TYPE_COLOR[s.pollution_type] || "default"} style={{ fontSize: 11 }}>
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
        extra={<Text type="secondary" style={{ fontSize: 12 }}>点击标记跳转详情；右上角切换矢量/影像底图</Text>}
        style={{ borderRadius: 8 }}
      >
        <SiteMap sites={mapSites} height={480} onMarkerClick={(s) => s.id && nav(`/sites/${s.id}`)} />
      </Card>
    </Space>
  );
}
