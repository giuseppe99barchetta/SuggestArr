import { expect, test } from "@playwright/test";

// Deliberately unsigned fixture token. Every API request is intercepted below.
const token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.";

async function mockApi(page, { subpath = "", setupCompleted = true } = {}) {
  let approved = false;
  let approveCalls = 0;
  let runCalls = 0;

  await page.addInitScript(() => {
    localStorage.setItem("suggestarr_tour_done", "1");
    localStorage.setItem("sj_jobs_tour_done", "1");
  });

  await page.route("http://localhost:5000/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const expectedPrefix = `${subpath}/api/`;
    if (!pathname.startsWith(expectedPrefix)) {
      throw new Error(`Expected API request under ${expectedPrefix}, got ${pathname}`);
    }
    const apiPath = pathname.slice(subpath.length);
    const json = (body) => route.fulfill({
      contentType: "application/json",
      headers: {
        "access-control-allow-origin": "http://127.0.0.1:5173",
        "access-control-allow-credentials": "true",
      },
      body: JSON.stringify(body),
    });

    if (apiPath === "/api/auth/status") return json({ auth_setup_complete: true, app_setup_complete: setupCompleted });
    if (apiPath === "/api/auth/login") return json({ access_token: token });
    if (apiPath === "/api/auth/refresh") return json({ access_token: token });
    if (apiPath === "/api/auth/me") return json({ id: 1, username: "admin", role: "admin" });
    if (apiPath === "/api/config/fetch") return json({ AUTH_MODE: "enabled" });
    if (apiPath === "/api/config/status") return json({ setup_completed: setupCompleted, is_complete: setupCompleted });
    if (apiPath === "/api/jobs") {
      return json({ status: "success", jobs: [{
        id: 7, name: "Manual job", job_type: "discover", media_type: "movie", enabled: true,
        max_results: 5, filters: {}, schedule_type: "preset", schedule_value: "daily",
        delivery_mode: "manual",
      }] });
    }
    if (apiPath === "/api/jobs/history") return json({ status: "success", history: [] });
    if (apiPath === "/api/jobs/queue-status") return json({ status: "success", queued: 0, submitting: 0, submitted: 0, failed: 0, total_pending: 0 });
    if (apiPath === "/api/jobs/7/dry-run" && request.method() === "POST") {
      return json({ status: "success", dry_run: true, items_count: 1, items: [{
        tmdb_id: 101, media_type: "movie", title: "Preview title", would_request: true,
      }] });
    }
    if (apiPath === "/api/jobs/7/run" && request.method() === "POST") {
      runCalls += 1;
      return json({ status: "success", results_count: 1, requested_count: 1, run_id: 9 });
    }
    if (apiPath === "/api/automation/requests/workflow/approve" && request.method() === "POST") {
      approved = true;
      approveCalls += 1;
      return json({ updated: 1 });
    }
    if (apiPath === "/api/automation/requests/workflow" || apiPath === "/api/automation/requests/workflow/") {
      return json({
        items: approved ? [] : [{ id: 42, tmdb_id: "42", title: "Smoke title", media_type: "movie", rating: 8.1, name: "Manual job", status: "awaiting_approval" }],
        total: approved ? 0 : 1, page: 1, pages: 1,
      });
    }
    if (apiPath === "/api/automation/requests") return json({ data: [], total_pages: 1, total_sources: 0, total_requests: 0, request_users: [] });
    return json({});
  });
  return { approveCalls: () => approveCalls, runCalls: () => runCalls };
}

async function injectSubpathIndex(page, subpath) {
  const inject = async (route) => {
    const response = await route.fetch();
    const body = (await response.text()).replace("<head>", `<head><meta name=\"suggestarr-subpath\" content=\"${subpath}\"><base href=\"${subpath}/\">`);
    await route.fulfill({ response, body });
  };
  await page.route(`**${subpath}/login`, inject);
  await page.route(`**${subpath}/requests**`, inject);
}

for (const subpath of ["", "/suggestarr"]) {
  test(`an administrator can sign in and approve a queued suggestion${subpath || " at root"}`, async ({ page }) => {
    const api = await mockApi(page, { subpath });
    if (subpath) await injectSubpathIndex(page, subpath);

    await page.goto(`${subpath}/login`);
    await page.getByLabel("Username").fill("admin");
    await page.getByLabel("Password").fill("correct-horse-battery-staple");
    await page.getByRole("button", { name: "Sign In" }).click();
    await expect(page).toHaveURL(new RegExp(`${subpath}/dashboard$`));

    await page.goto(`${subpath}/requests?status=awaiting_approval`);
    await expect(page.getByText("Smoke title")).toBeVisible();
    await page.getByRole("button", { name: "Approve request" }).click();
    await expect.poll(api.approveCalls).toBe(1);
    await expect(page.getByText("Smoke title")).toHaveCount(0);
  });
}

test("an authenticated administrator can start the setup wizard", async ({ page }) => {
  await mockApi(page, { setupCompleted: false });

  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/setup$/);

  await page.getByRole("button", { name: "Start Setup" }).click();
  await expect(page.getByText(/Step 1 of/)).toBeVisible();
});

test("a job preview and simulated request run without external providers", async ({ page }) => {
  const api = await mockApi(page);

  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByRole("button", { name: "Jobs" }).click();
  await expect(page.getByRole("heading", { name: "Manual job" })).toBeVisible();
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByRole("heading", { name: "Dry Run Preview" })).toBeVisible();
  await expect(page.getByText("Preview title")).toBeVisible();
  await expect(page.getByText("No actual requests were made")).toBeVisible();

  await page.getByRole("button", { name: "Run Job Now" }).click();
  await expect.poll(api.runCalls).toBe(1);
});
