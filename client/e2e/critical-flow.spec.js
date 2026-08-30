import { expect, test } from "@playwright/test";

const token = "eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.";

test("an administrator can sign in and approve a queued suggestion", async ({ page }) => {
  let approved = false;
  let approveCalls = 0;

  await page.route("http://localhost:5000/api/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const json = (body) => route.fulfill({
      contentType: "application/json",
      headers: { "access-control-allow-origin": "http://127.0.0.1:5173" },
      body: JSON.stringify(body),
    });

    if (pathname === "/api/auth/status") return json({ auth_setup_complete: true, app_setup_complete: true });
    if (pathname === "/api/auth/login") return json({ access_token: token });
    if (pathname === "/api/auth/me") return json({ id: 1, username: "admin", role: "admin" });
    if (pathname === "/api/config/status") return json({ setup_completed: true, is_complete: true });
    if (pathname === "/api/jobs") return json({ jobs: [{ id: 7, name: "Manual job", delivery_mode: "manual" }] });
    if (pathname === "/api/automation/requests/workflow/approve" && request.method() === "POST") {
      approved = true;
      approveCalls += 1;
      return json({ updated: 1 });
    }
    if (pathname === "/api/automation/requests/workflow") {
      return json({
        items: approved ? [] : [{ id: 42, tmdb_id: "42", title: "Smoke title", media_type: "movie", rating: 8.1, name: "Manual job", status: "awaiting_approval" }],
        total: approved ? 0 : 1, page: 1, pages: 1,
      });
    }
    if (pathname === "/api/automation/requests") return json({ data: [], total_pages: 1, total_sources: 0, total_requests: 0, request_users: [] });
    return json({});
  });

  await page.goto("/login");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto("/requests");
  await expect(page.getByText("Smoke title")).toBeVisible();
  await page.getByRole("button", { name: "Approve request" }).click();
  await expect.poll(() => approveCalls).toBe(1);
  await expect(page.getByText("Smoke title")).toHaveCount(0);
});
