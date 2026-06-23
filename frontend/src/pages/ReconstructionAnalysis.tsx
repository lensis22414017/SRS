import { useEffect, useState } from "react";
import { Card, Button, Empty, message, Row, Col, Statistic, Tag, Space, Table, Divider, Timeline, Progress, Alert } from "antd";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import FormulaBlock from "../components/FormulaBlock";
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
          {
            title: "贡献可视化", dataIndex: "contribution", key: "bar",
            render: (v: number) => (
              <Progress
                percent={v != null ? Math.min(Math.round(v), 100) : 0}
                size="small"
                strokeColor={v > 15 ? "#16a34a" : v > 8 ? "#3b82f6" : "#f59e0b"}
                format={(p) => `${p}分`}
                style={{ minWidth: 120 }}
              />
            ),
          },
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
  const [hasRun, setHasRun] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = (id?: number) => {
    const s = id ?? sid; if (!s) return;
    api.evaluation(s).then(setData).catch(() => setData(null));
  };
  useEffect(() => { if (sid) { setHasRun(false); load(sid); } }, [sid]);

  const run = async () => {
    if (!sid) return;
    setBusy(true);
    try { await api.runEvaluation(sid); setHasRun(true); message.success("评价完成"); load(sid); }
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
        <div style={{ marginTop: 12 }}>
          <FormulaBlock
            title="功能重构可行性综合得分"
            latex={"T_{total} = \\sum_{i=1}^{n} \\left(F_i \\times W_i\\right)"}
            source="《污染场地土壤生态-生产功能障碍识别与重构利用的评价方法》第二章 §2.3 改进模糊综合评价法"
            note="F_i 为第 i 项指标得分（1~100 分等），W_i 为归一化权重；T_total > 50 判定为可行"
          >
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
              {[
                { range: "> 70", label: "高度可行", color: "#16a34a" },
                { range: "50 ~ 70", label: "基本可行", color: "#3b82f6" },
                { range: "30 ~ 50", label: "有条件可行", color: "#f59e0b" },
                { range: "< 30", label: "不可行", color: "#dc2626" },
              ].map((g) => (
                <Tag key={g.range} color={g.color} style={{ fontSize: 11 }}>
                  {g.range}：{g.label}
                </Tag>
              ))}
            </div>
          </FormulaBlock>
        </div>
      </Card>
      {sid && (prod || eco) && !hasRun && (
        <Card size="small" title="历史功能重构评价（仅供参考，非本次运行）">
          <Alert
            type={prod?.is_stale || eco?.is_stale ? "warning" : "info"} showIcon
            message={`历史评价 ｜ 生产 ${prod?.score ?? "—"}(${prod?.grade ?? "—"}) / 生态 ${eco?.score ?? "—"}(${eco?.grade ?? "—"}) ｜ 当前数据版本 ${data?.current_data_version ?? "—"}`}
            description={prod?.is_stale || eco?.is_stale
              ? "⚠ 场地数据已变更，历史结果已过期(stale)，建议重新运行。"
              : "点击上方按钮可重新生成本次结果。"}
          />
        </Card>
      )}
      {hasRun && (prod || eco) ? (
        <Card title="功能重构可行性评价"
          extra={<span style={{ fontSize: 12, color: "#888" }}>本次运行 ｜ 数据版本 {prod?.data_version ?? eco?.data_version} ｜ {prod?.created_at ?? eco?.created_at}</span>}>
          <EvalBlock title="生产功能重构可行性" e={prod} />
          <EvalBlock title="生态功能重构可行性" e={eco} />
        </Card>
      ) : <Empty description="请选择场地并点击「运行」生成功能重构评价" />}
    </Space>
  );
}
