import { useEffect, useState } from "react";
import { Card, Tabs, Form, Input, Button, message, Table, Tag, Descriptions, Space } from "antd";
import { api } from "../api/client";
import { seqCol, numCol, textCol } from "../utils/table";

function ChangePassword() {
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();
  const submit = async (v: any) => {
    if (v.np !== v.np2) { message.error("两次新密码不一致"); return; }
    setLoading(true);
    try { await api.changePassword(v.op, v.np); message.success("密码已修改"); form.resetFields(); }
    catch (e: any) { message.error(e?.response?.data?.detail || "修改失败"); }
    finally { setLoading(false); }
  };
  return (
    <Form form={form} layout="vertical" style={{ maxWidth: 360 }} onFinish={submit}>
      <Form.Item name="op" label="原密码" rules={[{ required: true }]}><Input.Password /></Form.Item>
      <Form.Item name="np" label="新密码（≥6位）" rules={[{ required: true, min: 6 }]}><Input.Password /></Form.Item>
      <Form.Item name="np2" label="确认新密码" rules={[{ required: true }]}><Input.Password /></Form.Item>
      <Button type="primary" htmlType="submit" loading={loading}>修改密码</Button>
    </Form>
  );
}

function AuditLogs() {
  const [data, setData] = useState<any>({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const load = (p = page) => { setLoading(true); api.auditLogs({ page: p, size: 20 }).then(setData).catch(() => message.error("无权限或加载失败")).finally(() => setLoading(false)); };
  useEffect(() => { load(1); }, []);
  return (
    <Table rowKey="id" size="small" loading={loading} dataSource={data.items}
      pagination={{ current: page, pageSize: 20, total: data.total, onChange: (p) => { setPage(p); load(p); } }}
      columns={[
        seqCol(64),
        textCol("时间", "time"),
        textCol("操作人", "user"),
        { title: "操作", dataIndex: "action", align: "center" },
        textCol("对象", "resource"),
        { title: "结果", dataIndex: "result", align: "center",
          render: (v: string) => <Tag color={v === "success" ? "green" : v === "fail" ? "red" : "orange"}>{v}</Tag> },
        textCol("IP", "ip"),
      ]} />
  );
}

function SystemConfig() {
  const [cfg, setCfg] = useState<any>(null);
  useEffect(() => { api.systemConfig().then(setCfg).catch(() => {}); }, []);
  if (!cfg) return <span>加载中…</span>;
  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Descriptions bordered size="small" column={2}>
        <Descriptions.Item label="系统名称" span={2}>{cfg.app_name}</Descriptions.Item>
        <Descriptions.Item label="AI 模型">{cfg.ai_configured ? cfg.ai_model : "未配置"}</Descriptions.Item>
        <Descriptions.Item label="评价参数版本">{cfg.param_version}</Descriptions.Item>
        <Descriptions.Item label="知识库版本">{cfg.knowledge_base_version}</Descriptions.Item>
        <Descriptions.Item label="AI 状态">{cfg.ai_configured ? <Tag color="green">已启用</Tag> : <Tag>未配置</Tag>}</Descriptions.Item>
      </Descriptions>
      <Card type="inner" title="角色权限矩阵">
        <Table rowKey="code" size="small" pagination={false} dataSource={cfg.roles}
          columns={[
            textCol("角色", "name"),
            textCol("代码", "code"),
            numCol("权限数", "permissions", { render: (v: string[]) => v?.length ?? 0 }),
            textCol("权限明细", "permissions", { render: (v: string[]) => (v || []).map((p) => <Tag key={p}>{p}</Tag>) }),
          ]} />
      </Card>
    </Space>
  );
}

export default function SystemManagement() {
  return (
    <Card title="系统管理">
      <Tabs items={[
        { key: "pwd", label: "修改密码", children: <ChangePassword /> },
        { key: "cfg", label: "系统配置", children: <SystemConfig /> },
        { key: "log", label: "操作日志", children: <AuditLogs /> },
      ]} />
    </Card>
  );
}
