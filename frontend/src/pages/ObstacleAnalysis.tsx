import { useEffect, useState } from "react";
import { Card, Button, Row, Col, Space, Alert, Typography, App, Descriptions, Table, Tag, Timeline, Segmented, Tooltip, Select } from "antd";
import { InfoCircleOutlined, ExportOutlined, GlobalOutlined, HistoryOutlined } from "@ant-design/icons";
import ReactECharts from "echarts-for-react";
import dayjs from "dayjs";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import EmptyState from "../components/EmptyState";
import { seqCol, numCol, textCol } from "../utils/table";
import { POLLUTION_TYPE, POLLUTION_LABEL } from "../theme/palette";
import { SVG_OPTS } from "../theme/echarts";

const { Text, Paragraph } = Typography;

const AUC_GUIDE = `AUC 值含义（0-1 范围）:
≥ 0.90 → 优秀 — 模型能很好地区分障碍因子
0.80-0.90 → 良好 — 模型有较好的区分能力
0.70-0.80 → 一般 — 模型有一定参考价值
0.60-0.70 → 偏低 — 建议人工复核
< 0.60 → 低 — 结果不可靠，需检查数据`;

const F1_GUIDE = `F1 值含义（0-1 范围）:
≥ 0.85 → 优秀 — 诊断结论精准可靠
0.70-0.85 → 良好 — 诊断结论较为可靠
0.50-0.70 → 一般 — 存在一定误判风险
< 0.50 → 偏低 — 误判风险较高`;

