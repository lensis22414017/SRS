import { useEffect, useState } from "react";
import { Card, Button, Empty, App, Descriptions, Table, Tag, Space, Timeline, Divider, Row, Col, Segmented } from "antd";
import ReactECharts from "echarts-for-react";
import { api } from "../api/client";
import SitePicker from "../components/SitePicker";
import { seqCol, numCol, textCol } from "../utils/table";

export default function ObstacleAnalysis() {
  const { message } = App.useApp();
  const [sid, setSid] = useState<number>();
  const [diag, setDiag] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [landUse, setLandUse] = useState<string>("生产用地");

  const load = (id?: number) => {
    const s = id ?? sid; if (!s) return;
    api.diagnosis(s).then(setDiag).catch(() => setDiag(null));
    api.site(s).then((d: any) => setLandUse(d.land_use_type || "生产用地")).catch(() => {});
  };
  useEffect(() => { if (sid) load(sid); }, [sid]);

  const switchLandUse = async (v: string) => {
    if (!sid) return;
    try { await api.updateLandUse(sid, v); setLandUse(v); message.success(`修复后用途已切换为「${v}」, 诊断主轨 + 评价/SSUI/推荐将按此用途`); }
    catch (e: any) { message.error(e?.response?.data?.detail || "用途切换失败"); }
  };

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
    series: [{ type: "bar",
      data: diag.top_factors.map((t: any) => ({
        value: t.importance,
        itemStyle: { color: t.direction === "negative" ? "#4DBBD5" : "#E64B35" }  // 顶刊npg(Nature)配色: 负向缓解=蓝/正向加重=红橙(问题6)
      })),
      label: { show: true, position: "right" } }],
  } : null;
  // 裴总 deep-research: RF+SHAP 补可视化(局部SHAP解释 + 影响方向分布, NPG 顶刊色)
  // 局部SHAP条形图: 最高风险采样点的因子级SHAP(force plot近似), 正向加重=红/负向缓解=蓝
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
        itemStyle: { color: r.direction === "positive" ? "#E64B35" : "#4DBBD5",
          borderRadius: r.direction === "positive" ? [0, 3, 3, 0] : [3, 0, 0, 3] },
      })) }],
  } : null;
  // 方向分布饼图: 正向(加重) vs 负向(缓解) 因子数占比
  const tf = diag?.top_factors || [];
  const posCount = tf.filter((t: any) => t.direction === "positive").length;
  const negCount = tf.filter((t: any) => t.direction === "negative").length;
  const directionOption = tf.length ? {
    tooltip: { trigger: "item", formatter: "{b}: {c} 个 ({d}%)" },
    legend: { bottom: 0, data: ["正向(加重)", "负向(缓解)"] },
    series: [{ type: "pie", radius: ["42%", "68%"],
      data: [
        { name: "正向(加重)", value: posCount, itemStyle: { color: "#E64B35" } },
        { name: "负向(缓解)", value: negCount, itemStyle: { color: "#4DBBD5" } },
      ],
      label: { formatter: "{b}: {c}" } }],
  } : null;

  // 生产-生态双轨对比(裴总 goal: 双轨诊断真正生效, 后端 run_diagnosis 同时跑 prod+eco 两模型)
  const dual = (diag as any)?.shap_global?.dual_track;
  const dualOption = dual ? {
    tooltip: { trigger: "axis" },
    grid: { left: 80, right: 50, top: 16, bottom: 24 },
    xAxis: { type: "value", name: "高风险概率均值", max: 1 },
    yAxis: { type: "category", data: ["生态轨 eco", "生产轨 prod"] },
    series: [{ type: "bar", barMaxWidth: 30, data: [
      { value: dual.eco_proba_mean, itemStyle: { color: "#3C5488B0" } },
      { value: dual.prod_proba_mean, itemStyle: { color: "#E64B35" } },
    ], label: { show: true, position: "right", formatter: (p: any) => Number(p.value).toFixed(4) } }],
  } : null;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card>
        <Space style={{ width: "100%", justifyContent: "space-between", flexWrap: "wrap" }}>
          <Space wrap>
            <SitePicker value={sid} onChange={setSid} />
            <Segmented value={landUse} onChange={(v) => switchLandUse(v as string)} disabled={!sid}
              options={[{ label: "修复后·生产用地", value: "生产用地" }, { label: "修复后·生态用地", value: "生态用地" }]} />
          </Space>
          <Button type="primary" loading={busy} onClick={run} disabled={!sid}>运行 RF+SHAP 障碍因子识别</Button>
        </Space>
        <div style={{ marginTop: 8, color: "#666", fontSize: 12 }}>
          「修复后用途」决定诊断主轨(生产=GB15618严阈值/生态=GB36600二类宽阈值) + 功能重构评价方向 + SSUI + 方案推荐; 双轨对比卡片始终展示 prod/eco 全貌以供决策参照。
        </div>
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
          {dual && (
            <Card title={<Space><span>生产-生态双轨对比</span><Tag color={dual.dominant_track === "prod" ? "#E64B35" : "#00A087"} style={{ color: "#fff" }}>主导: {dual.dominant_track === "prod" ? "生产轨" : "生态轨"}</Tag></Space>}>
              <Row gutter={16}>
                <Col span={10}>
                  <ReactECharts option={dualOption} style={{ height: 200 }} />
                </Col>
                <Col span={14}>
                  <Descriptions size="small" column={2}>
                    <Descriptions.Item label="生产轨 proba">{dual.prod_proba_mean}</Descriptions.Item>
                    <Descriptions.Item label="生态轨 proba">{dual.eco_proba_mean}</Descriptions.Item>
                    <Descriptions.Item label="生产轨模型">{dual.prod_model}</Descriptions.Item>
                    <Descriptions.Item label="生态轨模型">{dual.eco_model}</Descriptions.Item>
                    <Descriptions.Item label="Δ(生产−生态)">{dual.delta_prod_minus_eco}</Descriptions.Item>
                    <Descriptions.Item label="生产/生态 AUC">{dual.prod_auc} / {dual.eco_auc}</Descriptions.Item>
                    <Descriptions.Item label="双轨说明" span={2}>生产轨用 GB15618 严阈值标签(风险判定保守)、生态轨用 GB36600 二类宽阈值标签; Δ&gt;0 表示生产功能重构风险系统性更高, 符合"严阈值→高 proba"物理解释。</Descriptions.Item>
                  </Descriptions>
                </Col>
              </Row>
              {(dual.prod_top_factors?.length || dual.eco_top_factors?.length) ? (
                <Row gutter={12} style={{ marginTop: 12 }}>
                  <Col span={12}>
                    <Card size="small" type="inner" title={<Space><span>生产轨 Top 障碍因子</span><Tag color="#E64B35" style={{ color: "#fff" }}>GB15618 严阈值</Tag></Space>}>
                      <Table rowKey="rank" size="small" pagination={false} dataSource={(dual.prod_top_factors || []).slice(0, 5)}
                        columns={[seqCol(40), textCol("因子", "factor"), numCol("|影响|", "importance"),
                          { title: "来源", dataIndex: "source", render: (v: string) => <Tag style={{ fontSize: 10 }}>{v === "rf_shap" ? "SHAP" : v === "threshold_exceedance_rule" ? "超标规则" : "短板规则"}</Tag> }]} />
                    </Card>
                  </Col>
                  <Col span={12}>
                    <Card size="small" type="inner" title={<Space><span>生态轨 Top 障碍因子</span><Tag color="#3C5488" style={{ color: "#fff" }}>GB36600 二类宽</Tag></Space>}>
                      <Table rowKey="rank" size="small" pagination={false} dataSource={(dual.eco_top_factors || []).slice(0, 5)}
                        columns={[seqCol(40), textCol("因子", "factor"), numCol("|影响|", "importance"),
                          { title: "来源", dataIndex: "source", render: (v: string) => <Tag style={{ fontSize: 10 }}>{v === "rf_shap" ? "SHAP" : v === "threshold_exceedance_rule" ? "超标规则" : "短板规则"}</Tag> }]} />
                    </Card>
                  </Col>
                </Row>
              ) : null}
            </Card>
          )}
          <Card title="Top-N 关键障碍因子（全局 SHAP 重要性）">
            {opt && <ReactECharts option={opt} style={{ height: 340 }} />}
            <Table rowKey="rank" size="small" pagination={false} dataSource={diag.top_factors}
              columns={[
                seqCol(64),
                textCol("障碍因子", "factor"),
                textCol("类别", "category"),
                numCol("|SHAP|", "importance"),
                { title: "影响方向", dataIndex: "direction", align: "center",
                  render: (v: string) => <Tag color={v === "positive" ? "#E64B35" : "#4DBBD5"} style={{ color: "#fff" }}>{v === "positive" ? "正向(加重)" : "负向(缓解)"}</Tag> },
              ]} />
          </Card>
          {(localOption || directionOption) && (
            <Row gutter={16}>
              {localOption && (
                <Col span={14}>
                  <Card title="局部 SHAP 解释（最高风险采样点 · force plot 近似）">
                    <ReactECharts option={localOption} style={{ height: 320 }} />
                  </Card>
                </Col>
              )}
              {directionOption && (
                <Col span={10}>
                  <Card title="障碍因子影响方向分布">
                    <ReactECharts option={directionOption} style={{ height: 320 }} />
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
      ) : <Empty description="请选择场地并运行障碍因子识别" />}
    </Space>
  );
}
