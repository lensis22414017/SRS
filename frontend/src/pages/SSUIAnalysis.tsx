import { useEffect, useState } from "react";
import { Card, Button, Empty, App, Row, Col, Statistic, Tag, Space, Table, Divider, Alert, Timeline, Typography, InputNumber, Select } from "antd";
import { ApartmentOutlined, ExportOutlined } from "@ant-design/icons";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import FormulaBlock from "../components/FormulaBlock";
import OrganicDegradedCard from "../components/OrganicDegradedCard";
import EmptyState from "../components/EmptyState";
import MethodFlowDrawer from "../components/MethodFlowDrawer";
import { seqCol, numCol, textCol } from "../utils/table";
import { SVG_OPTS } from "../theme/echarts";
import { getFlowConfig } from "../config/methodFlows";

const { Text } = Typography;

/** SSUI 评价 = 方法文件第3章 土壤持续利用经济性和安全性评价(SSUI 模型) */
export default function SSUIAnalysis() {
  const { message } = App.useApp();
  const [sid, setSid] = useState<number>();
  const [data, setData] = useState<any>(null);     // GET: 历史 + current_data_version
  const [hasRun, setHasRun] = useState(false);     // 是否已点击运行(控制本次结果区显隐, brief 4.5)
  const [busy, setBusy] = useState(false);
  const [flowOpen, setFlowOpen] = useState(false);
  // v1.0.2(GPT P0-4): SSUI 评价参数(t=利用年限, intensity=管理强度)
  const [evalT, setEvalT] = useState<number>(2);
  const [evalIntensity, setEvalIntensity] = useState<string>("medium");

  const load = (id?: number) => {
    const s = id ?? sid; if (!s) return;
    api.evaluation(s).then(setData).catch(() => setData(null));
  };
  useEffect(() => { if (sid) { setHasRun(false); load(sid); } }, [sid]);

  const run = async () => {
    if (!sid) return;
    setBusy(true);
    try {
      await api.runEvaluation(sid, { t: evalT, intensity: evalIntensity });
      setData(null);     // 清旧, 避免 load 完成前 race 显旧(M5)
      setHasRun(true);   // 标记本次运行完成, 显示结果区(避免历史伪装成本次)
      load(sid);         // 刷新最新结果(run 后已入库, is_stale=false)
      message.success("SSUI 评价完成");
    } catch (e: any) { message.error(e?.response?.data?.detail || "评价失败"); }
    finally { setBusy(false); }
  };

  const histS = data?.results?.ssui;   // 历史 SSUI(选场地即显元信息 + is_stale)
  const curDv = data?.current_data_version;
  const s = histS;                     // 完整结果(GET 含 score/dimensions/parts)
  const showResult = hasRun && !!s;    // 仅点击运行后才显完整结果区
  const parts = (s?.dimensions?.parts || []) as any[];
  const trace = (s?.dimensions?.calculation_trace || []) as string[];
  const gauge = s ? {
    series: [{ type: "gauge", min: 0, max: 1, splitNumber: 5,
      axisLine: { lineStyle: { width: 18, color: [[0.4, "#dc2626"], [0.6, "#f59e0b"], [0.8, "#3b82f6"], [1, "#16a34a"]] } },
      pointer: { width: 5 }, detail: { formatter: "{value}", fontSize: 24, offsetCenter: [0, "70%"] },
      data: [{ value: s.score }] }],
  } : null;
  // SSUI 补维度可视化(归一化得分 + 权重双轴条形图, NPG 顶刊色)
  // 一眼看出哪个元指标"得分低且权重大"(= 重点管控对象), 契合 SSUI 限制因子识别目标
  const partsOption = parts.length ? {
    tooltip: { trigger: "axis", formatter: (p: any) => {
      const d = parts[p[0].dataIndex];
      return `${d.meta}<br/>归一化得分: ${p[0].value}<br/>权重: ${d.weight != null ? (d.weight * 100).toFixed(1) + "%" : "—"}`;
    } },
    legend: { data: ["归一化得分", "权重(%)"] },
    grid: { left: 60, right: 60, top: 40, bottom: 70 },
    xAxis: { type: "category", data: parts.map((p: any) => p.meta), axisLabel: { rotate: 30, fontSize: 10 } },
    yAxis: [{ type: "value", name: "归一化得分", position: "left" },
            { type: "value", name: "权重(%)", position: "right", max: 100 }],
    series: [
      { name: "归一化得分", type: "bar", data: parts.map((p: any) => p.normalized ?? 0),
        itemStyle: { color: "#4DBBD5", borderRadius: [4,4,0,0], shadowBlur: 4, shadowColor: "rgba(0,0,0,0.15)" }, barMaxWidth: 32 },
      { name: "权重(%)", type: "bar", yAxisIndex: 1,
        data: parts.map((p: any) => (p.weight != null ? p.weight * 100 : 0)),
        itemStyle: { color: "#E64B35", borderRadius: [4,4,0,0], shadowBlur: 4, shadowColor: "rgba(0,0,0,0.15)" }, barMaxWidth: 32 },
    ],
  } : null;

  // Round7 追加: 安全-经济二维象限(从 parts 提取安全/经济类维度) + 趋势面积(f(t)) + 成本效益堆叠
  const safetyPart = parts.find((p: any) => (p.meta || "").includes("安全") || (p.meta || "").includes("毒性"));
  const econPart = parts.find((p: any) => (p.meta || "").includes("经济") || (p.meta || "").includes("成本"));
  const safetyScore = safetyPart ? (safetyPart.normalized ?? 0) : (s?.score ?? 0);
  const econScore = econPart ? (econPart.normalized ?? 0) : (s?.score ?? 0);
  const seScatterOption = s ? {
    tooltip: { trigger: "item", formatter: (p: any) => "安全性: " + p.data[0].toFixed(3) + "<br/>经济性: " + p.data[1].toFixed(3) },
    grid: { left: 60, right: 50, top: 50, bottom: 50 },
    xAxis: { name: "安全性", min: 0, max: 1, nameLocation: "middle", nameGap: 28 },
    yAxis: { name: "经济性", min: 0, max: 1, nameLocation: "middle", nameGap: 28 },
    series: [{ type: "scatter", symbolSize: 28, data: [[safetyScore, econScore]],
      itemStyle: { color: safetyScore >= 0.6 && econScore >= 0.6 ? "#15803d" : "#f59e0b" },
      label: { show: true, formatter: "本场地", position: "right" } }],
    graphic: [
      { type: "text", left: "62%", top: "30%", style: { text: "安全+经济\n双优", fill: "#15803d", fontSize: 10 } },
      { type: "text", left: "15%", top: "62%", style: { text: "双弱区\n(需重点修复)", fill: "#dc2626", fontSize: 10 } },
    ],
  } : null;
  // 趋势面积: f(t)=1+0.03t × SSUI score, 模拟修复后 0~10 年可持续性演变
  const trendAreaOption = s ? {
    tooltip: { trigger: "axis", formatter: (p: any) => "修复后 " + p[0].axisValue + " 年<br/>SSUI: " + p[0].value.toFixed(3) },
    grid: { left: 50, right: 20, top: 40, bottom: 40 },
    xAxis: { type: "category", data: ["0", "1", "2", "3", "5", "7", "10"], name: "修复后年数", nameLocation: "middle", nameGap: 25, axisLabel: { interval: 0 } },
    yAxis: { type: "value", name: "SSUI", min: 0, max: 1.3 },
    series: [{ type: "line", smooth: true, symbolSize: 6,
      data: ["0", "1", "2", "3", "5", "7", "10"].map((t) => Math.min(1.29, (s.score ?? 0) * (1 + 0.03 * Number(t)))),
      areaStyle: { color: "#4DBBD5", opacity: 0.22 }, lineStyle: { color: "#4DBBD5", width: 2 } }],
  } : null;
  // 成本效益堆叠: parts 按权重分堆(安全类/经济类/其他)
  const safetyW = parts.filter((p: any) => (p.meta || "").includes("安全") || (p.meta || "").includes("毒性")).reduce((s2: number, p: any) => s2 + (p.weight ?? 0), 0);
  const econW = parts.filter((p: any) => (p.meta || "").includes("经济") || (p.meta || "").includes("成本")).reduce((s2: number, p: any) => s2 + (p.weight ?? 0), 0);
  const otherW = parts.reduce((s2: number, p: any) => s2 + (p.weight ?? 0), 0) - safetyW - econW;
  const costBenefitOption = parts.length ? {
    tooltip: { trigger: "axis", formatter: (p: any) => p[0].name + ": " + (p[0].value * 100).toFixed(1) + "%" },
    legend: { data: ["安全性", "经济性", "其他"], top: 0, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 10 } },
    grid: { left: 70, right: 30, top: 32, bottom: 24 },
    xAxis: { type: "value", name: "权重占比", max: 1 },
    yAxis: { type: "category", data: ["权重分布"] },
    series: [
      { name: "安全性", type: "bar", stack: "w", color: "#3b82f6", barMaxWidth: 40, data: [safetyW || 0.001] },
      { name: "经济性", type: "bar", stack: "w", color: "#f59e0b", barMaxWidth: 40, data: [econW || 0.001] },
      { name: "其他", type: "bar", stack: "w", color: "#94a3b8", barMaxWidth: 40, data: [otherW || 0.001] },
    ],
  } : null;

  return (
    <>
      <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Space style={{ width: "100%", flexWrap: "wrap", rowGap: 8 }}>
          <SitePicker value={sid} onChange={setSid} style={{ maxWidth: 180 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>年限t:</Text>
          <InputNumber size="small" min={1} max={50} value={evalT} onChange={(v) => setEvalT(v ?? 2)} style={{ width: 56 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>强度:</Text>
          <Select size="small" value={evalIntensity} onChange={setEvalIntensity} style={{ width: 90 }}
            options={[
              { value: "weak", label: "粗放" },
              { value: "medium", label: "中等" },
              { value: "strong", label: "集约" },
            ]} />
          <Button icon={<ApartmentOutlined />} onClick={() => setFlowOpen(true)}>方法说明</Button>
          {data && <Button icon={<ExportOutlined />} onClick={() => {
            api.generateReport(sid!, "pdf").then(() => message.success("SSUI 评价报告生成中...")).catch(() => message.error("导出失败"));
            }}>导出报告</Button>}
          <Button type="primary" loading={busy} onClick={run} disabled={!sid}>运行评价</Button>
        </Space>
        <div style={{ marginTop: 12 }}>
          <FormulaBlock
            title="SSUI 土壤可持续利用综合指数"
            latex={"SSUI = \\left(\\sum_{i=1}^{n} vC_i \\cdot SC_i\\right) \\cdot f(t) \\cdot M"}
            source="《污染场地土壤生态-生产功能重构监管系统》评价方法文件第三章 §3.2（表3.49-3.50）"
            note="其中 f(t) = 1 + 0.03·t 为时间修正函数，M 为管理调节因子（表3.49），等级边界见下方说明"
          >
            <Alert type="info" showIcon style={{ marginBottom: 12 }}
              message="完整评价体系基于甲方方法 25 项元指标（D1-D25），按限制因子C1/风险因子C2/经济成本C3/经济效益C4 四个准则层分组。当前为 MVP 口径（场内 Min-Max 归一化），跨场地锚点/PCA 降维/博弈论赋权待后续版本接入多场地数据后启用。" />
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 4 }}>
              {[
                { range: "≥ 0.80", label: "高可持续性", color: "#16a34a" },
                { range: "0.60 ~ 0.80", label: "中高可持续性", color: "#3b82f6" },
                { range: "0.40 ~ 0.60", label: "中可持续性", color: "#f59e0b" },
                { range: "< 0.40", label: "低可持续性", color: "#dc2626" },
              ].map((g) => (
                <Tag key={g.range} color={g.color} style={{ fontSize: 11 }}>
                  {g.range}：{g.label}
                </Tag>
              ))}
            </div>
          </FormulaBlock>
          <FormulaBlock
            title="时间修正函数 f(t)"
            latex={"f(t) = 1 + 0.03 \\cdot t \\quad (t \\text{ 为修复后年数})"}
            source="评价方法文件第三章 §3.2.4"
            note="反映修复效果随时间累积改善的规律，t=0 时 f(t)=1（基准年）"
          />
        </div>
      </Card>
      {sid && histS && (
        <Card size="small" title="历史 SSUI 结果（仅供参考，非本次运行）">
          <Alert
            type={histS.is_stale ? "warning" : "info"}
            showIcon
            message={`历史 SSUI ｜ 生成时间 ${histS.created_at}｜结果数据版本 ${histS.data_version}｜当前数据版本 ${curDv ?? "—"}`}
            description={histS.is_stale
              ? "⚠ 场地数据已变更，该历史结果已过期(stale)，建议重新运行。"
              : histS.grade === "不适用(有机)"
                ? "该场地为有机污染，SSUI 不适用。点击上方按钮查看有机污染风险诊断降级说明。"
                : `历史得分 ${histS.score}（${histS.grade}）。点击上方按钮可重新生成本次结果。`}
          />
        </Card>
      )}
      {showResult && s?.grade === "不适用(有机)" ? (
        <OrganicDegradedCard
          organicRisk={data?.results?.organic_risk?.dimensions || s?.dimensions?.organic_risk}
          limitingFactors={s?.limiting_factors}
          explanation={s?.explanation}
          title="SSUI 可持续利用评价 — 不适用(有机污染场地)" />
      ) : showResult ? (
        <Card title="土壤持续利用度（SSUI）评价"
          extra={<Text type="secondary" style={{ fontSize: 12 }}>本次运行 ｜ 数据版本 {s?.data_version} ｜ 参数版本 {s?.param_version} ｜ {s?.created_at}</Text>}>
          <Alert type="warning" style={{ marginBottom: 16 }}
            message="25项完整口径（场内归一化 MVP）" description={s.explanation} />
          <Row gutter={16} align="middle">
            <Col span={8}>{gauge && <ReactECharts option={gauge} theme="srs-light" opts={SVG_OPTS} style={{ height: 220 }} />}</Col>
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
          {partsOption && (
            <Card size="small" title="各元指标归一化得分与权重（双轴条形图 · 识别重点管控对象）" style={{ marginTop: 12 }}>
              <ReactECharts option={partsOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 280 }} />
            </Card>
          )}
          {/* Round7 追加: 安全经济象限 + 趋势面积 + 成本效益堆叠, 保留上方仪表盘/双轴条形图 */}
          <Row gutter={16} style={{ marginTop: 12 }}>
            {seScatterOption && (
              <Col span={8}>
                <Card size="small" title="安全性-经济性二维象限">
                  <ReactECharts option={seScatterOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 280 }} />
                </Card>
              </Col>
            )}
            {trendAreaOption && (
              <Col span={8}>
                <Card size="small" title="长期利用趋势（f(t) 修正 · 修复后 0~10 年）">
                  <ReactECharts option={trendAreaOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 300 }} />
                </Card>
              </Col>
            )}
            {costBenefitOption && (
              <Col span={8}>
                <Card size="small" title="成本效益权重堆叠（安全/经济/其他）">
                  <ReactECharts option={costBenefitOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 280 }} />
                </Card>
              </Col>
            )}
          </Row>
          {trace.length > 0 && (
            <>
              <Divider />
              <Card size="small" title="计算过程追溯">
                <Timeline items={trace.map((step) => ({ children: step }))} />
              </Card>
            </>
          )}
        </Card>
      ) : <EmptyState description="请选择场地并运行 SSUI 评价" />}
    </Space>
      <MethodFlowDrawer open={flowOpen} onClose={() => setFlowOpen(false)} config={getFlowConfig("ssui_eval")!} />
    </>
  );
}
