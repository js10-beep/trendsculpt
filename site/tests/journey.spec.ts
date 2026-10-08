import { test, expect, Page } from "./fixtures";
const password = "Creator-test-password-42";
async function signup(page: Page, name: string) {
  await page.goto("/signup");
  await page.getByLabel("Full name").fill(name);
  const email = "test-" + crypto.randomUUID() + "@example.com";
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create my account" }).click();
  await expect(
    page.getByRole("heading", { name: "Your account recovery code." }),
  ).toBeVisible();
  const code = await page.locator(".recovery-code").innerText();
  await page.getByLabel("I have saved my recovery code.").check();
  await page.getByRole("button", { name: "Continue to my workspace" }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Start analyzing" }).click();
  await expect(
    page.getByRole("heading", {
      name: "Welcome back, " + name.split(" ")[0] + ".",
    }),
  ).toBeVisible();
  return { email, code };
}
async function logout(page: Page) {
  await page.getByRole("button", { name: /Free account/ }).click();
  await page.goto("/login");
}
test("secure creator journey persists and deletes with password confirmation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Shape your content/ }),
  ).toBeVisible();
  const { email } = await signup(page, "Jamie Creator");
  await page.screenshot({
    path: "/tmp/trendsculpt-new-dashboard.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Analyze new content" }).click();
  await page
    .getByLabel("Caption or content")
    .fill(
      "How to build 3 habits for creators? Save this practical guide and share your favorite habit. #creators",
    );
  await page.getByLabel("Topic / category").fill("creative habits");
  await page.getByLabel("Target audience").fill("creators");
  await page.getByRole("button", { name: "Analyze my content" }).click();
  await expect(
    page.getByRole("heading", { name: "Your content intelligence report." }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Evidence, with context." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Save analysis", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Saved to library" }),
  ).toBeDisabled();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Your content intelligence report." }),
  ).toBeVisible();
  await page.screenshot({
    path: "/tmp/trendsculpt-new-report.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Use this version" }).first().click();
  await expect(page.getByText(/Model estimate/)).toBeVisible();
  await page.getByRole("button", { name: "Save revision" }).click();
  await expect(
    page.getByRole("button", { name: "Saved to library" }),
  ).toBeDisabled();
  await page
    .getByRole("link", { name: "Content library", exact: true })
    .click();
  await expect(
    page.getByText("2 saved analyses", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Search analyses").fill("zzzzzz");
  await expect(
    page.getByRole("heading", { name: "Nothing matches these filters." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).first().click();
  await logout(page);
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill("wrong-password-42");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("incorrect");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await page
    .getByRole("link", { name: "Content library", exact: true })
    .click();
  await expect(
    page.getByText("2 saved analyses", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Delete How to build/ })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Delete analysis", exact: true })
    .click();
  await expect(
    page.getByText("1 saved analysis", { exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Settings", exact: true }).click();
  await page.getByLabel("Confirm account password").fill(password);
  await page
    .getByRole("button", { name: "Delete account", exact: true })
    .click();
  await page.getByRole("button", { name: "Delete my data" }).click();
  await expect(page).toHaveURL(/signup/);
  expect(errors).toEqual([]);
});
test("password recovery uses one-time codes and supports a fresh login", async ({
  page,
}) => {
  const { email, code } = await signup(page, "Recovery Creator");
  await logout(page);
  await page.getByRole("link", { name: "Forgot password?" }).click();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Recovery code", { exact: true }).fill(code);
  await page
    .getByLabel("New password", { exact: true })
    .fill("New-creator-password-42");
  await page
    .getByLabel("Confirm new password", { exact: true })
    .fill("New-creator-password-42");
  await page.getByRole("button", { name: "Reset my password" }).click();
  await expect(
    page.getByRole("heading", { name: "Your account recovery code." }),
  ).toBeVisible();
  expect(await page.locator(".recovery-code").innerText()).not.toBe(code);
  await page.getByLabel("I have saved my recovery code.").check();
  await page.getByRole("button", { name: "Continue to my workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back.", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("New-creator-password-42");
  await page.getByRole("button", { name: "Log in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back, Recovery." }),
  ).toBeVisible();
});
test("mobile navigation and actual image/video measurement work", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signup(page, "Alex Creator");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Toggle sidebar" }).click();
  await page
    .getByRole("link", { name: "Content library", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Your first content is waiting to be sculpted.",
    }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Analyze your first post" }).click();
  await page.getByRole("button", { name: "Image", exact: true }).click();
  await page.getByLabel("Upload media").setInputFiles({
    name: "invalid.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("invalid"),
  });
  await expect(page.getByRole("alert")).toContainText("isn’t supported");
  await page
    .getByLabel("Upload media")
    .setInputFiles("tests/fixtures/cover.png");
  await expect(page.getByAltText("Your uploaded content")).toBeVisible();
  await page.getByRole("button", { name: "Analyze my content" }).click();
  await expect(
    page.getByRole("heading", { name: "We looked at the actual pixels." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page
    .getByRole("button", { name: "Save analysis", exact: true })
    .click();
  await page.reload();
  await expect(page.getByAltText("Analyzed content")).toBeVisible();
  await page.getByRole("link", { name: "Analyze another" }).click();
  await page.getByRole("button", { name: "Video", exact: true }).click();
  await page
    .getByLabel("Upload media")
    .setInputFiles("tests/fixtures/short.mp4");
  await page.getByRole("button", { name: "Analyze my content" }).click();
  await expect(
    page.getByRole("heading", { name: "We looked at the actual pixels." }),
  ).toBeVisible();
  await expect(page.locator("video")).toBeVisible();
});
test("brands can update preferences and train/delete a private dataset", async ({
  page,
}) => {
  await signup(page, "Brand Studio");
  await page.getByRole("link", { name: "Profile", exact: true }).click();
  await page.getByLabel("Creator type").selectOption("Brand");
  await page.getByLabel("Primary platform").selectOption("YouTube Shorts");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status")).toContainText("preferences are saved");
  await page.reload();
  await expect(page.getByLabel("Creator type")).toHaveValue("Brand");
  await page.getByRole("link", { name: "Data & models", exact: true }).click();
  const csv =
    "caption,impressions,likes,comments\n" +
    Array.from(
      { length: 30 },
      (_, i) => `Brand content strategy ${i},1000,${30 + i * 3},${i}`,
    ).join("\n");
  await page.getByLabel("CSV dataset").setInputFiles({
    name: "brand-observations.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.getByLabel("I have permission to use these records.").check();
  await page.getByRole("button", { name: "Train my private model" }).click();
  await expect(page.getByText("Instagram · 30 records")).toBeVisible();
  await page.getByRole("button", { name: "Delete Instagram dataset" }).click();
  await page
    .getByRole("button", { name: "Delete dataset", exact: true })
    .click();
  await expect(page.getByText("Instagram · 30 records")).toHaveCount(0);
});
test("public routes, source ledger and tablet layout stay usable", async ({
  page,
}) => {
  for (const route of [
    "features",
    "impact",
    "about",
    "founder",
    "faqs",
    "privacy",
    "terms",
  ]) {
    await page.goto("/" + route);
    await expect(page.locator("h1")).toBeVisible();
  }
  await page.goto("/faqs");
  await page
    .getByText("How does the prediction work?", { exact: true })
    .click();
  await expect(page.getByText(/Local TF-IDF regression models/)).toBeVisible();
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto("/");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
});

test("shared-browser history cannot reveal another account’s report", async ({
  page,
}) => {
  await signup(page, "First Creator");
  await page.getByRole("link", { name: "Analyze new content" }).click();
  await page
    .getByLabel("Caption or content")
    .fill("Private first creator content about growing tomatoes.");
  await page.getByRole("button", { name: "Analyze my content" }).click();
  await expect(
    page.getByRole("heading", { name: "Your content intelligence report." }),
  ).toBeVisible();
  const path = new URL(page.url()).pathname;
  const report = await page.evaluate(() => window.history.state.usr.report);
  await logout(page);
  await signup(page, "Second Creator");
  await page.evaluate(
    ({ path, report }) => {
      window.history.pushState(
        { usr: { report }, key: "stale-owner", idx: 42 },
        "",
        path,
      );
      window.dispatchEvent(new PopStateEvent("popstate"));
    },
    { path, report },
  );
  await expect(
    page.getByRole("heading", { name: "Report not found." }),
  ).toBeVisible();
  await expect(
    page.getByText("Private first creator content about growing tomatoes", {
      exact: true,
    }),
  ).toHaveCount(0);
  const otherReportId = path.split("/").at(-1);
  expect(
    (await page.request.get("/api/reports/" + otherReportId)).status(),
  ).toBe(404);
  expect(
    (await page.request.delete("/api/reports/" + otherReportId)).status(),
  ).toBe(404);
});
