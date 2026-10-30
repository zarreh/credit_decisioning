import type { Page } from "@playwright/test";

import { expect, test } from "./fixtures";

const CORS = { "access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "*" };

const ANSWER = [
  "The model's performance:",
  "",
  "- **AUROC**: **0.780** with a 95% CI of **[0.751, 0.810]**",
  "- **Expected cost**: `0.541` per applicant",
  "",
  "| Model | AUROC |",
  "|---|---|",
  "| Champion | 0.780 |",
  "",
  "[bad](javascript:window.__pwned=true) and [docs](https://example.com)",
  "",
  "<script>window.__pwned = true</script>",
].join("\n");

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

async function mockAnalyst(page: Page, events: string) {
  await page.route("**/analyst/status", (route) =>
    route.fulfill({ json: { enabled: true, model: "stub" }, headers: CORS }),
  );
  await page.route("**/analyst/chat", (route) =>
    route.request().method() === "OPTIONS"
      ? route.fulfill({ status: 204, headers: CORS })
      : route.fulfill({ status: 200, contentType: "text/event-stream", headers: CORS, body: events }),
  );
}

test("analyst answers render as formatted Markdown, never as raw syntax or markup", async ({ page, consoleErrors }) => {
  await mockAnalyst(
    page,
    sse("answer", {
      text: ANSWER,
      claims: [],
      grounding: { verified: true, problems: [], numbers_checked: 4 },
    }),
  );
  await page.goto("/analyst");
  await page.getByLabel("Ask the analyst").fill("How good is the model?");
  await page.getByRole("button", { name: "Ask" }).click();

  await expect(page.locator("strong", { hasText: "0.780" }).first()).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Expected cost" })).toBeVisible();
  await expect(page.locator("code", { hasText: "0.541" })).toBeVisible();
  await expect(page.getByRole("table")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Champion" })).toBeVisible();

  const text = await page.locator("main").innerText();
  expect(text).not.toContain("**");
  expect(text).not.toContain("|---|");

  // Hostile output stays inert: the script is shown as text, the javascript: link has no href.
  await expect(page.getByText("<script>window.__pwned = true</script>")).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { __pwned?: boolean }).__pwned)).toBeUndefined();
  await expect(page.getByRole("link", { name: "docs", exact: true })).toHaveAttribute("href", "https://example.com");
  await expect(page.getByRole("link", { name: "bad", exact: true })).toHaveCount(0);
  void consoleErrors;
});

test("a report draft awaiting approval is previewed as formatted text", async ({ page, consoleErrors }) => {
  await mockAnalyst(
    page,
    sse("approval_needed", {
      requests: [{ name: "save_report_draft", args: { kind: "model_risk", title: "Risk", body: "### Findings\n\n- **AUROC** 0.78" } }],
    }),
  );
  await page.goto("/analyst");
  await page.getByLabel("Ask the analyst").fill("Draft a report");
  await page.getByRole("button", { name: "Ask" }).click();

  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible();
  await expect(page.locator("strong", { hasText: "AUROC" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save draft" })).toBeVisible();
  void consoleErrors;
});
