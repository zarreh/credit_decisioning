import { defineConfig, devices } from "@playwright/test";

// The specs need the API running (make dev, or the throwaway setup in docs/run-it-yourself.md).
// PW_PORT lets the suite run beside a dev server already holding :3000.
const PORT = process.env.PW_PORT ?? "3000";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: { baseURL: `http://localhost:${PORT}`, trace: "retain-on-failure" },
  webServer: {
    command: `npm run build && npm run start -- --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  projects: [
    { name: "light", use: { ...devices["Desktop Chrome"], colorScheme: "light" } },
    { name: "dark", use: { ...devices["Desktop Chrome"], colorScheme: "dark" } },
    { name: "mobile", use: { ...devices["Pixel 7"], colorScheme: "light" }, testMatch: /smoke/ },
  ],
});
