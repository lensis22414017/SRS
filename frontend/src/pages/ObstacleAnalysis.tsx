import { useEffect, useState } from "react";
import { Card, Button, Row, Col, Space, Alert, Typography, App, Descriptions, Table, Tag, Timeline, Segmented, Tooltip, Select, Collapse } from "antd";
import { InfoCircleOutlined, ExportOutlined, HistoryOutlined, ApartmentOutlined } from "@ant-design/icons";
import MethodFlowDrawer from "../components/MethodFlowDrawer";
import MethodExplainCard from "../components/MethodExplainCard";
import { getFlowConfig } from "../config/methodFlows";
import ReactECharts from "echarts-for-react";
import dayjs from "dayjs";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import EmptyState from "../components/EmptyState";
import { seqCol, numCol, textCol } from "../utils/table";
import { formatFactor } from "../utils/factorFormat";
import { POLLUTION_TYPE, POLLUTION_LABEL } from "../theme/palette";
import { SVG_OPTS } from "../theme/echarts";

const { Text, Paragraph } = Typography;

const AUC_GUIDE = `Spearman 秩相关系数含义（0-1 范围）:
≥ 0.90 → 优秀 — 模型排序能力极强
0.80-0.90 → 良好 — 模型有较好的排序能力
0.70-0.80 → 一般 — 模型有一定参考价值
0.60-0.70 → 偏低 — 建议人工复核
< 0.60 → 低 — 结果仅供参考，需检查数据`;

const F1_GUIDE = ``; // 已废弃，保留空串避免引用错误

