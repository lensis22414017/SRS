import { useState } from "react";
import { Layout, Menu, Dropdown, Avatar, Space, Typography, Breadcrumb, App as AntApp } from "antd";
import {
  DashboardOutlined, DatabaseOutlined, SearchOutlined, ExperimentOutlined,
  LineChartOutlined, NodeIndexOutlined, SettingOutlined, UserOutlined, LogoutOutlined,
  BulbOutlined, FolderOutlined,
} from "@ant-design/icons";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "./auth";
import AiAssistant from "./components/AiAssistant";
import "./App.css";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const ALL_NAV = [
  { key: "/", icon: <DashboardOutlined />, label: "数据概览", perm: null },
  { key: "/sites", icon: <DatabaseOutlined />, label: "场地管理", perm: "data:query" },
  { key: "/obstacle", icon: <SearchOutlined />, label: "障碍因子分析", perm: "data:query" },
  { key: "/reconstruction", icon: <ExperimentOutlined />, label: "功能重构分析", perm: "data:query" },
  { key: "/ssui", icon: <LineChartOutlined />, label: "SSUI评价", perm: "data:query" },
  { key: "/recommend", icon: <BulbOutlined />, label: "方案推荐", perm: "data:query" },
  { key: "/trace", icon: <NodeIndexOutlined />, label: "全流程追溯", perm: "workflow:view" },
  { key: "/files", icon: <FolderOutlined />, label: "文件管理", perm: "file:read" },
  { key: "/system", icon: <SettingOutlined />, label: "系统管理", perm: "user:manage" },
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
  "/files": "文件管理",
  "/system": "系统管理",
};

export default function AppLayout() {
  const nav = useNavigate();
  const loc = useLocation();
  const { user, logout, hasPermission } = useAuth();
  const { modal } = AntApp.useApp();
  const [collapsed, setCollapsed] = useState(false);
  const top = "/" + (loc.pathname.split("/")[1] || "");

  // 按权限过滤菜单
  const NAV = ALL_NAV.filter((n) => n.perm === null || hasPermission(n.perm));
  const selected = top === "/" ? "/" : NAV.find((n) => n.key === top)?.key || "/";

  const breadcrumbLabel = BREADCRUMB[selected] || "—";

  const handleLogout = () => {
    modal.confirm({
      title: "确认退出",
      content: "退出后需要重新登录，确认退出吗？",
      okText: "确认退出",
      cancelText: "取消",
      okButtonProps: { danger: true },
      onOk: () => {
        logout();
        nav("/login");
      },
    });
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      {/* ── 侧边栏(固定不随主体滚动) ──────────────────────── */}
      <Sider
        theme="dark"
        width={220}
        breakpoint="lg"
        collapsedWidth={collapsed ? 0 : 220}
        onCollapse={setCollapsed}
        style={{ position: "fixed", left: 0, top: 0, bottom: 0, height: "100vh", overflow: "auto", zIndex: 100 }}
      >
        {/* 导航菜单 — 按权限过滤 */}
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
          v1.0.1 · SRS
        </div>
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 0 : 220, transition: "margin-left 0.2s" }}>
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
              onClick: handleLogout,
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
          <div key={loc.pathname} className="page-transition-enter">
            <Outlet />
          </div>
        </Content>
      </Layout>

      <AiAssistant />
    </Layout>
  );
}
