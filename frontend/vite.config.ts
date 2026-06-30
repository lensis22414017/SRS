import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 后端地址可由环境变量覆盖(默认 8000), 便于指向不同验收实例
const backend = process.env.VITE_BACKEND || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: true },
    },
  },
  // 裴总 P2(T12): manualChunks 把大依赖分离成独立 vendor chunk,
  // 避免单个 chunk 超 500KB(echarts/katex 是最大头), 首屏只加载当前路由 + 必要 vendor。
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          echarts: ["echarts", "echarts-for-react"],
          katex: ["katex", "react-katex"],
          antd: ["antd", "@ant-design/icons"],
          react: ["react", "react-dom", "react-router-dom"],
        },
      },
    },
  },
});
