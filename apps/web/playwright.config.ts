import { defineConfig } from '@playwright/test'

const baseURL = process.env.PLAYWRIGHT_BASE_URL

export default defineConfig({
  testDir: './e2e',
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR ?? './test-results',
  use: { baseURL: baseURL ?? 'http://127.0.0.1:8000', trace: 'retain-on-failure' },
  webServer: baseURL ? undefined : {
    command: 'cd ../.. && MODEL_PROVIDER=mock DEMO_API_KEY= uv run uvicorn builder_cup.main:create_app --factory --host 127.0.0.1 --port 8000',
    url: 'http://127.0.0.1:8000/api/health',
    reuseExistingServer: false,
  },
})