export default function ObstacleAnalysis() {
  const { message } = App.useApp();
  const [sid, setSid] = useState<number>();
  const [diag, setDiag] = useState<any>(null);
  const [site, setSite] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [landUse, setLandUse] = useState<string>("生产用地");
  const [historyList, setHistoryList] = useState<any[]>([]);
  const [historyId, setHistoryId] = useState<number | null>(null);

  const load = (id?: number, diagnosisId?: number | null) => {
    const s = id ?? sid; if (!s) return;
    const diagPromise = diagnosisId
      ? api.diagnosisDetail(diagnosisId)
      : api.diagnosis(s);
    diagPromise.then(setDiag).catch(() => setDiag(null));
    api.site(s).then((d: any) => {
      setSite(d);
      setLandUse(d.land_use_type || "生产用地");
    }).catch(() => {});
    // 加载历史诊断列表
    if (!diagnosisId) {
      api.diagnosisHistory(s).then(setHistoryList).catch(() => setHistoryList([]));
    }
  };
  useEffect(() => { if (sid) { load(sid); setHistoryId(null); } }, [sid]);

  const switchLandUse = async (v: string) => {
    if (!sid) return;
    try {
      await api.updateLandUse(sid, v);
      setLandUse(v);
      message.success(`修复后用途已切换为「${v}」，请重新运行诊断以获取对应轨结果`);
    } catch (e: any) { message.error(e?.response?.data?.detail || "用途切换失败"); }
  };

  const run = async () => {
    if (!sid) return;
    setBusy(true);
    try { await api.runDiagnosis(sid); message.success("诊断完成"); load(sid); }
    catch (e: any) { message.error(e?.response?.data?.detail || "诊断失败"); }
    finally { setBusy(false); }
  };

  // 按 land_use_type 过滤显示对应轨的因子
  const trackKey = landUse === "生态用地" ? "eco" : "prod";
  const trackFactors = (diag?.shap_global?.dual_track?.[trackKey + "_top_factors"]) || diag?.top_factors || [];
  const probaMean = diag?.shap_global?.dual_track?.[trackKey + "_proba_mean"];

  const opt = trackFactors.length ? {
    tooltip: { trigger: "axis" }, grid: { left: 100, right: 30, top: 10, bottom: 30 },
    xAxis: { type: "value", name: "影响程度 |SHAP|" },
    yAxis: { type: "category", inverse: true, data: trackFactors.map((t: any) => t.factor) },
    series: [{ type: "bar",
      data: trackFactors.map((t: any) => ({
        value: t.importance,
        itemStyle: {
          color: t.direction === "negative" ? "#4DBBD5" : POLLUTION_TYPE["heavy_metal"],
          borderRadius: [0, 4, 4, 0],
          shadowBlur: 4,
          shadowColor: "rgba(0,0,0,0.15)",
        },
      })),
      emphasis: { focus: "series", blurScope: "coordinateSystem" },
      label: { show: true, position: "right" } }],
  } : null;

  const localRows = (diag?.local_explanation || []).slice(0, 12);
  const localOption = localRows.length ? {
    tooltip: { trigger: "axis", formatter: (p: any) => {
      const r = localRows[p[0].dataIndex];
      return `${r.factor}<br/>采样点: ${r.point_code}<br/>SHAP: ${r.shap_value?.toFixed?.(4)}<br/>方向: ${r.direction}`;
    } },
    grid: { left: 130, right: 50, top: 16, bottom: 24 },
    xAxis: { type: "value", name: "SHAP 值" },
    yAxis: { type: "category", inverse: true,
      data: localRows.map((r: any) => `${r.factor}@${r.point_code}`),
      axisLabel: { fontSize: 10 } },
    series: [{ type: "bar", barMaxWidth: 20,
      data: localRows.map((r: any) => ({
        value: r.shap_value ?? 0,
        itemStyle: {
          color: r.direction === "positive" ? POLLUTION_TYPE["heavy_metal"] : "#4DBBD5",
          borderRadius: r.direction === "positive" ? [0, 4, 4, 0] : [4, 0, 0, 4],
          shadowBlur: 4, shadowColor: "rgba(0,0,0,0.15)",
        },
      })),
      emphasis: { focus: "series", blurScope: "coordinateSystem" },
    }],
  } : null;

  const tf = trackFactors;
  const posCount = tf.filter((t: any) => t.direction === "positive").length;
  const negCount = tf.filter((t: any) => t.direction === "negative").length;
  const directionOption = tf.length ? {
    tooltip: { trigger: "item", formatter: "{b}: {c} 个 ({d}%)" },
    legend: { bottom: 0, data: ["正向(加重)", "负向(缓解)"] },
    series: [{ type: "pie", radius: ["42%", "68%"],
      itemStyle: { borderRadius: 4, borderColor: "#fff", borderWidth: 2 },
      data: [
        { name: "正向(加重)", value: posCount, itemStyle: { color: POLLUTION_TYPE["heavy_metal"] } },
        { name: "负向(缓解)", value: negCount, itemStyle: { color: "#4DBBD5" } },
      ],
      emphasis: { focus: "self", scale: true, label: { show: true, fontSize: 14, fontWeight: "bold" },
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: "rgba(0,0,0,0.3)" } },
      label: { formatter: "{b}: {c}" } }],
  } : null;

  // 场地背景信息卡片
  const siteBg = site ? (
    <Card size="small" style={{ background: "#f8f9fb" }}>
      <Descriptions size="small" column={2}>
        <Descriptions.Item label="场地区位">
          {[site.province, site.city].filter(Boolean).join(" ")}，{POLLUTION_LABEL[site.pollution_type] || "—"}污染场地
        </Descriptions.Item>
        <Descriptions.Item label="修复后用途">{landUse}</Descriptions.Item>
        <Descriptions.Item label="采样点">{site.n_points ?? "—"} 个</Descriptions.Item>
        <Descriptions.Item label="检测记录">{site.n_measurements ?? "—"} 条</Descriptions.Item>
      </Descriptions>
      <Paragraph type="secondary" style={{ fontSize: 12, margin: "8px 0 0 0" }}>
        诊断模型：RF+SHAP 综合诊断。当前为「{landUse}」轨专属诊断结果。
      </Paragraph>
    </Card>
  ) : null;

  // 诊断分低时警告
  const aucVal = diag?.model?.metrics?.auc;
  const f1Val = diag?.model?.metrics?.f1;
  const aucNum = typeof aucVal === "string" ? parseFloat(aucVal) : aucVal;
  const lowConfidence = aucNum != null && aucNum < 0.7;
  const veryLowConfidence = aucNum != null && aucNum < 0.5;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Space style={{ width: "100%", justifyContent: "space-between", flexWrap: "wrap" }}>
          <Space wrap>
            <SitePicker value={sid} onChange={setSid} />
            <Segmented value={landUse} onChange={(v) => switchLandUse(v as string)} disabled={!sid}
              options={[{ label: "修复后·生产用地", value: "生产用地" }, { label: "修复后·生态用地", value: "生态用地" }]} />
          </Space>
          <Space>
            {diag && (
              <Button icon={<ExportOutlined />} onClick={() => {
                api.generateReport(sid!, "pdf").then((r: any) => {
                  message.success("诊断报告生成中...");
                }).catch(() => message.error("导出失败"));
              }}>导出诊断报告</Button>
            )}
            <Button type="primary" loading={busy} onClick={run} disabled={!sid}>运行障碍因子诊断</Button>
          </Space>
        </Space>
        <div style={{ marginTop: 8, color: "#666", fontSize: 12 }}>
          「修复后用途」决定诊断轨。当前展示「{landUse}」专属诊断结果。切换用途后需重新运行诊断。
        </div>
      </Card>

      {diag ? (
        <>
          {/* 场地背景信息 */}
          {siteBg}

          {/* 模型与结论 — 术语简化 */}
          <Card title={
            <Space>
              <span>诊断模型与结论</span>
              {historyList.length > 1 && (
                <Select size="small" placeholder="选择历史诊断" value={historyId ?? undefined}
                  style={{ minWidth: 240, fontWeight: 400 }}
                  onChange={(v: number) => {
                    setHistoryId(v);
                    load(sid, v);
                    message.info(`正在查看历史诊断记录（${dayjs(historyList.find(h => h.id === v)?.created_at).format("MM-DD HH:mm")}）`);
                  }}
                  options={historyList.map((h: any) => ({
                    value: h.id,
                    label: `${dayjs(h.created_at).format("MM-DD HH:mm")}${h.is_latest ? " (最新)" : ""} — ${(h.top_factors_summary || []).slice(0, 3).join(", ")}`,
                  }))}
                />
              )}
              {historyId && (
                <Tag color="blue" icon={<HistoryOutlined />}>历史记录（{dayjs(historyList.find(h => h.id === historyId)?.created_at).format("MM-DD HH:mm")}）</Tag>
              )}
            </Space>
          }>
            {veryLowConfidence && (
              <Alert type="error" showIcon message="诊断结果不可靠，请检查数据完整性后重新诊断"
                style={{ marginBottom: 12 }} />
            )}
            {lowConfidence && !veryLowConfidence && (
              <Alert type="warning" showIcon message={`当前诊断结果置信度偏低（AUC: ${aucNum?.toFixed(2)}），建议人工复核关键因子`}
                style={{ marginBottom: 12 }} />
            )}
            <Descriptions size="small" column={2}>
              <Descriptions.Item label="诊断模型">{diag.model?.name || "RF+SHAP 综合诊断"}</Descriptions.Item>
              <Descriptions.Item label="模型可信度">
                AUC={aucVal ?? "—"}，F1={f1Val ?? "—"}
                <Tooltip title={<pre style={{ fontSize: 11, margin: 0, whiteSpace: "pre-line" }}>{AUC_GUIDE + "\n\n" + F1_GUIDE}</pre>}>
                  <InfoCircleOutlined style={{ marginLeft: 6, color: "#888", cursor: "help" }} />
                </Tooltip>
              </Descriptions.Item>
              <Descriptions.Item label="结论摘要" span={2}>
                <Paragraph style={{ marginBottom: 4, whiteSpace: "pre-wrap" }}>{diag.summary || "—"}</Paragraph>
                {diag.polish_model && (
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    ⓘ 此结论由 AI 辅助生成（{diag.polish_model}），仅供参考，以原始数据为准。
                  </Text>
                )}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 关键障碍因子 */}
          <Card title="关键障碍因子（影响程度排序）">
            {opt && <ReactECharts option={opt} theme="srs-light" opts={SVG_OPTS} style={{ height: 340 }} />}
            <Table rowKey="rank" size="small" pagination={false} dataSource={trackFactors}
              columns={[
                seqCol(64),
                { title: "障碍因子", dataIndex: "factor", render: (v: string, r: any) => (
                  <Space size={4}>
                    <span>{v}</span>
                    {(r.feature && r.feature.startsWith("gee_")) && (
                      <Tooltip title="该指标来源于卫星遥感/地理空间数据">
                        <GlobalOutlined style={{ color: "#52c41a", fontSize: 12 }} />
                      </Tooltip>
                    )}
                  </Space>
                )},
                textCol("类别", "category"),
                numCol("影响程度 |SHAP|", "importance"),
                { title: "影响方向", dataIndex: "direction", align: "center",
                  render: (v: string) => <Tag color={v === "positive" ? POLLUTION_TYPE["heavy_metal"] : "#4DBBD5"} style={{ color: "#fff" }}>{v === "positive" ? "正向(加重)" : "负向(缓解)"}</Tag> },
              ]} />
          </Card>

          {(localOption || directionOption) && (
            <Row gutter={16}>
              {localOption && (
                <Col span={14}>
                  <Card title="采样点风险成因分析">
                    <ReactECharts option={localOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 320 }} />
                  </Card>
                </Col>
              )}
              {directionOption && (
                <Col span={10}>
                  <Card title="障碍因子影响方向分布">
                    <ReactECharts option={directionOption} theme="srs-light" opts={SVG_OPTS} style={{ height: 320 }} />
                  </Card>
                </Col>
              )}
            </Row>
          )}

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
      ) : <EmptyState description="请选择场地并运行障碍因子识别" />}
    </Space>
  );
}
