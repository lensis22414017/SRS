import { useState } from "react";
import { Layout, Menu, Dropdown, Avatar, Space, Typography, Breadcrumb, App as AntApp } from "antd";
import {
  DashboardOutlined, DatabaseOutlined, SearchOutlined, ExperimentOutlined,
  LineChartOutlined, NodeIndexOutlined, SettingOutlined, UserOutlined, LogoutOutlined,
  BulbOutlined,
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
        {/* 系统 Logo 区 */}
        <div style={{
          padding: "16px 16px 12px",
          borderBottom: "1px solid rgba(255,255,255,.08)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            {/* SVG 图标 — 重构之盾(深蓝底板+白盾+双叶+数据节点) */}
            <svg width="28" height="28" viewBox="0 0 512 512" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="24" y="24" width="464" height="464" rx="104" fill="#123B73" />
              <path d="M256 87C300 116 343 129 386 137V235C386 326 338 394 256 429C174 394 126 326 126 235V137C169 129 212 116 256 87Z"
                fill="none" stroke="#FFFFFF" strokeWidth="18" strokeLinejoin="round" />
              <path d="M267 225C230 225 196 203 188 168C225 163 260 178 275 207C277 214 275 220 267 225Z" fill="#19A980" />
              <path d="M270 205C289 174 327 158 363 166C357 202 324 228 282 229C270 225 266 216 270 205Z" fill="#DCA75A" />
              <circle cx="162" cy="251" r="14" fill="#65E0C0" stroke="#123B73" strokeWidth="8" />
              <circle cx="278" cy="159" r="14" fill="#65E0C0" stroke="#123B73" strokeWidth="8" />
              <circle cx="302" cy="304" r="14" fill="#65E0C0" stroke="#123B73" strokeWidth="8" />
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
