import { useEffect, useState } from "react";
import {
  Card, Tabs, Form, Input, Button, message, Table, Tag, Descriptions,
  Space, Row, Col, Statistic, Badge, Typography, Alert, Divider, List,
  Select, Tooltip, Modal,
} from "antd";
import {
  CheckCircleOutlined, CloseCircleOutlined, WarningOutlined,
  DatabaseOutlined, SettingOutlined, TeamOutlined, FileTextOutlined,
  HeartOutlined, ApiOutlined, ThunderboltOutlined, PlusOutlined, ExperimentOutlined,
  InfoCircleOutlined, UserAddOutlined, PhoneOutlined, MailOutlined,
  EditOutlined, SaveOutlined, HomeOutlined,
} from "@ant-design/icons";
import { api } from "../api/client";
import { seqCol, textCol } from "../utils/table";

const { Text } = Typography;

/** 权限代码 → 中文显示名 */
const PERM_LABEL: Record<string, string> = {
  "audit:view": "审计日志查看",
  "data:archive": "数据归档",
  "data:export": "数据导出",
  "data:input": "数据录入",
  "data:query": "数据查询",
  "file:download": "文件下载",
  "map:view": "地图查看",
  "model:manage": "模型管理",
  "param:config": "参数配置",
  "report:generate": "报告生成",
  "role:manage": "角色管理",
  "tech:manage": "技术库管理",
  "user:manage": "用户管理",
  "workflow:view": "全流程查看",
};
const permLabel = (code: string) => PERM_LABEL[code] || code;

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: 系统概览（默认首标签页）
// ──────────────────────────────────────────────────────────────────────────────
function SystemOverview() {
  const features = [
    { module: "场地数据管理", desc: "多源数据导入/校验/存储/可视化", key: "1" },
    { module: "障碍因子诊断", desc: "规则诊断 + 模型贡献度解释识别关键障碍因子", key: "2" },
    { module: "功能重构评价", desc: "生态/生产功能重构可行性量化评估", key: "3" },
    { module: "SSUI 可持续评价", desc: "修复后中长期持续利用潜力评价", key: "4" },
    { module: "方案推荐", desc: "基于诊断结果的技术库匹配推荐", key: "5" },
    { module: "全流程追溯", desc: "五阶段监管追溯（调查→审批→施工→效果→管护）", key: "6" },
    { module: "报告生成", desc: "一键生成 PDF/DOCX 全流程监管报告", key: "7" },
    { module: "权限管理", desc: "四角色 RBAC + 组织级数据隔离", key: "8" },
  ];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      {/* 系统简介 */}
      <Card>
        <Typography.Title level={4} style={{ marginTop: 0, color: "#0f3d6e", marginBottom: 12 }}>
          <InfoCircleOutlined style={{ marginRight: 8 }} />
          污染场地土壤生态-生产功能重构监管系统（SRS）
        </Typography.Title>
        <Typography.Paragraph style={{ fontSize: 14, marginBottom: 0, lineHeight: 1.8 }}>
          本系统由生态环境部土壤与农业农村生态环境监管技术中心主持开发，面向污染场地全过程监管需求，
          集数据管理、障碍因子诊断、功能重构评价、方案推荐、全流程追溯于一体。
          系统覆盖污染场地从调查评估到后期管护的全生命周期，
          为监管部门和从业机构提供科学化、标准化的技术支撑平台。
        </Typography.Paragraph>
      </Card>

      {/* 参与单位 */}
      <Card
        size="small"
        title={<Space><TeamOutlined />参与单位</Space>}
      >
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="主持单位">
            生态环境部土壤与农业农村生态环境监管技术中心
          </Descriptions.Item>
          <Descriptions.Item label="技术支持">
            浙江大学王玮课题组
          </Descriptions.Item>
          <Descriptions.Item label="数据支持">
            浙江大学王玮课题组
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 核心功能 */}
      <Card
        size="small"
        title={<Space><CheckCircleOutlined />核心功能</Space>}
      >
        <Table
          rowKey="key"
          size="small"
          pagination={false}
          dataSource={features}
          columns={[
            {
              title: "功能模块",
              dataIndex: "module",
              width: 180,
              render: (v: string) => <Text strong style={{ color: "#0f3d6e" }}>{v}</Text>,
            },
            { title: "说明", dataIndex: "desc" },
          ]}
        />
      </Card>

      {/* 技术栈 */}
      <Card
        size="small"
        title={<Space><ApiOutlined />技术栈</Space>}
      >
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label="后端">
            Python FastAPI + SQLAlchemy + SQLite(演示) / PostgreSQL(部署)
          </Descriptions.Item>
          <Descriptions.Item label="前端">
            React 18 + TypeScript + Ant Design + ECharts 5
          </Descriptions.Item>
          <Descriptions.Item label="算法">
            scikit-learn RandomForest + SHAP + GEE 空间协变量
          </Descriptions.Item>
          <Descriptions.Item label="报告">
            Jinja2 模板 + WeasyPrint PDF 引擎
          </Descriptions.Item>
          <Descriptions.Item label="部署" span={2}>
            Docker + Nginx + 桌面端 PyInstaller 打包
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 数据标准依据 */}
      <Card
        size="small"
        title={<Space><FileTextOutlined />数据标准依据</Space>}
      >
        <List
          size="small"
          dataSource={[
            "GB 15618-2018 农用地土壤污染风险管控标准",
            "GB 36600-2018 建设用地土壤污染风险管控标准",
            "HJ 25.5-2018 污染地块风险管控与修复效果评估技术导则",
            "GEE 多源遥感与地理空间协变量（MODIS / WorldClim / SRTM / SoilGrids2.0）",
          ]}
          renderItem={(item) => (
            <List.Item style={{ padding: "4px 0" }}>
              <Text style={{ fontSize: 13 }}>{item}</Text>
            </List.Item>
          )}
        />
      </Card>
    </Space>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: 修改密码
