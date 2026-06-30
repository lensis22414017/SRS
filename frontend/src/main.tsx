import React, { Suspense, lazy } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider, App, Spin } from "antd";
import zhCN from "antd/locale/zh_CN";
import { AuthProvider, useAuth } from "./auth";
import AppLayout from "./App";

// 裴总 P2(T12): 路由级懒加载, 把 ECharts/leaflet/KaTeX 大依赖拆到各页面 chunk,
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

const Fallback = () => (
  <div style={{ padding: 120, textAlign: "center" }}><Spin size="large" /></div>
);

function Protected({ children }: { children: JSX.Element }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/login" replace />;
}

function AdminOnly({ children }: { children: JSX.Element }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!user.roles?.includes("admin")) return <ErrorPage status={403} />;
  return children;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{ token: {
      colorPrimary: "#2c5282",           // 蓝灰科技主色(原 #0f3d6e 政务深蓝)
      colorInfo: "#3b82f6",              // 科技亮蓝
      colorSuccess: "#16a34a",
      colorWarning: "#f59e0b",
      colorError: "#dc2626",
      colorBgLayout: "#f1f5f9",          // 冷调中性灰底(加大中性灰比例, 科技感)
      colorBgContainer: "#ffffff",
      colorBorderSecondary: "#e2e8f0",   // 冷调浅灰边
      colorTextSecondary: "#475569",     // 靛灰次要文字
      borderRadius: 6,                   // 略柔和(原4政务严肃, 科技风6克制不滑向SaaS大圆角)
      fontFamily: '"PingFang SC", "Microsoft YaHei", -apple-system, "Segoe UI", sans-serif',
    }, components: {
      // 蓝灰科技风 component token — 冷调中性 + 精致层次(去政务深蓝表头, 去SaaS高饱和)
      Card: { borderRadiusLG: 8, boxShadowTertiary: "0 4px 12px rgba(44, 82, 130, 0.06)" },
      Table: { headerBg: "#f1f5f9", headerColor: "#2c5282", rowHoverBg: "#f8fafc", borderColor: "#e2e8f0" },
      Button: { primaryShadow: "none", defaultShadow: "none", borderRadius: 6 },
      Menu: { itemSelectedBg: "#eaf1fb", itemSelectedColor: "#2c5282", activeBarBorderWidth: 0 },
      Tabs: { inkBarColor: "#2c5282", itemActiveColor: "#2c5282", itemSelectedColor: "#2c5282", titleFontSize: 14 },
      Tag: { defaultBg: "#f1f5f9", defaultColor: "#475569" },
      Statistic: { contentFontSize: 24 },
      Descriptions: { labelBg: "#f1f5f9", labelColor: "#475569" },
      Pagination: { itemActiveBg: "#eaf1fb" },
    } }}>
      {/* 裴总 P2(T11): App provider 包裹, 让静态 message/notification 消费 theme context, 抑制 AntD warning */}
      <App>
        <AuthProvider>
          <BrowserRouter>
            <Suspense fallback={<Fallback />}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/" element={<Protected><AppLayout /></Protected>}>
                  <Route index element={<Dashboard />} />
                  <Route path="sites" element={<SiteList />} />
                  <Route path="sites/import" element={<DataUpload />} />
                  <Route path="sites/import/wizard" element={<FieldMappingPage />} />
                  <Route path="sites/:id" element={<SiteDetail />} />
                  <Route path="obstacle" element={<ObstacleAnalysis />} />
                  <Route path="reconstruction" element={<ReconstructionAnalysis />} />
                  <Route path="ssui" element={<SSUIAnalysis />} />
                  <Route path="recommend" element={<RecommendationPage />} />
                  <Route path="trace" element={<TraceList />} />
                  <Route path="trace/:id" element={<TraceDetail />} />
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
