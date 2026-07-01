import { useState, useEffect } from "react";
import {
  Form, Input, Button, Card, App, Typography, Space, Radio, Divider, Alert, Progress,
} from "antd";
import {
  UserOutlined, LockOutlined, SafetyCertificateOutlined,
  TeamOutlined, ExperimentOutlined, AuditOutlined,
  PhoneOutlined, MailOutlined, BankOutlined,
} from "@ant-design/icons";
import { useNavigate, useLocation } from "react-router-dom";
import { api } from "../api/client";
import styles from "./Login.module.css";

const { Title, Text } = Typography;

const ROLE_OPTIONS = [
  { value: "enterprise", label: "企业用户", icon: <TeamOutlined />,
    desc: "可录入本企业场地数据、生成方案、上传流程记录" },
  { value: "agency", label: "第三方机构", icon: <ExperimentOutlined />,
    desc: "检测/评估机构，上传授权项目数据" },
  { value: "regulator", label: "监管人员", icon: <AuditOutlined />,
    desc: "政府管理人员，查看监管范围内数据与追溯" },
];

function passwordStrength(pw: string): { percent: number; status: "exception" | "active" | "success"; text: string } {
  if (!pw) return { percent: 0, status: "exception", text: "" };
  let score = 0;
  if (pw.length >= 8) score += 25;
  if (pw.length >= 12) score += 10;
  if (/[A-Z]/.test(pw)) score += 20;
  if (/[a-z]/.test(pw)) score += 15;
  if (/[0-9]/.test(pw)) score += 20;
  if (/[^A-Za-z0-9]/.test(pw)) score += 10;
  const percent = Math.min(100, score);
  if (percent >= 80) return { percent, status: "success", text: "强" };
  if (percent >= 50) return { percent, status: "active", text: "中" };
  return { percent, status: "exception", text: "弱" };
}

