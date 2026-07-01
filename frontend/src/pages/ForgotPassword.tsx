import { useState, useEffect } from "react";
import { Form, Input, Button, Card, App, Typography, Space, Alert, Divider, Steps } from "antd";
import { LockOutlined, SafetyCertificateOutlined, UserOutlined, PhoneOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import styles from "./Login.module.css";

const { Title, Text } = Typography;

export default function ForgotPassword() {
  const { message } = App.useApp();
  const nav = useNavigate();
  const [step, setStep] = useState(0); // 0=输入用户名, 1=重置密码
  const [submitting, setSubmitting] = useState(false);
  const [resetToken, setResetToken] = useState("");
  const [adminContact, setAdminContact] = useState<{ phone: string; email: string }>({ phone: "", email: "" });
  const [form] = Form.useForm();

  useEffect(() => {
    api.adminContact().then(setAdminContact).catch(() => {});
  }, []);

  // Step 1: 获取重置令牌
  const onRequestToken = async (v: { username: string }) => {
    setSubmitting(true);
    try {
      const r = await api.forgotPassword(v.username);
      if (r.reset_token) {
        setResetToken(r.reset_token);
        message.success("重置令牌已生成");
        setStep(1);
      } else {
        message.info(r.message || "若账户存在，重置令牌已生成。请联系系统管理员获取。");
        // 仍然进入下一步以便手动输入 token
        setStep(1);
      }
    } catch {
      message.error("请求失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  // Step 2: 重置密码
  const onResetPassword = async (v: { token: string; newPassword: string; confirmPassword: string }) => {
    if (v.newPassword !== v.confirmPassword) {
      message.error("两次输入的密码不一致");
      return;
    }
    setSubmitting(true);
    try {
      await api.resetPassword(v.token, v.newPassword);
      message.success("密码已重置，请使用新密码登录");
      nav("/login");
    } catch (e: any) {
      const msg = e?.response?.data?.detail || "重置失败，请检查令牌是否有效";
      message.error(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.loginContainer}>
      <Card className={styles.glassCard} style={{ maxWidth: 460 }}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <Space direction="vertical" size={0}>
            <SafetyCertificateOutlined style={{ fontSize: 40, color: "#0052D9", marginBottom: 12 }} />
            <Title level={4} style={{ color: "rgba(0,0,0,0.9)", margin: 0, fontWeight: 700 }}>
              找回密码
            </Title>
          </Space>
        </div>

        <Steps current={step} size="small" style={{ marginBottom: 24 }}
          items={[{ title: "验证身份" }, { title: "重置密码" }]} />

        {step === 0 && (
          <Form layout="vertical" onFinish={onRequestToken} size="large">
            <Text type="secondary" style={{ display: "block", marginBottom: 16, fontSize: 13, textAlign: "center" }}>
              请输入您的用户名，系统将生成重置令牌。
            </Text>
            <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
              <Input prefix={<UserOutlined style={{ color: "#bfbfbf" }} />} placeholder="请输入用户名" style={{ borderRadius: 3 }} />
            </Form.Item>
            <Form.Item style={{ marginTop: 24, marginBottom: 12 }}>
              <Button type="primary" htmlType="submit" size="large" block loading={submitting}
                style={{ borderRadius: 3, background: "#0052D9", color: "#FFFFFF", borderColor: "#0052D9", fontWeight: 600 }}>
                获取重置令牌
              </Button>
            </Form.Item>
          </Form>
        )}

        {step === 1 && (
          <Form form={form} layout="vertical" onFinish={onResetPassword} size="large"
            initialValues={{ token: resetToken }}
          >
            <Form.Item name="token" rules={[{ required: true, message: "请输入重置令牌" }]}>
              <Input.TextArea placeholder="请粘贴重置令牌（由管理员交付）" style={{ borderRadius: 3 }} rows={3} />
            </Form.Item>
            <Form.Item name="newPassword" rules={[
              { required: true, message: "请输入新密码" },
              { min: 8, message: "密码至少 8 位" },
            ]}>
              <Input.Password prefix={<LockOutlined style={{ color: "#bfbfbf" }} />} placeholder="新密码（至少8位）" style={{ borderRadius: 3 }} />
            </Form.Item>
            <Form.Item name="confirmPassword" rules={[
              { required: true, message: "请确认新密码" },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue("newPassword") === value) return Promise.resolve();
                  return Promise.reject(new Error("两次输入的密码不一致"));
                },
              }),
            ]}>
              <Input.Password prefix={<LockOutlined style={{ color: "#bfbfbf" }} />} placeholder="确认新密码" style={{ borderRadius: 3 }} />
            </Form.Item>
            <Form.Item style={{ marginTop: 24, marginBottom: 12 }}>
              <Button type="primary" htmlType="submit" size="large" block loading={submitting}
                style={{ borderRadius: 3, background: "#0052D9", color: "#FFFFFF", borderColor: "#0052D9", fontWeight: 600 }}>
                重置密码
              </Button>
            </Form.Item>
          </Form>
        )}

        <div style={{ textAlign: "center", fontSize: 13, marginTop: 8 }}>
          <a onClick={() => nav("/login")} style={{ color: "#888" }}>返回登录</a>
          {" | "}
          <a onClick={() => { setStep(0); form.resetFields(); }} style={{ color: "#888" }}>重新验证</a>
        </div>

        <Divider style={{ margin: "12px 0" }} />
        <Alert
          type="info"
          showIcon
          icon={<PhoneOutlined />}
          message="无法自助找回？"
          description={
            <span style={{ fontSize: 12 }}>
              请联系系统管理员协助重置密码。
              {adminContact.phone && <span style={{ marginLeft: 8, fontWeight: 600 }}>电话：{adminContact.phone}</span>}
              {adminContact.email && <span style={{ marginLeft: 8, fontWeight: 600 }}>邮箱：{adminContact.email}</span>}
            </span>
          }
          style={{ borderRadius: 4, fontSize: 12 }}
        />
      </Card>
    </div>
  );
}
