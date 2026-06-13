import { useEffect, useState } from "react";
import { Card, Table, Select, Spin, Empty, Row, Col, Tag, Space } from "antd";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import { seqCol, numCol, textCol } from "../utils/table";

/** 进入模型前的 EDA 数据体检: 概览指标表 + 选定因子直方图(真实数据)。 */
export default function EdaPanel({ siteId }: { siteId: number }) {
  const [data, setData] = useState<any>(null);
  const [sel, setSel] = useState<string>();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.eda(siteId).then((d) => {
      setData(d);
      if (d.factors?.length) setSel(d.factors[0].factor);
    }).catch(() => setData(null)).finally(() => setLoading(false));
  }, [siteId]);

  if (loading) return <Spin style={{ marginTop: 40 }} />;
  if (!data?.factors?.length) return <Empty description="暂无可分析数据" />;

  const cur = data.factors.find((f: any) => f.factor === sel);
  const hist = cur?.histogram;
  const histOption = hist?.counts?.length ? {
    tooltip: { trigger: "axis" },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "category", data: hist.edges.slice(0, -1).map((e: number, i: number) => `${e}~${hist.edges[i + 1]}`),
      axisLabel: { rotate: 45, fontSize: 9 }, name: cur.factor },
    yAxis: { type: "value", name: "频数" },
    series: [{ type: "bar", data: hist.counts, itemStyle: { color: "#0f3d6e" } }],
  } : null;

  const rows = data.factors.map((f: any) => ({ factor: f.factor, ...f.stats }));

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card title="各因子统计体检（真实数据，未插补）" size="small">
        <Table rowKey="factor" size="small" dataSource={rows} pagination={{ pageSize: 8 }}
          scroll={{ x: "max-content" }}
          columns={[
            seqCol(56),
            textCol("因子", "factor"),
            numCol("有效数", "count"),
            numCol("缺失%", "missing_pct"),
            numCol("均值", "mean"),
            numCol("中位数", "median"),
            numCol("标准差", "std"),
            numCol("CV", "cv"),
            numCol("偏度", "skew"),
            { title: "形态", dataIndex: "skew_flag", align: "center",
              render: (v: string) => <Tag color={v === "近似对称" ? "green" : "orange"}>{v || "—"}</Tag> },
            numCol("异常点", "outliers"),
            numCol("最小", "min"), numCol("最大", "max"),
          ]} />
      </Card>
      <Card title="分布直方图" size="small"
        extra={<Select style={{ width: 200 }} value={sel} onChange={setSel}
          options={data.factors.map((f: any) => ({ value: f.factor, label: f.factor }))} />}>
        <Row gutter={16}>
          <Col span={16}>{histOption ? <ReactECharts option={histOption} style={{ height: 320 }} /> : <Empty />}</Col>
          <Col span={8}>
            {cur && (
              <Table size="small" pagination={false} showHeader={false}
                rowKey="k" dataSource={[
                  { k: "均值/中位数", v: `${cur.stats.mean} / ${cur.stats.median}` },
                  { k: "标准差 / CV", v: `${cur.stats.std} / ${cur.stats.cv ?? "—"}` },
                  { k: "偏度 / 形态", v: `${cur.stats.skew ?? "—"} ${cur.stats.skew_flag ?? ""}` },
                  { k: "异常点(IQR)", v: `${cur.stats.outliers}（${cur.stats.outlier_pct}%）` },
                  { k: "P5 / P95", v: `${cur.stats.p05} / ${cur.stats.p95}` },
                  { k: "缺失率", v: `${cur.stats.missing_pct}%` },
                ]}
                columns={[textCol("指标", "k"), { title: "值", dataIndex: "v", align: "right" }]} />
            )}
          </Col>
        </Row>
      </Card>
    </Space>
  );
}
