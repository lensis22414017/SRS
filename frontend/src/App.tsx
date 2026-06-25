import { Layout, Menu, Dropdown, Avatar, Space, Typography, Breadcrumb } from "antd";
import {
  DashboardOutlined, DatabaseOutlined, SearchOutlined, ExperimentOutlined,
  LineChartOutlined, NodeIndexOutlined, SettingOutlined, UserOutlined, LogoutOutlined,
  BulbOutlined, AppstoreOutlined,
} from "@ant-design/icons";
import { Outlet, useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "./auth";
import AiAssistant from "./components/AiAssistant";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const NAV = [
  { key: "/", icon: <DashboardOutlined />, label: "数据概览" },
  { key: "/sites", icon: <DatabaseOutlined />, label: "场地管理" },
  { key: "/obstacle", icon: <SearchOutlined />, label: "障碍因子分析" },
  { key: "/reconstruction", icon: <ExperimentOutlined />, label: "功能重构分析" },
  { key: "/ssui", icon: <LineChartOutlined />, label: "SSUI评价" },
  { key: "/recommend", icon: <BulbOutlined />, label: "方案推荐" },
  { key: "/trace", icon: <NodeIndexOutlined />, label: "全流程追溯" },
  { key: "/system", icon: <SettingOutlined />, label: "系统管理" },
];

/** 路由 → 面包屑标签 */
const BREADCRUMB: Record<string, string> = {
  "/": "数据概览",
  "/sites": "场地管理",
  "/obstacle": "障碍因子分析",
  "/reconstruction": "功能重构分析",
  "/ssui": "SSUI 可持续利用评价",
  "/recommend": "方案推荐",
  "/trace": "全流程追溯",
  "/system": "系统管理",
};

export default function AppLayout() {
  const nav = useNavigate();
  const loc = useLocation();
  const { user, logout } = useAuth();
  const top = "/" + (loc.pathname.split("/")[1] || "");
  const selected = top === "/" ? "/" : NAV.find((n) => n.key === top)?.key || "/";

  const breadcrumbLabel = BREADCRUMB[selected] || "—";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {/* ── 侧边栏 ────────────────────────────────────────── */}
      <Sider
        theme="dark"
        width={220}
        breakpoint="lg"
        collapsedWidth="0"
        style={{ display: "flex", flexDirection: "column" }}
      >
        {/* 系统 Logo 区 */}
        <div style={{
          padding: "16px 16px 12px",
          borderBottom: "1px solid rgba(255,255,255,.08)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            {/* SVG 图标 — 污染场地监管主题（盾牌+叶子） */}
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M14 2L3 7v7c0 6.25 4.75 12.1 11 13.5C20.25 26.1 25 20.25 25 14V7L14 2z"
                fill="#1d6fb8" stroke="#0f3d6e" strokeWidth="1" />
              <path d="M14 8c-2.5 0-4.5 1.5-5 4 0 0 1 0.5 2.5 0.5C13 12.5 14 10 16.5 10c1.5 0 2.5 0.5 2.5 0.5C18.5 9.5 16.5 8 14 8z"
                fill="#4ade80" />
              <path d="M11.5 13c0 2.5 1.2 4.5 2.5 5.5 1.3-1 2.5-3 2.5-5.5H11.5z"
                fill="#4ade80" />
            </svg>
            <div>
              <div style={{ color: "#fff", fontWeight: 700, fontSize: 13, lineHeight: 1.2 }}>
                污染场地监管系统
              </div>
              <div style={{ color: "rgba(255,255,255,.45)", fontSize: 10 }}>
                土壤生态-生产功能重构
              </div>
            </div>
          </div>
        </div>

        {/* 导航菜单 */}
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected]}
          onClick={(e) => nav(e.key)}
          items={NAV}
          style={{ marginTop: 4, flex: 1, borderRight: 0 }}
        />

        {/* 版本号 */}
        <div style={{
          padding: "8px 16px",
          borderTop: "1px solid rgba(255,255,255,.08)",
          color: "rgba(255,255,255,.3)",
          fontSize: 10,
          userSelect: "none",
        }}>
          v0.1.0 · SRS MVP
        </div>
      </Sider>

      <Layout>
        {/* ── 顶部 Header ──────────────────────────────────── */}
        <Header style={{
          background: "#fff",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "0 24px",
          boxShadow: "0 1px 4px rgba(0,0,0,.06)",
          height: 52,
          lineHeight: "52px",
        }}>
          {/* 面包屑 */}
          <Breadcrumb
            items={[
              { title: <span style={{ color: "#888", fontSize: 12 }}>监管平台</span> },
              { title: <span style={{ color: "#0f3d6e", fontSize: 12, fontWeight: 600 }}>{breadcrumbLabel}</span> },
            ]}
          />

          {/* 用户信息 */}
          <Dropdown menu={{
            items: [{
              key: "logout",
              icon: <LogoutOutlined />,
              label: "退出登录",
              onClick: () => { logout(); nav("/login"); },
            }],
          }}>
            <Space style={{ cursor: "pointer" }}>
              <Avatar
                icon={<UserOutlined />}
                size={28}
                style={{ background: "#0f3d6e" }}
              />
              <span style={{ fontSize: 13 }}>
                {user?.display_name}
                <Text type="secondary" style={{ fontSize: 11, marginLeft: 4 }}>
                  ({user?.roles?.join(",")})
                </Text>
              </span>
            </Space>
          </Dropdown>
        </Header>

        {/* ── 内容区 ───────────────────────────────────────── */}
        <Content style={{ margin: 16, minHeight: "calc(100vh - 52px - 32px)" }}>
          <Outlet />
        </Content>
      </Layout>

      <AiAssistant />
    </Layout>
  );
}
