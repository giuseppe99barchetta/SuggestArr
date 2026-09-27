import { expect, test } from "@playwright/test";

// Render the actual Users page with fixture responses; never contact a real server.
async function openUsers(page, admin = true) {
  await page.route(url => url.pathname.startsWith("/api/"), route => {
    const path = new URL(route.request().url()).pathname;
    const user = { id: 1, username: "admin", role: "admin", is_active: true };
    const responses = {
      "/api/users": [user, { id: 2, username: "viewer", role: "user", is_active: true }],
      "/api/auth/me": user,
      "/api/users/me/links": [{ provider: "jellyfin", external_username: "admin" }],
      "/api/config/status": { selected_service: "jellyfin" },
    };
    return route.fulfill({
      json: responses[path] ?? { items: [], keys: [], users: [], languages: [] },
      headers: {
        "access-control-allow-origin": "http://127.0.0.1:5173",
        "access-control-allow-credentials": "true",
      },
    });
  });
  await page.route("**/users-layout-preview", route => route.fulfill({
    contentType: "text/html",
    body: `<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
      <body style="background:var(--surface-elevated-solid)"><div id="preview" style="max-width:1200px;margin:auto;padding:var(--spacing-lg)"></div><script type="module">
      import { createApp, h } from "/node_modules/.vite/deps/vue.js";
      import Users from "/src/components/settings/UserManagement.vue";
      import Profile from "/src/components/settings/UserProfile.vue";
      import { useAuth } from "/src/composables/useAuth.js";
      import "/src/assets/styles/theme.css";
      import "/src/assets/styles/global.css";
      useAuth().currentUser.value = { id: 1, username: "admin", role: "admin" };
      const app = createApp({ render: () => h(${admin ? 'Users' : 'Profile'}, { config: { SELECTED_SERVICE: "jellyfin" } }) });
      app.config.globalProperties.$toast = { error() {}, success() {} };
      app.mount("#preview");
      </script></body></html>`,
  }));
  await page.goto("/users-layout-preview");
}

test("Standalone profile has no administration controls", async ({ page }) => {
  await openUsers(page, false);
  await expect(page.getByRole("heading", { name: "My Profile" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "User Management", exact: true })).toHaveCount(0);
});

for (const width of [1280, 900, 390]) {
  test(`Users cards align and fit at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await openUsers(page);
    await expect(page.locator(".profile-nav, .settings-panel__toggle")).toHaveCount(0);
    for (const title of ["Account Information", "Title language", "API Keys", "Jellyfin Account", "Recommendation history", "Accounts", "Self-Registration"]) {
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    }
    await page.getByLabel("New username", { exact: true }).fill("draft-name");
    await page.getByLabel("Search TMDb").fill("Arrival");
    await page.locator("#profile-history-content .custom-dropdown").scrollIntoViewIfNeeded();
    await page.locator("#profile-history-content .custom-dropdown").click();
    await page.getByRole("menuitem", { name: "Movies", exact: true }).click();
    await expect(page.locator("#profile-history-content .value-text")).toHaveText("Movies");
    await expect(page.getByLabel("New username", { exact: true })).toHaveValue("draft-name");
    await expect(page.getByText("viewer", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "New User", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Create Account" })).toBeVisible();
    await page.getByRole("button", { name: "Close create account modal" }).click();
    await expect(page.getByRole("dialog", { name: "Create Account" })).toBeHidden();
    await page.screenshot({ path: testInfo.outputPath("users-cards.png"), fullPage: true, animations: "disabled" });
    const geometry = await page.locator(".settings-users--embedded > .settings-grid > .settings-group").evaluateAll(cards =>
      cards.map(card => {
        const rect = card.getBoundingClientRect();
        const title = card.querySelector("h3").getBoundingClientRect();
        return { x: rect.x, y: rect.y, bottom: rect.bottom, width: rect.width, inset: title.x - rect.x, overflow: card.scrollWidth > card.clientWidth + 1 };
      }));
    expect(geometry.every(card => !card.overflow)).toBe(true);
    if (width > 700) {
      const file = await page.locator(".history-file-control").boundingBox();
      const search = await page.getByLabel("Search TMDb").boundingBox();
      expect(Math.abs(file.y - search.y)).toBeLessThan(1);
      const upload = await page.locator(".history-import-controls > button").boundingBox();
      const submit = await page.locator(".history-search__controls > button").boundingBox();
      expect(Math.abs(upload.y + upload.height - submit.y - submit.height)).toBeLessThan(1);
    }
    expect(new Set(geometry.map(card => card.inset)).size).toBe(1);
    if (width > 1000) {
      const adminCards = page.locator(".settings-users:not(.settings-users--embedded) > .settings-grid > .settings-group");
      const accounts = await adminCards.nth(0).boundingBox();
      const registration = await adminCards.nth(1).boundingBox();
      expect(accounts.y).toBe(registration.y);
      expect(accounts.height).toBe(registration.height);
      expect(accounts.width).toBeGreaterThan(registration.width);
      expect(geometry[0].y).toBe(geometry[1].y);
      expect(geometry[0].bottom).toBe(geometry[2].bottom);
      expect(geometry[0].width).toBe(geometry[1].width);
      expect(geometry[1].x).toBe(geometry[2].x);
      expect(geometry[3].x).toBe(geometry[4].x);
      expect(geometry[3].width).toBe(geometry[4].width);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}
