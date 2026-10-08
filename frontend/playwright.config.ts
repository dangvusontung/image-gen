import os from 'node:os'
import path from 'node:path'
import { defineConfig } from '@playwright/test'

const backendDir = path.resolve(import.meta.dirname, '../backend')
const dataDir = path.join(os.tmpdir(), `charstudio-e2e-${process.pid}`)
const venvBin = path.join(backendDir, 'venv/bin')

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:5180',
    channel: process.env.PW_CHANNEL ?? 'chrome',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `${venvBin}/alembic upgrade head && ${venvBin}/uvicorn app.main:app --host 127.0.0.1 --port 8100`,
      cwd: backendDir,
      url: 'http://127.0.0.1:8100/health',
      // Blank keys: E2E must never reach paid providers, even if the shell exports real keys.
      env: { DATA_DIR: dataDir, CORS_ORIGINS: 'http://127.0.0.1:5180', GEMINI_API_KEY: '', BFL_API_KEY: '', MOCK_DELAY_SECONDS: '0.3', SPEND_LIMIT_USD_PER_DAY: '0' },
      reuseExistingServer: false,
    },
    {
      command: 'npx vite --host 127.0.0.1 --port 5180 --strictPort',
      url: 'http://127.0.0.1:5180',
      env: { API_PROXY_TARGET: 'http://127.0.0.1:8100' },
      reuseExistingServer: false,
    },
  ],
})
