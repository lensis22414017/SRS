import { useEffect, useState } from "react";
import { Card, Button, Empty, message, Row, Col, Statistic, Tag, Space, Table, Divider, Alert, Timeline } from "antd";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import { seqCol, numCol, textCol } from "../utils/table";

/** SSUI 评价 = 方法文件第3章 土壤持续利用经济性和安全性评价(SSUI 模型) */
export default function SSUIAnalysis() {
  const [sid, setSid] = useState<number>();
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  const load = (id?: number) => {
    const s = id ?? sid; if (!s) return;
    api.evaluation(s).then(setData).catch(() => setData(null));
  };
  useEffect(() => { if (sid) load(sid); }, [sid]);

  const run = async () => {
    if (!sid) return;
    setBusy(true);
    try { await api.runEvaluation(sid); message.success("SSUI 评价完成"); load(sid); }
    catch (e: any) { message.error(e?.response?.data?.detail || "评价失败"); }
    finally { setBusy(false); }
  };

  const s = data?.results?.ssui;
  const parts = (s?.dimensions?.parts || []) as any[];
  const trace = (s?.dimensions?.calculation_trace || []) as string[];
  const gauge = s ? {
    series: [{ type: "gauge", min: 0, max: 1, splitNumber: 5,
      axisLine: { lineStyle: { width: 18, color: [[0.4, "#dc2626"], [0.6, "#f59e0b"], [0.8, "#3b82f6"], [1, "#16a34a"]] } },
      pointer: { width: 5 }, detail: { formatter: "{value}", fontSize: 24, offsetCenter: [0, "70%"] },
      data: [{ value: s.score }] }],
  } : null;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Space style={{ width: "100%", justifyContent: "space-between" }}>
          <SitePicker value={sid} onChange={setSid} />
          <Button type="primary" loading={busy} onClick={run} disabled={!sid}>运行 SSUI 可持续利用评价</Button>
        </Space>
        <p style={{ color: "#888", marginTop: 8, marginBottom: 0, fontSize: 12 }}>
          方法依据：分维度多指标分块赋权 SSUI 模型 = (Σ vCi·SCi)·f(t)·M。来源评价方法文件第三章（表3.49 管理调节因子、表3.50 等级划分）。
        </p>
      </Card>
      {s ? (
        <Card title="土壤持续利用度（SSUI）评价">
          <Alert type="warning" style={{ marginBottom: 16 }}
            message="MVP 口径说明" description={s.explanation} />
          <Row gutter={16} align="middle">
            <Col span={8}>{gauge && <ReactECharts option={gauge} style={{ height: 220 }} />}</Col>
            <Col span={8}><Statistic title="SSUI 指数" value={s.score} /></Col>
            <Col span={8}><div>可持续性等级</div>
              <Tag color={s.grade?.includes("不") ? "red" : s.grade?.includes("低") ? "orange" : "green"}
                style={{ fontSize: 16, padding: "4px 12px", marginTop: 8 }}>{s.grade}</Tag></Col>
          </Row>
          <Divider />
          <h4>限制因子 C1 元指标得分</h4>
          <Table rowKey="meta" size="small" pagination={false} dataSource={parts}
            columns={[
              seqCol(64),
              textCol("元指标", "meta"),
              numCol("归一化得分", "normalized"),
              numCol("权重", "weight", { render: (v: number) => v != null ? (v * 100).toFixed(2) + "%" : "—" }),
            ]} />
          {trace.length > 0 && (
            <>
              <Divider />
              <Card size="small" title="计算过程追溯">
                <Timeline items={trace.map((step) => ({ children: step }))} />
              </Card>
            </>
          )}
        </Card>
      ) : <Empty description="请选择场地并运行 SSUI 评价" />}
    </Space>
  );
}
