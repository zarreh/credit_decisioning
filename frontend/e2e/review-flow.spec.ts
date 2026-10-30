import { expect, test } from "./fixtures";

test.beforeEach(() => {
  test.skip(test.info().project.name !== "light", "stateful: run once");
});

async function firstQueued(page: import("@playwright/test").Page, band: string): Promise<string> {
  const res = await page.request.get(`${process.env.API_BASE ?? "http://localhost:8000"}/applications`);
  const rows = (await res.json()) as { id: string; status: string }[];
  for (const row of rows.filter((r) => r.status === "queued")) {
    const started = await page.request.post(`${process.env.API_BASE ?? "http://localhost:8000"}/applications/${row.id}/start`);
    if ((await started.json()).recommendation === band) return row.id;
  }
  throw new Error(`no queued ${band} case left; run make queue-reset`);
}

test("score, review, send a verified decline, and it survives a reload", async ({ page, consoleErrors }) => {
  await page.goto("/queue");
  const queued = page.getByRole("row").filter({ hasText: "Not scored yet" }).first();
  const id = (await queued.getByRole("link").textContent())!.trim();
  await page.goto(`/applications/${id}`);
  await page.getByRole("button", { name: /Score this application/ }).click();
  await expect(page.getByText("Why the model leans this way")).toBeVisible();

  const declineId = await firstQueued(page, "decline");
  await page.goto(`/applications/${declineId}`);
  await expect(page.getByText("All eight checks passed. The notice may be sent.")).toBeVisible();
  await expect(page.getByText("We have declined your application for credit.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve (override)" })).toBeDisabled();
  await page.getByRole("button", { name: "Send the decline notice" }).click();
  await expect(page.getByRole("heading", { name: "Decision recorded" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Decision recorded" })).toBeVisible();
  await expect(page.getByText("Reviewer sent the decline notice")).toBeVisible();
  void consoleErrors;
});

test("a referred case can be declined only after a verified notice is prepared", async ({ page, consoleErrors }) => {
  const id = await firstQueued(page, "refer");
  await page.goto(`/applications/${id}`);
  await expect(page.getByRole("button", { name: "Send the decline notice" })).toHaveCount(0);
  await page.getByRole("button", { name: "Prepare a decline notice" }).click();
  await expect(page.getByText("All eight checks passed. The notice may be sent.")).toBeVisible();
  const select = page.getByRole("combobox").first();
  await select.selectOption("plain");
  await expect(page.getByRole("button", { name: "Send the decline notice" })).toBeDisabled();
  await page.getByRole("button", { name: "Apply wording and re-verify" }).click();
  await expect(page.getByText("Reviewer changed the wording")).toBeVisible();
  await page.getByRole("button", { name: "Send the decline notice" }).click();
  await expect(page.getByRole("heading", { name: "Decision recorded" })).toBeVisible();
  void consoleErrors;
});
