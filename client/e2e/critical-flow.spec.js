import { expect, test } from "@playwright/test";

const token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.";

async function mockApi(page, subpath = "") {
  let approved = false;
  let approveCalls = 0;

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
      headers: { "access-control-allow-origin": "http://127.0.0.1:5173" },
      body: JSON.stringify(body),
    });

    if (apiPath === "/api/auth/status") return json({ auth_setup_complete: true, app_setup_complete: true });
    if (apiPath === "/api/auth/login") return json({ access_token: token });
    if (apiPath === "/api/auth/me") return json({ id: 1, username: "admin", role: "admin" });
    if (apiPath === "/api/config/status") return json({ setup_completed: true, is_complete: true });
    if (apiPath === "/api/jobs") return json({ jobs: [{ id: 7, name: "Manual job", delivery_mode: "manual" }] });
    if (apiPath === "/api/automation/requests/workflow/approve" && request.method() === "POST") {
      approved = true;
      approveCalls += 1;
      return json({ updated: 1 });
    }
    if (apiPath === "/api/automation/requests/workflow") {
      return json({
        items: approved ? [] : [{ id: 42, tmdb_id: "42", title: "Smoke title", media_type: "movie", rating: 8.1, name: "Manual job", status: "awaiting_approval" }],
        total: approved ? 0 : 1, page: 1, pages: 1,
      });
    }
    if (apiPath === "/api/automation/requests") return json({ data: [], total_pages: 1, total_sources: 0, total_requests: 0, request_users: [] });
    return json({});
  });
  return () => approveCalls;
}

async function injectSubpathIndex(page, subpath) {
  await page.route(`**${subpath}/login`, async (route) => {
    const response = await route.fetch();
    const body = (await response.text()).replace("<head>", `<head><meta name=\"suggestarr-subpath\" content=\"${subpath}\"><base href=\"${subpath}/\">`);
    await route.fulfill({ response, body });
  });
}

for (const subpath of ["", "/suggestarr"]) {
  test(`an administrator can sign in and approve a queued suggestion${subpath || " at root"}`, async ({ page }) => {
    const approveCalls = await mockApi(page, subpath);
    if (subpath) await injectSubpathIndex(page, subpath);

    await page.goto(`${subpath}/login`);
    await page.getByLabel("Username").fill("admin");
    await page.getByLabel("Password").fill("correct-horse-battery-staple");
    await page.getByRole("button", { name: "Sign In" }).click();
    await expect(page).toHaveURL(new RegExp(`${subpath}/dashboard$`));

    await page.goto(`${subpath}/requests`);
    await expect(page.getByText("Smoke title")).toBeVisible();
    await page.getByRole("button", { name: "Approve request" }).click();
    await expect.poll(approveCalls).toBe(1);
    await expect(page.getByText("Smoke title")).toHaveCount(0);
  });
}
