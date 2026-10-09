import { useEffect, useState } from "react";
import { Alert, App, Button, Card, Collapse, Descriptions, Popconfirm, Select, Space, Steps, Table, Tag, Typography, Upload } from "antd";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import { useAuth } from "../auth";
import SitePicker from "../components/SitePicker";
import UtilizationPanel from "../components/UtilizationPanel";

const { Text, Paragraph } = Typography;
const STATUS: Record<string, { label: string; color: string }> = {
  previewed: { label: "已预览未确认", color: "blue" }, confirmed: { label: "已确认", color: "green" },
  rejected: { label: "已放弃", color: "default" }, superseded: { label: "已被新批次替代", color: "default" },
};
const ORIGINS = [
  { value: "client_real", label: "真实数据(甲方/课题组提供)" }, { value: "field", label: "现场实测" },
  { value: "monte_carlo_demo", label: "模拟数据——仅供测试/演示" },
];
const PROV = [{ value: "verified", label: "来源已核实" }, { value: "unverified", label: "来源未核实(仅作软件演示)" }];

/** v1.2 课题二: 28 项功能重构可行性指标导入(修复前) — 模板 → 上传校验 → 确认入库 → M-REC-2025 计算 → 导出 */
export default function ReconIndicatorImport() {
  const { message } = App.useApp();
  const { hasPermission } = useAuth();
  const canInput = hasPermission("data:input");
  const [sid, setSid] = useState<number | undefined>(() => Number(sessionStorage.getItem("srs_current_site_id")) || undefined);
  const [siteCode, setSiteCode] = useState("");
  const [origin, setOrigin] = useState("client_real");
  const [prov, setProv] = useState("verified");
  const [subtype, setSubtype] = useState<string>("未注明");
  const [ecoClass, setEcoClass] = useState("第一类用地");
  const [preview, setPreview] = useState<any>(null);
  const [batches, setBatches] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [baseline, setBaseline] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  const loadBatches = () => { if (sid) api.reconBatches(sid).then((r) => setBatches(r.batches)).catch(() => setBatches([])); };
  useEffect(() => { api.reconBaseline().then(setBaseline).catch(() => setBaseline(null)); }, []);
  useEffect(() => {
    setPreview(null); setDetail(null); loadBatches();
    if (sid) api.site(sid).then((s: any) => setSiteCode(s.site_code)).catch(() => setSiteCode(""));
  }, [sid]);

  const upload = (file: File) => {
    if (!sid) return false;
    setBusy(true);
    api.reconPreview(sid, file, { data_origin: origin, provenance_status: prov, land_subtype: subtype, eco_land_class: ecoClass })
      .then((r) => setPreview(r)).catch((e) => message.error(e?.response?.data?.detail || "校验失败")).finally(() => setBusy(false));
    return false;
  };
  const confirm = () => {
    setBusy(true);
    api.reconConfirm(preview.batch_id).then((r) => {
      message.success(`已确认入库 ${r.observations} 个观测值`);
      setPreview({ ...preview, confirmed: true, result: r }); loadBatches();
      api.reconBatch(preview.batch_id).then(setDetail);
    }).catch((e) => message.error(e?.response?.data?.detail || "确认失败")).finally(() => setBusy(false));
  };
  const reject = () => api.reconReject(preview.batch_id).then(() => { setPreview(null); loadBatches(); });
  const step = preview ? (preview.confirmed ? 3 : 2) : 1;

  const evalCard = (scope: "production" | "ecology", ev: any) => ev && (
    <Card size="small" title={`${scope === "production" ? "生产" : "生态"}功能重构可行性`} key={scope}
      extra={<Tag color={ev.grade === "可行" ? "green" : ev.grade === "不可行" ? "red" : "orange"}>{ev.grade}</Tag>}>
      <Descriptions size="small" column={3}>
        <Descriptions.Item label="综合得分">{ev.score ?? "—"}</Descriptions.Item>
        <Descriptions.Item label="计算路径">{ev.dimensions?.path === "full" ? "全指标(表2.18/2.20)" : "缺失数据(表2.19/2.21)"}</Descriptions.Item>
        <Descriptions.Item label="点位等级分布">{JSON.stringify(ev.dimensions?.point_grade_distribution || {})}</Descriptions.Item>
        <Descriptions.Item label="限制性指标(F≤60)" span={3}>{(ev.limiting_factors || []).join("、") || "无"}</Descriptions.Item>
      </Descriptions>
      <Paragraph type="secondary" style={{ marginBottom: 4 }}>{ev.explanation}</Paragraph>
      <Collapse size="small" items={[
        { key: "dims", label: "指标得分与权重", children:
          <Table size="small" rowKey={(r: any) => r.indicator} pagination={false} dataSource={ev.dimensions?.dimensions || []}
            columns={[{ title: "指标/准则", dataIndex: "indicator" }, { title: "代表值", dataIndex: "raw_value", render: (v: any) => v == null ? "—" : String(v) },
              { title: "F", dataIndex: "F" }, { title: "权重", dataIndex: "weight" }, { title: "贡献", dataIndex: "contribution" },
              { title: "规则", dataIndex: "rule", ellipsis: true }]} /> },
        { key: "trace", label: "计算过程", children: (ev.dimensions?.calculation_trace || []).map((t: string) => <div key={t}>{t}</div>) },
        { key: "ns", label: "未赋分指标及原因", children:
          Object.values(ev.dimensions?.not_scored || {}).map((x: any) => <div key={x.indicator}>· {x.indicator}: {x.status} — {x.rule}</div>) },
        { key: "as", label: "本次计算采用的假设", children: (ev.dimensions?.assumptions || []).map((t: string) => <div key={t}>· {t}</div>) },
      ]} />
    </Card>);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card title="课题二 · 功能重构可行性指标导入（修复前 28 项指标）">
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <Alert type="info" showIcon message="本页只接收修复前数据（课题二）"
            description="支持 SRS 模板 RECON-PRE-v1.2，也可直接上传子课题宽表（首行为表头、一行一个点位，中英文表头均可）。类别指标（容重、生物多样性、盐渍化、灌排能力、质地、C库变化因子、剖面构型）按方法表2.22 分级赋分；数值文本中的空格/制表符会被清洗并记录；Excel 错误值按缺测处理。" />
          <SitePicker value={sid} onChange={setSid} selectWidth={360} />
          <Space wrap>
            <Text>数据来源：</Text><Select style={{ width: 220 }} value={origin} onChange={setOrigin} options={ORIGINS} />
            <Text>来源核实：</Text><Select style={{ width: 200 }} value={prov} onChange={setProv} options={PROV} />
            <Text>农用地类型：</Text><Select style={{ width: 110 }} value={subtype} onChange={setSubtype}
              options={["未注明", "旱地", "水田"].map((v) => ({ value: v, label: v }))} />
            <Text>生态用地类别：</Text><Select style={{ width: 130 }} value={ecoClass} onChange={setEcoClass}
              options={["第一类用地", "第二类用地"].map((v) => ({ value: v, label: v }))} />
            <Button icon={<DownloadOutlined />} onClick={() => api.downloadTemplate(
              `/api/v1/templates/recon-pre?site_code=${encodeURIComponent(siteCode)}`, "SRS_课题二重构指标导入模板_RECON-PRE-v1.2.xlsx")}>下载模板</Button>
          </Space>
          <Steps size="small" current={step} items={[{ title: "下载模板" }, { title: "上传并校验预览" }, { title: "确认入库并计算" }, { title: "导出与利用结论" }]} />
          {canInput ? <Upload accept=".xlsx,.csv" maxCount={1} showUploadList={false} beforeUpload={upload} disabled={!sid || busy}>
            <Button type="primary" icon={<UploadOutlined />} loading={busy} disabled={!sid}>上传指标数据（仅校验，不入库）</Button>
          </Upload> : <Alert type="warning" showIcon message="当前账号无数据录入权限，只能查看已导入批次与结论" />}
          {baseline && <Text type="secondary">评价方法：{baseline.method_version}；来源：{baseline.source}；表2.18 权重和 {baseline.weights?.sum_2_18}（不归一）</Text>}
        </Space>
      </Card>

      {preview && <Card title={`校验预览 · 批次 #${preview.batch_id}`}
        extra={!preview.confirmed && canInput && <Space>
          <Popconfirm title="确认后将写入课题二指标数据并计算，确定？" onConfirm={confirm} disabled={!preview.can_confirm}>
            <Button type="primary" disabled={!preview.can_confirm} loading={busy}>确认入库</Button></Popconfirm>
          <Button onClick={reject}>放弃本批次</Button></Space>}>
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          {preview.meta?.data_origin === "monte_carlo_demo" && <Alert type="error" showIcon message="模拟数据——仅供测试/演示，不得用于正式报告" />}
          {preview.meta?.provenance_status === "unverified" && <Alert type="warning" showIcon message="来源未核实：结果仅作软件演示，不作正式结论" />}
          <Descriptions size="small" bordered column={3}>
            <Descriptions.Item label="工作表">{preview.sheet}</Descriptions.Item>
            <Descriptions.Item label="SHA-256"><Text copyable style={{ fontSize: 12 }}>{preview.sha256?.slice(0, 16)}…</Text></Descriptions.Item>
            <Descriptions.Item label="点位数">{preview.point_count}</Descriptions.Item>
            <Descriptions.Item label="已映射指标">{Object.keys(preview.mapping || {}).length} / 28</Descriptions.Item>
            <Descriptions.Item label="未提供的指标" span={2}>{(preview.absent_features || []).join("、") || "无"}</Descriptions.Item>
            <Descriptions.Item label="清洗记录">{preview.cleaning_log?.length || 0} 个单元格</Descriptions.Item>
            <Descriptions.Item label="告警">{preview.warning_count}</Descriptions.Item>
            <Descriptions.Item label="预览得分">{["production", "ecology"].map((s) => preview.preview_evaluation?.[s]
              ? `${s === "production" ? "生产" : "生态"} ${preview.preview_evaluation[s].score ?? "—"}（${preview.preview_evaluation[s].grade}）` : "").join("；")}</Descriptions.Item>
          </Descriptions>
          {preview.errors?.length > 0
            ? <Table size="small" rowKey={(_, i) => String(i)} pagination={{ pageSize: 10 }} dataSource={preview.errors}
                title={() => <Text type="danger">发现 {preview.errors.length} 处错误，修正后重新上传（不可确认）</Text>}
                columns={[{ title: "工作表", dataIndex: "sheet", width: 120 }, { title: "单元格", dataIndex: "cell", width: 90 }, { title: "问题", dataIndex: "message" }]} />
            : <Alert type="success" showIcon message={preview.confirmed ? "已确认入库" : "校验通过，可确认入库"} />}
          <Collapse size="small" items={[
            { key: "w", label: `告警（${preview.warning_count}）`, children: (preview.warnings || []).map((w: any, i: number) => <div key={i}>{w.cell} {w.message}</div>) },
            { key: "c", label: `数值文本清洗（${preview.cleaning_log?.length || 0}）`, children:
              <Table size="small" rowKey="cell" pagination={{ pageSize: 8 }} dataSource={preview.cleaning_log}
                columns={[{ title: "单元格", dataIndex: "cell" }, { title: "点位", dataIndex: "point" }, { title: "指标", dataIndex: "feature" },
                  { title: "原文", dataIndex: "original" }, { title: "清洗后", dataIndex: "cleaned" }, { title: "变换", dataIndex: "transform" }]} /> },
          ]} />
        </Space>
      </Card>}

      {detail && <Space direction="vertical" style={{ width: "100%" }}>
        {evalCard("production", detail.evaluation?.production)}{evalCard("ecology", detail.evaluation?.ecology)}
        <Alert type="info" showIcon message="评分不能替代法规安全门禁：修复前利用方向判断见下方“利用方向结论”（GB 15618 / GB 36600 门禁优先）。" />
      </Space>}

      <Card title="已导入批次（课题二 · 修复前）">
        <Table size="small" rowKey="batch_id" dataSource={batches} pagination={{ pageSize: 8 }}
          columns={[
            { title: "批次", dataIndex: "batch_id", width: 70 },
            { title: "状态", dataIndex: "status", render: (v: string) => <Tag color={STATUS[v]?.color}>{STATUS[v]?.label || v}</Tag> },
            { title: "来源", dataIndex: "data_origin_label", width: 210, render: (v: string, r: any) => <Tag style={{ whiteSpace: "normal" }} color={r.data_origin === "monte_carlo_demo" ? "red" : "default"}>{v}</Tag> },
            { title: "核实", dataIndex: "provenance_label" },
            { title: "点位", dataIndex: "point_count" },
            { title: "生产", render: (_: any, r: any) => r.production ? `${r.production.score ?? "—"}（${r.production.grade}）` : "—" },
            { title: "生态", render: (_: any, r: any) => r.ecology ? `${r.ecology.score ?? "—"}（${r.ecology.grade}）` : "—" },
            { title: "文件", dataIndex: "source_file", ellipsis: true },
            { title: "操作", render: (_: any, r: any) => r.status === "confirmed" || r.status === "superseded"
                ? <Space><a onClick={() => api.reconBatch(r.batch_id).then(setDetail)}>查看</a><a onClick={() => api.reconExport(r.batch_id)}>导出</a></Space> : "—" },
          ]} />
      </Card>
      <UtilizationPanel siteId={sid} stage="pre_remediation" />
    </Space>
  );
}
