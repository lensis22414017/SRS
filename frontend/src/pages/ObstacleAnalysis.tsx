import { useEffect, useState } from "react";
import { Card, Button, Row, Col, Space, Alert, Typography, App, Descriptions, Table, Tag, Timeline, Segmented, Tooltip, Select, Collapse } from "antd";
import { InfoCircleOutlined, ExportOutlined, HistoryOutlined, ApartmentOutlined } from "@ant-design/icons";
import MethodFlowDrawer from "../components/MethodFlowDrawer";
import MethodExplainCard from "../components/MethodExplainCard";
import FactorDictionaryTable from "../components/FactorDictionaryTable";
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

  const restoreDiagnosis = (d: any, expectedTrack: "prod" | "eco") => {
    if (!d || (d.diagnosis_method === "kos" && d.track !== expectedTrack)) {
      setDiag(null);
      setKosData(null);
      return;
    }
    setDiag(d);
    if (d.kos_result) {
      setKosData(d.kos_result);
      setKosTrack(expectedTrack);
    } else {
      setKosData(null);
    }
  };

  const load = async (id?: number, diagnosisId?: number | null, requestedTrack?: "prod" | "eco") => {
    const s = id ?? sid; if (!s) return;
    try {
      const siteData = await api.site(s);
      const expectedTrack = requestedTrack || (siteData.land_use_type === "生态用地" ? "eco" : "prod");
      setSite(siteData);
      setLandUse(expectedTrack === "eco" ? "生态用地" : "生产用地");
      setKosTrack(expectedTrack);

      const rawHistory = await api.diagnosisHistory(s) as any[];
      // 兼容升级前创建的历史摘要：旧后端摘要没有 track/method，按详情补齐后再筛选。
      const allHistory = await Promise.all(rawHistory.map(async (item) => {
        if (item.track && item.diagnosis_method) return item;
        try {
          const detail = await api.diagnosisDetail(item.id);
          return { ...item, track: detail.track, diagnosis_method: detail.diagnosis_method };
        } catch {
          return item;
        }
      }));
      const trackHistory = allHistory.filter(
        (item) => item.diagnosis_method === "kos" && item.track === expectedTrack,
      );
      setHistoryList(trackHistory);
      const selected = diagnosisId
        ? trackHistory.find((item) => item.id === diagnosisId)
        : trackHistory[0];
      if (!selected) {
        restoreDiagnosis(null, expectedTrack);
        return;
      }
      const detail = await api.diagnosisDetail(selected.id);
      restoreDiagnosis(detail, expectedTrack);
    } catch {
      setDiag(null);
      setKosData(null);
      setHistoryList([]);
    }
  };
  useEffect(() => { if (sid) { load(sid); setHistoryId(null); } }, [sid]);

  const switchLandUse = async (v: string) => {
    if (!sid) return;
    try {
      await api.updateLandUse(sid, v);
      const nextTrack = v === "生态用地" ? "eco" : "prod";
      setLandUse(v);
      setHistoryId(null);
      await load(sid, null, nextTrack);
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
      // Round8 审计 4.6: POST 直接返回时 r 已包含顶层 key_obstacles 等字段
      // 同时 r.kos_result 是与 GET 详情统一的完整结构, 直接用 r 即可
      // (key_obstacles/model_contribution/factor_statistics 等都在顶层)
      setKosData(r);
      setKosTrack(t);
      setDiag({ ...r, diagnosis_method: "kos", track: t, kos_result: r.kos_result || r });
      setHistoryId(r.diagnosis_id || null);
      api.diagnosisHistory(sid).then((items: any[]) => {
        setHistoryList(items.filter((item) => item.diagnosis_method === "kos" && item.track === t));
      }).catch(() => {});
    } catch (e: any) {
      // Round8 审计 4.3: 后端持久化失败会返回 503, 这里展示详细原因
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
  const qualityFlags = Array.from(new Set((kosData?.data_quality_flags || []).filter(Boolean))) as string[];

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
                  if (r?.report_id) {
                    const filename = r.file_name || `诊断报告_场地${sid}_${r.version}.pdf`;
                    api.downloadReport(r.report_id, filename);
                    message.success("报告已下载");
                  } else {
                    message.warning("报告已生成，请在追溯页面下载");
                  }
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
              {/* ─── KOS 诊断结果 ─── */}

              {/* 第一层: 污染场地关键障碍因子 Top-N (优先展示, 规则层 B=1 + 实测 + 综合评分排序) */}
              <Card title={
                <Space>
                  <span>污染场地关键障碍因子 Top-N</span>
                  <Tag color={kosTrack === "prod" ? "purple" : "green"}>
                    {kosTrack === "prod" ? "生产用途" : "生态用途"}
                  </Tag>
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
                    {kosData.model_contribution_scope === "local_point"
                      ? `ⓘ 当前为真实采样点 ${kosData.decision_point_code || kosData.decision_point_id || "—"} 的局部 SHAP 贡献；所有特征来自同一点位。`
                      : "ⓘ 当前局部解释不可用，图中仅为训练集全局背景贡献，不代表本场地局部贡献。"}
                    模型贡献仅作统计解释参考，不是因果证明，也不是法规判定依据；正式障碍判定以规则层和标准阈值为准。
                  </Paragraph>
                </Card>
              )}

              {/* 数据质量提示 — 折叠面板, 低调展示在模型贡献图之后 */}
              {(kosData.review_required || qualityFlags.length > 0) && (
                <Card size="small" style={{ marginTop: 12, borderLeft: "3px solid #d9d9d9" }}
                  title={
                    <span style={{ fontSize: 12, color: "#8c8c8c", fontWeight: 400 }}>
                      ▎{kosData.model_status === "exploratory"
                        ? `数据质量提示（探索性诊断，共 ${qualityFlags.length} 项）`
                        : `数据质量提示（共 ${qualityFlags.length} 项）`}
                    </span>
                  }
                >
                  <Collapse ghost size="small" items={[{
                    key: "quality-flags",
                    label: <span style={{ fontSize: 12, color: "#8c8c8c" }}>展开查看详情</span>,
                    children: <div style={{ maxHeight: 300, overflow: "auto", fontSize: 12 }}>
                      <ul style={{ margin: 0, paddingLeft: 18 }}>
                        {qualityFlags.map((f, i) => <li key={i}>{f}</li>)}
                      </ul>
                    </div>,
                  }]} />
                </Card>
              )}

              {/* 未知有机物防线(如有) */}
              {/* 未知有机物防线 — 折叠面板 */}
              {kosData.organic_guardrails && (kosData.organic_guardrails.n_family_warning > 0 || kosData.organic_guardrails.n_unknown > 0) && (
                <Card size="small" style={{ marginTop: 12, borderLeft: "3px solid #faad14" }}
                  title={
                    <span style={{ fontSize: 12, color: "#8c8c8c", fontWeight: 400 }}>
                      ▎检测到 {kosData.organic_guardrails.n_family_warning} 个族群未收录物质，{kosData.organic_guardrails.n_unknown} 个完全未知物质
                    </span>
                  }
                >
                  <Collapse ghost size="small" items={[{
                    key: "unknown-guard",
                    label: <span style={{ fontSize: 12, color: "#8c8c8c" }}>展开查看详情</span>,
                    children: <div style={{ fontSize: 12, color: "#666" }}>
                      <p style={{ margin: 0 }}>未收录因子不会丢失，已进入模型候选识别、族群级近邻分析和未知因子预警（不强行套用阈值）。系统不会假装识别未知物质，仅作为辅助识别参考，非法规超标判定。请参考「建议补测」或安排深度检测。</p>
                    </div>,
                  }]} />
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

      {/* v0.8.1 障碍因子集速查表（始终可见，供老专家参考） */}
      <FactorDictionaryTable />
    </Space>
  );
}
