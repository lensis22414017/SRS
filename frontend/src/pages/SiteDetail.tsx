import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, Descriptions, Tabs, Table, Button, Spin, Space, message, Select } from "antd";
import { api } from "../api/client";
import SiteMap from "../components/SiteMap";
import EdaPanel from "../components/EdaPanel";
import { seqCol, numCol, textCol } from "../utils/table";

export default function SiteDetail() {
  const { id } = useParams();
  const sid = Number(id);
  const nav = useNavigate();
  const [site, setSite] = useState<any>(null);
  const [points, setPoints] = useState<any[]>([]);
  const [wide, setWide] = useState<any>({ factors: [], items: [] });
  const [reports, setReports] = useState<any[]>([]);
  const [mapLayer, setMapLayer] = useState<any>(null);
  const [mapFactor, setMapFactor] = useState<string | undefined>();

  const load = async () => {
    setSite(await api.site(sid));
    setPoints(await api.points(sid));
    setWide(await api.pointsWide(sid).catch(() => ({ factors: [], items: [] })));
    setReports(await api.reports(sid).then((d) => d.items).catch(() => []));
    setMapLayer(await api.siteMapLayers(sid, mapFactor ? { factor: mapFactor } : undefined).catch(() => null));
  };
  useEffect(() => { load(); }, [sid]);
  useEffect(() => {
    if (!site) return;
    api.siteMapLayers(sid, mapFactor ? { factor: mapFactor } : undefined)
      .then(setMapLayer)
      .catch(() => setMapLayer(null));
  }, [mapFactor]);

  if (!site) return <Spin style={{ marginTop: 80 }} />;

  // 采样点宽表: 元数据列 + 动态因子列, 横向滚动
  const wideColumns: any[] = [
    { title: "序号", dataIndex: "seq", align: "center", width: 64, fixed: "left" },
    { title: "采样点编号", dataIndex: "point_code", align: "left", width: 130, fixed: "left" },
    { title: "区域", dataIndex: "region", align: "left", width: 90 },
    { title: "经度", dataIndex: "longitude", align: "center", width: 110 },
    { title: "纬度", dataIndex: "latitude", align: "center", width: 110 },
    { title: "深度cm", dataIndex: "depth", align: "center", width: 90 },
    { title: "土壤类型", dataIndex: "soil_type", align: "left", width: 130 },
    ...wide.factors.map((f: string) => ({
      title: f, dataIndex: f, align: "center", width: 110,
      render: (v: any) => (v === null || v === undefined ? "—" : v),
    })),
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Descriptions title={`${site.name}（${site.site_code}）`} column={3} size="small">
          <Descriptions.Item label="污染类型">{site.pollution_type || "—"}</Descriptions.Item>
          <Descriptions.Item label="用地类型">{site.land_use_type || "—"}</Descriptions.Item>
          <Descriptions.Item label="区域">{(site.province || "") + (site.city || "") || "—"}</Descriptions.Item>
          <Descriptions.Item label="采样点">{site.n_points}</Descriptions.Item>
          <Descriptions.Item label="检测记录">{site.n_measurements}</Descriptions.Item>
          <Descriptions.Item label="坐标">{site.longitude}, {site.latitude}</Descriptions.Item>
        </Descriptions>
        <Space style={{ marginTop: 12 }} wrap>
          <Button onClick={() => nav("/obstacle")}>障碍因子分析</Button>
          <Button onClick={() => nav("/reconstruction")}>功能重构分析</Button>
          <Button onClick={() => nav("/ssui")}>SSUI 评价</Button>
          <Button onClick={() => nav(`/trace/${sid}`)}>全流程追溯</Button>
          <Button type="primary" onClick={() => nav("/sites/import")}>导入数据</Button>
          <Button onClick={async () => { try { await api.exportMeasurements(sid, "csv"); message.success("已导出检测数据 CSV"); } catch (e: any) { message.error(e?.response?.data?.detail || "导出失败（需 data:export 权限）"); } }}>导出检测数据 CSV</Button>
          <Button onClick={async () => { try { await api.exportMeasurements(sid, "xlsx"); message.success("已导出检测数据 XLSX"); } catch (e: any) { message.error(e?.response?.data?.detail || "导出失败（需 data:export 权限）"); } }}>导出 XLSX</Button>
        </Space>
      </Card>

      <Tabs items={[
        {
          key: "map", label: "点位地图",
          children: <Card title="采样点空间分布与超标分级" extra={
            <Select allowClear placeholder="按污染物筛选" style={{ width: 220 }}
              value={mapFactor} onChange={setMapFactor}
              options={(mapLayer?.pollutants || []).map((p: any) => ({
                value: p.factor_code, label: `${p.factor_name || p.factor_code}${p.unit ? ` (${p.unit})` : ""}`,
              }))} />
          }>
            <SiteMap height={440} zoom={15} layerData={mapLayer}
              sites={points.map((p) => ({ point_code: p.point_code, longitude: p.longitude, latitude: p.latitude, pollution_type: site.pollution_type }))} />
          </Card>,
        },
        {
          key: "wide", label: `采样点检测数据（${wide.items.length}）`,
          children: <Card bodyStyle={{ padding: 12 }}>
            <Table rowKey="seq" size="small" dataSource={wide.items} columns={wideColumns}
              scroll={{ x: "max-content", y: 480 }} pagination={{ pageSize: 20 }} bordered />
          </Card>,
        },
        {
          key: "eda", label: "数据分析(EDA)",
          children: <EdaPanel siteId={sid} />,
        },
        {
          key: "report", label: `追溯报告（${reports.length}）`,
          children: reports.length ? <Table rowKey="report_id" size="small" pagination={false} dataSource={reports}
            columns={[
              seqCol(64), textCol("版本", "version"), textCol("生成时间", "generated_at"),
              { title: "下载", align: "center", render: (_: any, r: any) => <a onClick={() => api.downloadReport(r.report_id, `追溯报告_${site.site_code}_${r.version}.pdf`)}>下载</a> },
            ]} /> : <Space direction="vertical"><span>暂无报告</span><Button onClick={() => nav(`/trace/${sid}`)}>前往追溯页生成报告</Button></Space>,
        },
      ]} />
    </Space>
  );
}
