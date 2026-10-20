import { expect, test } from "@playwright/test";

const PHOTO = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=', 'base64');

// Render the actual Profile and Users pages with fixture responses; never contact a real server.
async function openPreview(page, component, { failUsers = false, users: suppliedUsers, photos = false, withSidebar = false } = {}) {
  const user = { id: 1, username: "admin", role: "admin", is_active: true, created_at: "2026-01-01T12:00:00Z", last_login: "2026-10-20T08:00:00Z", media_profiles: [{ provider: "jellyfin", external_user_id: "media-1", external_username: "Cinema admin", verified: true }] };
  const users = structuredClone(suppliedUsers || [user, { id: 2, username: "viewer", role: "user", is_active: true, created_at: "2026-03-01T12:00:00Z", last_login: null, visible_tabs: "requests,ai_search,profile", seer_user_id: 17, media_profiles: [] }]);
  const mutations = [];
  const avatarRequests = [];
  await page.route(url => !['127.0.0.1', 'localhost'].includes(url.hostname), route => route.abort());
  await page.route(url => url.pathname.startsWith("/api/"), route => {
    const path = new URL(route.request().url()).pathname;
    const method = route.request().method();
    const avatar = path.match(/^\/api\/users\/(\d+)\/avatar$/);
    if (avatar) {
      const id = Number(avatar[1]);
      avatarRequests.push(id);
      if (!photos) return route.fulfill({ status: 204 });
      const target = users.find(item => item.id === id);
      const source = target?.seer_user_id != null || id === 1 ? 'seer' : 'jellyfin';
      return route.fulfill({ contentType: 'image/png', headers: { 'X-Avatar-Source': source }, body: PHOTO });
    }
    if (method !== 'GET') {
      const body = route.request().postDataJSON();
      mutations.push({ path, method, body });
      const target = users.find(item => path === `/api/users/${item.id}` || path.startsWith(`/api/users/${item.id}/`));
      if (target && method === 'PATCH') Object.assign(target, body);
      if (target && path.endsWith('/permissions')) Object.assign(target, { ...body, visible_tabs: body.allowed_tabs });
      if (target && path.endsWith('/link/jellyfin')) target.media_profiles = [{ provider: 'jellyfin', ...body }];
      return route.fulfill({ json: { success: true } });
    }
    if (path === '/api/users' && failUsers) return route.fulfill({ status: 503, json: { error: 'Unavailable' } });
    const responses = {
      "/api/users": users,
      "/api/auth/me": user,
      "/api/users/me/links": [{ provider: "jellyfin", external_username: "admin" }],
      "/api/users/me/link/jellyfin/users": [{ id: 'media-1', name: 'Cinema admin' }, { id: 'media-2', name: 'Cinema viewer' }],
      "/api/seer/get_users": { users: [{ id: 17, displayName: 'Requests viewer' }] },
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
      <body><div id="preview" style="max-width:1200px;margin:auto;padding:24px"></div><script type="module">
      import { createApp, h } from "/node_modules/.vite/deps/vue.js";
      import Users from "/src/components/settings/UserManagement.vue";
      import Profile from "/src/components/settings/UserProfile.vue";
      import UserAvatar from "/src/components/ui/UserAvatar.vue";
      import { useAuth } from "/src/composables/useAuth.js";
      import "/src/assets/main.css";
      useAuth().currentUser.value = { id: 1, username: "admin", role: "admin" };
      const app = createApp({ render: () => h('div', [
        ${withSidebar ? `h(UserAvatar, {user: {id:1,username:'admin'},class:'h-8 w-8'}),` : ''}
        h(${component}, { config: { SELECTED_SERVICE: "jellyfin" } })
      ]) });
      app.config.globalProperties.$toast = { error() {}, success() {} };
      app.mount("#preview");
      </script></body></html>`,
  }));
  await page.goto("/users-layout-preview");
  return { mutations, avatarRequests };
}

for (const width of [1280, 390]) {
  test(`Account cards share the avatar loader and keep users distinct at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const { avatarRequests } = await openPreview(page, 'Users', { photos: true, withSidebar: true });
    const admins = page.getByRole('img', { name: 'admin avatar from Seer', exact: true });
    const viewer = page.getByRole('img', { name: 'viewer avatar from Seer', exact: true });
    await expect(admins).toHaveCount(2);
    await expect(viewer).toHaveCount(1);
    const sources = await admins.locator('img').evaluateAll(images => images.map(image => image.src));
    expect(sources[0]).toBe(sources[1]);
    const viewerSource = await viewer.locator('img').getAttribute('src');
    expect(viewerSource).not.toBe(sources[0]);
    expect(avatarRequests.sort()).toEqual([1, 2]);
    for (const image of await page.locator('[role="img"] img').all()) {
      await expect.poll(() => image.evaluate(element => element.complete && element.naturalWidth > 0)).toBe(true);
    }
    await page.screenshot({ path: testInfo.outputPath('users-profile-pictures.png'), fullPage: true });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}

test('Changing media and Seer assignments refreshes just the affected avatar', async ({ page }) => {
  const { avatarRequests } = await openPreview(page, 'Users', { photos: true, withSidebar: true });
  const viewer = page.getByRole('article', { name: 'Account viewer', exact: true });
  await expect(viewer.getByRole('img', { name: 'viewer avatar from Seer', exact: true })).toBeVisible();
  const originalSource = await viewer.locator('[role="img"] img').getAttribute('src');
  await viewer.getByRole('button', { name: 'Assign Jellyfin account to viewer' }).click();
  const link = page.getByRole('dialog', { name: 'Link media account', exact: true });
  await link.getByRole('button', { name: 'Select account', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Cinema viewer', exact: true }).click();
  await link.getByRole('button', { name: 'Save link', exact: true }).click();
  await expect(viewer.locator('[role="img"] img')).not.toHaveAttribute('src', originalSource);
  await expect.poll(() => avatarRequests.filter(id => id === 2).length).toBe(2);
  await viewer.getByRole('button', { name: 'Edit Seer identity for viewer', exact: true }).click();
  const permissions = page.getByRole('dialog', { name: 'Permissions', exact: true });
  await permissions.getByRole('button', { name: 'Requests viewer', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Technical user fallback', exact: true }).click();
  await permissions.getByRole('button', { name: 'Save permissions' }).click();
  await expect(viewer.getByRole('img', { name: 'viewer avatar from Jellyfin', exact: true })).toBeVisible();
  expect(avatarRequests.filter(id => id === 2)).toHaveLength(3);
  expect(avatarRequests.filter(id => id === 1)).toHaveLength(1);
});

test('Users overview, filters and account details reflect real account data', async ({ page }) => {
  await openPreview(page, 'Users');
  const overview = page.locator('dl[aria-label="Account overview"]').getByRole('definition');
  await expect(overview).toHaveText(['2', '2', '1', '1']);
  const admin = page.getByRole('article', { name: 'Account admin', exact: true });
  const viewer = page.getByRole('article', { name: 'Account viewer', exact: true });
  await expect(admin.getByText('Cinema admin', { exact: true })).toBeVisible();
  await expect(viewer.getByText('Requests viewer', { exact: true })).toBeVisible();
  await expect(viewer.getByText('Never', { exact: true })).toBeVisible();
  await expect(viewer.getByText('3 pages', { exact: true })).toHaveAttribute('title', 'Requests, AI Search, Profile');
  await expect(admin.getByText('All pages', { exact: true })).toBeVisible();
  await expect(admin.getByRole('button', { name: 'Deactivate admin', exact: true })).toBeDisabled();
  await expect(admin.getByRole('button', { name: 'Delete admin', exact: true })).toBeDisabled();
  await page.getByLabel('Find an account', { exact: true }).fill('Cinema admin');
  await expect(page.getByRole('article')).toHaveCount(1);
  await expect(admin).toBeVisible();
  await page.getByLabel('Filter accounts by role').selectOption('user');
  await expect(page.getByRole('status')).toContainText('No accounts match your filters.');
  await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
  await expect(page.getByRole('article')).toHaveCount(2);
  await page.getByLabel('Filter accounts by role').selectOption('user');
  await expect(page.getByRole('article')).toHaveCount(1);
  await expect(viewer).toBeVisible();
});

test('User controls still update status, role, permissions and media links', async ({ page }) => {
  const { mutations } = await openPreview(page, 'Users');
  const viewer = page.getByRole('article', { name: 'Account viewer', exact: true });
  await viewer.getByRole('button', { name: 'Deactivate viewer', exact: true }).click();
  await expect(viewer.getByRole('button', { name: 'Activate viewer', exact: true })).toBeVisible();
  expect(mutations[0]).toMatchObject({ method: 'PATCH', path: '/api/users/2', body: { is_active: false } });
  await viewer.getByRole('button', { name: 'Edit permissions for viewer', exact: true }).click();
  const permissions = page.getByRole('dialog', { name: 'Permissions', exact: true });
  await expect(permissions).toBeVisible();
  await permissions.getByRole('radio', { name: /^Admin/ }).check();
  await expect(permissions.getByText('Visible pages')).toHaveCount(0);
  await permissions.getByRole('button', { name: 'Save permissions' }).click();
  await expect(permissions).toHaveCount(0);
  expect(mutations[1]).toMatchObject({ method: 'PATCH', path: '/api/users/2', body: { role: 'admin' } });
  expect(mutations[2].body.allowed_tabs).toEqual(expect.arrayContaining(['requests', 'ai_search', 'profile']));
  await expect(viewer.getByText('Administrator', { exact: true })).toBeVisible();
  await expect(viewer.getByText('All pages', { exact: true })).toBeVisible();
  await viewer.getByRole('button', { name: 'Assign Jellyfin account to viewer' }).click();
  const link = page.getByRole('dialog', { name: 'Link media account', exact: true });
  await link.getByRole('button', { name: 'Select account', exact: true }).click();
  await page.getByRole('menuitem', { name: 'Cinema viewer', exact: true }).click();
  await link.getByRole('button', { name: 'Save link', exact: true }).click();
  await expect(link).toHaveCount(0);
  await expect(viewer.getByText('Cinema viewer', { exact: true })).toBeVisible();
  expect(mutations[3]).toMatchObject({ path: '/api/users/2/link/jellyfin', body: { external_user_id: 'media-2', external_username: 'Cinema viewer' } });
  await viewer.getByRole('button', { name: 'Assign Jellyfin account to viewer' }).click();
  await expect(page.getByRole('dialog').getByRole('button', { name: 'Cinema viewer', exact: true })).toBeVisible();
});

test('Own role and the last admin are locked, overview chips filter, list view keeps controls', async ({ page }) => {
  const { mutations } = await openPreview(page, 'Users');
  const admin = page.getByRole('article', { name: 'Account admin', exact: true });
  await admin.getByRole('button', { name: 'Edit permissions for admin', exact: true }).click();
  const permissions = page.getByRole('dialog', { name: 'Permissions', exact: true });
  await expect(permissions.getByRole('radio', { name: /^User/ })).toBeDisabled();
  await expect(permissions.getByText('You cannot change your own role.')).toBeVisible();
  await permissions.getByRole('button', { name: 'Cancel' }).click();

  await page.getByRole('button', { name: 'admins', exact: true }).click();
  await expect(page.getByRole('article')).toHaveCount(1);
  await page.getByRole('button', { name: `linked to Jellyfin`, exact: true }).click();
  await expect(page.getByRole('article')).toHaveCount(1);
  await page.getByRole('button', { name: 'accounts', exact: true }).click();
  await expect(page.getByRole('article')).toHaveCount(2);

  await page.getByRole('button', { name: 'List view', exact: true }).click();
  const viewer = page.getByRole('article', { name: 'Account viewer', exact: true });
  await expect(viewer.getByText('never signed in')).toBeVisible();
  await viewer.getByRole('button', { name: 'Deactivate viewer', exact: true }).click();
  expect(mutations[0]).toMatchObject({ method: 'PATCH', path: '/api/users/2', body: { is_active: false } });
  await page.reload();
  await expect(page.getByRole('button', { name: 'List view', exact: true })).toHaveAttribute('aria-pressed', 'true');
});

test('Self-registration switch saves sign-up pages', async ({ page }) => {
  const { mutations } = await openPreview(page, 'Users');
  await page.getByRole('switch', { name: /Allow sign-ups/ }).click();
  await expect(page.getByRole('switch', { name: /Allow sign-ups/ })).toHaveAttribute('aria-checked', 'true');
  expect(mutations[0]).toMatchObject({ path: '/api/config/section/advanced', body: { ALLOW_REGISTRATION: true, REGISTRATION_DEFAULT_TABS: 'requests,jobs,profile' } });
  await page.getByRole('group', { name: 'Pages for new accounts' }).getByLabel('Jobs').uncheck();
  await expect.poll(() => mutations[1]?.body.REGISTRATION_DEFAULT_TABS).toBe('requests,profile');
});

test('Failed account load offers retry and never claims zero accounts', async ({ page }) => {
  await openPreview(page, 'Users', { failUsers: true });
  await expect(page.getByRole('alert')).toContainText('Could not load accounts');
  await expect(page.getByRole('definition').filter({ hasText: '—' })).toHaveCount(4);
  await page.route('**/api/users', route => route.fulfill({ json: [] }));
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.getByText('No accounts found.', { exact: true })).toBeVisible();
});

test('Long usernames and disabled accounts fit on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 1000 });
  const username = 'a'.repeat(64);
  await openPreview(page, 'Users', { users: [{ id: 12, username, role: 'user', is_active: false, media_profiles: [{ provider: 'jellyfin', external_username: 'linked'.repeat(20) }] }] });
  const account = page.getByRole('article', { name: `Account ${username}`, exact: true });
  await expect(account.getByRole('button', { name: `Activate ${username}` })).toBeVisible();
  expect(await account.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

const cardGeometry = page => page.locator("[data-users-page] [data-users-cards] > section").evaluateAll(cards =>
  cards.map(card => {
    const rect = card.getBoundingClientRect();
    const title = card.querySelector("h2").getBoundingClientRect();
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
    await expect(page.getByRole("dialog", { name: "Create account" })).toBeVisible();
    await page.getByRole("button", { name: "Close" }).click();
    await expect(page.getByRole("dialog", { name: "Create account" })).toBeHidden();
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
