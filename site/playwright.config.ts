import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
const targetURL = process.env.TRENDSCULPT_TEST_URL;
const useChrome = process.env.TRENDSCULPT_TEST_BROWSER === "chrome";
export default defineConfig({
  testDir: "tests",
  timeout: targetURL ? 120000 : 45000,
  expect: { timeout: targetURL ? 20000 : 5000 },
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: targetURL || "http://127.0.0.1:5174",
    headless: true,
    channel: useChrome ? "chrome" : undefined,
    navigationTimeout: targetURL ? 60000 : 30000,
    launchOptions: {
      executablePath: !useChrome && existsSync("/usr/bin/chromium")
        ? "/usr/bin/chromium"
        : undefined,
      args: ["--no-sandbox"],
    },
  },
  webServer: targetURL
    ? undefined
    : {
        command: "npm run dev",
        url: "http://127.0.0.1:5174",
        reuseExistingServer: !process.env.CI,
        timeout: 45000,
      },
});