export default function ObstacleAnalysis() {
  const { message } = App.useApp();
  const [sid, setSid] = useState<number>();
  const [diag, setDiag] = useState<any>(null);
  const [site, setSite] = useState<any>(null);
  const [landUse, setLandUse] = useState<string>("生产用地");
  const [historyList, setHistoryList] = useState<any[]>([]);
  const [historyId, setHistoryId] = useState<number | null>(null);
  const [flowOpen, setFlowOpen] = useState(false);
  // P4 KOS 三层输出
  const [kosData, setKosData] = useState<any>(null);
  const [kosBusy, setKosBusy] = useState(false);
  const [kosTrack, setKosTrack] = useState<"prod" | "eco">("prod");

  const load = (id?: number, diagnosisId?: number | null) => {
    const s = id ?? sid; if (!s) return;
    // R3-P0-8: 旧 api.diagnosis(GET /diagnosis) 已废弃, 改为从历史取最新
    const diagPromise = diagnosisId
      ? api.diagnosisDetail(diagnosisId)
      : api.diagnosisHistory(s).then((list: any[]) => list[0] ? api.diagnosisDetail(list[0].id) : null);
    diagPromise.then((d: any) => setDiag(d)).catch(() => setDiag(null));
    api.site(s).then((d: any) => {
      setSite(d);
      setLandUse(d.land_use_type || "生产用地");
    }).catch(() => {});
    // 加载历史诊断列表
    if (!diagnosisId) {
      api.diagnosisHistory(s).then(setHistoryList).catch(() => setHistoryList([]));
    }
  };
  useEffect(() => { if (sid) { load(sid); setHistoryId(null); setKosData(null); } }, [sid]);

  const switchLandUse = async (v: string) => {
    if (!sid) return;
    try {
      await api.updateLandUse(sid, v);
      setLandUse(v);
      message.success(`修复后用途已切换为「${v}」，请重新运行诊断以获取对应轨结果`);
    } catch (e: any) { message.error(e?.response?.data?.detail || "用途切换失败"); }
  };

  // R3-P0-8: 旧 run() 已删除(调废弃 410 端点), 统一用 KOS 路径
  // P4 KOS 诊断(三层输出: 明确障碍 + 关键障碍 + 补测建议)
  const runKos = async (track?: "prod" | "eco") => {
    if (!sid) return;
    const t = track || kosTrack;
    setKosBusy(true);
    try {
      const r = await api.kosDiagnosis(sid, t);
      setKosData(r);
      setKosTrack(t);
      if (r.review_required) {
        message.warning("诊断完成,但部分结果需人工复核(见数据质量提示)");
      } else {
        message.success(`KOS ${t === "prod" ? "生产" : "生态"}诊断完成`);
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "KOS 诊断失败");
      setKosData(null);
    } finally { setKosBusy(false); }
  };

  // 按 land_use_type 过滤显示对应轨的因子
  const trackKey = landUse === "生态用地" ? "eco" : "prod";
  const trackFactors = (diag?.shap_global?.dual_track?.[trackKey + "_top_factors"]) || diag?.top_factors || [];
  // 旧「影响程度 |SHAP|」主图(opt)随关键障碍因子表一并下线, 改由 KOS Top-N 承载;
  // trackFactors 仍供方向分布饼图(directionOption)使用。

  // Round7 追加: 五分量证据堆叠条(R+W+M+S+E), 数据来自 kosData.key_obstacles[].components
  const barrierStackData = (kosData?.key_obstacles || []).map((k: any) => {
    const c = k.components || {};
    return { factor: k.factor, R: Number(c.R || 0), W: Number(c.W || 0),
      M: Number(c.M || 0), S: Number(c.S || 0), E: Number(c.E || 0) };
  });

  const localRows = (diag?.local_explanation || []).slice(0, 12);
  const localOption = localRows.length ? {
    tooltip: { trigger: "axis", formatter: (p: any) => {
      const r = localRows[p[0].dataIndex];
      return `${r.factor}<br/>采样点: ${r.point_code}<br/>模型贡献值: ${r.shap_value?.toFixed?.(4)}<br/>方向: ${r.direction}`;
    } },
    grid: { left: 130, right: 50, top: 16, bottom: 24 },
    xAxis: { type: "value", name: "模型贡献值" },
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
        诊断方法：规则诊断 + 模型贡献度解释。当前为「{landUse}」轨专属诊断结果。
      </Paragraph>
    </Card>
  ) : null;

  // 诊断置信度: 改用 Spearman 秩相关(回归模型), 不再用 AUC(分类指标)
  const spearmanVal = diag?.model?.metrics?.cv_spearman_mean ?? diag?.model?.metrics?.test_spearman;
  const aucVal = spearmanVal; // 兼容旧变量名
  const f1Val = undefined; // 废弃
  const aucNum = typeof spearmanVal === "string" ? parseFloat(spearmanVal) : spearmanVal;
  const lowConfidence = aucNum != null && aucNum < 0.7;
  const veryLowConfidence = aucNum != null && aucNum < 0.5;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Space style={{ width: "100%", justifyContent: "space-between", flexWrap: "wrap" }}>
          <Space wrap>
            <SitePicker value={sid} onChange={setSid} />
            {/* v1.0.2(GPT 4.1-4.3 + ): 顶部卡片背景统一蓝色调 */}
            <Segmented value={landUse} onChange={(v) => switchLandUse(v as string)} disabled={!sid}
              options={[{ label: "修复后·生产用地", value: "生产用地" }, { label: "修复后·生态用地", value: "生态用地" }]}
              style={{ background: "#e6f4ff", padding: 4, borderRadius: 6 }} />
          </Space>
          <Space>
            {diag && (
              <Button icon={<ExportOutlined />} onClick={() => {
                api.generateReport(sid!, "pdf").then((r: any) => {
                  message.success("诊断报告生成中...");
                }).catch(() => message.error("导出失败"));
              }}>导出诊断报告</Button>
            )}
            <Button icon={<ApartmentOutlined />} onClick={() => setFlowOpen(true)}>方法说明</Button>
            {/* v1.0.2(GPT 4.4-4.5): 单一运行按钮, 按顶部 Segmented 选轨跑 KOS */}
            <Button type="primary" loading={kosBusy} onClick={() => runKos(landUse === "生态用地" ? "eco" : "prod")} disabled={!sid}>运行障碍因子诊断</Button>
          </Space>
        </Space>
        <div style={{ marginTop: 8, color: "#666", fontSize: 12 }}>
          「修复后用途」决定诊断轨。当前展示「{landUse}」专属诊断结果。选中上方卡片后点击「运行障碍因子诊断」即可。
        </div>
      </Card>

      {(diag || kosData) ? (
        <>
          {/* 场地背景信息 */}
          {siteBg}

          {/* 历史诊断切换(保留功能, 迁移到独立紧凑区) */}
          {historyList.length > 1 && (
            <Card size="small" style={{ marginBottom: 16 }}>
              <Space>
                <HistoryOutlined />
                <Select size="small" placeholder="选择历史诊断" value={historyId ?? undefined}
                  style={{ minWidth: 320 }}
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
                {historyId && (
                  <Tag color="blue" icon={<HistoryOutlined />}>历史记录（{dayjs(historyList.find(h => h.id === historyId)?.created_at).format("MM-DD HH:mm")}）</Tag>
                )}
                {veryLowConfidence && (
                  <Tag color="red">结果不可靠</Tag>
                )}
                {lowConfidence && !veryLowConfidence && (
                  <Tag color="orange">置信度偏低（Spearman: {aucNum?.toFixed(2)}）建议人工复核</Tag>
                )}
              </Space>
            </Card>
          )}

          {/* ───── P4 KOS 三层诊断输出 ───── */}
          {kosData && (
            <>
              {/* 数据质量 + 复核标记 */}
              {(kosData.review_required || kosData.data_quality_flags?.length > 0) && (
                <Alert
                  type={kosData.model_status === "exploratory" ? "warning" : "info"}
                  showIcon
                  style={{ marginBottom: 0 }}
                  message={kosData.model_status === "exploratory"
                    ? "当前为探索性诊断,建议结合规则筛查和人工复核"
                    : "诊断已完成,请注意以下数据质量提示"}
                  description={kosData.data_quality_flags?.length > 0 ? (
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {kosData.data_quality_flags.map((f: string, i: number) => <li key={i} style={{ fontSize: 12 }}>{f}</li>)}
                    </ul>
                  ) : undefined}
                />
              )}

              {/* 第一层: 污染场地关键障碍因子 Top-N (优先展示, 规则层 B=1 + 实测 + 综合评分排序) */}
              <Card title={
                <Space>
                  <span>污染场地关键障碍因子 Top-N</span>
                  <Tag color={kosTrack === "prod" ? "purple" : "green"}>
                    {kosTrack === "prod" ? "生产用途" : "生态用途"}
                  </Tag>
                  <Tag color="blue">{kosData.model_id}</Tag>
                  {kosData.model_status === "exploratory" && <Tag color="orange">探索性</Tag>}
                </Space>
              }>
                {kosData.key_obstacles?.length > 0 ? (
                  <>
                    <Table rowKey="rank" size="small" pagination={false}
                      dataSource={kosData.key_obstacles}
                      columns={[
                        { title: "排名", dataIndex: "rank", width: 60, align: "center",
                          render: (v: number) => <strong style={{ color: v <= 3 ? "#fa541c" : "#666" }}>#{v}</strong> },
                        { title: "关键障碍因子", dataIndex: "factor", width: 180,
                          render: (v: string, r: any) => (
                            <Space size="small">
                              <span style={{ fontWeight: 600 }}>{formatFactor(v)}</span>
                              {r.threshold_resolution_status === "heuristic" && (
                                <Tooltip title="该因子为启发式识别(关键词匹配), 阈值已用 GB15618 通用档兜底, 待专家核实">
                                  <Tag color="orange" style={{ fontSize: 10 }}>启发式·待核实</Tag>
                                </Tooltip>
                              )}
                              {r.threshold_resolution_status === "fallback" && (
                                <Tooltip title="该因子阈值已用 GB15618 通用档兜底(无精确 pH/用地匹配)">
                                  <Tag color="gold" style={{ fontSize: 10 }}>兜底阈值</Tag>
                                </Tooltip>
                              )}
                            </Space>
                          ) },
                        { title: "KOS 评分", dataIndex: "KOS", width: 110, align: "center",
                          render: (v: number, r: any) => {
                            const c = r.components || {};
                            return (
                            <Tooltip title={`R严重度=${c.R ?? "—"}  W权重=${c.W ?? "—"}  M模型贡献=${c.M ?? "—"}  S稳定性=${c.S ?? "—"}  E证据=${c.E ?? "—"}`}>
                              <div style={{ width: 70, display: "inline-block" }}>
                                <div style={{ background: "#f0f0f0", borderRadius: 3, height: 16, overflow: "hidden" }}>
                                  <div style={{ width: `${(v * 100).toFixed(0)}%`, background: v > 0.6 ? "#fa541c" : v > 0.4 ? "#faad14" : "#52c41a", height: "100%", borderRadius: 3 }} />
                                </div>
                                <span style={{ fontSize: 11 }}>{v.toFixed(3)}</span>
                              </div>
                            </Tooltip>
                            );
                          } },
                        { title: "证据等级", dataIndex: "evidence", width: 80, align: "center",
                          render: (v: string) => <Tag color={v === "A" ? "green" : v === "B" ? "blue" : v === "C" ? "orange" : "red"}>{v}</Tag> },
                      ]} />
                    <Paragraph type="secondary" style={{ fontSize: 11, marginTop: 8, marginBottom: 0 }}>
                      KOS = B × (0.30×R严重度 + 0.25×W用途权重 + 0.15×M模型贡献度 + 0.20×S稳定性 + 0.10×E证据等级)。
                      只有规则判定超标(B=1)且实测的因子进入排名。
                    </Paragraph>
                  </>
                ) : (
                  <EmptyState description="未生成关键障碍排名(可能因 pH/用地缺失已用兜底阈值,请核对场地数据完整性)" />
                )}
              </Card>

              {/* Round7 追加: 五分量证据堆叠条(R+W+M+S+E), 保留上方 Top-N 进度条表, 此处追加堆叠可视化 */}
              {barrierStackData.length > 0 && (
                <Card title={<Space><span>五分量证据堆叠条（R规则严重度 + W用途权重 + M模型贡献度 + S稳定性 + E证据等级）</span></Space>} size="small">
                  <ReactECharts option={{
                    tooltip: { trigger: "axis", axisPointer: { type: "shadow" },
                      formatter: (params: any) => {
                        const d = barrierStackData[params[0].dataIndex];
                        const weightMap: any = { "R规则严重度": 0.30, "W用途权重": 0.25, "M模型贡献度": 0.15, "S稳定性": 0.20, "E证据等级": 0.10 };
                        return "<b>" + formatFactor(d.factor) + "</b><br/>" +
                          params.map((p: any) => {
                            const w = weightMap[p.seriesName] || 0;
                            const raw = (p.value / w).toFixed(3);
                            return p.marker + p.seriesName + ": " + p.value.toFixed(3) + " (分量" + raw + "×权重" + w + ")";
                          }).join("<br/>");
                      } },
                    legend: { top: 0, type: "scroll", data: ["R规则严重度", "W用途权重", "M模型贡献度", "S稳定性", "E证据等级"] },
                    grid: { left: 120, right: 24, top: 40, bottom: 30 },
                    xAxis: { type: "value", name: "分量贡献(加权和前)", max: 1 },
                    yAxis: { type: "category", inverse: true, data: barrierStackData.map((d: any) => formatFactor(d.factor)) },
                    series: [
                      { name: "R规则严重度", type: "bar", stack: "kos", color: "#E64B35", data: barrierStackData.map((d: any) => d.R * 0.30) },
                      { name: "W用途权重", type: "bar", stack: "kos", color: "#4DBBD5", data: barrierStackData.map((d: any) => d.W * 0.25) },
                      { name: "M模型贡献度", type: "bar", stack: "kos", color: "#00A087", data: barrierStackData.map((d: any) => d.M * 0.15) },
                      { name: "S稳定性", type: "bar", stack: "kos", color: "#3C5488", data: barrierStackData.map((d: any) => d.S * 0.20) },
                      { name: "E证据等级", type: "bar", stack: "kos", color: "#F39B7F", data: barrierStackData.map((d: any) => d.E * 0.10) },
                    ],
                  }} theme="srs-light" opts={SVG_OPTS} style={{ height: 320 }} />
                  <Paragraph type="secondary" style={{ fontSize: 11, marginTop: 8, marginBottom: 0 }}>
                    ⓘ 每条堆叠总长 = KOS 综合评分(B=1 时的加权和)。红色(R规则严重度)越长, 说明该因子超标越严重; 蓝色(W用途权重)反映双轨差异; 绿色(M模型贡献度)仅辅助参考, 非因果。
                  </Paragraph>
                </Card>
              )}

              {/* 第二层: 模型贡献度(不写SHAP) */}
              {kosData.model_contribution?.length > 0 && (
                <Card title="模型贡献度（因子对障碍指数的解释贡献）">
                  <ReactECharts option={{
                    tooltip: { trigger: "axis" },
                    grid: { left: 140, right: 40, top: 10, bottom: 30 },
                    xAxis: { type: "value", name: "贡献份额", max: 1 },
                    yAxis: { type: "category", inverse: true, data: kosData.model_contribution.slice(0, 10).map((m: any) => formatFactor(m.factor)) },
                    series: [{ type: "bar",
                      data: kosData.model_contribution.slice(0, 10).map((m: any) => ({
                        value: m.contribution,
                        itemStyle: { color: m.direction === "negative" ? "#4DBBD5" : "#722ed1", borderRadius: [0, 4, 4, 0] },
                      })),
                      label: { show: true, position: "right", formatter: (p: any) => p.value.toFixed(3) } }],
                  }} theme="srs-light" opts={SVG_OPTS} style={{ height: 300 }} />
                  <Paragraph type="secondary" style={{ fontSize: 11, margin: "8px 0 0 0" }}>
                    ⓘ 模型贡献度（Mᵢ，权重仅0.15）反映该因子对障碍指数的统计解释贡献，仅作辅助参考。它不是因果证明，也不是法规判定依据。正式障碍判定以规则层（Bᵢ）和标准阈值（Rᵢ）为底线——未检测或无阈值的因子不会进入正式 Top-N。
                  </Paragraph>
                </Card>
              )}

              {/* 未知有机物防线(如有) */}
              {kosData.organic_guardrails && (kosData.organic_guardrails.n_family_warning > 0 || kosData.organic_guardrails.n_unknown > 0) && (
                <Alert type="warning" showIcon style={{ marginTop: 0 }}
                  message={`检测到 ${kosData.organic_guardrails.n_family_warning} 个族群未收录物质,${kosData.organic_guardrails.n_unknown} 个完全未知物质`}
                  description={`未收录因子不会丢失, 已进入模型候选识别、族群级近邻分析和未知因子预警(不强行套用阈值)。系统不会假装识别未知物质, 仅作为辅助识别参考, 非法规超标判定。请参考「建议补测」或安排深度检测。`} />
              )}

              {/* ───── M0-5: 开放集四层结果真实展示(模型候选 / 族群预警 / 未知因子) ───── */}
              {(kosData.model_candidates?.length > 0 ||
                kosData.family_alerts?.length > 0 ||
                kosData.unknown_measured_factors?.length > 0) && (
                <Card title={<Space><span>开放集识别结果（辅助识别 · 非法规超标结论）</span></Space>} size="small">
                  <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
                    以下三类结果属于辅助识别层, 与上方「关键障碍因子 Top-N」(法规超标层)严格区分, 仅供人工复核与补测决策。
                  </Paragraph>
                  <Collapse size="small" defaultActiveKey={["model_candidates", "family_alerts", "unknown_factors"]} items={[
                    {
                      key: "model_candidates",
                      label: `① 模型候选障碍（${kosData.model_candidates?.length ?? 0}）`,
                      children: (
                        <>
                          <Paragraph type="secondary" style={{ fontSize: 11, marginBottom: 8 }}>
                            模型或文献数据提示其值得关注，但不属于法规超标结论。
                          </Paragraph>
                          <Table
                            size="small" pagination={false} rowKey="original_name"
                            dataSource={kosData.model_candidates || []}
                            locale={{ emptyText: "无" }}
                            columns={[
                              textCol("原始名称", "original_name"),
                              textCol("规范名称", "canonical"),
                              textCol("候选原因", "reason"),
                              { title: "模型贡献", dataIndex: "candidate_attention", align: "center", width: 110,
                                render: (v: any) => {
                                  if (v == null) return "—";
                                  const score = typeof v === "object" ? v?.candidate_attention_score : v;
                                  return score == null ? "—" : Number(score).toFixed(3);
                                } },
                              { title: "需复核", dataIndex: "review_required", align: "center", width: 80,
                                render: (v: any) => v ? <Tag color="orange">是</Tag> : <Tag color="default">否</Tag> },
                            ]}
                          />
                        </>
                      ),
                    },
                    {
                      key: "family_alerts",
                      label: `② 族群级预警（${kosData.family_alerts?.length ?? 0}）`,
                      children: (
                        <>
                          <Paragraph type="secondary" style={{ fontSize: 11, marginBottom: 8 }}>
                            族群归类属于规则型辅助识别，不等同于具体化合物确认或法规判定。
                          </Paragraph>
                          <Table
                            size="small" pagination={false} rowKey="original_name"
                            dataSource={kosData.family_alerts || []}
                            locale={{ emptyText: "无" }}
                            columns={[
                              textCol("原始名称", "original_name"),
                              { title: "匹配族群", dataIndex: "matched_family", align: "center", width: 110,
                                render: (v: string) => v ? <Tag color="blue">{v}</Tag> : "—" },
                              { title: "置信度", dataIndex: "family_match_confidence", align: "center", width: 90,
                                render: (v: any) => v == null ? "—" : Number(v).toFixed(3) },
                              textCol("匹配理由", "family_match_reasons", {
                                render: (v: any) => Array.isArray(v) && v.length ? v.join("；") : (v || "—"),
                              }),
                              textCol("原始单位", "original_unit"),
                              { title: "需复核", dataIndex: "review_required", align: "center", width: 80,
                                render: (v: any) => v ? <Tag color="orange">是</Tag> : <Tag color="default">否</Tag> },
                            ]}
                          />
                        </>
                      ),
                    },
                    {
                      key: "unknown_factors",
                      label: `③ 未知实测因子（${kosData.unknown_measured_factors?.length ?? 0}）`,
                      children: (
                        <>
                          <Paragraph type="secondary" style={{ fontSize: 11, marginBottom: 8 }}>
                            系统已保留该项实测数据，但目前无法可靠映射，建议补充 CAS、单位或检测方法。
                          </Paragraph>
                          <Table
                            size="small" pagination={false} rowKey="original_name"
                            dataSource={kosData.unknown_measured_factors || []}
                            locale={{ emptyText: "无" }}
                            columns={[
                              textCol("原始名称", "original_name"),
                              textCol("单位", "original_unit"),
                              numCol("最大值", "max", { width: 90,
                                render: (v: any) => v == null ? "—" : Number(v).toFixed(3) }),
                              numCol("中位数", "median", { width: 90,
                                render: (v: any) => v == null ? "—" : Number(v).toFixed(3) }),
                              numCol("P95", "p95", { width: 90,
                                render: (v: any) => v == null ? "—" : Number(v).toFixed(3) }),
                              numCol("点位数", "n_points", { width: 80 }),
                              textCol("未识别原因", "unknown_reason"),
                            ]}
                          />
                        </>
                      ),
                    },
                  ]} />
                </Card>
              )}

              {/* 诊断方法说明卡片(移到最底部, 优先展示 Top-N 结果后再解释方法) */}
              <MethodExplainCard track={kosTrack} flowKey="obstacle_analysis" />
            </>
          )}
        </>
      ) : <EmptyState description="请选择场地并运行障碍因子识别" />}

      <MethodFlowDrawer open={flowOpen} onClose={() => setFlowOpen(false)}
        config={getFlowConfig("obstacle_analysis")!} />
    </Space>
  );
}
