import { defineConfig } from '@playwright/test';

const PORT = 8000;
const BASE = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  retries: 0,
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
  use: {
    baseURL: BASE,
    headless: true,
    viewport: { width: 1280, height: 800 },
  },
  webServer: {
    command: `cd .. && python3 -m uvicorn novel_writer.server:app --port ${PORT}`,
    url: `${BASE}/api/status`,
    reuseExistingServer: true,
    timeout: 15000,
  },
});