// ──────────────────────────────────────────────────────────────────────────────
function ChangePassword() {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const submit = async (v: any) => {
    if (v.np !== v.np2) { message.error("两次新密码不一致"); return; }
    setLoading(true);
    try {
      await api.changePassword(v.op, v.np);
      message.success("密码已修改");
      form.resetFields();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "修改失败");
    } finally { setLoading(false); }
  };
  return (
    <Card
      type="inner"
      title="修改登录密码"
      style={{ maxWidth: 440 }}
      styles={{ body: { padding: "24px" } }}
    >
      <Form form={form} layout="vertical" onFinish={submit}>
        <Form.Item name="op" label="原密码" rules={[{ required: true }]}>
          <Input.Password />
        </Form.Item>
        <Form.Item name="np" label="新密码（≥6位）" rules={[{ required: true, min: 6 }]}>
          <Input.Password />
        </Form.Item>
        <Form.Item name="np2" label="确认新密码" rules={[{ required: true }]}>
          <Input.Password />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          修改密码
        </Button>
      </Form>
    </Card>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: 操作日志
// ──────────────────────────────────────────────────────────────────────────────
function AuditLogs() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const load = (p = page) => {
    setLoading(true);
    api.auditLogs({ page: p, size: 20 })
      .then(setData)
      .catch(() => message.error("无权限或加载失败"))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(1); }, []);
  return (
    <Table
      rowKey="id"
      size="small"
      loading={loading}
      dataSource={data.items}
      pagination={{
        current: page, pageSize: 20, total: data.total,
        onChange: (p) => { setPage(p); load(p); },
        showTotal: (t) => `共 ${t} 条记录`,
      }}
      columns={[
        seqCol(64),
        textCol("时间", "time", {
          render: (v: string) => v ? new Date(v).toLocaleString("zh-CN") : "—",
        }),
        textCol("操作人", "user"),
        { title: "操作", dataIndex: "action", align: "center" as const,
          render: (v: string) => <Tag>{v}</Tag> },
        textCol("对象", "resource"),
        {
          title: "结果", dataIndex: "result", align: "center" as const,
          render: (v: string) => (
            <Tag color={v === "success" ? "green" : v === "fail" ? "red" : "orange"}>
              {v === "success" ? "成功" : v === "fail" ? "失败" : v}
            </Tag>
          ),
        },
        textCol("IP", "ip"),
      ]}
    />
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: 系统配置与角色权限矩阵
// ──────────────────────────────────────────────────────────────────────────────
function SystemConfig() {
  const [cfg, setCfg] = useState<any>(null);
  useEffect(() => { api.systemConfig().then(setCfg).catch(() => {}); }, []);
  if (!cfg) return <Text type="secondary">加载中…</Text>;
  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Descriptions bordered size="small" column={2} title="系统信息">
        <Descriptions.Item label="系统名称" span={2}>{cfg.app_name}</Descriptions.Item>
        <Descriptions.Item label="AI 模型">
          {cfg.ai_configured ? cfg.ai_model : <Tag>未配置</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="AI 状态">
          {cfg.ai_configured
            ? <Tag color="green" icon={<CheckCircleOutlined />}>已启用</Tag>
            : <Tag icon={<CloseCircleOutlined />}>未配置</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="评价参数版本">{cfg.param_version}</Descriptions.Item>
        <Descriptions.Item label="知识库版本">{cfg.knowledge_base_version}</Descriptions.Item>
      </Descriptions>

      <Card type="inner" title="角色权限矩阵">
        <Table
          rowKey="code"
          size="small"
          pagination={false}
          dataSource={cfg.roles}
          columns={[
            { title: "角色", dataIndex: "name", align: "center" as const,
              width: 110, render: (v: string) => <Text strong>{v}</Text> },
            { title: "代码", dataIndex: "code", align: "center" as const,
              width: 110, render: (v: string) => <Tag>{v}</Tag> },
            { title: "权限数", dataIndex: "permissions", align: "center" as const,
              width: 80,
              render: (v: string[]) => <Badge count={v?.length ?? 0} color="#0f3d6e" /> },
            { title: "权限明细（中文）", dataIndex: "permissions", align: "center" as const,
              render: (v: string[]) => (
                <Space wrap size={4} style={{ justifyContent: "center", width: "100%" }}>
                  {(v || []).map((p) => (
                    <Tooltip key={p} title={p}>
                      <Tag color="blue" style={{ fontSize: 12, margin: 2 }}>{permLabel(p)}</Tag>
                    </Tooltip>
                  ))}
                </Space>
              ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: 系统健康监控（环境自检结果展示）
// ──────────────────────────────────────────────────────────────────────────────
function SystemHealth() {
  const [cfg, setCfg] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  useEffect(() => {
    api.systemConfig().then(setCfg).catch(() => {});
    api.systemHealth().then(setHealth).catch(() => {});
  }, []);

  // 真实健康检查(/system/health: SELECT 1 ping DB + 模型产物 + AI 配置), 替代此前硬编码 ok:true
  const items = cfg ? [
    {
      name: "数据库连接",
      ok: health?.checks?.database?.ok === true,
      detail: health?.checks?.database?.detail || "检测中…",
      icon: <DatabaseOutlined />,
    },
    {
      name: "AI 大模型",
      ok: cfg.ai_configured,
      detail: cfg.ai_configured ? `${cfg.ai_model} 已启用` : "未配置 AI_API_KEY，降级为规则答复",
      icon: <SettingOutlined />,
    },
    {
      name: "知识库",
      ok: !!cfg.knowledge_base_version,
      detail: cfg.knowledge_base_version ? `版本 ${cfg.knowledge_base_version}` : "知识库未加载",
      icon: <FileTextOutlined />,
    },
    {
      name: "评价算法参数",
      ok: !!cfg.param_version,
      detail: cfg.param_version ? `版本 ${cfg.param_version}` : "参数文件未加载",
      icon: <HeartOutlined />,
    },
  ] : [];

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Alert
        type="info"
        showIcon
        message="系统健康检查"
        description="展示当前运行时关键组件状态。若需重新检查，请刷新页面。"
        style={{ borderRadius: 6 }}
      />
      <Row gutter={16}>
        {items.map((item) => (
          <Col span={12} key={item.name} style={{ marginBottom: 12 }}>
            <Card
              size="small"
              style={{
                borderRadius: 8,
                borderLeft: `4px solid ${item.ok ? "#16a34a" : "#dc2626"}`,
              }}
            >
              <Space>
                <div style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: item.ok ? "#f0fdf4" : "#fef2f2",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: item.ok ? "#16a34a" : "#dc2626",
                  fontSize: 14,
                }}>
                  {item.icon}
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>
                    {item.ok
                      ? <CheckCircleOutlined style={{ color: "#16a34a", marginRight: 4 }} />
                      : <WarningOutlined style={{ color: "#f59e0b", marginRight: 4 }} />}
                    {item.name}
                  </div>
                  <div style={{ fontSize: 11, color: "#888" }}>{item.detail}</div>
                </div>
              </Space>
            </Card>
          </Col>
        ))}
      </Row>

      <Card type="inner" title="数据备份说明" size="small">
        <List
          size="small"
          dataSource={[
            "SQLite 模式: 数据库文件默认在 ~/.srs/srs.db，手动复制即可备份",
            "PostgreSQL 模式: 建议使用 pg_dump 定期备份，参考 /deploy/backup.sh",
            "上传文件: 存储在 FILE_STORAGE_DIR 目录，建议定期同步至对象存储",
            "知识库与算法参数: 位于 /data/knowledge_base，版本控制由 Git 管理",
          ]}
          renderItem={(item) => (
            <List.Item style={{ padding: "4px 0" }}>
              <Text style={{ fontSize: 12 }}>• {item}</Text>
            </List.Item>
          )}
        />
      </Card>
    </Space>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: AI 模型接入配置（用户自选服务商 / 自定义端点，默认智谱 GLM 官方免费）
// ──────────────────────────────────────────────────────────────────────────────
function AiModelConfig() {
  const [cfg, setCfg] = useState<any>(null);
  const [presets, setPresets] = useState<any[]>([]);
  const [provider, setProvider] = useState<string>("zhipu");
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);

  const load = () => {
    api.aiConfigGet().then((d) => {
      setCfg(d);
      setPresets(d.presets || []);
      setProvider(d.provider || "zhipu");
      form.setFieldsValue({ base_url: d.base_url, model: d.model, api_key: "" });
    }).catch(() => message.error("无权限或加载失败（需参数配置权限）"));
  };
  useEffect(() => { load(); }, []);

  const onPreset = (id: string) => {
    setProvider(id);
    const p = presets.find((x) => x.id === id);
    if (p && id !== "custom") {
      form.setFieldsValue({ base_url: p.base_url, model: p.model });
    }
  };

  const save = async (v: any) => {
    setSaving(true);
    try {
      const r = await api.aiConfigPut({
        base_url: v.base_url, model: v.model, provider,
        api_key: v.api_key || undefined,   // 留空＝沿用已存 key
      });
      message.success(
        r.connectivity_ok ? `已保存并连通正常（${r.model}）`
        : r.configured ? `已保存，但连通失败：${r.connectivity_error || "请点「测试连通」排查 key/模型/端点"}`
        : "已保存（尚未填写 API Key）");
      form.setFieldsValue({ api_key: "" });
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    } finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true);
    try {
      const r = await api.aiConfigTest();
      r.ok ? message.success(r.message) : message.warning(r.message);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "测试失败");
    } finally { setTesting(false); }
  };

  const curPreset = presets.find((p) => p.id === provider);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Alert
        type="info" showIcon
        message="接入你自己的大模型"
        description="支持任意 OpenAI 兼容服务（/chat/completions）。默认使用智谱 GLM 官方免费模型；可改用 DeepSeek、通义千问、硅基流动、Kimi、OpenAI 或本地 Ollama。API Key 仅保存在本机配置文件，不入库、不上传。"
        style={{ borderRadius: 6 }}
      />

      <Card type="inner" title={<Space><ApiOutlined />当前状态</Space>} size="small">
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="配置">
            {cfg?.configured
              ? <Tag color="blue" icon={<CheckCircleOutlined />}>已配置</Tag>
              : <Tag icon={<CloseCircleOutlined />}>未配置 Key</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="连通性">
            {cfg?.connectivity_ok === true
              ? <Tag color="green" icon={<CheckCircleOutlined />}>已连通</Tag>
              : cfg?.connectivity_ok === false
                ? <Tag color="red" icon={<CloseCircleOutlined />} title={cfg?.connectivity_error || ""}>连通失败</Tag>
                : <Tag color="orange">未测试</Tag>}
          </Descriptions.Item>
          <Descriptions.Item label="当前模型">{cfg?.model || "—"}</Descriptions.Item>
          <Descriptions.Item label="接入端点" span={2}>
            <Text code style={{ fontSize: 12 }}>{cfg?.base_url || "—"}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="API Key">{cfg?.api_key_masked || "（未设置）"}</Descriptions.Item>
          <Descriptions.Item label="配置来源">
            {cfg?.source === "override" ? "本机自定义" : cfg?.source === "env" ? ".env 默认" : "内置默认"}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card type="inner" title={<Space><ThunderboltOutlined />模型接入配置</Space>} size="small"
        style={{ maxWidth: 620 }}>
        <Form form={form} layout="vertical" onFinish={save}>
          <Form.Item label="服务商预设">
            <Select
              value={provider}
              onChange={onPreset}
              options={presets.map((p) => ({ value: p.id, label: p.name }))}
            />
            {curPreset?.note && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                {curPreset.note}
                {curPreset.apply_url && (
                  <> · <a href={curPreset.apply_url} target="_blank" rel="noreferrer">申请 API Key</a></>
                )}
              </Text>
            )}
          </Form.Item>
          <Form.Item name="base_url" label="接入端点 base_url"
            rules={[{ required: true, message: "请填写 OpenAI 兼容端点" }]}>
            <Input placeholder="https://open.bigmodel.cn/api/paas/v4" />
          </Form.Item>
          <Form.Item name="model" label="模型名称"
            rules={[{ required: true, message: "请填写模型名" }]}>
            <Input placeholder="GLM-4.7-Flash" />
          </Form.Item>
          <Form.Item name="api_key" label="API Key"
            extra="留空＝沿用已保存的 Key；仅保存在本机，不会回显明文。">
            <Input.Password placeholder={cfg?.has_key ? "已设置（留空不修改）" : "粘贴你的 API Key"} />
          </Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={saving}>保存配置</Button>
            <Button onClick={test} loading={testing} icon={<ThunderboltOutlined />}>
              测试连通
            </Button>
          </Space>
        </Form>
      </Card>
    </Space>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: 技术库管理(brief 4.6) — 列表/搜索/新增/编辑/删除
// ──────────────────────────────────────────────────────────────────────────────
function TechLibrary() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [modal, setModal] = useState<any>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  const load = (query = q) => {
    setLoading(true);
    api.technologies(query ? { q: query } : {})
      .then(setData)
      .catch(() => message.error("加载失败（需 tech:manage 权限）"))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(""); }, []);

  const openCreate = () => { form.resetFields(); setModal({ mode: "create" }); };
  const openEdit = (r: any) => {
    form.setFieldsValue({
      ...r,
      applicable_pollutants: r.applicable_pollutants ? JSON.stringify(r.applicable_pollutants, null, 2) : "",
      applicable_land_type: r.applicable_land_type ? JSON.stringify(r.applicable_land_type, null, 2) : "",
    });
    setModal({ mode: "edit", id: r.id });
  };

  const save = async (v: any) => {
    setSaving(true);
    const payload: any = { ...v };
    try {
      if (v.applicable_pollutants) payload.applicable_pollutants = JSON.parse(v.applicable_pollutants);
      if (v.applicable_land_type) payload.applicable_land_type = JSON.parse(v.applicable_land_type);
    } catch {
      message.error("适用污染物 / 适用用地必须是合法 JSON"); setSaving(false); return;
    }
    try {
      if (modal.mode === "create") await api.createTechnology(payload);
      else await api.updateTechnology(modal.id, payload);
      message.success("已保存"); setModal(null); load();
    } catch (e: any) { message.error(e?.response?.data?.detail || "保存失败"); }
    finally { setSaving(false); }
  };

  const del = async (id: number, name: string) => {
    if (!window.confirm(`确认删除技术「${name}」?`)) return;
    try { await api.deleteTechnology(id); message.success("已删除"); load(); }
    catch (e: any) { message.error(e?.response?.data?.detail || "删除失败"); }
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size={12}>
      <Alert type="info" showIcon
        message="修复技术库管理"
        description="推荐引擎从此库规则匹配方案（不让 AI 编造）。支持新增/编辑/删除，绑定适用污染物、用地、阶段、成本、工期、禁用条件与法规来源。"
        style={{ borderRadius: 6 }} />
      <Space>
        <Input.Search placeholder="搜索技术名称" value={q}
          onChange={(e) => setQ(e.target.value)} onSearch={() => load()} style={{ width: 260 }} />
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增技术</Button>
      </Space>
      <Table rowKey="id" size="small" loading={loading} dataSource={data.items}
        pagination={{ pageSize: 10 }} scroll={{ x: "max-content" }}
        columns={[
          seqCol(56),
          textCol("技术名称", "tech_name", { width: 160 }),
          { title: "适用污染物", dataIndex: "applicable_pollutants", width: 150,
            render: (v: any) => v ? <Tag>{typeof v === "string" ? v : JSON.stringify(v)}</Tag> : "—" },
          textCol("适用阶段", "applicable_stage", { width: 90 }),
          { title: "成本", dataIndex: "cost_level", width: 70, align: "center" as const,
            render: (v: string) => <Tag color={v === "低" ? "green" : v === "高" ? "red" : "orange"}>{v || "—"}</Tag> },
          { title: "工期", dataIndex: "duration_level", width: 70, align: "center" as const,
            render: (v: string) => <Tag>{v || "—"}</Tag> },
          textCol("来源", "source", { width: 150 }),
          { title: "操作", width: 140, render: (_: any, r: any) => (
            <Space>
              <Button size="small" onClick={() => openEdit(r)}>编辑</Button>
              <Button size="small" danger onClick={() => del(r.id, r.tech_name)}>删除</Button>
            </Space>
          ) },
        ]} />
      <Modal title={modal?.mode === "create" ? "新增修复技术" : "编辑修复技术"}
        open={!!modal} onCancel={() => setModal(null)} footer={null} width={720} destroyOnHidden>
        <Form form={form} layout="vertical" onFinish={save}>
          <Form.Item name="tech_name" label="技术名称" rules={[{ required: true, message: "请填写技术名称" }]}>
            <Input placeholder="如: 固化/稳定化" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}><Form.Item name="applicable_pollutants" label="适用污染物(JSON)"
              tooltip='例: {"重金属":["砷","铅"]}'>
              <Input.TextArea rows={2} placeholder='{"重金属":["砷","铅"]}' />
            </Form.Item></Col>
            <Col span={12}><Form.Item name="applicable_land_type" label="适用用地(JSON)"
              tooltip='例: {"生产用地":true}'>
              <Input.TextArea rows={2} placeholder='{"生产用地":true}' />
            </Form.Item></Col>
          </Row>
          <Row gutter={12}>
            <Col span={8}><Form.Item name="applicable_stage" label="适用阶段"><Input placeholder="调查/修复/验收" /></Form.Item></Col>
            <Col span={8}><Form.Item name="cost_level" label="成本">
              <Select allowClear options={[{ value: "低" }, { value: "中" }, { value: "高" }]} />
            </Form.Item></Col>
            <Col span={8}><Form.Item name="duration_level" label="工期">
              <Select allowClear options={[{ value: "短" }, { value: "中" }, { value: "长" }]} />
            </Form.Item></Col>
          </Row>
          <Form.Item name="applicable_soil" label="适用土壤"><Input placeholder="砂土/黏土/各类" /></Form.Item>
          <Form.Item name="advantages" label="优点"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="limitations" label="局限"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="secondary_risk" label="二次风险"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="forbidden_conditions" label="禁用条件"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="source" label="来源(法规/文献)"><Input placeholder="GB 36600-2018 / HJ 25.4-2019" /></Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={saving}>保存</Button>
            <Button onClick={() => setModal(null)}>取消</Button>
          </Space>
        </Form>
      </Modal>
    </Space>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: 账户审核
// ──────────────────────────────────────────────────────────────────────────────
function AccountApprovals() {
  const [data, setData] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.pendingApprovals().then((r) => setData(r.items || [])).catch(() => message.error("无权限"))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const approve = (uid: number) => {
    Modal.confirm({
      title: "确认通过", content: "通过后用户即可登录系统", onOk: () =>
        api.approveUser(uid).then(() => { message.success("已激活"); load(); }).catch((e) =>
          message.error(e?.response?.data?.detail || "操作失败")),
    });
  };
  const reject = (uid: number) => {
    let reason = "";
    Modal.confirm({
      title: "拒绝注册",
      content: (
        <Input.TextArea placeholder="请输入拒绝原因" onChange={(e) => reason = e.target.value} rows={3} style={{ marginTop: 8 }} />
      ),
      onOk: () => {
        if (!reason.trim()) { message.warning("请填写拒绝原因"); return Promise.reject(); }
        return api.rejectUser(uid, reason).then(() => { message.success("已拒绝"); load(); }).catch((e) =>
          message.error(e?.response?.data?.detail || "操作失败"));
      },
    });
  };

  return (
    <Table rowKey="user_id" loading={loading} dataSource={data}
      columns={[
        { title: "用户名", dataIndex: "username" },
        { title: "显示名", dataIndex: "display_name" },
        { title: "申请角色", dataIndex: "role_code", render: (v: string) => {
          const m: Record<string, string> = { enterprise: "企业用户", agency: "第三方机构", regulator: "监管人员" };
          return m[v] || v;
        }},
        { title: "组织", dataIndex: "organization_name" },
        { title: "联系方式", render: (_: any, r: any) =>
          [r.contact_phone, r.contact_email].filter(Boolean).join(" / ") || "—" },
        { title: "申请时间", dataIndex: "created_at", render: (v: string) =>
          v ? new Date(v).toLocaleString("zh-CN") : "—" },
        { title: "操作", render: (_: any, r: any) => (
          <Space>
            <Button type="primary" size="small" icon={<CheckCircleOutlined />}
              onClick={() => approve(r.user_id)}>通过</Button>
            <Button danger size="small" icon={<CloseCircleOutlined />}
              onClick={() => reject(r.user_id)}>拒绝</Button>
          </Space>
        )},
      ]}
      locale={{ emptyText: "暂无待审核账户" }}
    />
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: 系统联系方式编辑
// ──────────────────────────────────────────────────────────────────────────────
function ContactInfoEditor() {
  const [info, setInfo] = useState({ phone: "", email: "", display_name: "", updated_at: "" });
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [saving, setSaving] = useState(false);

  const load = () => {
    api.contactInfo().then((r) => {
      setInfo(r); setPhone(r.phone || ""); setEmail(r.email || "");
    }).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const save = async (field: "phone" | "email", value: string) => {
    setSaving(true);
    try {
      await api.updateContactInfo({ [field]: value });
      message.success(`${field === "phone" ? "电话" : "邮箱"}已更新`);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || "保存失败");
    } finally { setSaving(false); }
  };

  return (
    <Space direction="vertical" style={{ width: "100%", maxWidth: 520 }} size={16}>
      <Alert type="info" showIcon
        message="此处填写的联系方式将在新用户注册页面展示，供申请人联系审核。" />
      <Card type="inner" size="small">
        <Descriptions column={1} size="small">
          <Descriptions.Item label="联系电话">
            <Space>
              <Input prefix={<PhoneOutlined />} value={phone} onChange={(e) => setPhone(e.target.value)}
                style={{ width: 260 }} placeholder="请设置联系电话" />
              <Button icon={<SaveOutlined />} loading={saving} onClick={() => save("phone", phone)}>保存</Button>
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="联系邮箱">
            <Space>
              <Input prefix={<MailOutlined />} value={email} onChange={(e) => setEmail(e.target.value)}
                style={{ width: 260 }} placeholder="请设置联系邮箱" />
              <Button icon={<SaveOutlined />} loading={saving} onClick={() => save("email", email)}>保存</Button>
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="最后更新">{info.updated_at ? new Date(info.updated_at).toLocaleString("zh-CN") : "—"}</Descriptions.Item>
        </Descriptions>
      </Card>
    </Space>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 主页面
// ──────────────────────────────────────────────────────────────────────────────
export default function SystemManagement() {
  return (
    <Card
      title={
        <Space>
          <SettingOutlined style={{ color: "#0f3d6e" }} />
          系统管理
        </Space>
      }
      style={{ borderRadius: 8 }}
    >
      <Tabs
        items={[
          { key: "overview", label: <Space><HomeOutlined />系统概览</Space>, children: <SystemOverview /> },
          { key: "health", label: <Space><HeartOutlined />系统健康</Space>, children: <SystemHealth /> },
          { key: "approvals", label: <Space><UserAddOutlined />账户审核</Space>, children: <AccountApprovals /> },
          { key: "tech", label: <Space><ExperimentOutlined />技术库管理</Space>, children: <TechLibrary /> },
          { key: "contact", label: <Space><PhoneOutlined />联系方式</Space>, children: <ContactInfoEditor /> },
          { key: "cfg", label: <Space><SettingOutlined />系统配置</Space>, children: <SystemConfig /> },
          { key: "ai", label: <Space><ApiOutlined />AI 模型配置</Space>, children: <AiModelConfig /> },
          { key: "log", label: <Space><FileTextOutlined />操作日志</Space>, children: <AuditLogs /> },
          { key: "pwd", label: <Space><TeamOutlined />修改密码</Space>, children: <ChangePassword /> },
          { key: "about", label: <Space><InfoCircleOutlined />关于系统</Space>, children: <AboutSystem /> },
        ]}
        defaultActiveKey="overview"
      />
    </Card>
  );
}

// ──────────────────────────────────────────────────────────────────────────────
// 子组件: 关于系统(系统内展示开发者信息、版本、版权)
// ──────────────────────────────────────────────────────────────────────────────
function AboutSystem() {
  return (
    <Space direction="vertical" style={{ width: "100%" }} size={16}>
      <Card title={<Space><InfoCircleOutlined />系统信息</Space>}>
        <Descriptions bordered size="small" column={1}>
          <Descriptions.Item label="系统名称">污染场地土壤生态-生产功能重构监管系统</Descriptions.Item>
          <Descriptions.Item label="英文名称">Soil Remediation Supervision System (SRS)</Descriptions.Item>
          <Descriptions.Item label="版本">v1.0.0 (2026-07-01)</Descriptions.Item>
          <Descriptions.Item label="开源协议">
            <Tag color="green">MIT License</Tag> 允许商用/修改/分发, 保留版权声明即可
          </Descriptions.Item>
          <Descriptions.Item label="开发者">
            生态环境部土壤与农业农村生态环境监管技术中心<br/>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Soil Remediation Supervision System (SRS)
            </Text>
          </Descriptions.Item>
          <Descriptions.Item label="版权">Copyright © 2026 生态环境部土壤与农业农村生态环境监管技术中心</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title={<Space><ExperimentOutlined />核心技术</Space>} size="small">
        <Descriptions bordered size="small" column={2}>
          <Descriptions.Item label="后端">FastAPI + SQLAlchemy</Descriptions.Item>
          <Descriptions.Item label="前端">React + Ant Design + ECharts</Descriptions.Item>
          <Descriptions.Item label="算法">双轨防泄漏 RF + SHAP (CV Spearman 0.85+)</Descriptions.Item>
          <Descriptions.Item label="协变量">GEE (MODIS/WorldClim/SRTM/SoilGrids2.0)</Descriptions.Item>
          <Descriptions.Item label="报告">Jinja2 + WeasyPrint/xhtml2pdf</Descriptions.Item>
          <Descriptions.Item label="数据库">SQLite (桌面) / PostgreSQL (生产)</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title={<Space><InfoCircleOutlined />数据来源与标准</Space>} size="small">
        <List size="small" split>
          <List.Item>Google Earth Engine (GEE): 协变量采样, 非商业科研用途</List.Item>
          <List.Item>GB 15618-2018 农用地土壤污染风险管控标准</List.Item>
          <List.Item>GB 36600-2018 建设用地土壤污染风险管控标准</List.Item>
          <List.Item>HJ 25.5-2018 污染地块风险管控与土壤修复效果评估技术导则</List.Item>
          <List.Item>第三方组件清单详见 NOTICE 文件 (FastAPI/React/scikit-learn/SHAP 等均 MIT/BSD/Apache 商用友好)</List.Item>
        </List>
      </Card>

      <Card size="small">
        <Text type="secondary" style={{ fontSize: 12 }}>
          本系统基于真实文献数据训练, 双轨 RF 防泄漏(剔除污染物浓度列), CV Spearman 0.85+ 为可信诊断。
          所有结论可追溯到检测值与标准来源, 详见追溯报告。
        </Text>
      </Card>
    </Space>
  );
}
