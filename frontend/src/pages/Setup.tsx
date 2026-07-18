import { useState } from "react";
import { Form, Input, Button, Card, App, Typography, Space, Steps, Alert } from "antd";
import {
  UserOutlined, LockOutlined, SafetyCertificateOutlined, CheckCircleOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import styles from "./Login.module.css";

const { Title, Text } = Typography;

export default function Setup() {
  const { message } = App.useApp();
  const nav = useNavigate();
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [createdUsername, setCreatedUsername] = useState("");

  const onFinish = async (v: { username: string; password: string; confirm_password: string }) => {
    setSubmitting(true);
    try {
      const r = await api.setupComplete({
        username: v.username,
        password: v.password,
        confirm_password: v.confirm_password,
      });
      setCreatedUsername(v.username);
      setDone(true);
      message.success(r.message || "管理员创建成功");
    } catch (err: any) {
      const detail = err?.response?.data?.detail || "设置失败, 请检查后重试";
      message.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className={styles.loginContainer}>
        <Card className={styles.glassCard}>
          <div style={{ textAlign: "center", padding: "24px 0" }}>
            <CheckCircleOutlined style={{ fontSize: 48, color: "#52c41a", marginBottom: 16 }} />
            <Title level={4} style={{ marginBottom: 8 }}>系统初始化完成</Title>
            <Text type="secondary">
              管理员账号 <strong>{createdUsername}</strong> 已创建成功。
              <br />请使用该账号登录系统。
            </Text>
            <div style={{ marginTop: 24 }}>
              <Button type="primary" size="large" block
                style={{ borderRadius: 3, background: "#0052D9", borderColor: "#0052D9" }}
                onClick={() => nav("/login", { state: { username: createdUsername } })}>
                前往登录
              </Button>
            </div>
          </div>
        </Card>
        <div className={styles.footerText}>
          © {new Date().getFullYear()} 生态环境部土壤与农业农村生态环境监管技术中心 版权所有
        </div>
      </div>
    );
  }

  return (
    <div className={styles.loginContainer}>
      <Card className={styles.glassCard}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <Space direction="vertical" size={0}>
            <SafetyCertificateOutlined style={{ fontSize: 40, color: "#0052D9", marginBottom: 12 }} />
            <Title level={4} style={{ color: "rgba(0,0,0,0.9)", margin: 0, fontWeight: 700 }}>
              系统首次启动
            </Title>
            <Title level={5} style={{ color: "#0052D9", margin: "4px 0 0 0", fontWeight: 500 }}>
              管理员账号设置
            </Title>
          </Space>
        </div>

        <Steps current={0} size="small" style={{ marginBottom: 24 }}
          items={[{ title: "设置管理员" }, { title: "完成" }]} />

        <Alert type="info" showIcon style={{ marginBottom: 20 }}
          message="这是系统首次启动, 请设置管理员账号。"
          description="设置完成后, 该账号将拥有系统全部权限, 请妥善保管密码。" />

        <Form form={form} layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" label="管理员用户名"
            rules={[
              { required: true, message: "请输入用户名" },
              { min: 3, message: "至少 3 个字符" },
              { max: 32, message: "不超过 32 个字符" },
            ]}>
            <Input
              prefix={<UserOutlined style={{ color: "#bfbfbf" }} />}
              size="large"
              placeholder="设置管理员用户名(如 admin)"
              style={{ borderRadius: 3 }}
            />
          </Form.Item>
          <Form.Item name="password" label="密码"
            rules={[
              { required: true, message: "请输入密码" },
              { min: 8, message: "密码至少 8 位" },
            ]}
            extra="至少 8 位, 含大小写字母和数字">
            <Input.Password
              prefix={<LockOutlined style={{ color: "#bfbfbf" }} />}
              size="large"
              placeholder="设置密码"
              style={{ borderRadius: 3 }}
            />
          </Form.Item>
          <Form.Item name="confirm_password" label="确认密码"
            dependencies={["password"]}
            rules={[
              { required: true, message: "请再次输入密码" },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("password") === value) return Promise.resolve();
                  return Promise.reject(new Error("两次输入的密码不一致"));
                },
              }),
            ]}>
            <Input.Password
              prefix={<LockOutlined style={{ color: "#bfbfbf" }} />}
              size="large"
              placeholder="再次输入密码"
              style={{ borderRadius: 3 }}
            />
          </Form.Item>
          <Form.Item style={{ marginTop: 8, marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" size="large" block loading={submitting}
              style={{ borderRadius: 3, background: "#0052D9", color: "#FFFFFF", borderColor: "#0052D9", fontWeight: 600 }}>
              完成设置并创建管理员
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <div className={styles.footerText}>
        © {new Date().getFullYear()} 生态环境部土壤与农业农村生态环境监管技术中心 版权所有
      </div>
    </div>
  );
}
