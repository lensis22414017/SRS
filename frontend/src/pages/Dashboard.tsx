import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Spin, Button, List, Tag, Space } from "antd";
import { PlusOutlined, ImportOutlined, FileTextOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import SiteMap from "../components/SiteMap";

export default function Dashboard() {
  const nav = useNavigate();
  const [sites, setSites] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.sites({ size: 200 }).then((d) => setSites(d.items)).finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin style={{ marginTop: 80 }} />;

  const points = sites.reduce((a, s) => a + (s.n_points || 0), 0);
  const heavy = sites.filter((s) => s.pollution_type === "heavy_metal").length;
  const provinces = new Set(sites.map((s) => s.province).filter(Boolean)).size;

  const byType = ["heavy_metal", "organic", "composite"].map((t) => ({
    name: { heavy_metal: "重金属", organic: "有机", composite: "复合" }[t],
    value: sites.filter((s) => s.pollution_type === t).length,
  })).filter((x) => x.value > 0);

  const pieOption = {
    tooltip: { trigger: "item" },
    legend: { bottom: 0 },
    series: [{ type: "pie", radius: ["45%", "70%"], data: byType,
      label: { formatter: "{b}: {c}" },
      color: ["#dc2626", "#f59e0b", "#7c3aed"] }],
  };

  const mapSites = sites.map((s) => ({
    id: s.id, name: s.name, longitude: s.longitude, latitude: s.latitude,
    pollution_type: s.pollution_type,
    status: s.pollution_type === "heavy_metal" ? "danger" : s.pollution_type === "organic" ? "warning" : "info",
  }));

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="场地总数" value={sites.length} valueStyle={{ color: "#0f3d6e" }} /></Card></Col>
        <Col span={6}><Card><Statistic title="重金属污染场地" value={heavy} valueStyle={{ color: "#dc2626" }} /></Card></Col>
        <Col span={6}><Card><Statistic title="采样点总数" value={points} valueStyle={{ color: "#0f766e" }} /></Card></Col>
        <Col span={6}><Card><Statistic title="覆盖省份" value={provinces} valueStyle={{ color: "#b45309" }} /></Card></Col>
      </Row>

      <Row gutter={16}>
        <Col span={16}>
          <Card title="污染类型分布">
            {byType.length ? <ReactECharts option={pieOption} style={{ height: 300 }} /> : <span>暂无数据</span>}
          </Card>
        </Col>
        <Col span={8}>
          <Card title="快捷操作" style={{ marginBottom: 16 }}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Button block icon={<ImportOutlined />} type="primary" onClick={() => nav("/sites/import")}>批量导入数据</Button>
              <Button block icon={<PlusOutlined />} onClick={() => nav("/sites")}>场地管理</Button>
              <Button block icon={<FileTextOutlined />} onClick={() => nav("/trace")}>全流程追溯与报告</Button>
            </Space>
          </Card>
          <Card title="场地清单（最近）">
            <List size="small" dataSource={sites.slice(0, 5)}
              renderItem={(s) => (
                <List.Item actions={[<a onClick={() => nav(`/sites/${s.id}`)}>详情</a>]}>
                  <Space><Tag color={s.pollution_type === "heavy_metal" ? "red" : "orange"}>{s.pollution_type || "—"}</Tag>{s.name}</Space>
                </List.Item>
              )} />
          </Card>
        </Col>
      </Row>

      <Card title="场地分布地图（天地图）">
        <SiteMap sites={mapSites} height={460} onMarkerClick={(s) => s.id && nav(`/sites/${s.id}`)} />
      </Card>
    </Space>
  );
}
