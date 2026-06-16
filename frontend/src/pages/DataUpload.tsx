import { useState } from "react";
import { Card, Upload, Button, Select, message, Tag, Space, Alert, Table, Typography } from "antd";
import { InboxOutlined, ControlOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

const { Text } = Typography;

const MAPPINGS = [
  { value: "yunnan_gejiu", label: "云南个旧重金属污染场地（标准模板）" },
  { value: "nanjing_qixia", label: "南京栖霞有机污染场地（有机污染模板）" },
  { value: "xiangcun_fuhe", label: "乡村建设用地复合污染场地（复合污染模板）" },
];

export default function DataUpload() {
  const nav = useNavigate();
  const [mapping, setMapping] = useState("yunnan_gejiu");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [batchResult, setBatchResult] = useState<any>(null);

  const submit = async () => {
    if (!files.length) { message.warning("请先选择 Excel/CSV 文件"); return; }
    setLoading(true);
    try {
      let r: any;
      if (files.length > 1) {
        r = await api.importBatch(mapping, files);
      } else {
        // 单文件走单文件接口(避免重复导入), 包装成与 batch 同构的结果
        const one = await api.importData(mapping, files[0]);
        r = { total: 1, succeeded: 1, failed: 0,
          results: [{ ...one, ok: true, original_filename: files[0].name }] };
      }
      setBatchResult(r);
      if (r.failed === 0) message.success(`导入完成：${r.succeeded}/${r.total} 成功`);
      else if (r.succeeded > 0) message.warning(`部分成功：${r.succeeded} 成功, ${r.failed} 失败`);
      else message.error("全部导入失败，请查看详情");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "导入失败");
    } finally { setLoading(false); }
  };

  // 批量结果表格
  const resultRows = (batchResult?.results || []).map((r: any, i: number) => ({
    key: i,
    filename: r.original_filename || "—",
    ok: r.ok,
    site_id: r.site_id,
    n_points: r.n_points ?? r.validation?.n_points,
    n_measurements: r.n_measurements,
    n_errors: r.validation?.n_errors,
    n_exceed: r.validation?.n_exceed,
    exceed_factors: r.validation?.exceed_factors || [],
    error: r.error,
  }));

  // 成功导入的场地(取第一个成功的用于"查看详情")
  const firstOk = resultRows.find((r: any) => r.ok);

  return (
    <Card title="数据导入"
      extra={
        <Button icon={<ControlOutlined />} onClick={() => nav("/sites/import/wizard")}>
          自定义字段映射 Wizard
        </Button>
      }>
      <Alert type="info" style={{ marginBottom: 16 }}
        message="支持 .xlsx / .csv，可批量多文件。选择字段映射模板后上传，系统会自动解析→字段映射→校验→写入长表。多文件串行处理，单文件失败不阻断其余。如数据列名与预设模板不同，请使用右上角【自定义字段映射 Wizard】按钮。" />
      <Space direction="vertical" style={{ width: "100%" }} size={16}>
        <Space>
          <span>字段映射模板：</span>
          <Select style={{ width: 360 }} value={mapping} onChange={setMapping} options={MAPPINGS} />
        </Space>
        <Upload.Dragger multiple
          beforeUpload={(f) => { setFiles((prev) => [...prev, f]); return false; }}
          onRemove={(f) => setFiles((prev) => prev.filter((x) => !(x.name === f.name && x.size === f.size)))}
          accept=".xlsx,.xls,.csv"
          fileList={files.map((f, i) => ({ uid: `${i}`, name: f.name, status: "done" } as any))}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p>点击或拖拽文件到此处上传（支持多选）</p>
          <p style={{ color: "#999" }}>{files.length ? `已选 ${files.length} 个文件` : "支持批量 Excel / CSV"}</p>
        </Upload.Dragger>
        <Button type="primary" loading={loading} onClick={submit} disabled={!files.length}>
          {files.length > 1 ? `批量导入 ${files.length} 个文件并校验` : "开始导入并校验"}
        </Button>
      </Space>

      {batchResult && (
        <div style={{ marginTop: 16 }}>
          <Alert
            type={batchResult.failed === 0 ? "success" : batchResult.succeeded > 0 ? "warning" : "error"}
            message={`批量导入结果：成功 ${batchResult.succeeded} / 失败 ${batchResult.failed} / 共 ${batchResult.total}`}
            style={{ marginBottom: 12 }}
          />
          <Table size="small" pagination={false} dataSource={resultRows}
            columns={[
              { title: "文件", dataIndex: "filename", ellipsis: true },
              { title: "状态", dataIndex: "ok", align: "center", width: 80,
                render: (ok: boolean) => ok ? <Tag color="green">成功</Tag> : <Tag color="red">失败</Tag> },
              { title: "场地", dataIndex: "site_id", width: 70,
                render: (id: number) => id ? <a onClick={() => nav(`/sites/${id}`)}>#{id}</a> : "—" },
              { title: "采样点", dataIndex: "n_points", width: 70, render: (v: any) => v ?? "—" },
              { title: "检测记录", dataIndex: "n_measurements", width: 80, render: (v: any) => v ?? "—" },
              { title: "校验错误", dataIndex: "n_errors", width: 70, render: (v: any) => v ?? "—" },
              { title: "超标", dataIndex: "n_exceed", width: 60, render: (v: any) => v ?? "—" },
              { title: "超标因子", dataIndex: "exceed_factors", render: (fs: string[]) =>
                fs?.length ? fs.map((f) => <Tag color="red" key={f}>{f}</Tag>) : <Text type="secondary">—</Text> },
              { title: "错误信息", dataIndex: "error", ellipsis: true,
                render: (e: string) => e ? <Text type="danger">{e}</Text> : <Text type="secondary">—</Text> },
            ]} />
          {firstOk && (
            <Space style={{ marginTop: 12 }}>
              <Button type="primary" onClick={() => nav(`/sites/${firstOk.site_id}`)}>查看首个成功场地详情</Button>
              <Button onClick={() => nav("/sites")}>返回场地列表</Button>
            </Space>
          )}
        </div>
      )}
    </Card>
  );
}
