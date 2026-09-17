import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  use: {
    launchOptions: {
      args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
    },
    baseURL: "http://127.0.0.1:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1100 },
      },
    },
  ],
  webServer: {
    command: "npm run start",
    url: "http://127.0.0.1:3100/api/health",
    reuseExistingServer: !process.env.CI,
    env: { PORT: "3100", GEMINI_API_KEY: "", ANALYSIS_ACCESS_TOKEN: "" },
    timeout: 60_000,
  },
});
