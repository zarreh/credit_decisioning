import { expect, test } from "./fixtures";

const main = (page: import("@playwright/test").Page) => page.getByRole("navigation", { name: "Main" });

test("home explains the system and loads live evidence", async ({ page, consoleErrors }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "How it works, and who owns each step" })).toBeVisible();
  await expect(page.getByText(/broken notices rejected/)).toBeVisible();
  await expect(page.getByText("Finding we disclose")).toBeVisible();
  void consoleErrors;
});

test("navigation reaches every page", async ({ page, consoleErrors }) => {
  await page.goto("/");
  for (const [label, heading] of [
    ["Review queue", "Applications waiting for a decision"],
    ["Evidence", "What was measured, on what, and how sure we are"],
    ["Analyst", "Ask about the evidence, a case, or the data"],
  ]) {
    await main(page).getByRole("link", { name: label }).click();
    await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  }
  void consoleErrors;
});

test("evidence shows gaps as gaps", async ({ page, consoleErrors }) => {
  await page.goto("/evidence");
  await expect(page.getByText("insufficient n").first()).toBeVisible();
  await expect(page.getByText(/Meta-mutation/)).toBeVisible();
  void consoleErrors;
});

test("unknown application shows an actionable error", async ({ page }) => {
  page.on("console", () => undefined);
  await page.goto("/applications/APP-999");
  await expect(page.getByText(/No application 'APP-999'/)).toBeVisible();
});
