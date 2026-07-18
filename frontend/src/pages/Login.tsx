import { useState, useEffect } from "react";
import { Form, Input, Button, Card, App, Typography, Space, Row, Col, Modal } from "antd";
import {
  UserOutlined, LockOutlined, SafetyCertificateOutlined,
  CrownOutlined, TeamOutlined, ExperimentOutlined, AuditOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import styles from "./Login.module.css";

const { Title } = Typography;

const ROLE_CARDS = [
  { icon: <CrownOutlined />, label: "系统管理员",
    desc: "全功能访问，用户审核，系统配置", color: "#2c5282",
    username: "admin", roleCode: "admin" },
  { icon: <TeamOutlined />, label: "企业用户",
    desc: "方案上传与审批，场地修复施工，监理数据录入", color: "#1B7837",
    username: "", roleCode: "enterprise" },
  { icon: <ExperimentOutlined />, label: "第三方机构",
    desc: "检测/评估，授权项目数据上传", color: "#3680ae",
    username: "", roleCode: "agency" },
  { icon: <AuditOutlined />, label: "监管人员",
    desc: "政府监管，查看与审计", color: "#E08214",
    username: "", roleCode: "regulator" },
];

export default function Login() {
  const { message } = App.useApp();
  const nav = useNavigate();
  const { setSession } = useAuth();
  const [form] = Form.useForm();

  const [submitting, setSubmitting] = useState(false);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);

  // R3 审计第六类: 检测首启状态, needs_setup=true 时跳转到首启向导
  useEffect(() => {
    api.setupStatus().then((s) => {
      if (s.needs_setup) {
        nav("/setup");
      }
    }).catch(() => { /* 静默忽略, 不阻断登录页 */ });
  }, [nav]);

  // 接收 setup 页面传来的用户名
  useEffect(() => {
    const state = (history.state || {}) as { username?: string };
    if (state.username) {
      form.setFieldsValue({ username: state.username });
    }
  }, [form]);

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

  const handleRoleCardClick = (role: typeof ROLE_CARDS[0]) => {
    setSelectedRole(role.label);
    if (role.username) {
      // 系统管理员: 自动填入用户名，提示输入密码
      form.setFieldsValue({ username: role.username });
      message.info(`已选择"${role.label}"身份，请输入密码登录。初次登录请修改密码。`);
    } else {
      // 其他角色: 引导注册
      Modal.confirm({
        title: `以"${role.label}"身份使用系统`,
        content: "您需要先注册账号，等待管理员审核通过后方可登录。",
        okText: "前往注册",
        cancelText: "取消",
        onOk: () => nav("/register", { state: { role: role.roleCode } }),
      });
    }
  };

  const getCardStyle = (role: typeof ROLE_CARDS[0]) => {
    const isSelected = selectedRole === role.label;
    return {
      textAlign: "center" as const,
      padding: "10px 4px",
      borderRadius: 6,
      background: isSelected ? role.color + "15" : "#f8f9fb",
      border: isSelected ? `2px solid ${role.color}` : `2px solid ${role.color}20`,
      cursor: "pointer",
      transition: "all 0.25s ease",
      transform: isSelected ? "translateY(-2px)" : "none",
      boxShadow: isSelected ? `0 4px 12px ${role.color}30` : "none",
    };
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

        {/* 四类角色身份选择 — 点击可选中/跳转注册 */}
        <Row gutter={[8, 8]} style={{ marginBottom: 24 }}>
          {ROLE_CARDS.map((r) => (
            <Col span={6} key={r.label}>
              <div
                style={getCardStyle(r)}
                onMouseEnter={(e) => {
                  if (selectedRole !== r.label) {
                    e.currentTarget.style.border = `2px solid ${r.color}`;
                    e.currentTarget.style.background = r.color + "10";
                    e.currentTarget.style.transform = "translateY(-1px)";
                  }
                }}
                onMouseLeave={(e) => {
                  if (selectedRole !== r.label) {
                    e.currentTarget.style.border = `2px solid ${r.color}20`;
                    e.currentTarget.style.background = "#f8f9fb";
                    e.currentTarget.style.transform = "none";
                  }
                }}
                onClick={() => handleRoleCardClick(r)}
              >
                <div style={{ fontSize: 18, color: r.color, marginBottom: 2 }}>{r.icon}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: "#333", lineHeight: 1.3, whiteSpace: "nowrap" }}>{r.label}</div>
                <div style={{ fontSize: 9, color: "#999", lineHeight: 1.4, marginTop: 2 }}>{r.desc}</div>
              </div>
            </Col>
          ))}
        </Row>

        <Form form={form} layout="vertical" onFinish={onFinish}>
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
        © {new Date().getFullYear()} 生态环境部土壤与农业农村生态环境监管技术中心 版权所有
      </div>
    </div>
  );
}
