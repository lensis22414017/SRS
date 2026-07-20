import { defineConfig, devices } from "@playwright/test";

/**
 * Round9 P0-5.6: Playwright 配置(为 SSUI 经济数据 e2e 验证)。
 * 项目已有 @playwright/test 依赖, 此前无 config; 此 config 仅做最小化基础设置。
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,        // SRS 后端单进程 SQLite, 避免并发冲突
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? "github" : "list",
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    storageState: undefined,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: process.env.CI ? undefined : {
    // 本地开发时自动起 dev server; CI 由 workflow 自行启动
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
