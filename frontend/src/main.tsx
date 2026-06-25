import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { AuthProvider, useAuth } from "./auth";
import AppLayout from "./App";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import SiteList from "./pages/SiteList";
import SiteDetail from "./pages/SiteDetail";
import DataUpload from "./pages/DataUpload";
import ObstacleAnalysis from "./pages/ObstacleAnalysis";
import ReconstructionAnalysis from "./pages/ReconstructionAnalysis";
import SSUIAnalysis from "./pages/SSUIAnalysis";
import TraceList from "./pages/TraceList";
import TraceDetail from "./pages/TraceDetail";
import SystemManagement from "./pages/SystemManagement";
import RecommendationPage from "./pages/RecommendationPage";
import FieldMappingPage from "./pages/FieldMappingPage";
import ErrorPage from "./pages/ErrorPage";

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
      colorPrimary: "#0f3d6e",
      borderRadius: 4,  // 政府严肃风格(小圆角,去AI味,问题10)
      fontFamily: '"PingFang SC", "Microsoft YaHei", -apple-system, "Segoe UI", sans-serif',  // 政务中文字体
    } }}>
      <AuthProvider>
        <BrowserRouter>
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
        </BrowserRouter>
      </AuthProvider>
    </ConfigProvider>
  </React.StrictMode>
);
