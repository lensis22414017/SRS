/**
 * 字段映射 Wizard（三步式）
 *
 * Step 1 — 上传文件 → 后端返回列名 + 前3行预览
 * Step 2 — 映射字段
 *   2a. 场地基本信息（手填）
 *   2b. 点位列映射（源列 → 标准点位字段）
 *   2c. 因子列映射（源列 → 因子代码/类别/单位）
 * Step 3 — 确认并导入 → 显示校验结果
 *
 * 满足 AC-03：完成源列→标准字段映射并校验，输出结构化校验报告。
 */
import { useState } from "react";
import {
  Steps, Card, Upload, Button, Form, Input, Select, Table, Tag, Space,
  Alert, message, Divider, Typography, Tooltip, Spin,
} from "antd";
import {
  InboxOutlined, PlusOutlined, DeleteOutlined, QuestionCircleOutlined,
  CheckCircleOutlined, WarningOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

const { Text } = Typography;

// ─── 常量 ───────────────────────────────────────────────────────────────────

const POLLUTION_TYPES = [
  { value: "heavy_metal", label: "重金属污染" },
  { value: "organic", label: "有机污染" },
  { value: "composite", label: "复合污染" },
];

const LAND_USE_TYPES = ["生产用地", "建设用地", "生态用地", "农用地", "工业用地", "其他用地"];

// 标准点位字段定义
const POINT_STD_FIELDS: { key: string; label: string; required: boolean; hint: string }[] = [
  { key: "point_code", label: "采样点编号", required: true, hint: "每行唯一标识，必填" },
  { key: "longitude", label: "经度", required: false, hint: "WGS-84，如 103.8" },
  { key: "latitude", label: "纬度", required: false, hint: "WGS-84，如 23.4" },
  { key: "region", label: "区域/分区", required: false, hint: "如 A区、北部" },
  { key: "depth_top_cm", label: "深度上限(cm)", required: false, hint: "数字，如 0" },
  { key: "depth_bottom_cm", label: "深度下限(cm)", required: false, hint: "数字，如 20" },
  { key: "soil_type", label: "土壤类型", required: false, hint: "如 壤土、粘土" },
  { key: "remark", label: "备注", required: false, hint: "自由文本" },
];

// 常用因子快速选择（来自知识库，覆盖三类污染场地主要指标）
const COMMON_FACTORS: { value: string; label: string; category: string; factor_type: string; unit: string }[] = [
  { value: "pH", label: "pH", category: "化学性质", factor_type: "chemical", unit: "" },
  { value: "有机质", label: "有机质", category: "肥力指标", factor_type: "fertility", unit: "g/kg" },
  { value: "全氮", label: "全氮", category: "肥力指标", factor_type: "fertility", unit: "g/kg" },
  { value: "全磷", label: "全磷", category: "肥力指标", factor_type: "fertility", unit: "g/kg" },
  { value: "全钾", label: "全钾", category: "肥力指标", factor_type: "fertility", unit: "g/kg" },
  { value: "水解性氮", label: "水解性氮", category: "肥力指标", factor_type: "fertility", unit: "mg/kg" },
  { value: "有效磷", label: "有效磷", category: "肥力指标", factor_type: "fertility", unit: "mg/kg" },
  { value: "速效钾", label: "速效钾", category: "肥力指标", factor_type: "fertility", unit: "mg/kg" },
  { value: "铜", label: "铜 (Cu)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "铅", label: "铅 (Pb)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "锌", label: "锌 (Zn)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "镉", label: "镉 (Cd)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "汞", label: "汞 (Hg)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "砷", label: "砷 (As)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "铬", label: "铬 (Cr)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "镍", label: "镍 (Ni)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "苯", label: "苯", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "甲苯", label: "甲苯", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "多环芳烃", label: "多环芳烃 (PAHs)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "石油烃", label: "石油烃 (TPH)", category: "环境指标", factor_type: "pollutant", unit: "mg/kg" },
  { value: "土壤容重", label: "土壤容重", category: "物理性质", factor_type: "physical", unit: "g/cm³" },
  { value: "土壤质地", label: "土壤质地", category: "物理性质", factor_type: "physical", unit: "" },
  { value: "阳离子交换量", label: "阳离子交换量 (CEC)", category: "化学性质", factor_type: "chemical", unit: "cmol/kg" },
];

const FACTOR_CATEGORIES = ["化学性质", "物理性质", "肥力指标", "环境指标", "生物指标"];
const FACTOR_TYPES = [
  { value: "pollutant", label: "污染物" },
  { value: "chemical", label: "化学性质" },
  { value: "physical", label: "物理性质" },
  { value: "fertility", label: "肥力指标" },
  { value: "biological", label: "生物指标" },
];

// ─── 类型 ────────────────────────────────────────────────────────────────────

interface FactorRow {
  key: string;
  source_col: string;
  factor_code: string;
  factor_name: string;
  level1_category: string;
  factor_type: string;
  unit: string;
}

// ─── 主组件 ──────────────────────────────────────────────────────────────────

export default function FieldMappingPage() {
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);

  // Step 1
  const [file, setFile] = useState<File | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [preview, setPreview] = useState<Record<string, string>[]>([]);
  const [nRows, setNRows] = useState(0);

  // Step 2a — 场地信息
  const [siteForm] = Form.useForm();

  // Step 2b — 点位列映射 { point_code: "采样点编号", longitude: "经度", ... }
  const [pointMap, setPointMap] = useState<Record<string, string>>({ point_code: "" });

  // Step 2c — 因子行列表
  const [factorRows, setFactorRows] = useState<FactorRow[]>([]);

  // Step 3 — 导入结果
  const [result, setResult] = useState<any>(null);

  // ── 工具 ────────────────────────────────────────────────────────────────

  const colOptions = columns.map((c) => ({ value: c, label: c }));

  const addFactorRow = () => {
    const key = `row_${Date.now()}`;
    setFactorRows((prev) => [...prev, {
      key, source_col: "", factor_code: "", factor_name: "",
      level1_category: "环境指标", factor_type: "pollutant", unit: "mg/kg",
    }]);
  };

  const updateFactor = (key: string, field: keyof FactorRow, val: string) => {
    setFactorRows((prev) => prev.map((r) => {
      if (r.key !== key) return r;
      const updated = { ...r, [field]: val };
      // 选择预设因子时自动填充其他字段
      if (field === "factor_code") {
        const preset = COMMON_FACTORS.find((f) => f.value === val);
        if (preset) {
          updated.factor_name = preset.label.replace(/\s*\(.*\)$/, "");
          updated.level1_category = preset.category;
          updated.factor_type = preset.factor_type;
          updated.unit = preset.unit;
        } else {
          updated.factor_name = val;
        }
      }
      return updated;
    }));
  };

  // ── Step 1: 上传并解析列 ───────────────────────────────────────────────

  const handleUpload = async (f: File) => {
    setFile(f);
    setLoading(true);
    try {
      const res = await api.importColumns(f);
      setColumns(res.columns);
      setPreview(res.preview);
      setNRows(res.n_rows);
      // 自动预填: 若列名中有明显匹配，自动填入点位映射
      const autoMap: Record<string, string> = { point_code: "" };
      const tryMatch = (field: string, keywords: string[]) => {
        const hit = res.columns.find((c) =>
          keywords.some((k) => c.toLowerCase().includes(k.toLowerCase()))
        );
        if (hit) autoMap[field] = hit;
      };
      tryMatch("point_code", ["点编号", "点号", "采样点", "sample", "point"]);
      tryMatch("longitude", ["经度", "lon", "lng", "x坐标"]);
      tryMatch("latitude", ["纬度", "lat", "y坐标"]);
      tryMatch("region", ["区域", "分区", "region"]);
      tryMatch("depth_top_cm", ["深度_上", "上限"]);
      tryMatch("depth_bottom_cm", ["深度_下", "下限"]);
      tryMatch("soil_type", ["土壤类型", "soil"]);
      setPointMap(autoMap);
      message.success(`解析成功，共 ${res.columns.length} 列，${res.n_rows} 行`);
      setStep(1);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "文件解析失败");
    } finally {
      setLoading(false);
    }
    return false;
  };

  // ── Step 2 → 3: 验证映射完整性 ───────────────────────────────────────

  const validateMapping = (): boolean => {
    if (!pointMap.point_code) {
      message.error("必须映射【采样点编号】列");
      return false;
    }
    const badFactors = factorRows.filter((r) => !r.source_col || !r.factor_code);
    if (badFactors.length) {
      message.error("存在未完整填写的因子行（源列和因子代码均必填）");
      return false;
    }
    return true;
  };

  // ── Step 3: 构建 mapping JSON 并导入 ─────────────────────────────────

  const doImport = async () => {
    const siteVals = await siteForm.validateFields().catch(() => null);
    if (!siteVals) return;
    if (!validateMapping()) return;
    if (!file) return;

    // 构建与后端 mapping JSON 格式一致的对象
    const mapping = {
      mapping_id: "wizard_custom",
      description: `Wizard 自定义映射 — ${siteVals.name}`,
      sheet: null,
      site: {
        site_code: siteVals.site_code || `WIZARD-${Date.now()}`,
        name: siteVals.name,
        pollution_type: siteVals.pollution_type,
        land_use_type: siteVals.land_use_type || "其他用地",
        province: siteVals.province || "",
        city: siteVals.city || "",
        sampled_at: siteVals.sampled_at || "",
      },
      point_columns: Object.fromEntries(
        Object.entries(pointMap).filter(([, v]) => v)
      ),
      factor_columns: factorRows.map((r) => ({
        column: r.source_col,
        factor_code: r.factor_code,
        factor_name: r.factor_name || r.factor_code,
        level1_category: r.level1_category || "环境指标",
        factor_type: r.factor_type || "pollutant",
        unit: r.unit || null,
        in_kb: true,
      })),
      required_point_fields: ["point_code"],
    };

    setLoading(true);
    try {
      const res = await api.importWizard(mapping, file);
      setResult(res);
      setStep(2);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "导入失败");
    } finally {
      setLoading(false);
    }
  };

  // ─── 渲染 ─────────────────────────────────────────────────────────────────

  return (
    <Card title="字段映射导入 Wizard"
      extra={<Button onClick={() => nav("/sites/import")}>返回普通导入</Button>}>
      <Steps current={step} style={{ marginBottom: 24 }} items={[
        { title: "上传文件" },
        { title: "映射字段" },
        { title: "导入结果" },
      ]} />

      {/* ── Step 0: 上传 ─────────────────────────────────────── */}
      {step === 0 && (
        <Spin spinning={loading}>
          <Upload.Dragger beforeUpload={handleUpload} accept=".xlsx,.xls,.csv"
            maxCount={1} showUploadList={false}>
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p>点击或拖拽 Excel/CSV 文件到此处</p>
            <p style={{ color: "#999", fontSize: 12 }}>
              上传后系统自动读取列名，下一步手动配置映射关系
            </p>
          </Upload.Dragger>
        </Spin>
      )}

      {/* ── Step 1: 映射字段 ─────────────────────────────────── */}
      {step === 1 && (
        <Space direction="vertical" style={{ width: "100%" }} size={20}>
          {/* 文件列预览 */}
          <Alert type="info" showIcon
            message={`已解析文件列：${columns.length} 列，${nRows} 行数据`}
            description={
              <div style={{ marginTop: 6 }}>
                {columns.map((c) => <Tag key={c} style={{ marginBottom: 4 }}>{c}</Tag>)}
              </div>
            } />

          <Divider orientation="left">① 场地基本信息</Divider>
          <Form form={siteForm} layout="inline" style={{ gap: 8 }}>
            <Form.Item name="name" label="场地名称" rules={[{ required: true }]}>
              <Input style={{ width: 200 }} placeholder="如 云南个旧污染场地" />
            </Form.Item>
            <Form.Item name="site_code" label="场地编号">
              <Input style={{ width: 160 }} placeholder="如 GJ-2025-001" />
            </Form.Item>
            <Form.Item name="pollution_type" label="污染类型" rules={[{ required: true }]}>
              <Select style={{ width: 140 }} options={POLLUTION_TYPES} />
            </Form.Item>
            <Form.Item name="land_use_type" label="修复后用途"
              tooltip="决定诊断路由: 生产轨(GB15618农用地+GB36600一类,严,人体健康) / 生态轨(CJ/T340绿化+GB36600二类,宽,植被修复)">
              <Select style={{ width: 200 }} placeholder="选择修复后用途"
                options={[
                  { value: "生产", label: "生产(农用地/一类·严)" },
                  { value: "生态", label: "生态(绿化/二类·宽)" },
                ]} />
            </Form.Item>
            <Form.Item name="province" label="省份">
              <Input style={{ width: 100 }} placeholder="如 云南省" />
            </Form.Item>
            <Form.Item name="city" label="城市">
              <Input style={{ width: 100 }} placeholder="如 个旧市" />
            </Form.Item>
            <Form.Item name="sampled_at" label="采样日期">
              <Input style={{ width: 130 }} placeholder="YYYY-MM-DD" />
            </Form.Item>
          </Form>

          <Divider orientation="left">② 点位字段映射（源列 → 标准字段）</Divider>
          <Table
            size="small"
            pagination={false}
            dataSource={POINT_STD_FIELDS}
            rowKey="key"
            columns={[
              {
                title: "标准字段",
                dataIndex: "label",
                width: 160,
                render: (label: string, r) => (
                  <Space>
                    {r.required && <Tag color="red" style={{ fontSize: 10 }}>必填</Tag>}
                    {label}
                    <Tooltip title={r.hint}>
                      <QuestionCircleOutlined style={{ color: "#999" }} />
                    </Tooltip>
                  </Space>
                ),
              },
              {
                title: "对应源列（文件中的列名）",
                render: (_: any, r) => (
                  <Select
                    allowClear
                    showSearch
                    style={{ width: 280 }}
                    placeholder="选择文件中对应的列"
                    value={pointMap[r.key] || undefined}
                    onChange={(v) => setPointMap((prev) => ({ ...prev, [r.key]: v || "" }))}
                    options={colOptions}
                  />
                ),
              },
              {
                title: "预览值（第1行）",
                render: (_: any, r) => {
                  const col = pointMap[r.key];
                  if (!col || !preview[0]) return <Text type="secondary">—</Text>;
                  return <Text code>{preview[0][col] ?? "—"}</Text>;
                },
              },
            ]}
          />

          <Divider orientation="left">③ 因子列映射（检测指标 / 污染物）</Divider>
          <Alert type="warning" showIcon style={{ marginBottom: 12 }}
            message={"每行对应一个检测因子。【因子代码】须与知识库一致（从下拉中选取）；未在知识库中的因子可自定义代码，但不会进行阈值比对。"} />

          <Table
            size="small"
            pagination={false}
            dataSource={factorRows}
            rowKey="key"
            locale={{ emptyText: <Text type="secondary">暂未添加因子，点击"添加因子行"</Text> }}
            columns={[
              {
                title: "源列（文件中的检测列）",
                dataIndex: "source_col",
                width: 200,
                render: (_: any, r) => (
                  <Select showSearch style={{ width: 190 }} placeholder="选择源列"
                    value={r.source_col || undefined}
                    onChange={(v) => updateFactor(r.key, "source_col", v)}
                    options={colOptions} />
                ),
              },
              {
                title: "因子代码（标准）",
                dataIndex: "factor_code",
                width: 200,
                render: (_: any, r) => (
                  <Select showSearch style={{ width: 190 }}
                    placeholder="选择或输入因子代码"
                    value={r.factor_code || undefined}
                    onChange={(v) => updateFactor(r.key, "factor_code", v)}
                    options={COMMON_FACTORS.map((f) => ({
                      value: f.value,
                      label: `${f.label} (${f.category})`,
                    }))}
                    filterOption={(input, opt) =>
                      String(opt?.label ?? "").toLowerCase().includes(input.toLowerCase())
                    }
                  />
                ),
              },
              {
                title: "类别",
                dataIndex: "level1_category",
                width: 130,
                render: (_: any, r) => (
                  <Select style={{ width: 120 }} value={r.level1_category}
                    onChange={(v) => updateFactor(r.key, "level1_category", v)}
                    options={FACTOR_CATEGORIES.map((c) => ({ value: c, label: c }))} />
                ),
              },
              {
                title: "类型",
                dataIndex: "factor_type",
                width: 120,
                render: (_: any, r) => (
                  <Select style={{ width: 110 }} value={r.factor_type}
                    onChange={(v) => updateFactor(r.key, "factor_type", v)}
                    options={FACTOR_TYPES} />
                ),
              },
              {
                title: "单位",
                dataIndex: "unit",
                width: 110,
                render: (_: any, r) => (
                  <Input style={{ width: 100 }} value={r.unit}
                    placeholder="mg/kg"
                    onChange={(e) => updateFactor(r.key, "unit", e.target.value)} />
                ),
              },
              {
                title: "预览",
                render: (_: any, r) => {
                  if (!r.source_col || !preview[0]) return <Text type="secondary">—</Text>;
                  return <Text code>{preview[0][r.source_col] ?? "—"}</Text>;
                },
              },
              {
                title: "",
                width: 48,
                render: (_: any, r) => (
                  <Button type="text" danger size="small" icon={<DeleteOutlined />}
                    onClick={() => setFactorRows((prev) => prev.filter((x) => x.key !== r.key))} />
                ),
              },
            ]}
          />
          <Button icon={<PlusOutlined />} onClick={addFactorRow} style={{ marginTop: 4 }}>
            添加因子行
          </Button>

          <Divider />
          <Space>
            <Button onClick={() => setStep(0)}>上一步</Button>
            <Button type="primary" loading={loading} onClick={doImport}>
              确认映射并导入
            </Button>
          </Space>
        </Space>
      )}

      {/* ── Step 2: 导入结果 ─────────────────────────────────── */}
      {step === 2 && result && (
        <Space direction="vertical" style={{ width: "100%" }} size={16}>
          <Alert
            type={result.validation?.n_errors === 0 ? "success" : "warning"}
            icon={result.validation?.n_errors === 0
              ? <CheckCircleOutlined /> : <WarningOutlined />}
            showIcon
            message={
              result.validation?.n_errors === 0
                ? `导入成功！场地 ID: ${result.site_id}`
                : `导入完成，但存在 ${result.validation?.n_errors} 处校验错误`
            }
            description={
              <Space direction="vertical" size={4} style={{ marginTop: 8 }}>
                <Text>采样点：{result.validation?.n_points ?? result.n_points} 个</Text>
                <Text>检测记录：{result.validation?.n_measurements ?? result.n_measurements} 条</Text>
                {result.validation?.n_exceed > 0 && (
                  <Text type="danger">超标因子 ({result.validation.n_exceed})：
                    {result.validation.exceed_factors?.map((f: string) =>
                      <Tag color="red" key={f}>{f}</Tag>
                    )}
                  </Text>
                )}
                {result.validation?.n_errors > 0 && (
                  <Text type="warning">校验错误数：{result.validation.n_errors}（含缺失值/格式错误）</Text>
                )}
              </Space>
            }
          />

          <Space>
            <Button type="primary" onClick={() => nav(`/sites/${result.site_id}`)}>
              查看场地详情
            </Button>
            <Button onClick={() => nav("/sites")}>返回场地列表</Button>
            <Button onClick={() => { setStep(0); setFile(null); setColumns([]); setResult(null); setFactorRows([]); }}>
              继续导入新文件
            </Button>
          </Space>
        </Space>
      )}
    </Card>
  );
}
