import { useEffect, useState } from "react";
import { Card, Button, Empty, message, Descriptions, Table, Tag, Space, Timeline, Divider } from "antd";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import { seqCol, numCol, textCol } from "../utils/table";

export default function ObstacleAnalysis() {
  const [sid, setSid] = useState<number>();
  const [diag, setDiag] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  const load = (id?: number) => {
    const s = id ?? sid; if (!s) return;
    api.diagnosis(s).then(setDiag).catch(() => setDiag(null));
  };
  useEffect(() => { if (sid) load(sid); }, [sid]);

  const run = async () => {
    if (!sid) return;
    setBusy(true);
    try { await api.runDiagnosis(sid); message.success("诊断完成"); load(sid); }
    catch (e: any) { message.error(e?.response?.data?.detail || "诊断失败"); }
    finally { setBusy(false); }
  };

  const opt = diag?.top_factors?.length ? {
    tooltip: { trigger: "axis" }, grid: { left: 100, right: 30, top: 10, bottom: 30 },
    xAxis: { type: "value", name: "|SHAP|" },
    yAxis: { type: "category", inverse: true, data: diag.top_factors.map((t: any) => t.factor) },
    series: [{ type: "bar", data: diag.top_factors.map((t: any) => t.importance),
      itemStyle: { color: "#0f3d6e" }, label: { show: true, position: "right" } }],
  } : null;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Space style={{ width: "100%", justifyContent: "space-between" }}>
          <SitePicker value={sid} onChange={setSid} />
          <Button type="primary" loading={busy} onClick={run} disabled={!sid}>运行 RF+SHAP 障碍因子识别</Button>
        </Space>
      </Card>
      {diag ? (
        <>
          <Card title="模型与结论">
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="模型">{diag.model?.name} {diag.model?.version}</Descriptions.Item>
              <Descriptions.Item label="模型指标">AUC={diag.model?.metrics?.auc}，F1={diag.model?.metrics?.f1}</Descriptions.Item>
              <Descriptions.Item label="数据版本">{diag.data_version}</Descriptions.Item>
              <Descriptions.Item label="训练数据">{diag.model?.training_data_version}</Descriptions.Item>
              <Descriptions.Item label="结论摘要" span={2}>{diag.summary}</Descriptions.Item>
            </Descriptions>
          </Card>
          <Card title="Top-N 关键障碍因子（全局 SHAP 重要性）">
            {opt && <ReactECharts option={opt} style={{ height: 340 }} />}
            <Table rowKey="rank" size="small" pagination={false} dataSource={diag.top_factors}
              columns={[
                seqCol(64),
                textCol("障碍因子", "factor"),
                textCol("类别", "category"),
                numCol("|SHAP|", "importance"),
                { title: "影响方向", dataIndex: "direction", align: "center",
                  render: (v: string) => <Tag color={v === "positive" ? "red" : "green"}>{v === "positive" ? "正向(加重)" : "负向(缓解)"}</Tag> },
              ]} />
          </Card>
          {diag.shap_global?.calculation_trace?.length > 0 && (
            <Card title="计算过程追溯">
              <Timeline items={diag.shap_global.calculation_trace.map((s: string) => ({ children: s }))} />
            </Card>
          )}
          {diag.local_explanation?.length > 0 && (
            <Card title="局部解释（最高风险采样点）">
              <Table rowKey={(r: any) => r.factor + r.point_code} size="small" pagination={false}
                dataSource={diag.local_explanation}
                columns={[seqCol(64), textCol("采样点", "point_code"), textCol("因子", "factor"),
                  numCol("SHAP值", "shap_value"),
                  { title: "方向", dataIndex: "direction", align: "center" }]} />
            </Card>
          )}
        </>
      ) : <Empty description="请选择场地并运行障碍因子识别" />}
    </Space>
  );
}
