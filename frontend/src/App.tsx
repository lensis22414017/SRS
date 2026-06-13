import { Layout, Menu, Dropdown, Avatar, Space } from "antd";
import {
  DashboardOutlined, DatabaseOutlined, SearchOutlined, ExperimentOutlined,
  LineChartOutlined, NodeIndexOutlined, SettingOutlined, UserOutlined, LogoutOutlined,
  BulbOutlined,
} from "@ant-design/icons";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import AiAssistant from "./components/AiAssistant";

const { Header, Sider, Content } = Layout;

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

export default function AppLayout() {
  const nav = useNavigate();
  const loc = useLocation();
  const { user, logout } = useAuth();
  const top = "/" + (loc.pathname.split("/")[1] || "");
  const selected = top === "/" ? "/" : NAV.find((n) => n.key === top)?.key || "/";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="dark" width={220} breakpoint="lg" collapsedWidth="0">
        <div style={{ color: "#fff", padding: "18px 16px", fontSize: 15, fontWeight: 700, lineHeight: 1.4, borderBottom: "1px solid rgba(255,255,255,.1)" }}>
          🌱 污染场地土壤生态-<br />生产功能重构监管系统
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[selected]}
          onClick={(e) => nav(e.key)} items={NAV} style={{ marginTop: 8 }} />
      </Sider>
      <Layout>
        <Header style={{ background: "#fff", display: "flex", justifyContent: "space-between", alignItems: "center", padding: "0 24px", boxShadow: "0 1px 4px rgba(0,0,0,.06)" }}>
          <div style={{ fontWeight: 600, color: "#0f3d6e" }}>污染场地监管平台</div>
          <Dropdown menu={{ items: [{ key: "logout", icon: <LogoutOutlined />, label: "退出登录", onClick: () => { logout(); nav("/login"); } }] }}>
            <Space style={{ cursor: "pointer" }}>
              <Avatar icon={<UserOutlined />} style={{ background: "#0f3d6e" }} />
              <span>{user?.display_name}（{user?.roles?.join(",")}）</span>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 16 }}>
          <Outlet />
        </Content>
      </Layout>
      <AiAssistant />
    </Layout>
  );
}
