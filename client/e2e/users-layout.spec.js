import { expect, test } from "@playwright/test";

// Render the actual Profile and Users pages with fixture responses; never contact a real server.
async function openPreview(page, component) {
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
      import "/src/assets/main.css";
      useAuth().currentUser.value = { id: 1, username: "admin", role: "admin" };
      const app = createApp({ render: () => h(${component}, { config: { SELECTED_SERVICE: "jellyfin" } }) });
      app.config.globalProperties.$toast = { error() {}, success() {} };
      app.mount("#preview");
      </script></body></html>`,
  }));
  await page.goto("/users-layout-preview");
}

const cardGeometry = page => page.locator("#preview > .settings-users > .settings-grid > .settings-group").evaluateAll(cards =>
  cards.map(card => {
    const rect = card.getBoundingClientRect();
    const title = card.querySelector("h3").getBoundingClientRect();
    return { x: rect.x, y: rect.y, bottom: rect.bottom, width: rect.width, height: rect.height, inset: title.x - rect.x, overflow: card.scrollWidth > card.clientWidth + 1 };
  }));

test("Profile has no administration controls", async ({ page }) => {
  await openPreview(page, "Profile");
  await expect(page.getByRole("heading", { name: "My profile" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Accounts", exact: true })).toHaveCount(0);
});

test("Users page manages accounts without the admin's own profile", async ({ page }) => {
  await openPreview(page, "Users");
  await expect(page.getByRole("heading", { name: "Users", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Account", exact: true })).toHaveCount(0);
});

for (const width of [1280, 900, 390]) {
  test(`Profile cards align and fit at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await openPreview(page, "Profile");
    for (const title of ["Account", "Title language", "API keys", "Linked accounts", "Recommendation history"]) {
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    }
    await page.getByLabel("New username", { exact: true }).fill("draft-name");
    await page.getByLabel("Search TMDb").fill("Arrival");
    await page.getByLabel("Media type", { exact: true }).selectOption("movie");
    await expect(page.getByLabel("Media type", { exact: true })).toHaveValue("movie");
    await expect(page.getByLabel("New username", { exact: true })).toHaveValue("draft-name");
    await page.screenshot({ path: testInfo.outputPath("profile-cards.png"), fullPage: true, animations: "disabled" });

    const cards = await page.locator("[data-profile-page] section").evaluateAll(sections =>
      sections.map(section => {
        const rect = section.getBoundingClientRect();
        return { title: section.querySelector("h2")?.textContent.trim(), x: rect.x, y: rect.y, width: rect.width, overflow: section.scrollWidth > section.clientWidth + 1 };
      }));
    expect(cards.every(card => !card.overflow)).toBe(true);
    if (width > 1000) {
      const byTitle = Object.fromEntries(cards.map(card => [card.title, card]));
      // Account on the left, preferences and keys stacked on the right, same top edge and width.
      expect(byTitle["Account"].y).toBe(byTitle["Title language"].y);
      expect(byTitle["Account"].width).toBe(byTitle["Title language"].width);
      expect(byTitle["Title language"].x).toBe(byTitle["API keys"].x);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });

  test(`Users cards align and fit at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await openPreview(page, "Users");
    for (const title of ["Accounts", "Self-Registration"]) {
      await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
    }
    await expect(page.getByText("viewer", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "New User", exact: true }).click();
    await expect(page.getByRole("dialog", { name: "Create Account" })).toBeVisible();
    await page.getByRole("button", { name: "Close create account modal" }).click();
    await expect(page.getByRole("dialog", { name: "Create Account" })).toBeHidden();
    await page.screenshot({ path: testInfo.outputPath("users-cards.png"), fullPage: true, animations: "disabled" });

    const geometry = await cardGeometry(page);
    expect(geometry.every(card => !card.overflow)).toBe(true);
    expect(new Set(geometry.map(card => card.inset)).size).toBe(1);
    if (width > 1000) {
      const [accounts, registration] = geometry;
      expect(accounts.y).toBe(registration.y);
      expect(accounts.height).toBe(registration.height);
      expect(accounts.width).toBeGreaterThan(registration.width);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}