export default function Register() {
  const { message } = App.useApp();
  const nav = useNavigate();
  const location = useLocation();
  const preselectedRole = (location.state as any)?.role || "";
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);
  const [pwStrength, setPwStrength] = useState<{ percent: number; status: "exception" | "active" | "success"; text: string }>({ percent: 0, status: "exception", text: "" });
  const [adminContact, setAdminContact] = useState<{ phone: string; email: string }>({ phone: "", email: "" });

  useEffect(() => {
    api.adminContact().then(setAdminContact).catch(() => {});
  }, []);

  const onFinish = async (v: any) => {
    if (v.password !== v.confirmPassword) {
      message.error("两次输入的密码不一致");
      return;
    }
    setSubmitting(true);
    try {
      await api.register({
        username: v.username,
        password: v.password,
        display_name: v.displayName,
        organization_name: v.organizationName,
        role_code: v.roleCode,
        contact_email: v.email || undefined,
        contact_phone: v.phone || undefined,
      });
      message.success("注册申请已提交，请等待管理员审核。如需加急请联系系统管理员。");
      nav("/login");
    } catch (e: any) {
      const msg = e?.response?.data?.detail || "注册失败，请稍后重试";
      message.error(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.loginContainer} style={{ paddingTop: 24, paddingBottom: 48 }}>
      <Card className={styles.glassCard} style={{ maxWidth: 520 }}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <Space direction="vertical" size={0}>
            <SafetyCertificateOutlined style={{ fontSize: 40, color: "#0052D9", marginBottom: 12 }} />
            <Title level={4} style={{ color: "rgba(0,0,0,0.9)", margin: 0, fontWeight: 700 }}>
              系统账号注册
            </Title>
            <Text type="secondary" style={{ fontSize: 13 }}>
              系统管理员不开放注册，仅限企业用户/第三方机构/监管人员
            </Text>
          </Space>
        </div>

        <Form form={form} layout="vertical" onFinish={onFinish} size="large">
          <Form.Item name="username" rules={[
            { required: true, message: "请输入用户名" },
            { min: 3, message: "用户名至少 3 位" },
            { max: 20, message: "用户名最多 20 位" },
            { pattern: /^[a-zA-Z0-9_-]+$/, message: "仅允许字母、数字、下划线、连字符" },
          ]}>
            <Input prefix={<UserOutlined style={{ color: "#bfbfbf" }} />} placeholder="用户名（3-20位字母数字）" style={{ borderRadius: 3 }} />
          </Form.Item>

          <Form.Item name="displayName" rules={[{ required: true, message: "请输入显示名" }]}>
            <Input placeholder="显示名称（如：XX公司检测部）" style={{ borderRadius: 3 }} />
          </Form.Item>

          <Form.Item name="organizationName" rules={[{ required: true, message: "请输入组织名称" }]}>
            <Input prefix={<BankOutlined style={{ color: "#bfbfbf" }} />} placeholder="组织/企业名称" style={{ borderRadius: 3 }} />
          </Form.Item>

          {/* 角色选择 — 不含管理员 */}
          <Form.Item name="roleCode" rules={[{ required: true, message: "请选择角色" }]}
            style={{ marginBottom: 8 }}
            initialValue={preselectedRole || undefined}
          >
            <Radio.Group style={{ width: "100%" }}>
              <Space direction="vertical" style={{ width: "100%" }}>
                {ROLE_OPTIONS.map((r) => (
                  <Radio key={r.value} value={r.value} style={{
                    padding: "10px 12px", borderRadius: 4, border: "1px solid #e8e8e8",
                    width: "100%", margin: 0, transition: "all 0.2s",
                  }}>
                    <Space>
                      <span style={{ color: "#0052D9", fontSize: 16 }}>{r.icon}</span>
                      <span style={{ fontWeight: 600 }}>{r.label}</span>
                      <Text type="secondary" style={{ fontSize: 12 }}>{r.desc}</Text>
                    </Space>
                  </Radio>
                ))}
              </Space>
            </Radio.Group>
          </Form.Item>
          <Text type="secondary" style={{ display: "block", marginBottom: 16, fontSize: 12, marginTop: -4 }}>
            系统管理员由系统初始化预置，不开放注册
          </Text>

          <Form.Item name="password" rules={[
            { required: true, message: "请输入密码" },
            { min: 8, message: "密码至少 8 位" },
          ]}>
            <Input.Password
              prefix={<LockOutlined style={{ color: "#bfbfbf" }} />}
              placeholder="密码（至少8位，含大小写字母+数字+特殊字符至少3类）"
              style={{ borderRadius: 3 }}
              onChange={(e) => setPwStrength(passwordStrength(e.target.value))}
            />
          </Form.Item>
          {pwStrength.text && (
            <div style={{ marginTop: -16, marginBottom: 16 }}>
              <Progress percent={pwStrength.percent} status={pwStrength.status} showInfo={false}
                size="small" strokeColor={pwStrength.status === "success" ? "#16a34a" : pwStrength.status === "active" ? "#f59e0b" : "#dc2626"} />
              <Text style={{ fontSize: 11, color: pwStrength.status === "success" ? "#16a34a" : pwStrength.status === "active" ? "#f59e0b" : "#dc2626" }}>
                密码强度：{pwStrength.text}
              </Text>
            </div>
          )}

          <Form.Item name="confirmPassword" rules={[
            { required: true, message: "请确认密码" },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue("password") === value) return Promise.resolve();
                return Promise.reject(new Error("两次输入的密码不一致"));
              },
            }),
          ]}>
            <Input.Password prefix={<LockOutlined style={{ color: "#bfbfbf" }} />} placeholder="确认密码" style={{ borderRadius: 3 }} />
          </Form.Item>

          <Form.Item name="email" rules={[{ type: "email", message: "请输入有效的邮箱地址" }]}>
            <Input prefix={<MailOutlined style={{ color: "#bfbfbf" }} />} placeholder="联系邮箱（选填）" style={{ borderRadius: 3 }} />
          </Form.Item>

          <Form.Item name="phone">
            <Input prefix={<PhoneOutlined style={{ color: "#bfbfbf" }} />} placeholder="联系电话（选填）" style={{ borderRadius: 3 }} />
          </Form.Item>

          <Form.Item style={{ marginTop: 16, marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" size="large" block loading={submitting}
              style={{ borderRadius: 3, background: "#0052D9", color: "#FFFFFF", borderColor: "#0052D9", fontWeight: 600 }}>
              提交注册
            </Button>
          </Form.Item>

          <div style={{ textAlign: "center", fontSize: 13, marginBottom: 16 }}>
            <a onClick={() => nav("/login")} style={{ color: "#888" }}>已有账号？返回登录</a>
          </div>
        </Form>

        <Divider style={{ margin: "8px 0" }} />

        {/* 管理员联系方式 */}
        <Alert
          type="info"
          showIcon
          icon={<PhoneOutlined />}
          message="审核联系"
          description={
            <span style={{ fontSize: 12 }}>
              提交后需等待系统管理员审核通过后方可登录。
              如有疑问请联系系统管理员：
              {adminContact.phone && <span style={{ marginLeft: 8, fontWeight: 600 }}>电话：{adminContact.phone}</span>}
              {adminContact.email && <span style={{ marginLeft: 8, fontWeight: 600 }}>邮箱：{adminContact.email}</span>}
              {!adminContact.phone && !adminContact.email && "联系方式暂未设置，请联系系统管理方。"}
            </span>
          }
          style={{ borderRadius: 4, fontSize: 12 }}
        />
      </Card>
    </div>
  );
}
