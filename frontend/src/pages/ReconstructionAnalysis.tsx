import { useEffect, useState } from "react";
import { Card, Button, Empty, message, Row, Col, Statistic, Tag, Space, Table, Divider, Timeline } from "antd";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import { seqCol, numCol, textCol } from "../utils/table";

/** 功能重构分析 = 方法文件第2章 污染土壤生产-生态功能重构可行性评价(生产功能 + 生态功能) */
function EvalBlock({ title, e }: { title: string; e: any }) {
  if (!e) return <Empty description={`暂无${title}结果`} />;
  const dims = (e.dimensions?.dimensions || []) as any[];
  const trace = (e.dimensions?.calculation_trace || []) as string[];
  return (
    <Card type="inner" title={title} style={{ marginBottom: 16 }}>
      <Row gutter={16} style={{ marginBottom: 12 }}>
        <Col span={8}><Statistic title="综合得分" value={e.score} suffix="分"
          valueStyle={{ color: e.grade === "可行" ? "#15803d" : "#b91c1c" }} /></Col>
        <Col span={8}><div>评价等级</div><Tag color={e.grade === "可行" ? "green" : "red"} style={{ fontSize: 16, padding: "4px 12px", marginTop: 8 }}>{e.grade}</Tag></Col>
        <Col span={8}><div>关键限制因子</div><div style={{ marginTop: 8 }}>{(e.limiting_factors || []).map((f: string) => <Tag color="orange" key={f}>{f}</Tag>) || "—"}</div></Col>
      </Row>
      <p style={{ color: "#666", fontSize: 13 }}>{e.explanation}</p>
      <Divider style={{ margin: "12px 0" }} />
      <Table rowKey="indicator" size="small" pagination={false} dataSource={dims}
        columns={[
          seqCol(64),
          textCol("评价指标", "indicator"),
          numCol("指标得分 F", "F"),
          numCol("归一权重", "norm_weight", { render: (v: number) => v != null ? (v * 100).toFixed(2) + "%" : "—" }),
          numCol("贡献分", "contribution"),
        ]} />
      {trace.length > 0 && (
        <>
          <Divider style={{ margin: "12px 0" }} />
          <Card size="small" title="计算过程追溯">
            <Timeline items={trace.map((step) => ({ children: step }))} />
          </Card>
        </>
      )}
    </Card>
  );
}

export default function ReconstructionAnalysis() {
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
    try { await api.runEvaluation(sid); message.success("评价完成"); load(sid); }
    catch (e: any) { message.error(e?.response?.data?.detail || "评价失败"); }
    finally { setBusy(false); }
  };

  const prod = data?.results?.reconstruction_prod;
  const eco = data?.results?.reconstruction_eco;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Space style={{ width: "100%", justifyContent: "space-between" }}>
          <SitePicker value={sid} onChange={setSid} />
          <Button type="primary" loading={busy} onClick={run} disabled={!sid}>运行功能重构可行性评价</Button>
        </Space>
        <p style={{ color: "#888", marginTop: 8, marginBottom: 0, fontSize: 12 }}>
          方法依据：改进模糊综合评价法（指标分等赋值 × 权重，&gt;50 可行）。来源《污染场地土壤生态-生产功能障碍识别与重构利用的评价方法》第二章。
        </p>
      </Card>
      {prod || eco ? (
        <Card title="功能重构可行性评价">
          <EvalBlock title="生产功能重构可行性" e={prod} />
          <EvalBlock title="生态功能重构可行性" e={eco} />
        </Card>
      ) : <Empty description="请选择场地并运行功能重构评价" />}
    </Space>
  );
}
