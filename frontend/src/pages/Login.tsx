import { useState } from "react";
import { Form, Input, Button, Card, App, Typography, Space, Tag, Row, Col } from "antd";
import {
  UserOutlined, LockOutlined, SafetyCertificateOutlined,
  CrownOutlined, TeamOutlined, ExperimentOutlined, AuditOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import styles from "./Login.module.css";

const { Title, Text } = Typography;

const ROLE_CARDS = [
  { icon: <CrownOutlined />, label: "系统管理员", desc: "全功能访问，用户审核，系统配置", color: "#2c5282", username: "admin" },
  { icon: <TeamOutlined />, label: "企业用户", desc: "场地数据录入，方案生成，流程上传", color: "#1B7837", username: "" },
  { icon: <ExperimentOutlined />, label: "第三方机构", desc: "检测/评估，授权项目数据上传", color: "#3680ae", username: "" },
  { icon: <AuditOutlined />, label: "监管人员", desc: "政府监管，查看与审计", color: "#E08214", username: "" },
];

export default function Login() {
  const { message } = App.useApp();
  const nav = useNavigate();
  const { setSession } = useAuth();

  const [submitting, setSubmitting] = useState(false);

  const onFinish = async (v: { username: string; password: string }) => {
    setSubmitting(true);
    try {
      const r = await api.login(v.username, v.password);
      setSession(r.access_token, r.user);
      message.success(`欢迎回来，${r.user.display_name}`);
      nav("/");
    } catch {
      message.error("用户名或密码错误");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.loginContainer}>
      <Card className={styles.glassCard}>
        <div style={{ textAlign: "center", marginBottom: 24 }}>
          <Space direction="vertical" size={0}>
            <SafetyCertificateOutlined style={{ fontSize: 40, color: "#0052D9", marginBottom: 12 }} />
            <Title level={4} style={{ color: "rgba(0,0,0,0.9)", margin: 0, fontWeight: 700, letterSpacing: 1 }}>
              污染场地土壤生态-生产
            </Title>
            <Title level={5} style={{ color: "#0052D9", margin: "4px 0 0 0", fontWeight: 500 }}>
              功能重构监管系统
            </Title>
          </Space>
        </div>

        {/* 四类角色身份选择 — 点击预填用户名 */}
        <Row gutter={[8, 8]} style={{ marginBottom: 24 }}>
          {ROLE_CARDS.map((r, idx) => (
            <Col span={6} key={r.label}>
              <div style={{
                textAlign: "center", padding: "8px 4px", borderRadius: 4,
                background: "#f8f9fb", border: `2px solid ${r.color}20`,
                cursor: "pointer", transition: "all 0.2s",
              }}
                onMouseEnter={(e) => { e.currentTarget.style.border = `2px solid ${r.color}`; e.currentTarget.style.background = r.color + "10"; }}
                onMouseLeave={(e) => { e.currentTarget.style.border = `2px solid ${r.color}20`; e.currentTarget.style.background = "#f8f9fb"; }}
                onClick={() => {
                  if (r.username) {
                    // 获取表单实例并设置用户名
                    const form = document.querySelector('form');
                    if (form) {
                      const usernameInput = form.querySelector('input[id="username"], input[placeholder*="用户名"]') as HTMLInputElement;
                      if (usernameInput) {
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                        nativeInputValueSetter?.call(usernameInput, r.username);
                        usernameInput.dispatchEvent(new Event('input', { bubbles: true }));
                      }
                    }
                  }
                  // 系统管理员直接聚焦密码框，其他角色提示注册
                  if (r.label === "系统管理员") {
                    message.info("已选择系统管理员身份，输入密码登录");
                  } else {
                    message.info(`${r.label}请先注册账号，等待管理员审核后登录`);
                  }
                }}
              >
                <div style={{ fontSize: 18, color: r.color, marginBottom: 2 }}>{r.icon}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#333", lineHeight: 1.3 }}>{r.label}</div>
                <div style={{ fontSize: 9, color: "#999", lineHeight: 1.2, marginTop: 2 }}>{r.desc}</div>
              </div>
            </Col>
          ))}
        </Row>

        <Form layout="vertical" onFinish={onFinish}>
          <Form.Item name="username" rules={[{ required: true, message: "请输入用户名" }]}>
            <Input
              prefix={<UserOutlined style={{ color: "#bfbfbf" }} />}
              size="large"
              placeholder="请输入用户名"
              style={{ borderRadius: 3 }}
            />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: "请输入密码" }]}>
            <Input.Password
              prefix={<LockOutlined style={{ color: "#bfbfbf" }} />}
              size="large"
              placeholder="请输入密码"
              style={{ borderRadius: 3 }}
            />
          </Form.Item>
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: -12, marginBottom: 24, fontSize: 13 }}>
            <a onClick={() => nav("/register")}>还没有账号？立即注册</a>
            <a onClick={() => nav("/forgot-password")} style={{ color: "#888" }}>忘记密码？</a>
          </div>
          <Form.Item style={{ marginTop: 8, marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" size="large" block loading={submitting}
              style={{ borderRadius: 3, background: "#0052D9", color: "#FFFFFF", borderColor: "#0052D9", fontWeight: 600 }}>
              系统登录
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <div className={styles.footerText}>
        © {new Date().getFullYear()} 污染场地土壤生态-生产功能重构评价课题组 版权所有
      </div>
    </div>
  );
}
