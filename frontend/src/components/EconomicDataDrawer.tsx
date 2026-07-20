import { useEffect, useState } from "react";
import {
  Drawer, Table, Button, Form, InputNumber, Input, Select, Space,
  Popconfirm, message, Tag, Alert, Upload, Divider, Typography,
} from "antd";
import {
  PlusOutlined, DeleteOutlined, DownloadOutlined, UploadOutlined,
  EditOutlined, ReloadOutlined,
} from "@ant-design/icons";
import type { UploadProps } from "antd";
import { api } from "../api/client";
import { seqCol, numCol, textCol } from "../utils/table";

const { Text } = Typography;

/** Round9 P0-5: SSUI D18-D25 经济数据管理 Drawer。
 *
 * 功能(审计 P0-5.1-5.10):
 *  - 列表显示已有经济指标(按年份+场景分组)
 *  - 录入/编辑 8 项 D18-D25 表单
 *  - 单位/方向/来源/is_proxy 显式标注
 *  - Excel 模板下载 + Excel 批量导入
 *  - 删除单年/全部
 */
export default function EconomicDataDrawer({
  siteId, open, onClose, onSaved,
}: {
  siteId: number | undefined;
  open: boolean;
  onClose: () => void;
  onSaved?: () => void;
}) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [editForm] = Form.useForm();
  const [editModal, setEditModal] = useState<{ year: number; scenario: string } | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => {
    if (!siteId) return;
    setLoading(true);
    api.getEconomicData(siteId).then(setData).catch(() => setData(null)).finally(() => setLoading(false));
  };

  useEffect(() => { if (open && siteId) load(); }, [open, siteId]);

  // D18-D25 指标定义(从后端 indicator_definitions 读; 兜底硬编码)
  const INDICATORS = data?.indicator_definitions || {
    D18: { name: "劳动力成本", unit: "元/亩", direction: "negative" },
    D19: { name: "机械作业及服务成本", unit: "元/亩", direction: "negative" },
    D20: { name: "土地租金或折算土地成本", unit: "元/亩", direction: "negative" },
    D21: { name: "种子肥料农药等非机械化物质投入", unit: "元/亩", direction: "negative" },
    D22: { name: "单位面积总产值", unit: "元/公顷", direction: "positive" },
    D23: { name: "效益费用比", unit: "无量纲", direction: "positive" },
    D24: { name: "人均可支配收入", unit: "元/人", direction: "positive" },
    D25: { name: "单位面积实物产量", unit: "kg/公顷", direction: "positive" },
  };

  // 按 (year, scenario) 分组
  const grouped: Record<string, any[]> = {};
  for (const r of (data?.indicators || [])) {
    const key = `${r.year}|${r.scenario}`;
    (grouped[key] ||= []).push(r);
  }
  const groups = Object.entries(grouped).map(([key, rows]) => {
    const [year, scenario] = key.split("|");
    return { year: Number(year), scenario, rows, key };
  }).sort((a, b) => b.year - a.year);

  const openCreate = () => {
    editForm.resetFields();
    editForm.setFieldsValue({
      evaluation_year: new Date().getFullYear(),
      scenario: "production",
      crop_or_land_use: "水稻",
      // 默认 8 项空值, 由用户填
      indicators: Object.keys(INDICATORS).map((code) => ({
        indicator_code: code, value: undefined,
        unit: INDICATORS[code].unit, source_type: "site_actual",
        source_name: "", source_year: new Date().getFullYear(),
        is_proxy: false,
      })),
      // 原始汇总(可选)
      area_hectare: undefined, yield_kg: undefined,
      gross_output_yuan: undefined, total_cost_yuan: undefined,
    });
    setEditModal({ year: new Date().getFullYear(), scenario: "production" });
  };

  const openEdit = (g: any) => {
    const byCode: Record<string, any> = {};
    for (const r of g.rows) byCode[r.code] = r;
    editForm.setFieldsValue({
      evaluation_year: g.year,
      scenario: g.scenario,
      crop_or_land_use: g.rows[0]?.crop_or_land_use || "水稻",
      indicators: Object.keys(INDICATORS).map((code) => ({
        indicator_code: code,
        value: byCode[code]?.value,
        unit: byCode[code]?.unit || INDICATORS[code].unit,
        source_type: byCode[code]?.source_type || "site_actual",
        source_name: byCode[code]?.source_name || "",
        source_year: byCode[code]?.source_year || g.year,
        is_proxy: byCode[code]?.is_proxy || false,
      })),
    });
    setEditModal({ year: g.year, scenario: g.scenario });
  };

  const save = async () => {
    if (!siteId) return;
    try {
      const v = await editForm.validateFields();
      // 转换 indicators: antd Form 用数组, 后端期望数组
      const indicators = (v.indicators || []).map((ind: any) => ({
        indicator_code: ind.indicator_code,
        value: ind.value,
        unit: ind.unit,
        source_type: ind.source_type,
        source_name: ind.source_name || null,
        source_year: ind.source_year || null,
        is_proxy: ind.is_proxy || false,
      }));
      // 缺值的指标后端会拒绝; 这里过滤掉 value 为 undefined 的项让用户先存部分
      const validIndicators = indicators.filter((i: any) => i.value !== undefined && i.value !== null);
      if (validIndicators.length === 0) {
        message.warning("请至少录入一项指标值");
        return;
      }
      setSaving(true);
      const body: any = {
        evaluation_year: v.evaluation_year,
        scenario: v.scenario,
        crop_or_land_use: v.crop_or_land_use,
        indicators: validIndicators,
      };
      if (v.area_hectare != null) body.area_hectare = v.area_hectare;
      if (v.yield_kg != null) body.yield_kg = v.yield_kg;
      if (v.gross_output_yuan != null) body.gross_output_yuan = v.gross_output_yuan;
      if (v.total_cost_yuan != null) body.total_cost_yuan = v.total_cost_yuan;
      const r = await api.saveEconomicData(siteId, body);
      message.success(`保存成功: ${r.indicators_saved}/8 项${r.economic_complete ? "(8/8 齐全, 可生成正式 SSUI)" : `(缺 ${r.missing?.length || 0} 项)`}`);
      setEditModal(null);
      load();
      onSaved?.();
    } catch (e: any) {
      if (e?.errorFields) return; // antd Form 校验错
      message.error(e?.response?.data?.detail || "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const del = async (year: number) => {
    if (!siteId) return;
    try {
      await api.deleteEconomicData(siteId, year);
      message.success(`已删除 ${year} 年数据`);
      load();
      onSaved?.();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "删除失败");
    }
  };

  // Excel 导入(用 Upload beforeUpload 拦截手动 POST)
  const uploadProps: UploadProps = {
    accept: ".xlsx,.xls",
    showUploadList: false,
    beforeUpload: async (file) => {
      if (!siteId) return false;
      try {
        setSaving(true);
        const r = await api.importEconomicData(siteId, file);
        message.success(`导入成功: ${r.indicators_saved}/8 项`);
        load();
        onSaved?.();
      } catch (e: any) {
        message.error(e?.response?.data?.detail || "Excel 导入失败");
      } finally {
        setSaving(false);
      }
      return false; // 阻止默认上传
    },
  };

  return (
    <Drawer
      title="D18-D25 经济数据管理"
      placement="right"
      width={960}
      open={open}
      onClose={onClose}
      destroyOnClose
      extra={
        <Space>
          <Button size="small" icon={<ReloadOutlined />} onClick={load}>刷新</Button>
          <Button size="small" icon={<DownloadOutlined />}
            onClick={() => siteId && window.open(api.economicTemplateUrl(siteId))}>下载模板</Button>
          <Upload {...uploadProps}>
            <Button size="small" icon={<UploadOutlined />} loading={saving}>导入 Excel</Button>
          </Upload>
          <Button size="small" type="primary" icon={<PlusOutlined />} onClick={openCreate}>录入</Button>
        </Space>
      }
    >
      <Alert
        type="info" showIcon style={{ marginBottom: 12 }}
        message="数据来源分层"
        description={
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li><Tag color="green">site_actual</Tag>场地真实记录(合同/发票) → 正式 SSUI</li>
            <li><Tag color="orange">regional_official_proxy</Tag>区域代理/官方参照 → 仅参考 SSUI</li>
            <li><Tag color="red">test_fixture</Tag>测试夹具, 生产环境严禁</li>
          </ul>
        }
      />

      <Table
        size="small" rowKey="key" loading={loading}
        dataSource={groups} pagination={false}
        expandable={{
          expandedRowRender: (g) => (
            <Table size="small" rowKey="code" dataSource={g.rows} pagination={false}
              columns={[
                seqCol(),
                textCol("指标代码", "code"),
                textCol("指标名称", "name"),
                numCol("数值", "value"),
                textCol("单位", "unit"),
                textCol("方向", "direction"),
                {
                  title: "来源类型", dataIndex: "source_type", key: "source_type",
                  render: (v: string) => (
                    <Tag color={v === "site_actual" ? "green" : v === "regional_official_proxy" ? "orange" : "red"}>
                      {v || "—"}
                    </Tag>
                  ),
                },
                {
                  title: "代理", dataIndex: "is_proxy", key: "is_proxy",
                  render: (v: boolean) => v ? <Tag color="orange">是</Tag> : <Tag>否</Tag>,
                },
                textCol("来源", "source_name"),
              ]}
            />
          ),
        }}
        columns={[
          { title: "年份", dataIndex: "year", key: "year", width: 80 },
          {
            title: "场景", dataIndex: "scenario", key: "scenario", width: 100,
            render: (v: string) => <Tag color={v === "production" ? "blue" : "green"}>{v}</Tag>,
          },
          { title: "指标数", key: "count", width: 80, render: (_: any, r: any) => `${r.rows.length}/8` },
          {
            title: "是否齐全", key: "complete", width: 100,
            render: (_: any, r: any) => r.rows.length === 8
              ? <Tag color="green">8/8</Tag>
              : <Tag color="orange">{r.rows.length}/8</Tag>,
          },
          {
            title: "操作", key: "ops", width: 140,
            render: (_: any, r: any) => (
              <Space size="small">
                <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
                <Popconfirm title={`删除 ${r.year} 年全部经济数据?`} onConfirm={() => del(r.year)}>
                  <Button size="small" danger icon={<DeleteOutlined />}>删</Button>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      {/* 录入/编辑 Modal */}
      {editModal && (
        <Drawer
          title={`${editModal.year} 年 ${editModal.scenario} — 经济指标录入`}
          width={680} open={!!editModal} onClose={() => setEditModal(null)}
          extra={<Space>
            <Button onClick={() => setEditModal(null)}>取消</Button>
            <Button type="primary" loading={saving} onClick={save}>保存</Button>
          </Space>}
        >
          <Form form={editForm} layout="vertical" initialValues={{ scenario: "production" }}>
            <Space style={{ width: "100%" }} size="middle">
              <Form.Item name="evaluation_year" label="年份" rules={[{ required: true }]}>
                <InputNumber min={2000} max={2100} style={{ width: 100 }} />
              </Form.Item>
              <Form.Item name="scenario" label="场景" rules={[{ required: true }]}>
                <Select style={{ width: 140 }} options={[
                  { value: "production", label: "生产(production)" },
                  { value: "ecology", label: "生态(ecology)" },
                ]} />
              </Form.Item>
              <Form.Item name="crop_or_land_use" label="作物/用地">
                <Input style={{ width: 140 }} placeholder="如: 水稻" />
              </Form.Item>
            </Space>
            <Divider orientation="left">D18-D25 八项指标</Divider>
            <Form.List name="indicators">
              {(fields) => fields.map((field) => {
                const code = editForm.getFieldValue(["indicators", field.name, "indicator_code"]);
                const def = INDICATORS[code] || {};
                return (
                  <Space key={field.key} style={{ display: "flex", marginBottom: 8 }} align="baseline">
                    <Text strong style={{ width: 60 }}>{code}</Text>
                    <Text type="secondary" style={{ width: 200, fontSize: 12 }}>{def.name}</Text>
                    <Form.Item name={[field.name, "value"]} label="值" rules={[{ required: true }]}>
                      <InputNumber style={{ width: 130 }} />
                    </Form.Item>
                    <Form.Item name={[field.name, "unit"]} label="单位">
                      <Input style={{ width: 90 }} />
                    </Form.Item>
                    <Form.Item name={[field.name, "source_type"]} label="来源类型">
                      <Select style={{ width: 150 }} options={[
                        { value: "site_actual", label: "场地实测(green)" },
                        { value: "regional_official_proxy", label: "区域代理(orange)" },
                      ]} />
                    </Form.Item>
                    <Form.Item name={[field.name, "is_proxy"]} label="代理" valuePropName="checked">
                      <InputNumber style={{ width: 60 }} min={0} max={1} />
                    </Form.Item>
                  </Space>
                );
              })}
            </Form.List>
            <Divider orientation="left">原始汇总值(可选, 用于 D23/D25 交叉校验)</Divider>
            <Space style={{ width: "100%" }} size="middle">
              <Form.Item name="area_hectare" label="面积(公顷)"><InputNumber style={{ width: 120 }} /></Form.Item>
              <Form.Item name="yield_kg" label="总产量(kg)"><InputNumber style={{ width: 140 }} /></Form.Item>
              <Form.Item name="gross_output_yuan" label="总产值(元)"><InputNumber style={{ width: 140 }} /></Form.Item>
              <Form.Item name="total_cost_yuan" label="总成本(元)"><InputNumber style={{ width: 140 }} /></Form.Item>
            </Space>
          </Form>
        </Drawer>
      )}
    </Drawer>
  );
}
