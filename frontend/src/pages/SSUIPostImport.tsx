import { useEffect, useState } from "react";
import { Alert, App, Button, Card, Descriptions, Popconfirm, Radio, Space, Steps, Table, Tag, Typography, Upload } from "antd";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import { useAuth } from "../auth";
import SitePicker from "../components/SitePicker";
import UtilizationPanel from "../components/UtilizationPanel";

const { Text, Paragraph } = Typography;
const TRACK_CN: Record<string, string> = { production: "生产利用", ecology: "生态利用" };
const STATUS: Record<string, { label: string; color: string }> = {
  previewed: { label: "已预览未确认", color: "blue" }, confirmed: { label: "已确认", color: "green" },
  rejected: { label: "已放弃", color: "default" }, superseded: { label: "已被新批次替代", color: "default" },
};

/** v1.1 (C4): 课题三 修复后 SSUI 独立导入 — 模板下载 → 上传校验预览 → 确认入库 → 计算 → 导出 → 利用结论 */
export default function SSUIPostImport() {
  const { message } = App.useApp();
  const { hasPermission } = useAuth();
  const canInput = hasPermission("data:input");
  const [sid, setSid] = useState<number | undefined>(() => Number(sessionStorage.getItem("srs_current_site_id")) || undefined);
  const [siteCode, setSiteCode] = useState("");
  const [track, setTrack] = useState("production");
  const [preview, setPreview] = useState<any>(null);
  const [batches, setBatches] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);

  const loadBatches = () => { if (sid) api.ssuiPostBatches(sid).then((r) => setBatches(r.batches)).catch(() => setBatches([])); };
  useEffect(() => {
    setPreview(null); loadBatches();
    if (sid) api.site(sid).then((s: any) => setSiteCode(s.site_code)).catch(() => setSiteCode(""));
  }, [sid]);

  const step = preview ? (preview.confirmed ? 3 : 2) : 1;
  const upload = (file: File) => {
    if (!sid) return false;
    setBusy(true);
    api.ssuiPostPreview(sid, file, track).then((r) => setPreview(r))
      .catch((e) => message.error(e?.response?.data?.detail || "校验失败"))
      .finally(() => setBusy(false));
    return false;
  };
  const confirm = () => {
    setBusy(true);
    api.ssuiPostConfirm(preview.batch_id).then((r) => {
      message.success(`已确认入库: SSUI = ${r.calc?.ssui ?? "—"}`);
      setPreview({ ...preview, confirmed: true, result: r }); loadBatches();
    }).catch((e) => message.error(e?.response?.data?.detail || "确认失败")).finally(() => setBusy(false));
  };
  const reject = () => api.ssuiPostReject(preview.batch_id).then(() => { setPreview(null); loadBatches(); });

  const calc = preview?.result?.calc || preview?.preview_calc;
  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card title="课题三 · 修复后土壤持续利用度（SSUI）导入">
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Alert type="info" showIcon message="本页只接收修复后数据"
            description="课题一（障碍因子）与课题二（重构可行性）使用修复前检测数据，请在“场地管理 → 数据导入”上传；修复后 SSUI 数据与之物理分离，不会进入课题一/二的计算。" />
          <SitePicker value={sid} onChange={setSid} selectWidth={360} />
          <Space wrap>
            <Text>评价轨道：</Text>
            <Radio.Group value={track} onChange={(e) => { setTrack(e.target.value); setPreview(null); }}
              options={[{ value: "production", label: "生产利用" }, { value: "ecology", label: "生态利用" }]} optionType="button" />
            <Button icon={<DownloadOutlined />} onClick={() => api.downloadTemplate(
              `/api/v1/templates/ssui-post?track=${track}&site_code=${encodeURIComponent(siteCode)}`,
              `SRS_课题三修复后SSUI导入模板_${TRACK_CN[track]}.xlsx`)}>下载{TRACK_CN[track]}模板</Button>
          </Space>
          <Steps size="small" current={step} items={[
            { title: "下载模板" }, { title: "上传并校验预览" }, { title: "确认入库并计算" }, { title: "导出与利用结论" }]} />
          {canInput ? <Upload accept=".xlsx" maxCount={1} showUploadList={false} beforeUpload={upload} disabled={!sid || busy}>
            <Button type="primary" icon={<UploadOutlined />} loading={busy} disabled={!sid}>上传已填写的模板（仅校验，不入库）</Button>
          </Upload> : <Alert type="warning" showIcon message="当前账号无数据录入权限，只能查看已导入批次与结论" />}
        </Space>
      </Card>

      {preview && <Card title={`校验预览 · 批次 #${preview.batch_id}`}
        extra={!preview.confirmed && canInput && <Space>
          <Popconfirm title="确认后将写入修复后数据并计算 SSUI，确定？" onConfirm={confirm} disabled={!preview.can_confirm}>
            <Button type="primary" disabled={!preview.can_confirm} loading={busy}>确认入库</Button></Popconfirm>
          <Button onClick={reject}>放弃本批次</Button></Space>}>
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          {preview.data_origin === "monte_carlo_demo" && <Alert type="error" showIcon message="模拟数据——仅供测试/演示，不得用于正式报告" />}
          <Descriptions size="small" bordered column={3}>
            <Descriptions.Item label="文件">{preview.filename}</Descriptions.Item>
            <Descriptions.Item label="SHA-256"><Text copyable style={{ fontSize: 12 }}>{preview.sha256?.slice(0, 16)}…</Text></Descriptions.Item>
            <Descriptions.Item label="模板版本">{preview.template_version}</Descriptions.Item>
            <Descriptions.Item label="轨道">{TRACK_CN[preview.track] || "—"}</Descriptions.Item>
            <Descriptions.Item label="t（年）">{preview.t ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="M">{preview.M ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="数据来源">{preview.data_origin_label || "—"}</Descriptions.Item>
            <Descriptions.Item label="指标行">{preview.records?.length ?? 0} / 25</Descriptions.Item>
            <Descriptions.Item label="污染物检测">{preview.n_pollutant_rows} 行 · {preview.n_points} 个点位</Descriptions.Item>
          </Descriptions>
          {preview.n_errors > 0
            ? <Table size="small" rowKey={(_, i) => String(i)} pagination={{ pageSize: 10 }} dataSource={preview.errors}
                title={() => <Text type="danger">发现 {preview.n_errors} 处错误，修正后重新上传（不可确认）</Text>}
                columns={[{ title: "工作表", dataIndex: "sheet", width: 150 }, { title: "行", dataIndex: "row", width: 70 },
                          { title: "列", dataIndex: "col", width: 60 }, { title: "问题", dataIndex: "message" }]} />
            : <Alert type="success" showIcon message={preview.confirmed ? "已确认入库" : "校验通过，可确认入库"} />}
          {preview.warnings?.map((w: string) => <Alert key={w} type="warning" showIcon message={w} />)}
          {calc && calc.status === "ok" && <Descriptions size="small" bordered column={4} title="SSUI 计算（方法 PPT 第 15 页原式，未截断）">
            <Descriptions.Item label="SSUI">{calc.ssui?.toFixed(4)}</Descriptions.Item>
            <Descriptions.Item label="等级">{calc.grade}</Descriptions.Item>
            <Descriptions.Item label="f(t)">{calc.f_t}</Descriptions.Item>
            <Descriptions.Item label="Σ vⱼ·Sⱼ">{calc.weighted_sum?.toFixed(4)}</Descriptions.Item>
            {Object.entries(calc.criterion_scores || {}).map(([k, v]: any) =>
              <Descriptions.Item key={k} label={`S(${k}) × v=${calc.criterion_weights?.[k]}`}>{Number(v).toFixed(4)}</Descriptions.Item>)}
          </Descriptions>}
          {calc?.exceeds_unit_range && <Alert type="warning" showIcon message="SSUI 原值超过 1.0：方法等级区间仅定义到 1.0，已按“高度可持续”显示并标记待课题组确认（未截断）" />}
          {calc?.warnings?.map((w: string) => <Paragraph key={w} type="secondary" style={{ margin: 0 }}>· {w}</Paragraph>)}
        </Space>
      </Card>}

      <Card title="已导入批次（修复后）">
        <Table size="small" rowKey="batch_id" dataSource={batches} pagination={{ pageSize: 8 }}
          columns={[
            { title: "批次", dataIndex: "batch_id", width: 70 },
            { title: "轨道", dataIndex: "track", render: (v: string) => TRACK_CN[v] || v },
            { title: "状态", dataIndex: "status", render: (v: string) => <Tag color={STATUS[v]?.color}>{STATUS[v]?.label || v}</Tag> },
            { title: "来源", dataIndex: "data_origin_label", render: (v: string, r: any) =>
                <Tag color={r.data_origin === "monte_carlo_demo" ? "red" : "default"}>{v}</Tag> },
            { title: "t / M", render: (_: any, r: any) => `${r.t ?? "—"} / ${r.M ?? "—"}` },
            { title: "SSUI", dataIndex: "ssui", render: (v: number, r: any) => v == null ? "—" :
                <span>{v.toFixed(4)} {r.exceeds_unit_range && <Tag color="orange">&gt;1</Tag>}</span> },
            { title: "等级", dataIndex: "grade" },
            { title: "文件", dataIndex: "source_file", ellipsis: true },
            { title: "操作", render: (_: any, r: any) => r.status === "confirmed" || r.status === "superseded"
                ? <a onClick={() => api.ssuiPostExport(r.batch_id)}>导出结果</a> : "—" },
          ]} />
      </Card>

      <UtilizationPanel siteId={sid} stage="post_remediation" />
    </Space>
  );
}
