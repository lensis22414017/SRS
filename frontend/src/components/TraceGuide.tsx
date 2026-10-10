import { useEffect, useState } from "react";
import { Alert, Button, Card, Col, Progress, Row, Space, Steps, Tag, Typography } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import { api } from "../api/client";

const { Text } = Typography;
const STAGE_TAG: Record<string, { label: string; color: string }> = {
  pre_remediation: { label: "修复前数据", color: "blue" },
  post_remediation: { label: "修复后数据", color: "green" },
};

/** v1.1 (C5): 进入即展示全流程追溯引导; 只读, 不创建任何记录。 */
export function TraceGuide() {
  const [g, setG] = useState<any>(null);
  useEffect(() => { api.traceGuide().then(setG).catch(() => setG(null)); }, []);
  if (!g) return null;
  return (
    <Card title={g.title} extra={<Text type="secondary">{g.principle}</Text>}>
      <Steps direction="horizontal" size="small" current={-1} style={{ marginBottom: 16 }}
        items={g.stages.map((s: any) => ({ title: s.name,
          description: <Space size={2} wrap>{s.data_stage && <Tag color={STAGE_TAG[s.data_stage].color}>{STAGE_TAG[s.data_stage].label}</Tag>}
            {s.subprojects.map((x: string) => <Tag key={x}>{x}</Tag>)}</Space> }))} />
      <Row gutter={[12, 12]}>
        {g.stages.map((s: any) => (
          <Col xs={24} md={12} xl={8} key={s.stage}>
            <Card size="small" type="inner" title={s.name}>
              <div><Text strong>系统操作：</Text>{s.system_steps.join(" → ")}</div>
              <div><Text strong>需上传：</Text>{s.uploads.join("、") || "—"}</div>
              <div><Text strong>可下载：</Text>{s.downloads.join("、") || "—"}</div>
            </Card>
          </Col>))}
      </Row>
      <Space wrap style={{ marginTop: 12 }}>
        <Text strong>模板下载：</Text>
        {g.templates.map((t: any) => <Button key={t.url} size="small" icon={<DownloadOutlined />}
          onClick={() => api.downloadTemplate(t.url, `${t.name}.xlsx`)}>{t.name}</Button>)}
      </Space>
      <Alert style={{ marginTop: 12 }} type="warning" showIcon message={g.data_origin_rule} />
    </Card>
  );
}

/** v1.1 (C5) / v1.2.1 (R03): 软件操作里程碑与五阶段业务记录分开显示(只读查询)。 */
export function TraceProgress({ siteId }: { siteId: number }) {
  const [p, setP] = useState<any>(null);
  useEffect(() => { api.traceProgress(siteId).then(setP).catch(() => setP(null)); }, [siteId]);
  if (!p) return null;
  return (
    <Card size="small" title="七项软件操作里程碑（不等于五阶段业务完成）" extra={p.next_step ? <Tag color="blue">下一步：{p.next_step}</Tag> : <Tag color="green">软件操作已全部执行</Tag>}>
      <Space direction="vertical" style={{ width: "100%" }}>
        <Progress percent={Math.round((p.completed / p.total) * 100)} format={() => `${p.completed}/${p.total}`} />
        <Space wrap>{p.milestones.map((m: any) => <Tag key={m.key} color={m.done ? "green" : "default"}>
          {m.done ? "✓" : "○"} {m.name}{m.count ? `（${m.count}）` : ""}{m.pending_preview ? ` · 待确认 ${m.pending_preview}` : ""}</Tag>)}</Space>
        {Array.isArray(p.business_stages) && (
          <div>
            <Text strong>五阶段业务记录：{p.business_completed}/{p.business_total} 阶段已完成并有材料</Text>
            <div style={{ marginTop: 4 }}>
              <Space wrap>{p.business_stages.map((b: any) => (
                <Tag key={b.stage} color={b.status === "completed" ? "green" : b.status.startsWith("in_progress") ? "blue" : "default"}>
                  {b.name}：{b.status_cn}{b.n_attachments ? `（附件 ${b.n_attachments}）` : ""}
                </Tag>))}</Space>
            </div>
          </div>
        )}
        {!p.workflow_initialized && <Text type="secondary">五阶段追溯记录尚未初始化（查看本页不会创建记录）。</Text>}
      </Space>
    </Card>
  );
}
