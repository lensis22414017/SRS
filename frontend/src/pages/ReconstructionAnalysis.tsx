import { useEffect, useState } from "react";
import { Card, Button, Empty, App, Row, Col, Statistic, Tag, Space, Table, Divider, Timeline, Progress, Alert, Collapse } from "antd";
import { ApartmentOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import MethodFlowDrawer from "../components/MethodFlowDrawer";
import { getFlowConfig } from "../config/methodFlows";
import FormulaBlock from "../components/FormulaBlock";
import OrganicDegradedCard from "../components/OrganicDegradedCard";
import ReactECharts from "echarts-for-react";
import ReportActions from "../components/ReportActions";
import { seqCol, numCol, textCol } from "../utils/table";
import { formatFactor } from "../utils/factorFormat";
import { SVG_OPTS } from "../theme/echarts";

/** 功能重构分析 = 方法文件第2章 污染土壤生产-生态功能重构可行性评价(生产功能 + 生态功能) */
function EvalBlock({ title, e, organicRisk }: { title: string; e: any; organicRisk?: any }) {
  if (!e) return <Empty description={`暂无${title}结果`} />;
  // 有机场地降级 — 不显示 null 分, 改有机风险诊断卡片
  if (e.grade === "不适用(有机)") {
    return <OrganicDegradedCard organicRisk={organicRisk || e.dimensions?.organic_risk}
      limitingFactors={e.limiting_factors} explanation={e.explanation}
      title={`${title} — 不适用(有机污染场地)`} />;
  }
  const dims = (e.dimensions?.dimensions || []) as any[];
  const trace = (e.dimensions?.calculation_trace || []) as string[];
  // 功能重构模块补可视化(雷达图 + 贡献度条形图, NPG 顶刊色)
  // 雷达图: 各评价指标 F 得分(0-100), 一眼识别短板(木桶效应可视化)
  const radarOption = dims.length >= 3 ? {
    tooltip: {},
    radar: { indicator: dims.map((d: any) => ({ name: d.indicator ?? "?", max: 100 })), radius: "60%", center: ["55%", "52%"] },
    series: [{ type: "radar", data: [{ value: dims.map((d: any) => d.F ?? 0), name: title,
      areaStyle: { color: "#3C5488", opacity: 0.22 }, lineStyle: { color: "#3C5488", width: 2 },
      itemStyle: { color: "#3C5488" } }] }],
  } : null;
  // 贡献度条形图: 按 contribution 降序, 前2红(主限制)/中2蓝/其余深蓝(NPG 梯度突出障碍因子)
  const sortedDims = [...dims].sort((a: any, b: any) => (b.contribution ?? 0) - (a.contribution ?? 0));
  const contribOption = sortedDims.length ? {
    tooltip: { trigger: "axis", formatter: (p: any) => {
      const d = sortedDims[p[0].dataIndex];
      return `${d.indicator}<br/>贡献: ${p[0].value}<br/>权重: ${d.norm_weight != null ? (d.norm_weight * 100).toFixed(1) + "%" : "—"}`;
    } },
    grid: { left: 80, right: 40, top: 16, bottom: 24 },
    xAxis: { type: "value", name: "贡献" },
    yAxis: { type: "category", inverse: true, data: sortedDims.map((d: any) => d.indicator),
      axisLabel: { fontSize: 11 } },
    series: [{ type: "bar", barMaxWidth: 22,
      data: sortedDims.map((d: any, i: number) => ({ value: d.contribution ?? 0,
        itemStyle: { color: i < 2 ? "#E64B35" : i < 4 ? "#4DBBD5" : "#3C5488", borderRadius: [0, 3, 3, 0] } })),
      label: { show: true, position: "right", fontSize: 10 } }],
  } : null;
  // Round7 追加: 指标贡献瀑布图(累计贡献叠加) + 短板仪表盘(最低维度得分)
  const waterfallOption = sortedDims.length >= 2 ? {
    tooltip: { trigger: "axis", formatter: (p: any) => {
      const d = sortedDims[p[0].dataIndex];
      return d.indicator + "<br/>贡献分: " + (d.contribution ?? 0);
    } },
    grid: { left: 50, right: 30, top: 5, bottom: 130, containLabel: true },
    xAxis: { type: "category", data: sortedDims.map((d: any) => d.indicator),
      axisLabel: { rotate: 35, fontSize: 11, interval: 0, width: 120,
        formatter: (v: string) => v.length > 8 ? v.substring(0, 7) + "…" : v },
      axisLine: { onZero: true } },
    yAxis: { type: "value", name: "累计贡献", nameTextStyle: { fontSize: 12, padding: [0, 0, 0, 30] },
      nameLocation: "middle", nameGap: 35,
      axisLabel: { fontSize: 10 } },
    series: [{ type: "bar", barMaxWidth: 44, barGap: "10%",
      data: sortedDims.map((d: any, i: number) => {
        const cum = sortedDims.slice(0, i + 1).reduce((s: number, x: any) => s + (x.contribution ?? 0), 0);
        return { value: cum, itemStyle: { color: i < 2 ? "#E64B35" : "#4DBBD5" } };
      }),
      label: { show: true, position: "top", fontSize: 10, formatter: ({ value }: any) => Math.round(value) } }],
  } : null;
  const minDim = sortedDims.length ? [...sortedDims].sort((a: any, b: any) => (a.F ?? 100) - (b.F ?? 100))[0] : null;
  const gaugeOption = minDim ? {
    series: [{ type: "gauge", min: 0, max: 100, startAngle: 210, endAngle: -30, radius: "75%",
      center: ["50%", "45%"],
      progress: { show: true, width: 12 },
      axisLine: { lineStyle: { width: 12 } },
      axisTick: { show: false }, splitLine: { length: 6 },
      axisLabel: { distance: 10, fontSize: 10 },
      pointer: { width: 4, length: "60%" },
      detail: { valueAnimation: true, formatter: "{value} 分", fontSize: 18, offsetCenter: [0, "35%"] },
      title: { offsetCenter: [0, "85%"], fontSize: 12, color: "#555" },
      data: [{ value: minDim.F ?? 0, name: (minDim.indicator ?? "短板").length > 8 ? (minDim.indicator ?? "短板").substring(0, 8) + "…" : (minDim.indicator ?? "短板") }] }],
  } : null;
  return (
    <Card type="inner" title={title} style={{ marginBottom: 16 }}>
      <Row gutter={16} style={{ marginBottom: 12 }}>
        <Col span={8}><Statistic title="综合得分" value={e.score} suffix="分"
          valueStyle={{ color: e.grade === "可行" ? "#15803d" : "#b91c1c" }} /></Col>
        <Col span={8}><div>评价等级</div><Tag color={e.grade === "可行" ? "green" : "red"} style={{ fontSize: 16, padding: "4px 12px", marginTop: 8 }}>{e.grade}</Tag></Col>
        <Col span={8}><div>关键限制因子</div><div style={{ marginTop: 8 }}>{(e.limiting_factors || []).map((f: string) => <Tag color="orange" key={f}>{formatFactor(f)}</Tag>) || "—"}</div></Col>
      </Row>
      <p style={{ color: "#666", fontSize: 13 }}>{e.explanation}</p>
      <Divider style={{ margin: "12px 0" }} />
      <Table rowKey="indicator" size="small" pagination={false} dataSource={dims}
        columns={[
          seqCol(64),
          textCol("评价指标", "indicator"),
          numCol("指标得分 F", "F"),
          numCol("归一权重", "norm_weight", { render: (v: number) => v != null ? (v * 100).toFixed(2) + "%" : "—" }),
          numCol("贡献", "contribution"),
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
      {(radarOption || contribOption) && (
        <Row gutter={16} style={{ marginTop: 12 }}>
          {radarOption && (
            <Col span={10}>
              <Card size="small" title="各评价指标得分">
                <ReactECharts option={radarOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 260 }} />
              </Card>
            </Col>
          )}
          {contribOption && (
            <Col span={14}>
              <Card size="small" title="指标贡献度排序（突出障碍因子）">
                <ReactECharts option={contribOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 260 }} />
              </Card>
            </Col>
          )}
        </Row>
      )}
      {/* Round7 追加: 瀑布图(累计贡献) + 短板仪表盘(最低维度), 保留上方雷达+条形图; 默认折叠避免双轨×4图过载 */}
      {(waterfallOption || gaugeOption) && (
        <Collapse size="small" style={{ marginTop: 12 }} items={[{
          key: "advanced", label: "高级可视化（贡献瀑布图 + 短板仪表盘 · 点击展开）",
          children: (
            <Row gutter={16}>
              {waterfallOption && (
                <Col span={14}>
                  <Card size="small" title="生产类指标贡献瀑布图（累计叠加 · 识别主导因子）">
                    <ReactECharts option={waterfallOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 440 }} />
                  </Card>
                </Col>
              )}
              {gaugeOption && (
                <Col span={10}>
                  <Card size="small" title="短板仪表盘（木桶效应 · 最低分）">
                    <ReactECharts option={gaugeOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 440 }} />
                  </Card>
                </Col>
              )}
            </Row>
          ),
        }]} />
      )}
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
  const { message } = App.useApp();
  const [sid, setSid] = useState<number>();
  const [data, setData] = useState<any>(null);
  const [hasRun, setHasRun] = useState(false);
  const [busy, setBusy] = useState(false);
  const [flowOpen, setFlowOpen] = useState(false);

  const load = (id?: number) => {
    const s = id ?? sid; if (!s) return;
    api.evaluation(s).then(setData).catch(() => setData(null));
  };
  useEffect(() => { if (sid) { setHasRun(false); load(sid); } }, [sid]);

  const run = async () => {
    if (!sid) return;
    setBusy(true);
    try { await api.runEvaluation(sid); setData(null); setHasRun(true); message.success("评价完成"); load(sid); }
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
          <Space>
            {data && <ReportActions siteId={sid!} reportScope="reconstruction" label="功能重构分析报告" />}
            <Button icon={<ApartmentOutlined />} onClick={() => setFlowOpen(true)}>方法说明</Button>
            <Button type="primary" loading={busy} onClick={run} disabled={!sid}>运行功能重构可行性评价</Button>
          </Space>
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
          <EvalBlock title="生产功能重构可行性" e={prod} organicRisk={data?.results?.organic_risk?.dimensions} />
          <EvalBlock title="生态功能重构可行性" e={eco} organicRisk={data?.results?.organic_risk?.dimensions} />
        </Card>
      ) : <Empty description="请选择场地并点击「运行」生成功能重构评价" />}
      <MethodFlowDrawer open={flowOpen} onClose={() => setFlowOpen(false)} config={getFlowConfig("reconstruction_eval")!} />
    </Space>
  );
}
