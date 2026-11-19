import { expect, test } from "@playwright/test";

// "Reject all" must cover every suggestion waiting for approval, not only the
// cards loaded so far, and the dialog must stay open while a large batch is
// still being sent in chunks of 100.

const token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.";
const pending = Array.from({ length: 130 }, (_, index) => ({
  id: index + 1, tmdb_id: String(index + 1), title: `Pick ${index + 1}`, media_type: "movie",
  name: "Manual job", status: "awaiting_approval", backend: "seer",
}));

async function mockApi(page, { rejectFails } = {}) {
  const calls = { pending: 0, reject: [], lists: 0 };
  await page.route((url) => !["127.0.0.1", "localhost"].includes(url.hostname), (route) => route.abort());
  await page.route(/\/src\/data\/releaseNotes\.js/, route => route.fulfill({ contentType: 'application/javascript', body: 'export const RELEASES_URL = ""; export const WHATS_NEW = {id:"none",title:"none",slides:[]};' }));
  await page.addInitScript(() => {
    localStorage.setItem("suggestarr_tour_done", "1");
    localStorage.setItem("suggestarr_jobs_tour_done", "1");
  });
  await page.route("http://localhost:5000/**", async (route) => {
    const request = route.request();
    const apiPath = new URL(request.url()).pathname;
    const json = (body, status = 200) => route.fulfill({
      status,
      contentType: "application/json",
      headers: { "access-control-allow-origin": "http://127.0.0.1:5173", "access-control-allow-credentials": "true" },
      body: JSON.stringify(body),
    });

    if (apiPath === "/api/auth/status") return json({ auth_setup_complete: true, app_setup_complete: true });
    if (apiPath === "/api/auth/login" || apiPath === "/api/auth/refresh") return json({ access_token: token });
    if (apiPath === "/api/auth/me") return json({ id: 1, username: "admin", role: "admin" });
    if (apiPath === "/api/config/fetch") return json({ AUTH_MODE: "enabled" });
    if (apiPath === "/api/config/status") return json({ setup_completed: true, is_complete: true });
    if (apiPath === "/api/jobs") return json({ status: "success", jobs: [{ id: 7, name: "Manual job", job_type: "discover", media_type: "movie", enabled: true, delivery_mode: "manual" }] });
    if (apiPath.endsWith("-servers")) return json({ servers: [] });
    if (apiPath === "/api/automation/requests/workflow/pending") {
      calls.pending += 1;
      return json({ status: "success", items: pending, truncated: false });
    }
    if (apiPath === "/api/automation/requests/workflow/reject" && request.method() === "POST") {
      calls.reject.push(request.postDataJSON().ids);
      if (rejectFails === "drop") return route.abort("failed");
      if (rejectFails === "refused") return json({ status: "error", message: "Invalid profile request" }, 400);
      // Slow enough to try closing the dialog while the batch is in flight.
      await new Promise((resolve) => setTimeout(resolve, 1500));
      return json({ status: "success", updated: request.postDataJSON().ids.length });
    }
    if (apiPath === "/api/automation/requests/workflow") {
      calls.lists += 1;
      const done = calls.reject.length >= 2;
      return json({ status: "success", items: done ? [] : pending.slice(0, 24), total: done ? 0 : pending.length, page: 1, pages: done ? 1 : 6 });
    }
    if (apiPath === "/api/automation/requests") return json({ data: [], total_pages: 1, total_sources: 0, total_requests: 0, request_users: [] });
    return json({});
  });
  return calls;
}

async function openQueue(page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto("/requests?status=awaiting_approval");
}

test("reject all covers every waiting suggestion and cannot be dismissed while sending", async ({ page }) => {
  const calls = await mockApi(page);
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto("/requests?status=awaiting_approval");

  await page.getByRole("button", { name: "Reject all (130)" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("130 selected items will be removed from the approval queue.")).toBeVisible();
  await expect(dialog.getByText("Pick 130")).toBeAttached();
  expect(calls.pending).toBe(1);

  await dialog.getByRole("button", { name: "Reject requests" }).click();
  await expect.poll(() => calls.reject.length).toBe(1);
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5); // the backdrop
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeDisabled();

  await expect.poll(() => calls.reject.length).toBe(2);
  await expect(dialog).toBeHidden({ timeout: 10_000 });
  expect(calls.reject.map(ids => ids.length)).toEqual([100, 30]);
  expect(calls.reject.flat()).toEqual(pending.map(item => item.id));
});

test("a lost response refreshes the queue, since the server may have applied it", async ({ page }) => {
  const calls = await mockApi(page, { rejectFails: "drop" });
  await openQueue(page);
  await page.getByRole("button", { name: "Reject all (130)" }).click();
  const lists = calls.lists;
  await page.getByRole("dialog").getByRole("button", { name: "Reject requests" }).click();

  await expect(page.getByText("The connection dropped; some requests may already be updated")).toBeVisible();
  await expect(page.getByRole("dialog")).toBeHidden();
  // Once now and once more after the server had time to commit a late decision.
  await expect.poll(() => calls.lists, { timeout: 8_000 }).toBeGreaterThanOrEqual(lists + 2);
});

test("a refused request keeps the dialog open with the reason", async ({ page }) => {
  const calls = await mockApi(page, { rejectFails: "refused" });
  await openQueue(page);
  await page.getByRole("button", { name: "Reject all (130)" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Reject requests" }).click();

  await expect(page.getByText("Invalid profile request")).toBeVisible();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(calls.reject).toHaveLength(1);
});
