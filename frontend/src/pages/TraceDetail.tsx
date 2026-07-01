import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card, Steps, Tag, Button, Space, Upload, Select, Modal, Input, message, Table, Descriptions, Spin, Tooltip, Typography,
} from "antd";
import { UploadOutlined, FileAddOutlined, DownloadOutlined, EyeOutlined, ApartmentOutlined } from "@ant-design/icons";
import { api } from "../api/client";
import MethodFlowDrawer from "../components/MethodFlowDrawer";
import { getFlowConfig } from "../config/methodFlows";
import { seqCol, textCol } from "../utils/table";

const STATUS: Record<string, { c: string; t: string; step: any }> = {
  completed: { c: "green", t: "已完成", step: "finish" },
  in_progress: { c: "blue", t: "进行中", step: "process" },
  returned: { c: "red", t: "已退回", step: "error" },
  not_started: { c: "default", t: "未开始", step: "wait" },
};

function formatBytes(bytes: number | undefined | null): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// 通用文件角色(原始报告/审批意见/盖章版报告/补充材料) + 各阶段专属角色
// 支持监理上传→甲方审批→盖章版上传 的角色流转
const COMMON_FILE_ROLES = ["原始报告", "审批意见", "盖章版报告", "补充材料"];
const FILE_ROLES: Record<string, string[]> = {
  survey: [...COMMON_FILE_ROLES, "场地调查报告", "检测数据", "障碍因子识别结果", "可行性分析结论"],
  approval: [...COMMON_FILE_ROLES, "重构方案", "修改记录", "最终通过版本"],
  construction: [...COMMON_FILE_ROLES, "施工方案", "监理方案", "施工进度记录", "材料使用台账"],
  effect: [...COMMON_FILE_ROLES, "效果检测数据", "效果评估报告", "达标结论"],
  maintenance: [...COMMON_FILE_ROLES, "管护方案", "定期监测数据", "功能维护记录"],
};

