/** Round10: 文件管理中心 — 独立跨场地文件库，支持分类筛选、上传、预览、下载。 */
import { useEffect, useState } from "react";
import {
  Card, Table, Tag, Button, Space, Select, Input, Modal, Upload, Popconfirm,
  Tooltip, Typography, message, App, DatePicker,
} from "antd";
import {
  UploadOutlined, DownloadOutlined, EyeOutlined, EditOutlined,
  DeleteOutlined, FolderOutlined, SearchOutlined, ReloadOutlined,
  FilePdfOutlined, FileImageOutlined, FileWordOutlined, FileExcelOutlined, FileOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import { seqCol } from "../utils/table";

function formatBytes(bytes: number | undefined | null): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** 根据 content_type 返回文件图标 */
function fileIcon(ct: string | null) {
  if (!ct) return <FileOutlined />;
  if (ct.includes("pdf")) return <FilePdfOutlined style={{ color: "#dc2626" }} />;
  if (ct.includes("image")) return <FileImageOutlined style={{ color: "#16a34a" }} />;
  if (ct.includes("word") || ct.includes("document")) return <FileWordOutlined style={{ color: "#2563eb" }} />;
  if (ct.includes("excel") || ct.includes("spreadsheet")) return <FileExcelOutlined style={{ color: "#059669" }} />;
  return <FileOutlined />;
}

/** 判断文件是否可在浏览器内预览 */
function canPreview(ct: string | null): boolean {
  if (!ct) return false;
  return ct.includes("pdf") || ct.includes("image");
}

export default function FileManagement() {
  const { modal } = App.useApp();
  const [files, setFiles] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [categories, setCategories] = useState<{ value: string; label: string }[]>([]);
  const [sites, setSites] = useState<any[]>([]);

  // 筛选
  const [filterSite, setFilterSite] = useState<number | undefined>();
  const [filterCategory, setFilterCategory] = useState<string | undefined>();
  const [searchText, setSearchText] = useState("");

  // 上传弹窗
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadSite, setUploadSite] = useState<number | undefined>();
  const [uploadCategory, setUploadCategory] = useState("other");
  const [uploadDesc, setUploadDesc] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);

  // 编辑弹窗
  const [editOpen, setEditOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [editCategory, setEditCategory] = useState("");
  const [editDesc, setEditDesc] = useState("");

  // 预览弹窗
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTitle, setPreviewTitle] = useState("");
  const [previewUrl, setPreviewUrl] = useState("");

  const loadFiles = async () => {
    setLoading(true);
    try {
      const res = await api.listFiles({
        site_id: filterSite,
        category: filterCategory,
        search: searchText || undefined,
        page,
        page_size: 20,
      });
      setFiles(res.items);
      setTotal(res.total);
    } catch (e: any) {
      message.error("加载文件列表失败");
    } finally {
      setLoading(false);
    }
  };

  const loadMeta = async () => {
    try {
      const [catRes, siteRes] = await Promise.all([
        api.fileCategories(),
        api.sites(),
      ]);
      setCategories(catRes.categories || []);
      setSites((siteRes as any)?.items || siteRes || []);
    } catch { /* 非关键 */ }
  };

  useEffect(() => { loadMeta(); }, []);
  useEffect(() => { loadFiles(); }, [page, filterSite, filterCategory]);

  const doUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    try {
      await api.uploadFile(uploadFile, uploadCategory, uploadDesc || undefined, uploadSite);
      message.success("文件上传成功");
      setUploadOpen(false);
      setUploadFile(null);
      setUploadDesc("");
      setUploadCategory("other");
      loadFiles();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const doEdit = async () => {
    if (!editId) return;
    try {
      await api.updateFileMeta(editId, editCategory || undefined, editDesc || undefined);
      message.success("文件信息已更新");
      setEditOpen(false);
      loadFiles();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "更新失败");
    }
  };

  const doDelete = async (fileId: number) => {
    try {
      await api.deleteFile(fileId);
      message.success("文件已删除");
      loadFiles();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "删除失败");
    }
  };

  const openPreview = (file: any) => {
    if (!canPreview(file.content_type)) {
      message.info("此文件类型不支持在线预览，请下载后查看");
      return;
    }
    setPreviewTitle(file.original_name);
    setPreviewUrl(api.previewFileUrl(file.id));
    setPreviewOpen(true);
  };

  const doDownload = (file: any) => {
    const a = document.createElement("a");
    a.href = api.downloadFileUrl(file.id);
    a.download = file.original_name;
    a.click();
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      {/* ── 顶部操作栏 ── */}
      <Card size="small">
        <Space wrap>
          <Select
            allowClear
            placeholder="选择场地"
            style={{ width: 180 }}
            value={filterSite}
            onChange={(v) => { setFilterSite(v); setPage(1); }}
            options={sites.map((s: any) => ({ value: s.id, label: s.name || s.site_code }))}
          />
          <Select
            allowClear
            placeholder="文件类型"
            style={{ width: 150 }}
            value={filterCategory}
            onChange={(v) => { setFilterCategory(v); setPage(1); }}
            options={categories}
          />
          <Input
            placeholder="搜索文件名..."
            prefix={<SearchOutlined />}
            style={{ width: 200 }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onPressEnter={() => { setPage(1); loadFiles(); }}
          />
          <Button icon={<ReloadOutlined />} onClick={loadFiles}>刷新</Button>
          <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>
            上传文件
          </Button>
        </Space>
      </Card>

      {/* ── 文件表格 ── */}
      <Card
        title={<Space><FolderOutlined />文件库<Tag>{total} 个文件</Tag></Space>}
      >
        <Table
          rowKey="id"
          size="middle"
          bordered
          loading={loading}
          dataSource={files}
          pagination={{ current: page, pageSize: 20, total, onChange: setPage, showSizeChanger: false }}
          columns={[
            seqCol(50, page, 20),
            {
              title: "文件名", dataIndex: "original_name", ellipsis: true,
              render: (v: string, r: any) => (
                <a onClick={() => openPreview(r)} style={{ cursor: "pointer" }}>
                  <Space>{fileIcon(r.content_type)}{v}</Space>
                </a>
              ),
            },
            {
              title: "类型", dataIndex: "category_label", width: 120, align: "center",
              render: (v: string) => <Tag color="blue">{v || "—"}</Tag>,
            },
            {
              title: "所属场地", dataIndex: "site_name", width: 130, ellipsis: true,
              render: (v: string) => v || "—",
            },
            {
              title: "大小", width: 80, align: "right",
              render: (_: any, r: any) => (
                <Tooltip title={`${r.size_bytes ?? 0} 字节`}>
                  <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                    {formatBytes(r.size_bytes)}
                  </Typography.Text>
                </Tooltip>
              ),
            },
            {
              title: "上传单位", dataIndex: "organization_name", width: 130, ellipsis: true,
              render: (v: string) => v || "—",
            },
            {
              title: "上传者", dataIndex: "uploaded_by_name", width: 90,
              render: (v: string) => v || "—",
            },
            {
              title: "上传时间", dataIndex: "created_at", width: 150,
              render: (v: string) => v ? new Date(v).toLocaleString("zh-CN") : "—",
            },
            {
              title: "操作", width: 160, align: "center",
              render: (_: any, r: any) => (
                <Space size="small">
                  {canPreview(r.content_type) && (
                    <Tooltip title="预览">
                      <Button size="small" icon={<EyeOutlined />} onClick={() => openPreview(r)} />
                    </Tooltip>
                  )}
                  <Tooltip title="下载">
                    <Button size="small" icon={<DownloadOutlined />} onClick={() => doDownload(r)} />
                  </Tooltip>
                  <Tooltip title="编辑">
                    <Button size="small" icon={<EditOutlined />} onClick={() => {
                      setEditId(r.id);
                      setEditCategory(r.category || "");
                      setEditDesc(r.description || "");
                      setEditOpen(true);
                    }} />
                  </Tooltip>
                  <Popconfirm
                    title="确认删除该文件？"
                    onConfirm={() => doDelete(r.id)}
                    okText="删除" cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Tooltip title="删除">
                      <Button size="small" danger icon={<DeleteOutlined />} />
                    </Tooltip>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      {/* ── 上传弹窗 ── */}
      <Modal
        title="上传文件"
        open={uploadOpen}
        onCancel={() => { setUploadOpen(false); setUploadFile(null); }}
        onOk={doUpload}
        confirmLoading={uploading}
        okText="确认上传"
      >
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <div>
            <Typography.Text strong>关联场地（可选）</Typography.Text>
            <Select
              allowClear
              placeholder="选择场地"
              style={{ width: "100%", marginTop: 4 }}
              value={uploadSite}
              onChange={setUploadSite}
              options={sites.map((s: any) => ({ value: s.id, label: s.name || s.site_code }))}
            />
          </div>
          <div>
            <Typography.Text strong>文件类型</Typography.Text>
            <Select
              style={{ width: "100%", marginTop: 4 }}
              value={uploadCategory}
              onChange={setUploadCategory}
              options={categories}
            />
          </div>
          <div>
            <Typography.Text strong>描述（可选）</Typography.Text>
            <Input.TextArea
              rows={2}
              style={{ marginTop: 4 }}
              value={uploadDesc}
              onChange={(e) => setUploadDesc(e.target.value)}
              placeholder="简要描述文件内容"
            />
          </div>
          <Upload.Dragger
            maxCount={1}
            beforeUpload={(file) => { setUploadFile(file); return false; }}
            onRemove={() => setUploadFile(null)}
            fileList={uploadFile ? [{ uid: "-1", name: uploadFile.name, status: "done" } as any] : []}
          >
            <Space direction="vertical">
              <UploadOutlined style={{ fontSize: 24, color: "#0f3d6e" }} />
              <span>点击或拖拽文件到此区域上传</span>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                支持 PDF、Word、Excel、图片、CSV、ZIP 等格式，最大 50MB
              </Typography.Text>
            </Space>
          </Upload.Dragger>
        </Space>
      </Modal>

      {/* ── 编辑弹窗 ── */}
      <Modal
        title="编辑文件信息"
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={doEdit}
        okText="保存"
      >
        <Space direction="vertical" style={{ width: "100%" }} size={12}>
          <div>
            <Typography.Text strong>文件类型</Typography.Text>
            <Select
              style={{ width: "100%", marginTop: 4 }}
              value={editCategory}
              onChange={setEditCategory}
              options={categories}
            />
          </div>
          <div>
            <Typography.Text strong>描述</Typography.Text>
            <Input.TextArea
              rows={3}
              value={editDesc}
              onChange={(e) => setEditDesc(e.target.value)}
            />
          </div>
        </Space>
      </Modal>

      {/* ── 预览弹窗 ── */}
      <Modal
        title={previewTitle}
        open={previewOpen}
        onCancel={() => { setPreviewOpen(false); setPreviewUrl(""); }}
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
    </Space>
  );
}
