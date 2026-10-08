import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
const targetURL = process.env.TRENDSCULPT_TEST_URL;
export default defineConfig({
  testDir: "tests",
  timeout: 45000,
  use: {
    baseURL: targetURL || "http://127.0.0.1:5174",
    headless: true,
    launchOptions: {
      executablePath: existsSync("/usr/bin/chromium")
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
