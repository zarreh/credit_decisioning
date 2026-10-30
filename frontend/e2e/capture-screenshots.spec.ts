import { test } from "@playwright/test";

// `make screenshots`: every page and key state, in the light and dark projects.
// Needs a freshly reset queue (make queue-reset) and the API on :8000.
const API = process.env.API_BASE ?? "http://localhost:8000";
const OUT = "../docs/assets/screenshots";

async function caseIn(request: import("@playwright/test").APIRequestContext, band: string, status: string) {
  const rows = (await (await request.get(`${API}/applications`)).json()) as { id: string; status: string; recommendation: string | null }[];
  const found = rows.find((r) => r.recommendation === band && r.status === status);
  if (found) return found.id;
  for (const r of rows.filter((x) => x.status === "queued")) {
    const d = await (await request.post(`${API}/applications/${r.id}/start`)).json();
    if (d.recommendation === band) return r.id;
  }
  throw new Error(`no ${band} case`);
}

test("capture", async ({ page, request }, info) => {
  const shot = async (name: string) => {
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${OUT}/${info.project.name}/${name}.png`, fullPage: true });
  };
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await shot("01-home");
  await page.goto("/queue");
  await shot("02-queue");
  const rows = (await (await request.get(`${API}/applications`)).json()) as { id: string; status: string }[];
  const queued = rows.find((r) => r.status === "queued");
  if (queued) {
    await page.goto(`/applications/${queued.id}`);
    await shot("03-application-not-scored");
  }
  await page.goto(`/applications/${await caseIn(request, "decline", "needs_review")}`);
  await shot("04-application-decline-review");
  await page.goto(`/applications/${await caseIn(request, "refer", "needs_review")}`);
  await shot("05-application-refer-review");
  await page.goto(`/applications/${await caseIn(request, "approve", "recorded")}`);
  await shot("06-application-auto-approved");
  await page.goto("/evidence");
  await shot("07-evidence");
  await page.goto("/analyst");
  await shot("08-analyst");
});
