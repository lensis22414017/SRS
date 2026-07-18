import { useState } from "react";
import { Card, Upload, Button, Select, App, Tag, Space, Alert, Table, Typography, Radio } from "antd";
import { InboxOutlined, ControlOutlined, ApartmentOutlined } from "@ant-design/icons";
import MethodFlowDrawer from "../components/MethodFlowDrawer";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { getFlowConfig } from "../config/methodFlows";
import ReactECharts from "echarts-for-react";
import { SVG_OPTS } from "../theme/echarts";

const { Text } = Typography;

// v1.0.2(+ GPT 2.2): 完全删除预设模板, 只保留自动识别
const MAPPINGS = [
  { value: "auto", label: "自动识别（按列名/工作表智能匹配污染类型）" },
];

export default function DataUpload() {
  const { message } = App.useApp();
  const nav = useNavigate();
  const [mapping, setMapping] = useState("auto");
  const [files, setFiles] = useState<File[]>([]);
  const [conflict, setConflict] = useState("skip");  // 重复导入策略
  const [loading, setLoading] = useState(false);
  const [batchResult, setBatchResult] = useState<any>(null);
  const [flowOpen, setFlowOpen] = useState(false);

  const submit = async () => {
    if (!files.length) { message.warning("请先选择 Excel/CSV 文件"); return; }
    setLoading(true);
    try {
      let r: any;
      if (files.length > 1) {
        r = await api.importBatch(mapping, files, conflict);
      } else {
        // 单文件走单文件接口(避免重复导入), 包装成与 batch 同构的结果
        const one = await api.importData(mapping, files[0], conflict);
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
    mapping_label: r.mapping_label || r.mapping_id,
    site_id: r.site_id,
    n_points: r.n_points ?? r.validation?.n_points,
    n_measurements: r.n_measurements,
    n_errors: r.validation?.n_errors,
    n_exceed: r.validation?.n_exceed,
    exceed_factors: r.validation?.exceed_factors || [],
    error: r.error,
    action: r.action,
  }));

  // 成功导入的场地(取第一个成功的用于"查看详情")
  const firstOk = resultRows.find((r: any) => r.ok);

  return (
    <>
      <Card title="数据导入"
      extra={
        <Space>
          <Button icon={<ApartmentOutlined />} onClick={() => setFlowOpen(true)}>方法说明</Button>
          <Button icon={<ControlOutlined />} onClick={() => nav("/sites/import/wizard")}>
            自定义字段映射 Wizard
          </Button>
        </Space>
      }>
      <Alert type="info" style={{ marginBottom: 16 }}
        message="支持 .xlsx / .csv，可批量多文件。选择字段映射模板后上传，系统会自动解析→字段映射→校验→写入长表。多文件串行处理，单文件失败不阻断其余。如数据列名与预设模板不同，请使用右上角【自定义字段映射 Wizard】按钮。" />
      <Space direction="vertical" style={{ width: "100%" }} size={16}>
        <Space>
          <span>字段映射模板：</span>
          <Select style={{ width: 360 }} value={mapping} onChange={setMapping} options={MAPPINGS} />
        </Space>
        <Space>
          <span>重复导入策略：</span>
          <Radio.Group value={conflict} onChange={(e) => setConflict(e.target.value)}>
            <Radio value="skip">跳过(默认, 不重复)</Radio>
            <Radio value="overwrite">覆盖</Radio>
            <Radio value="new_version">作为新版本</Radio>
          </Radio.Group>
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
              { title: "操作", dataIndex: "action", align: "center", width: 80,
                render: (a: string) => {
                  const m: Record<string, [string, string]> = {
                    created: ["green", "新增"], skipped: ["default", "跳过"],
                    overwritten: ["blue", "覆盖"], new_version: ["purple", "新版本"],
                  };
                  const [c, t] = m[a] || ["default", a || "—"];
                  return <Tag color={c}>{t}</Tag>;
                } },
              { title: "识别模板", dataIndex: "mapping_label", ellipsis: true,
                render: (v: string) => v ? <Tag color="blue">{v}</Tag> : <Text type="secondary">—</Text> },
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

          {/* Round7 追加: 导入质量概览(错误/超标 Pareto + 超标因子分布), 保留上方结果 Table */}
          {(() => {
            const okRows = resultRows.filter((r: any) => r.ok);
            const totalErr = okRows.reduce((s: number, r: any) => s + (r.n_errors || 0), 0);
            const totalExceed = okRows.reduce((s: number, r: any) => s + (r.n_exceed || 0), 0);
            const factorCount: Record<string, number> = {};
            okRows.forEach((r: any) => (r.exceed_factors || []).forEach((f: string) => { factorCount[f] = (factorCount[f] || 0) + 1; }));
            const factorSorted = Object.entries(factorCount).sort((a, b) => b[1] - a[1]).slice(0, 10);
            if (totalErr === 0 && totalExceed === 0 && factorSorted.length === 0) return null;
            return (
              <Card size="small" title="导入质量概览（错误 Pareto + 超标因子分布 · Round7 追加）" style={{ marginTop: 16 }}>
                <Space size="large" wrap>
                  <span>校验错误总数: <b style={{ color: totalErr > 0 ? "#dc2626" : "#16a34a" }}>{totalErr}</b></span>
                  <span>超标记录总数: <b style={{ color: totalExceed > 0 ? "#f59e0b" : "#16a34a" }}>{totalExceed}</b></span>
                  <span>涉及超标因子: <b>{Object.keys(factorCount).length}</b> 种</span>
                </Space>
                {factorSorted.length > 0 && (
                  <div style={{ marginTop: 12 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>超标因子频次分布（Top10，覆盖场地数）：</Text>
                    <ReactECharts option={{
                      tooltip: { trigger: "axis" },
                      grid: { left: 80, right: 30, top: 16, bottom: 24 },
                      xAxis: { type: "value", name: "覆盖场地数" },
                      yAxis: { type: "category", inverse: true, data: factorSorted.map((f) => f[0]),
                        axisLabel: { fontSize: 11 } },
                      series: [{ type: "bar", barMaxWidth: 18,
                        data: factorSorted.map((f) => ({ value: f[1], itemStyle: { color: "#E64B35", borderRadius: [0, 4, 4, 0] } })),
                        label: { show: true, position: "right", fontSize: 10 } }],
                    }} theme="srs-light" opts={SVG_OPTS} style={{ height: Math.max(160, factorSorted.length * 32) }} />
                  </div>
                )}
                <Text type="secondary" style={{ fontSize: 11, display: "block", marginTop: 8 }}>
                  ⓘ 字段缺失率热图/因子覆盖率需进入场地详情「数据分析(EDA)」Tab 查看（按场地级展示更准确）。
                </Text>
              </Card>
            );
          })()}
        </div>
      )}
    </Card>
      <MethodFlowDrawer open={flowOpen} onClose={() => setFlowOpen(false)} config={getFlowConfig("data_import")!} />
    </>
  );
}
