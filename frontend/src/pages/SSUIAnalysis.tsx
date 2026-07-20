import { useEffect, useState } from "react";
import { Card, Button, App, Row, Col, Statistic, Tag, Space, Table, Divider, Alert, Timeline, Typography, InputNumber, Select, Checkbox } from "antd";
import { ApartmentOutlined, ExportOutlined, DatabaseOutlined } from "@ant-design/icons";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import FormulaBlock from "../components/FormulaBlock";
import OrganicDegradedCard from "../components/OrganicDegradedCard";
import EmptyState from "../components/EmptyState";
import MethodFlowDrawer from "../components/MethodFlowDrawer";
import EconomicDataDrawer from "../components/EconomicDataDrawer";
import { seqCol, numCol, textCol } from "../utils/table";
import { SVG_OPTS } from "../theme/echarts";
import { getFlowConfig } from "../config/methodFlows";

const { Text } = Typography;

/** SSUI 评价 = 方法文件第3章 土壤持续利用经济性和安全性评价(SSUI 模型) */
export default function SSUIAnalysis() {
  const { message, modal } = App.useApp();
  const [sid, setSid] = useState<number>();
  const [data, setData] = useState<any>(null);     // GET: 历史 + current_data_version
  const [hasRun, setHasRun] = useState(false);     // 是否已点击运行(控制本次结果区显隐, brief 4.5)
  const [busy, setBusy] = useState(false);
  const [flowOpen, setFlowOpen] = useState(false);
  const [ecoOpen, setEcoOpen] = useState(false);   // Round9 P0-5: 经济数据管理 Drawer
  // v1.0.2(GPT P0-4): SSUI 评价参数(t=利用年限, intensity=管理强度)
  const [evalT, setEvalT] = useState<number>(2);
  const [evalIntensity, setEvalIntensity] = useState<string>("medium");
  // Round9 P0-5: 完整评价参数(年份/场景/scope/allow_proxy)
  const [evalYear, setEvalYear] = useState<number | undefined>(undefined);
  const [evalScenario, setEvalScenario] = useState<"production" | "ecology">("production");
  const [evalScope, setEvalScope] = useState<"production" | "ecology">("production");
  const [allowProxy, setAllowProxy] = useState(false);

  const load = (id?: number) => {
    const s = id ?? sid; if (!s) return;
    api.evaluation(s).then(setData).catch(() => setData(null));
  };
  useEffect(() => { if (sid) { setHasRun(false); load(sid); } }, [sid]);

  const run = async () => {
    if (!sid) return;
    setBusy(true);
    try {
      await api.runEvaluation(sid, {
        t: evalT, intensity: evalIntensity,
        evaluation_year: evalYear, scenario: evalScenario,
        scope: evalScope, allow_proxy: allowProxy,
      });
      const refreshed = await api.evaluation(sid);
      setData(refreshed);
      setHasRun(true);
      message.success("SSUI 评价完成");
    } catch (e: any) { message.error(e?.response?.data?.detail || "评价失败"); }
    finally { setBusy(false); }
  };

  // Round9 P0-5.3: 勾选 allow_proxy 前必须 Modal.confirm 提示
  const toggleAllowProxy = (checked: boolean) => {
    if (checked) {
      modal.confirm({
        title: "确认使用区域代理数据?",
        content: "勾选后生成的 SSUI 结果为参考评价, 不代表场地真实经济数据。请在能接受'参考评价'语义时使用。",
        okText: "确认勾选",
        cancelText: "取消",
        onOk: () => setAllowProxy(true),
        onCancel: () => setAllowProxy(false),
      });
    } else {
      setAllowProxy(false);
    }
  };

  const histS = data?.results?.ssui;   // 历史 SSUI(选场地即显元信息 + is_stale)
  const curDv = data?.current_data_version;
  const s = histS;                     // 完整结果(GET 含 score/dimensions/parts)
  const showResult = !!s;
  const parts = (s?.dimensions?.parts || []) as any[];
  const trace = (s?.calculation_trace || s?.dimensions?.calculation_trace || []) as string[];
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

  // 只使用后端真实准则层结果，不从指标中文名称猜测维度。
  const safetyScore = s?.dimensions?.B1_safety;
  const econScore = s?.dimensions?.B2_economy;
  const seScatterOption = Number.isFinite(safetyScore) && Number.isFinite(econScore) ? {
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
  const criterionValues = [
    s?.dimensions?.SC1_limit, s?.dimensions?.SC2_risk,
    s?.dimensions?.SC3_cost, s?.dimensions?.SC4_benefit,
  ];
  const costBenefitOption = criterionValues.every((value) => Number.isFinite(value)) ? {
    tooltip: { trigger: "axis", formatter: (p: any) => p[0].name + ": " + (p[0].value * 100).toFixed(1) + "%" },
    legend: { data: ["C1限制", "C2风险", "C3成本", "C4效益"], top: 0, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 10 } },
    grid: { left: 70, right: 30, top: 32, bottom: 24 },
    xAxis: { type: "value", name: "准则层得分", min: 0, max: 1 },
    yAxis: { type: "category", data: ["本场地"] },
    series: [
      { name: "C1限制", type: "bar", color: "#3b82f6", data: [criterionValues[0]] },
      { name: "C2风险", type: "bar", color: "#dc2626", data: [criterionValues[1]] },
      { name: "C3成本", type: "bar", color: "#f59e0b", data: [criterionValues[2]] },
      { name: "C4效益", type: "bar", color: "#16a34a", data: [criterionValues[3]] },
    ],
  } : null;

  return (
    <>
      <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Space style={{ width: "100%", flexWrap: "wrap", rowGap: 8 }}>
          <SitePicker value={sid} onChange={setSid} style={{ width: 360, maxWidth: 360 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>年限t:</Text>
          <InputNumber size="small" min={1} max={50} value={evalT} onChange={(v) => setEvalT(v ?? 2)} style={{ width: 56 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>强度:</Text>
          <Select size="small" value={evalIntensity} onChange={setEvalIntensity} style={{ width: 90 }}
            options={[
              { value: "low", label: "粗放" },
              { value: "medium", label: "中等" },
              { value: "high", label: "集约" },
            ]} />
          <Text type="secondary" style={{ fontSize: 12 }}>年份:</Text>
          <InputNumber size="small" min={2000} max={2100} placeholder="自动" value={evalYear}
            onChange={(v) => setEvalYear(v ?? undefined)} style={{ width: 90 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>场景:</Text>
          <Select size="small" value={evalScenario} onChange={(v) => setEvalScenario(v)} style={{ width: 100 }}
            options={[{ value: "production", label: "生产" }, { value: "ecology", label: "生态" }]} />
          <Text type="secondary" style={{ fontSize: 12 }}>scope:</Text>
          <Select size="small" value={evalScope} onChange={(v) => setEvalScope(v)} style={{ width: 100 }}
            options={[{ value: "production", label: "production" }, { value: "ecology", label: "ecology" }]} />
          <Checkbox checked={allowProxy} onChange={(e) => toggleAllowProxy(e.target.checked)}>允许代理(参考)</Checkbox>
          <Button icon={<DatabaseOutlined />} onClick={() => setEcoOpen(true)} disabled={!sid}>经济数据</Button>
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
              message="正式评价仅在 D1-D25 全部具备可审计数据时生成：D1-D15 使用外部参照总体，D16-D17 使用法规阈值，D18-D25 使用版本化官方年度参照样本。缺项或阈值未解析会明确阻断。" />
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
      {sid && histS && !hasRun && (
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
      ) : showResult && (s?.dimensions?.is_blocked || s?.grade?.startsWith("blocked")) ? (
        <Card title="土壤持续利用度（SSUI）评价 — 数据不足">
          <Alert type="warning" showIcon style={{ marginBottom: 16 }}
            message={`SSUI 评价受阻: ${s?.blocked_reason || "25项证据不完整"}`}
            description={s?.explanation || "D1-D25 任一指标缺失、阈值未解析或归一化依据不足时不能生成正式 SSUI。"}
            action={
              <Space direction="vertical" size="small">
                <Button type="primary" size="small" icon={<DatabaseOutlined />} onClick={() => setEcoOpen(true)}>补录经济数据</Button>
              </Space>
            } />
          {(s?.coverage || s?.dimensions?.coverage) && (
            <div style={{ marginBottom: 16 }}>
              <Text strong>25项覆盖: </Text>
              <Tag color={s?.coverage?.complete_25 ? "green" : "orange"}>
                {s?.coverage?.measured_total ?? "—"}/{s?.coverage?.required_total ?? 25}
              </Tag>
            </div>
          )}
          {trace.length > 0 && (
            <Card size="small" title="计算追溯" style={{ marginTop: 16 }}>
              <Timeline items={trace.map((t: string, i: number) => ({ children: t, key: i }))} />
            </Card>
          )}
        </Card>
      ) : showResult ? (
        <Card title="土壤持续利用度（SSUI）评价"
          extra={<Text type="secondary" style={{ fontSize: 12 }}>本次运行 ｜ 数据版本 {s?.data_version} ｜ 参数版本 {s?.param_version} ｜ {s?.created_at}</Text>}>
          {/* Round9 P0-5.5: 正式 vs 参考评价视觉区分 */}
          {(s?.is_reference || s?.is_proxy || s?.has_fallback_threshold) && (
            <Alert type="warning" showIcon style={{ marginBottom: 16 }}
              message="⚠ 参考评价(非场地正式结论)"
              description={
                s?.has_fallback_threshold
                  ? "本评价使用了 fallback/heuristic 阈值(非权威法规阈值), 仅供参考。请补充权威阈值后重评。"
                  : "本评价基于区域代理数据(非场地真实经济数据), 仅供参考, 不作为场地正式结论。"
              } />
          )}
          {/* Round9 P0-2.6: 最严重超标因子显示 */}
          {s?.worst_factor && (
            <Alert type={s?.severity_forced_downgrade ? "error" : "info"} showIcon style={{ marginBottom: 16 }}
              message={`最严重超标因子: ${s.worst_factor} ${s.worst_ratio ? `(超标 ${s.worst_ratio.toFixed(2)} 倍)` : ""}`}
              description={s?.severity_forced_downgrade
                ? `Round9 P0-2.4 安全门禁: 超标≥5倍触发强制等级降级, 禁止评"优/良好"。`
                : undefined} />
          )}
          <Alert type="info" style={{ marginBottom: 16 }}
            message={`${s?.coverage?.complete_25 ? "25项完整口径" : "部分指标口径"}（${s?.is_reference ? "参考评价" : "正式评价"}）`} description={s.explanation} />
          <Row gutter={16} align="middle">
            <Col span={8}>{gauge && <ReactECharts option={gauge} theme="srs-light" opts={SVG_OPTS} style={{ height: 220 }} />}</Col>
            <Col span={8}><Statistic title="SSUI 指数" value={s.score} /></Col>
            <Col span={8}><div>可持续性等级</div>
              <Tag color={s.grade?.includes("不") ? "red" : s.grade?.includes("低") ? "orange" : "green"}
                style={{ fontSize: 16, padding: "4px 12px", marginTop: 8 }}>{s.grade}</Tag></Col>
          </Row>
          <Divider />
          <h4>D1-D25 元指标得分</h4>
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
          {/* 仅展示后端真实返回的准则层结果；没有真实时间序列时不绘制趋势。 */}
          <Row gutter={16} style={{ marginTop: 12 }}>
            {seScatterOption && (
              <Col span={8}>
                <Card size="small" title="安全性-经济性二维象限">
                  <ReactECharts option={seScatterOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 280 }} />
                </Card>
              </Col>
            )}
            {costBenefitOption && (
              <Col span={12}>
                <Card size="small" title="C1-C4 准则层真实得分">
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
      <EconomicDataDrawer siteId={sid} open={ecoOpen} onClose={() => setEcoOpen(false)} onSaved={() => load(sid)} />
    </>
  );
}
