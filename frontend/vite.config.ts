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
});
