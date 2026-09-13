import { expect, test } from "@playwright/test";

// Approving sends an item to Jellyseerr with a quality profile, and that
// cannot be taken back.  The one-click approval is only right when the server
// list has loaded and is empty — never while it is loading or after a lookup
// failed.  Both green check marks are covered: the Requests page and the
// dashboard.

const token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.";
const radarr = [{ id: 0, name: "Radarr", is4k: false, profiles: [{ id: 7, name: "HD" }], rootFolders: [{ path: "/movies" }] }];

async function mockApi(page, { servers }) {
  const calls = { approve: [] };
  // Hermetic: posters and fonts from the internet would hold up the page's
  // load event, and a slow network then looks like a failing test.
  await page.route((url) => !["127.0.0.1", "localhost"].includes(url.hostname), (route) => route.abort());
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
    if (apiPath === "/api/seer/radarr-servers") {
      if (servers === "slow") await new Promise((resolve) => setTimeout(resolve, 4000));
      return json({ servers: radarr });
    }
    if (apiPath === "/api/seer/sonarr-servers") {
      if (servers === "sonarr-fails") return json({ message: "unavailable" }, 503);
      return json({ servers: [] });
    }
    if (apiPath === "/api/automation/requests/workflow/approve" && request.method() === "POST") {
      calls.approve.push(request.postDataJSON());
      return json({ status: "success", updated: 1 });
    }
    if (apiPath.startsWith("/api/automation/requests/workflow")) {
      return json({
        items: calls.approve.length ? [] : [{ id: 42, tmdb_id: "42", title: "Smoke title", media_type: "movie", rating: 8.1, name: "Manual job", status: "awaiting_approval" }],
        total: calls.approve.length ? 0 : 1, page: 1, pages: 1,
      });
    }
    if (apiPath === "/api/automation/requests") return json({ data: [], total_pages: 1, total_sources: 0, total_requests: 0, request_users: [] });
    return json({});
  });
  return calls;
}

async function signIn(page) {
  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("e2e-password");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}

const places = {
  "the Requests page": async (page) => { await page.goto("/requests?status=awaiting_approval"); },
  "the dashboard": async () => {},
};

for (const [place, open] of Object.entries(places)) {
  test(`on ${place}, picking only the quality profile sends server, profile and folder`, async ({ page }) => {
    const calls = await mockApi(page, { servers: "ok" });
    await signIn(page);
    await open(page);
    await expect(page.getByText("Smoke title").first()).toBeVisible();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: "Approve request" }).first().click();

    const dialog = page.getByRole("dialog");
    // One Radarr, one folder: both are already there, nobody has to pick them.
    await expect(dialog.getByText("/movies")).toBeVisible();
    await dialog.locator(".form-group-modern", { hasText: "Quality profile" }).getByRole("button").click();
    await page.getByRole("menuitem", { name: "HD" }).click();
    await dialog.getByRole("button", { name: "Send", exact: true }).click();

    await expect.poll(() => calls.approve.length).toBe(1);
    expect(calls.approve[0].profile).toEqual({ movie: { serverId: 0, profileId: 7, rootFolder: "/movies", is4k: false } });
  });

  test(`on ${place}, a failed server lookup still asks before approving`, async ({ page }) => {
    const calls = await mockApi(page, { servers: "sonarr-fails" });
    await signIn(page);
    await open(page);
    await expect(page.getByText("Smoke title").first()).toBeVisible();
    // Give the (failing) lookup time to settle, so this is the failure case and not the loading case.
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: "Approve request" }).first().click();

    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("Send to Seer").first()).toBeVisible();
    // Radarr answered, so its choice is still offered despite Sonarr failing.
    await expect(dialog.getByText("Quality profile").first()).toBeVisible();
    expect(calls.approve).toHaveLength(0);
  });

  test(`on ${place}, a click while the servers are still loading does not approve`, async ({ page }) => {
    const calls = await mockApi(page, { servers: "slow" });
    await signIn(page);
    await open(page);
    await expect(page.getByText("Smoke title").first()).toBeVisible();
    await page.getByRole("button", { name: "Approve request" }).first().click();

    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("Loading quality profiles")).toBeVisible();
    expect(calls.approve).toHaveLength(0);
    // Once loaded, the choice appears in the open dialog.
    await expect(dialog.getByText("Leave the quality profile empty")).toBeVisible({ timeout: 10_000 });
  });
}
