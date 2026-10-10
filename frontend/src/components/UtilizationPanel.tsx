import { useEffect, useState } from "react";
import { Alert, App, Button, Card, Descriptions, List, Select, Space, Table, Tag, Typography } from "antd";
import { api } from "../api/client";
import { useAuth } from "../auth";

const { Text, Paragraph } = Typography;

const STATE: Record<string, { label: string; color: string }> = {
  both_supported: { label: "生产与生态均支持", color: "green" },
  production_supported: { label: "支持生产利用", color: "green" },
  ecology_supported: { label: "支持生态利用", color: "green" },
  neither_supported: { label: "均不支持", color: "red" },
  insufficient_evidence: { label: "证据不足", color: "orange" },
  needs_manual_use_selection: { label: "须选择用途（仅保守假设筛查，无正式结论）", color: "orange" },
  regulatory_applicability_unresolved: { label: "法规适用性未定（无正式结论）", color: "orange" },
};
const TRACK: Record<string, string> = {
  supported: "支持", not_supported: "不支持", insufficient: "证据不足", withheld_use: "用途未定，结论暂缓",
};
const USE: Record<string, string> = {
  explicit: "已选择", needs_manual_use_selection: "未选择用途", regulatory_applicability_unresolved: "法规适用性未定",
};
const GATE: Record<string, { label: string; color: string }> = {
  pass: { label: "通过", color: "green" },
  conditional: { label: "条件通过", color: "gold" },
  fail: { label: "未通过", color: "red" },
  insufficient: { label: "证据不足", color: "orange" },
};

