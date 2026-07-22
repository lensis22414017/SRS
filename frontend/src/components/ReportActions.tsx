/** Round10: 报告操作共享组件 — 预览 PDF + 下载 PDF/DOCX。
 *  替代 SSUI/Obstacle/Reconstruction 页面中重复的报告生成代码。
 */
import { useState } from "react";
import { Button, Space, Modal, Tooltip, message } from "antd";
import { EyeOutlined, DownloadOutlined, FilePdfOutlined, FileWordOutlined } from "@ant-design/icons";
import { api } from "../api/client";

interface Props {
  siteId: number;
  siteCode?: string;
  reportScope: "ssui" | "diagnosis" | "reconstruction" | "full";
  /** 报告标题前缀（如 "SSUI评价报告"、"诊断报告"） */
  label?: string;
  /** 是否禁用（如无数据时不显示） */
  disabled?: boolean;
}

export default function ReportActions({ siteId, siteCode, reportScope, label, disabled }: Props) {
  const [busy, setBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState("");

  const scopeLabels: Record<string, string> = {
    ssui: "SSUI 可持续利用分析",
    diagnosis: "障碍因子诊断",
    reconstruction: "功能重构分析",
    full: "全流程追溯",
  };
  const scopeLabel = label || scopeLabels[reportScope] || "报告";

  const genAndPreview = async (format: "pdf" | "docx" = "pdf") => {
    setBusy(true);
    try {
      const r = await api.generateReport(siteId, format, reportScope);
      if (!r?.report_id) {
        message.error("报告生成失败：未返回报告 ID");
        return;
      }
      if (format === "pdf") {
        // PDF → 获取 blob 并在 Modal 中预览
        const blob = await api.reportBlob(r.report_id);
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);
        setPreviewTitle(`${scopeLabel}报告预览 — ${siteCode || ""} ${r.version}`);
      } else {
        // DOCX → 直接下载
        const filename = r.file_name || `${scopeLabel}报告_场地${siteId}_${r.version}.docx`;
        await api.downloadReport(r.report_id, filename);
        message.success(`${scopeLabel}报告 ${r.version} 已下载`);
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || `${scopeLabel}报告生成失败`);
    } finally {
      setBusy(false);
    }
  };

  const closePreview = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl(null);
    }
  };

  if (disabled) return null;

  return (
    <>
      <Space>
        <Tooltip title={`预览 ${scopeLabel} PDF 报告`}>
          <Button
            icon={<EyeOutlined />}
            loading={busy}
            onClick={() => genAndPreview("pdf")}
          >
            预览 PDF
          </Button>
        </Tooltip>
        <Tooltip title={`下载 ${scopeLabel} PDF`}>
          <Button
            icon={<FilePdfOutlined />}
            loading={busy}
            onClick={() => {
              setBusy(true);
              api.generateReport(siteId, "pdf", reportScope).then((r: any) => {
                if (r?.report_id) {
                  const fn = r.file_name || `${scopeLabel}报告_场地${siteId}_${r.version}.pdf`;
                  api.downloadReport(r.report_id, fn);
                  message.success(`${scopeLabel} PDF 已下载`);
                }
              }).catch((e: any) => message.error(e?.response?.data?.detail || "导出失败"))
                .finally(() => setBusy(false));
            }}
          >
            下载 PDF
          </Button>
        </Tooltip>
        <Tooltip title={`下载 ${scopeLabel} DOCX（可编辑）`}>
          <Button
            icon={<FileWordOutlined />}
            loading={busy}
            onClick={() => genAndPreview("docx")}
          >
            下载 DOCX
          </Button>
        </Tooltip>
      </Space>

      {/* PDF 预览 Modal */}
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
    </>
  );
}
