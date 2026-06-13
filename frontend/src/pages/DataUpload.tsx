import { useState } from "react";
import { Card, Upload, Button, Select, message, Descriptions, Tag, Space, Alert, Result } from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

const MAPPINGS = [
  { value: "yunnan_gejiu", label: "云南个旧重金属污染场地（标准模板）" },
];

export default function DataUpload() {
  const nav = useNavigate();
  const [mapping, setMapping] = useState("yunnan_gejiu");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);

  const submit = async () => {
    if (!file) { message.warning("请先选择 Excel/CSV 文件"); return; }
    setLoading(true);
    try {
      const r = await api.importData(mapping, file);
      setResult(r);
      message.success("导入完成");
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "导入失败");
    } finally { setLoading(false); }
  };

  return (
    <Card title="数据导入">
      <Alert type="info" style={{ marginBottom: 16 }}
        message="支持 .xlsx / .csv。选择对应字段映射模板后上传，系统会自动解析→字段映射→校验→写入长表。" />
      <Space direction="vertical" style={{ width: "100%" }} size={16}>
        <Space>
          <span>字段映射模板：</span>
          <Select style={{ width: 360 }} value={mapping} onChange={setMapping} options={MAPPINGS} />
        </Space>
        <Upload.Dragger maxCount={1} beforeUpload={(f) => { setFile(f); return false; }}
          onRemove={() => setFile(null)}
          accept=".xlsx,.xls,.csv">
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p>点击或拖拽文件到此处上传</p>
          <p style={{ color: "#999" }}>单个文件，支持 Excel / CSV</p>
        </Upload.Dragger>
        <Button type="primary" loading={loading} onClick={submit} disabled={!file}>开始导入并校验</Button>
      </Space>

      {result && (
        <Result style={{ marginTop: 16 }}
          status={result.validation?.passed ? "success" : "warning"}
          title={`导入完成：场地 #${result.site_id}`}
          subTitle={
            <Descriptions column={2} size="small" style={{ textAlign: "left", maxWidth: 600, margin: "0 auto" }}>
              <Descriptions.Item label="采样点">{result.n_points}</Descriptions.Item>
              <Descriptions.Item label="检测记录">{result.n_measurements}</Descriptions.Item>
              <Descriptions.Item label="校验错误">{result.validation?.n_errors}</Descriptions.Item>
              <Descriptions.Item label="超标提示">{result.validation?.n_exceed}</Descriptions.Item>
              <Descriptions.Item label="超标因子" span={2}>
                {(result.validation?.exceed_factors || []).map((f: string) => <Tag color="red" key={f}>{f}</Tag>)}
              </Descriptions.Item>
            </Descriptions>
          }
          extra={[
            <Button type="primary" key="d" onClick={() => nav(`/sites/${result.site_id}`)}>查看场地详情</Button>,
            <Button key="l" onClick={() => nav("/sites")}>返回场地列表</Button>,
          ]} />
      )}
    </Card>
  );
}