export default function TraceDetail() {
  const { id } = useParams();
  const sid = Number(id);
  const nav = useNavigate();
  const [site, setSite] = useState<any>(null);
  const [stages, setStages] = useState<any[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [modal, setModal] = useState<{ stage: string; role: string } | null>(null);
  const [comment, setComment] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState("");
  const [flowOpen, setFlowOpen] = useState(false);

  const load = async () => {
    setSite(await api.site(sid));
    const wf = await api.workflow(sid);
    setStages(wf.stages || []);
    setReports(await api.reports(sid).then((d) => d.items).catch(() => []));
  };
  useEffect(() => { load(); }, [sid]);

  const init = async () => { setBusy(true); try { await api.initWorkflow(sid); message.success("已初始化五阶段"); await load(); } finally { setBusy(false); } };

  const setStatus = async (stage: string, status: string) => {
    setBusy(true);
    try { await api.updateStage(sid, stage, { status, review_comment: comment || undefined, is_completed: status === "completed" }); message.success("已更新"); setComment(""); await load(); }
    catch (e: any) { message.error(e?.response?.data?.detail || "更新失败"); }
    finally { setBusy(false); }
  };

  const doUpload = async (file: File) => {
    if (!modal) return false;
    setBusy(true);
    try { await api.uploadAttachment(sid, modal.stage, file, modal.role); message.success("上传成功"); setModal(null); await load(); }
    catch (e: any) { message.error(e?.response?.data?.detail || "上传失败"); }
    finally { setBusy(false); }
    return false;
  };

  const openPreview = async (reportId: number, siteCode: string, version: string) => {
    try {
      setBusy(true);
      const blob = await api.reportBlob(reportId);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      const url = URL.createObjectURL(blob);
      setPreviewUrl(url);
      setPreviewTitle(`追溯报告预览 — ${siteCode} ${version}`);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "预览加载失败");
    } finally {
      setBusy(false);
    }
  };

  const closePreview = () => {
    if (previewUrl) { URL.revokeObjectURL(previewUrl); setPreviewUrl(null); }
  };

  const genReport = async (format: "pdf" | "docx" = "pdf") => {
    setBusy(true);
    try { const r = await api.generateReport(sid, format); message.success(`${format.toUpperCase()} 报告 ${r.version} 已生成`); await load(); }
    catch (e: any) { message.error(e?.response?.data?.detail || "生成失败(需 report:generate 权限)"); }
    finally { setBusy(false); }
  };

  if (!site) return <Spin style={{ marginTop: 80 }} />;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card title={`全流程追溯 — ${site.name}（${site.site_code}）`}
        extra={<Space>
          <Button onClick={() => nav("/trace")}>返回列表</Button>
          {stages.length === 0 && <Button type="primary" loading={busy} onClick={init}>初始化五阶段</Button>}
          <Button type="primary" loading={busy} onClick={() => genReport("pdf")}>生成 PDF 报告</Button>
          <Button loading={busy} onClick={() => genReport("docx")}>生成 DOCX 报告</Button>
          <Button icon={<ApartmentOutlined />} onClick={() => setFlowOpen(true)}>方法说明</Button>
        </Space>}>
        {stages.length === 0 ? <span>尚未初始化五阶段，请点击右上角“初始化五阶段”。</span> : (
          <Steps direction="vertical" current={-1}
            items={stages.map((s) => ({
              status: STATUS[s.status]?.step,
              title: <Space>{s.stage_name}<Tag color={STATUS[s.status]?.c}>{STATUS[s.status]?.t}</Tag>
                <span style={{ fontSize: 12, color: "#999" }}>版本{s.version}｜附件{s.n_attachments}</span></Space>,
              description: (
                <div style={{ marginTop: 6 }}>
                  {s.review_comment && <div style={{ color: "#666", fontSize: 13 }}>意见：{s.review_comment}</div>}
                  <Space wrap style={{ marginTop: 6 }}>
                    <Button size="small" icon={<FileAddOutlined />} onClick={() => setModal({ stage: s.stage, role: FILE_ROLES[s.stage][0] })}>上传材料</Button>
                    <Button size="small" onClick={() => setStatus(s.stage, "in_progress")}>标记进行中</Button>
                    <Button size="small" type="primary" onClick={() => setStatus(s.stage, "completed")}>标记完成</Button>
                    <Button size="small" danger onClick={() => setStatus(s.stage, "returned")}>退回</Button>
                  </Space>
                  {s.attachments?.length > 0 && (
                    <div style={{ marginTop: 6 }}>
                      {s.attachments.map((a: any) => (
                        <div key={a.id} style={{ marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                          <Tag color="blue" style={{ margin: 0 }}>{a.file_role || "材料"}</Tag>
                          <a style={{ fontSize: 13 }}
                             onClick={() => api.downloadAttachment(sid, s.stage, a.id, a.original_name || a.file_role || "附件")}>
                            <DownloadOutlined style={{ marginRight: 2 }} />
                            {a.original_name || a.file_role || "附件"}
                          </a>
                          {a.size_bytes != null && (
                            <Tooltip title={`${a.size_bytes} 字节`}>
                              <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                                {formatBytes(a.size_bytes)}
                              </Typography.Text>
                            </Tooltip>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ),
            }))} />
        )}
      </Card>

      {/* 网盘 · 跨阶段已上传文件库汇总(存放已上传数据) */}
      {(() => {
        const allFiles = stages.flatMap((s: any) =>
          (s.attachments || []).map((a: any) => ({ ...a, stage: s.stage, stage_name: s.stage_name })));
        if (!allFiles.length) return null;
        return (
          <Card title={<Space><FileAddOutlined />网盘 · 已上传文件库（{allFiles.length} 个文件）</Space>} size="small">
            <Table rowKey={(r: any) => `${r.stage}_${r.id}`} size="small" pagination={{ pageSize: 8 }} dataSource={allFiles}
              columns={[
                seqCol(50),
                textCol("所属阶段", "stage_name"),
                { title: "文件类型", dataIndex: "file_role", align: "left", render: (v: any) => v || "—" },
                { title: "文件名", dataIndex: "original_name", align: "left",
                  render: (v: any) => v || "—" },
                { title: "大小", align: "right", width: 80,
                  render: (_: any, r: any) => (
                    <Tooltip title={r.size_bytes != null ? `${r.size_bytes} 字节` : undefined}>
                      <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                        {formatBytes(r.size_bytes)}
                      </Typography.Text>
                    </Tooltip>) },
                { title: "上传者", dataIndex: "uploaded_by_name", align: "center", width: 100,
                  render: (v: any) => v || "—" },
                { title: "上传时间", dataIndex: "uploaded_at", align: "center", width: 150,
                  render: (v: any) => v || "—" },
                { title: "操作", align: "center", width: 80,
                  render: (_: any, r: any) => (
                    <Button size="small" icon={<DownloadOutlined />}
                      onClick={() => api.downloadAttachment(sid, r.stage, r.id, r.original_name || r.file_role || "附件")}>下载</Button>) },
              ]} />
          </Card>
        );
      })()}

      {reports.length > 0 && (
        <Card title="已生成报告">
          <Table rowKey="report_id" size="small" pagination={false} dataSource={reports}
            columns={[seqCol(64), textCol("版本", "version"), textCol("生成时间", "generated_at"),
              { title: "格式", align: "center", render: (_: any, r: any) => (r.data_snapshot?.format || "pdf").toUpperCase() },
              { title: "操作", align: "center", render: (_: any, r: any) => {
                  const fmt = r.data_snapshot?.format || "pdf";
                  return (
                    <Space>
                      {fmt === "pdf" && (
                        <Button size="small" icon={<EyeOutlined />}
                          onClick={() => openPreview(r.report_id, site.site_code, r.version)}>
                          预览
                        </Button>
                      )}
                      <Button size="small" icon={<DownloadOutlined />}
                        onClick={() => api.downloadReport(r.report_id, `追溯报告_${site.site_code}_${r.version}.${fmt}`)}>
                        下载
                      </Button>
                    </Space>
                  );
                } }]} />
        </Card>
      )}

      {/* PDF 内嵌预览 Modal */}
      <Modal
        open={!!previewUrl}
        title={previewTitle}
        onCancel={closePreview}
        footer={null}
        width="80vw"
        style={{ top: 20 }}
        styles={{ body: { padding: 0, height: "80vh" } }}
      >
        {previewUrl && (
          <iframe
            src={previewUrl}
            title={previewTitle}
            style={{ width: "100%", height: "100%", border: "none" }}
          />
        )}
      </Modal>

      <Modal open={!!modal} title={`上传材料 — ${modal ? stages.find(s => s.stage === modal.stage)?.stage_name : ""}`}
        onCancel={() => setModal(null)} footer={null}>
        {modal && (
          <Space direction="vertical" style={{ width: "100%" }}>
            <div>材料类型：<Select style={{ width: 240 }} value={modal.role}
              onChange={(v) => setModal({ ...modal, role: v })}
              options={FILE_ROLES[modal.stage].map((r) => ({ value: r, label: r }))} /></div>
            <Upload beforeUpload={doUpload} maxCount={1} showUploadList={false}>
              <Button icon={<UploadOutlined />} loading={busy}>选择文件上传（任意类型）</Button>
            </Upload>
          </Space>
        )}
      </Modal>

      <MethodFlowDrawer open={flowOpen} onClose={() => setFlowOpen(false)} config={getFlowConfig("trace_workflow")!} />
    </Space>
  );
}
