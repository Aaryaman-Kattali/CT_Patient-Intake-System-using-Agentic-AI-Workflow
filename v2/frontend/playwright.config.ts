import { defineConfig, devices } from "@playwright/test";

// End-to-end tests against the REAL backend with a rule-based fake understander
// (tests/e2e_server.py): no Gemini calls, no API key, synthetic data only.
const API = "http://127.0.0.1:8001";
const WEB = "http://localhost:5173";

export default defineConfig({
  testDir: "e2e",
  workers: 1,
  timeout: 60_000,
  reporter: [["list"]],
  use: { baseURL: WEB, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `uv run --directory ../backend python -m tests.e2e_server --port 8001 --origin ${WEB}`,
      url: `${API}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "npx vite --port 5173 --strictPort",
      url: WEB,
      env: { VITE_API_URL: API },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