/** v1.1 (C3): 利用方向结论。法规安全门禁不可被评分抵消; 证据缺失不视为通过。 */
export default function UtilizationPanel({ siteId, stage }: { siteId?: number; stage: "pre_remediation" | "post_remediation" }) {
  const { message } = App.useApp();
  const { hasPermission } = useAuth();
  const [d, setD] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [farmland, setFarmland] = useState<string | undefined>();
  const [ecoClass, setEcoClass] = useState<string | undefined>();

  useEffect(() => {
    setD(null);
    if (!siteId) return;
    api.utilizationLatest(siteId, stage).then((r) => setD(r.decision ? normalize(r.decision) : null)).catch(() => setD(null));
  }, [siteId, stage]);

  const run = () => {
    if (!siteId) return;
    setLoading(true);
    api.utilizationRun(siteId, stage, { farmland_type: farmland, eco_land_class: ecoClass })
      .then((r) => setD(normalize(r)))
      .catch((e) => message.error(e?.response?.data?.detail || "运行失败"))
      .finally(() => setLoading(false));
  };

  const pre = stage === "pre_remediation";
  return (
    <Card title={pre ? "修复前情景利用判断（修复目标导向）" : "修复后利用方向结论（生产 / 生态）"}
      extra={<Space wrap>
        <Select allowClear placeholder="农用地类型（正式结论必选）" style={{ width: 210 }} value={farmland} onChange={setFarmland}
          options={[{ value: "水田", label: "水田" }, { value: "其他", label: "其他农用地" }]} />
        <Select allowClear placeholder="建设用地类别（正式结论必选）" style={{ width: 230 }} value={ecoClass} onChange={setEcoClass}
          options={[{ value: "第一类用地", label: "第一类用地" }, { value: "第二类用地", label: "第二类用地" },
            { value: "非建设用地生态用途", label: "非建设用地生态用途（GB 36600 适用性未定）" }]} />
        {hasPermission("data:input") && <Button type="primary" loading={loading} onClick={run} disabled={!siteId}>运行判定</Button>}
      </Space>}>
      <Paragraph type="secondary" style={{ marginBottom: 12 }}>
        判定规则：生产轨道按 GB 15618-2018、生态轨道按 GB 36600-2018 设置法规安全门禁，门禁不可被任何评分抵消；
        必测项目缺测、阈值缺失或 pH 未知导致无法判定时，一律视为证据不足。门禁通过后再参考
        {pre ? "课题二重构可行性评分" : "课题三 SSUI"}。
      </Paragraph>
      {!d && <Alert type="info" showIcon message="尚未运行利用判定" />}
      {d && <Space direction="vertical" style={{ width: "100%" }} size={12}>
        {d.data_origin === "monte_carlo_demo" && <Alert type="error" showIcon message="模拟数据——仅供测试/演示，不得用于正式报告" />}
        <Space wrap>
          <Tag color={STATE[d.decision_state]?.color} style={{ fontSize: 15, padding: "4px 10px" }}>{STATE[d.decision_state]?.label}</Tag>
          <Tag color="purple">方法状态：{d.method_status === "provisional" ? "暂定（待课题组确认）" : d.method_status}</Tag>
          {pre && <Tag color="blue">修复前情景判断，非修复后结论</Tag>}
          <Text type="secondary">决策 #{d.decision_id} · {d.method_version}</Text>
        </Space>
        <Alert type={d.decision_state === "neither_supported" ? "error" : String(d.decision_state).endsWith("_supported") ? "success" : "warning"}
          message={d.conclusion_text} />
        {d.hypothetical_screen && <Alert type="warning" showIcon
          message="未选择用途或法规适用性未定：以下门禁结果为保守假设筛查，不构成正式利用结论"
          description={d.use_scope_note} />}
        <Table size="small" pagination={false} rowKey="track"
          dataSource={[
            { track: "生产（农用地）", gate: d.production_gate, score: d.production_score_obj, status: d.production_status, use: d.use_state?.production },
            { track: "生态", gate: d.ecology_gate, score: d.ecology_score_obj, status: d.ecology_status, use: d.use_state?.ecology },
          ]}
          columns={[
            { title: "轨道", dataIndex: "track", width: 110 },
            { title: "标准", render: (_: any, r: any) => r.gate?.standard + (r.gate?.land_class ? `（${r.gate.land_class}）` : "") },
            { title: "门禁", render: (_: any, r: any) => <Tag color={GATE[r.gate?.state]?.color}>{GATE[r.gate?.state]?.label}</Tag> },
            { title: "超管制值", render: (_: any, r: any) => (r.gate?.exceed_control || []).join("、") || "—" },
            { title: "仅超筛选值", render: (_: any, r: any) => (r.gate?.exceed_screening_only || []).join("、") || "—" },
            { title: "缺测必测项", render: (_: any, r: any) => r.gate?.missing_required?.length ? `${r.gate.missing_required.length} 项` : "—" },
            { title: "用途", render: (_: any, r: any) => USE[r.use] || "—" },
            { title: "功能评分", render: (_: any, r: any) => r.score ? (r.score.status === "out_of_domain"
                ? `${r.score.value ?? "—"}（超出有效域，不分级）` : `${r.score.value ?? "—"} ${r.score.label ?? ""}`) : "—" },
            { title: "轨道结论", render: (_: any, r: any) => TRACK[r.status] || r.status || "—" },
          ]} />
        {d.remediation_targets && <Descriptions size="small" column={1} bordered title="修复目标（降至筛选值以下）">
          <Descriptions.Item label="生产用途">{(d.remediation_targets.production || []).join("、") || "—"}</Descriptions.Item>
          <Descriptions.Item label="生态用途">{(d.remediation_targets.ecology || []).join("、") || "—"}</Descriptions.Item>
        </Descriptions>}
        {d.missing_evidence?.length > 0 && <List size="small" header={<b>需补充的证据</b>} bordered dataSource={d.missing_evidence}
          renderItem={(x: string) => <List.Item>{x}</List.Item>} />}
        {d.assumptions?.length > 0 && <List size="small" header={<b>假设与说明</b>} bordered dataSource={d.assumptions}
          renderItem={(x: string) => <List.Item>{x}</List.Item>} />}
      </Space>}
    </Card>
  );
}

function normalize(r: any) {
  // POST 返回引擎结构; GET 返回持久化记录结构 — 统一成面板字段
  if (r.production && r.production.gate) {
    return { ...r, production_gate: r.production.gate, ecology_gate: r.ecology.gate,
      production_score_obj: r.production.score, ecology_score_obj: r.ecology.score,
      production_status: r.production.track_status, ecology_status: r.ecology.track_status };
  }
  const ev = r.evidence || {};
  return { ...r, production_score_obj: ev.production?.score, ecology_score_obj: ev.ecology?.score,
    production_status: ev.production?.track_status, ecology_status: ev.ecology?.track_status,
    remediation_targets: ev.remediation_targets };
}
