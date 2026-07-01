import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider, App, Spin } from "antd";
import zhCN from "antd/locale/zh_CN";
import { AuthProvider, useAuth } from "./auth";
import AppLayout from "./App";
import "./theme/echarts";  // ECharts SVG 全局主题注册

// 路由级懒加载, 把 ECharts/leaflet/KaTeX 大依赖拆到各页面 chunk,
// 主 bundle 从 ~2.6MB 降到 ~1MB, 首屏只加载当前路由代码。
const Login = lazy(() => import("./pages/Login"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const SiteList = lazy(() => import("./pages/SiteList"));
const SiteDetail = lazy(() => import("./pages/SiteDetail"));
const DataUpload = lazy(() => import("./pages/DataUpload"));
const ObstacleAnalysis = lazy(() => import("./pages/ObstacleAnalysis"));
const ReconstructionAnalysis = lazy(() => import("./pages/ReconstructionAnalysis"));
const SSUIAnalysis = lazy(() => import("./pages/SSUIAnalysis"));
const TraceList = lazy(() => import("./pages/TraceList"));
const TraceDetail = lazy(() => import("./pages/TraceDetail"));
const SystemManagement = lazy(() => import("./pages/SystemManagement"));
const RecommendationPage = lazy(() => import("./pages/RecommendationPage"));
const FieldMappingPage = lazy(() => import("./pages/FieldMappingPage"));
const ErrorPage = lazy(() => import("./pages/ErrorPage"));
const Register = lazy(() => import("./pages/Register"));
const ForgotPassword = lazy(() => import("./pages/ForgotPassword"));
const DashboardScreen = lazy(() => import("./pages/DashboardScreen"));

const Fallback = () => (
  <div style={{ padding: 120, textAlign: "center" }}><Spin size="large" /></div>
);

function Protected({ children }: { children: JSX.Element }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/login" replace />;
}

function RequirePermission({ code, children }: { code: string; children: JSX.Element }) {
  const { user, hasPermission } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!hasPermission(code)) return <ErrorPage status={403} />;
  return children;
}

function AdminOnly({ children }: { children: JSX.Element }) {
  const { user, hasPermission } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!hasPermission("user:manage")) return <ErrorPage status={403} />;
  return children;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{ 
      token: {
        colorPrimary: "#0052D9",           // 腾讯蓝
        colorInfo: "#0052D9",              
        colorSuccess: "#00A870",           // TDesign 绿
        colorWarning: "#ED7B2F",           // TDesign 橙
        colorError: "#E34D59",             // TDesign 红
        colorBgBase: "#FFFFFF",
        colorBgLayout: "#F3F3F3",          // TDesign 底层灰
        colorBgContainer: "#FFFFFF", 
        colorBorderSecondary: "#E7E7E7",   // TDesign 边框线
        colorTextBase: "rgba(0,0,0,0.9)",
        colorTextSecondary: "rgba(0,0,0,0.6)",
        borderRadius: 3,                   // 极小圆角，工业感
        fontFamily: 'PingFang SC, Microsoft YaHei, Arial, sans-serif',
      }, components: {
        Card: { borderRadiusLG: 8, boxShadowTertiary: "0 2px 8px rgba(0, 0, 0, 0.04)" },
        Table: { headerBg: "#F3F3F3", headerColor: "rgba(0,0,0,0.9)", rowHoverBg: "#F3F3F3", borderColor: "#E7E7E7" },
        Button: { primaryShadow: "none", defaultShadow: "none", borderRadius: 3 },
        Menu: { itemSelectedBg: "#E0EBFF", itemSelectedColor: "#0052D9", activeBarBorderWidth: 0 },
        Tabs: { inkBarColor: "#0052D9", itemActiveColor: "#0052D9", itemSelectedColor: "#0052D9", titleFontSize: 14 },
        Tag: { defaultBg: "#F3F3F3", defaultColor: "rgba(0,0,0,0.9)" },
        Statistic: { contentFontSize: 24, titleFontSize: 14 },
        Descriptions: { labelBg: "#F3F3F3", labelColor: "rgba(0,0,0,0.6)" },
        Pagination: { itemActiveBg: "#E0EBFF" },
    } }}>
      {/* App provider 包裹, 让静态 message/notification 消费 theme context, 抑制 AntD warning */}
      <App>
        <AuthProvider>
          <BrowserRouter>
            <Suspense fallback={<Fallback />}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/forgot-password" element={<ForgotPassword />} />
                <Route path="/dashboard/screen" element={<Protected><DashboardScreen /></Protected>} />
                <Route path="/" element={<Protected><AppLayout /></Protected>}>
                  <Route index element={<Dashboard />} />
                  <Route path="sites" element={<RequirePermission code="data:query"><SiteList /></RequirePermission>} />
                  <Route path="sites/import" element={<RequirePermission code="data:input"><DataUpload /></RequirePermission>} />
                  <Route path="sites/import/wizard" element={<RequirePermission code="data:input"><FieldMappingPage /></RequirePermission>} />
                  <Route path="sites/:id" element={<RequirePermission code="data:query"><SiteDetail /></RequirePermission>} />
                  <Route path="obstacle" element={<RequirePermission code="data:query"><ObstacleAnalysis /></RequirePermission>} />
                  <Route path="reconstruction" element={<RequirePermission code="data:query"><ReconstructionAnalysis /></RequirePermission>} />
                  <Route path="ssui" element={<RequirePermission code="data:query"><SSUIAnalysis /></RequirePermission>} />
                  <Route path="recommend" element={<RequirePermission code="data:query"><RecommendationPage /></RequirePermission>} />
                  <Route path="trace" element={<RequirePermission code="workflow:view"><TraceList /></RequirePermission>} />
                  <Route path="trace/:id" element={<RequirePermission code="workflow:view"><TraceDetail /></RequirePermission>} />
                  <Route path="system" element={<AdminOnly><SystemManagement /></AdminOnly>} />
                  <Route path="*" element={<ErrorPage />} />
                </Route>
                <Route path="*" element={<ErrorPage />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </AuthProvider>
      </App>
    </ConfigProvider>
  </React.StrictMode>
);
