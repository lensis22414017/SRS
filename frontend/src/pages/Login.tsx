import { Form, Input, Button, Card, message, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";

export default function Login() {
  const nav = useNavigate();
  const { setSession } = useAuth();

  const onFinish = async (v: { username: string; password: string }) => {
    try {
      const r = await api.login(v.username, v.password);
      setSession(r.access_token, r.user);
      message.success(`欢迎，${r.user.display_name}`);
      nav("/");
    } catch {
      message.error("用户名或密码错误");
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "linear-gradient(135deg,#0f3d6e,#1a5a9e)" }}>
      <Card style={{ width: 380 }}>
        <Typography.Title level={4} style={{ textAlign: "center", color: "#0f3d6e" }}>
          污染场地土壤生态-生产<br />功能重构监管系统
        </Typography.Title>
        <Form layout="vertical" onFinish={onFinish} initialValues={{ username: "admin", password: "Demo@2026" }}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input size="large" placeholder="admin / enterprise / agency / regulator" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password size="large" />
          </Form.Item>
          <Button type="primary" htmlType="submit" size="large" block>登录</Button>
        </Form>
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, fontSize: 12 }}>
          演示账号密码均为 Demo@2026；不同角色可见数据与权限不同。
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
