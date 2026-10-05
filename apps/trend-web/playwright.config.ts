import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  // CI runners are slower than a workstation; these bounds only matter when a step is slow.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR ?? "test-results",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  reporter: "list",
});
