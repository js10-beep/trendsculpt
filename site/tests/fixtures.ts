import { test as base, expect } from "@playwright/test";
import type { Page } from "@playwright/test";

export { expect };
export type { Page };

// Each test may create only its own randomized example.com accounts. Track those
// credentials in memory and delete the accounts even when a browser assertion fails.
export const test = base.extend({
  page: async ({ page }, use, testInfo) => {
    const accounts = new Map<string, string>();
    const pending = new Set<Promise<void>>();
    const origin = new URL(
      process.env.TRENDSCULPT_TEST_URL || "http://127.0.0.1:5174",
    ).origin;
    let activeEmail: string | undefined;
    page.on("requestfailed", (request) => {
      const url = new URL(request.url());
      if (url.origin === origin && url.pathname.startsWith("/api/")) {
        console.log("LIVE_CHECK_HTTP " + JSON.stringify({
          method: request.method(),
          path: url.pathname.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/gi, ":id"),
          status: 0,
        }));
      }
    });
    page.on("response", (response) => {
      const request = response.request();
      const url = new URL(request.url());
      const path = url.pathname;
      if (
        url.origin === origin &&
        path.startsWith("/api/") &&
        response.status() >= 400
      ) {
        const route = path.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/gi, ":id");
        console.log(
          "LIVE_CHECK_HTTP " +
            JSON.stringify({
              method: request.method(),
              path: route,
              status: response.status(),
            }),
        );
      }
      if (
        response.status() !== 200 ||
        url.origin !== origin ||
        ![
          "/api/auth/signup",
          "/api/auth/login",
          "/api/auth/logout",
          "/api/auth/recover",
          "/api/account",
        ].includes(path)
      )
        return;
      const observe = (async () => {
        if (path === "/api/account" && request.method() === "DELETE") {
          if (activeEmail) accounts.delete(activeEmail);
          activeEmail = undefined;
          return;
        }
        if (path === "/api/auth/logout") {
          activeEmail = undefined;
          return;
        }
        const fields = request.postDataJSON();
        const email = String(fields?.email ?? "").toLowerCase();
        if (!/^test-[0-9a-f-]+@example\.com$/.test(email)) return;
        if (
          path === "/api/auth/signup" ||
          (path === "/api/auth/recover" && accounts.has(email))
        ) {
          accounts.set(email, String(fields.password));
        }
        if (
          path === "/api/auth/signup" ||
          (path === "/api/auth/login" && accounts.has(email))
        )
          activeEmail = email;
        if (path === "/api/auth/recover") activeEmail = undefined;
        const result = await response.json();
        if (process.env.GITHUB_ACTIONS && result.recoveryCode) {
          console.log(`::add-mask::${result.recoveryCode}`);
        }
      })().catch(() => {});
      pending.add(observe);
      void observe.finally(() => pending.delete(observe));
    });
    try {
      await use(page);
    } finally {
      if (testInfo.status !== testInfo.expectedStatus && !page.isClosed()) {
        const diagnostics = await page.evaluate(() => ({
          route: location.pathname.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/gi, ":id"),
          processing: !!document.querySelector(".processing"),
          mediaPreview: !!document.querySelector(".media-preview"),
          unsupportedVideo: document.body.innerText.includes("This video cannot be played in this browser."),
          missingUpload: document.body.innerText.includes("Upload your image or video first."),
          hasAlert: !!document.querySelector('[role="alert"]'),
          invalidInputs: document.querySelectorAll("input:invalid").length,
          invalidFields: Array.from(document.querySelectorAll<HTMLInputElement>("input:invalid")).map((input) => ({
            label: input.closest("label")?.textContent?.trim(),
            type: input.type,
            length: input.value.length,
            missing: input.validity.valueMissing,
            typeMismatch: input.validity.typeMismatch,
            tooShort: input.validity.tooShort,
            tooLong: input.validity.tooLong,
            patternMismatch: input.validity.patternMismatch,
          })),
          recoveryPending: Array.from(document.querySelectorAll("button")).some((b) => b.textContent?.includes("Reset my password") && b.disabled),
        })).catch(() => null);
        if (diagnostics) console.log("LIVE_CHECK_UI " + JSON.stringify(diagnostics));
      }
      await Promise.all([...pending]);
      const failures: string[] = [];
      for (const [email, password] of accounts) {
        let removed = false;
        for (let attempt = 0; attempt < 4 && !removed; attempt++) {
          try {
            const login = await page.request.post("/api/auth/login", {
              data: { email, password },
              headers: { Origin: origin },
              timeout: 20000,
            });
            if (login.status() === 200) {
              const deletion = await page.request.delete("/api/account", {
                data: { password },
                headers: { Origin: origin },
                timeout: 20000,
              });
              removed = deletion.status() === 200;
            }
          } catch {
            // Allow a short redeployment or free-server wakeup to finish.
          }
          if (!removed)
            await new Promise((resolve) => setTimeout(resolve, 3000));
        }
        if (!removed)
          failures.push("Could not delete a temporary test account.");
      }
      if (failures.length) throw new Error(failures.join(" "));
    }
  },
});
