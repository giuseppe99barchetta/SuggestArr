import { expect, test } from '@playwright/test';

const PHOTO = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=', 'base64');

async function preview(page, { width = 1280, subpath = false, photo = false, broken = false, offline = false } = {}) {
  await page.setViewportSize({ width, height: 950 });
  const errors = [];
  const avatarRequests = [];
  let linked = false;
  page.on('pageerror', error => errors.push(error.message));
  await page.route(url => url.pathname.startsWith('/api/') || url.pathname.startsWith('/suggestarr/api/'), async route => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/suggestarr/, '');
    if (/^\/api\/users\/\d+\/avatar$/.test(path)) {
      avatarRequests.push({ path: url.pathname, authorization: route.request().headers().authorization });
      if (offline) return route.fulfill({ status: 503, body: '' });
      if (!photo && !linked) return route.fulfill({ status: 204 });
      return route.fulfill({ contentType: 'image/png', headers: { 'X-Avatar-Source': 'jellyfin' }, body: broken ? Buffer.from('invalid image') : PHOTO });
    }
    if (path === '/api/integrations/jellyfin/link') {
      linked = true;
      return route.fulfill({ json: { external_username: 'Cinema fan' } });
    }
    if (path === '/api/users/me/link/jellyfin' && route.request().method() === 'DELETE') {
      linked = false;
      return route.fulfill({ json: {} });
    }
    const responses = {
      '/api/auth/me': { id: 3, username: 'Cinema fan', role: 'user' },
      '/api/config/status': { selected_service: 'jellyfin' },
      '/api/users/me/links': linked ? [{ provider: 'jellyfin', external_username: 'Cinema fan', verified: true }] : [],
      '/api/users/me/link/jellyfin/users': [{ id: 'user-42', name: 'Cinema fan' }],
      '/api/tmdb/languages': { languages: [] },
    };
    return route.fulfill({ json: responses[path] ?? [] });
  });
  await page.route('**/avatar-preview', route => route.fulfill({
    contentType: 'text/html',
    body: `<html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body><div id="preview"></div><script type="module">
    import { mountAvatarPreview } from '/e2e/fixtures/avatarPreview.js';
    mountAvatarPreview(${JSON.stringify({ subpath })});
    </script></body></html>`,
  }));
  await page.goto('/avatar-preview');
  await expect(page.getByRole('heading', { name: 'My profile' })).toBeVisible();
  await expect.poll(() => avatarRequests.length).toBeGreaterThan(0);
  return { errors, avatarRequests };
}

for (const width of [1280, 390]) {
  test(`linked photo is shared across sidebar and profile at ${width}px`, async ({ page }) => {
    const { errors, avatarRequests } = await preview(page, { width, photo: true });
    const avatars = page.getByRole('img', { name: 'Cinema fan avatar from Jellyfin' });
    await expect(avatars).toHaveCount(2);
    for (const avatar of await avatars.all()) {
      await expect.poll(() => avatar.locator('img').evaluate(img => img.complete && img.naturalWidth > 0)).toBe(true);
    }
    expect(avatarRequests).toHaveLength(1);
    expect(avatarRequests[0].authorization).toBe('Bearer test-only');
    const sources = await avatars.locator('img').evaluateAll(images => images.map(image => image.src));
    expect(sources[0]).toBe(sources[1]);
    expect(sources[0]).toMatch(/^blob:/);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}

test('linking and unlinking refresh both avatars under a subpath', async ({ page }) => {
  const { errors, avatarRequests } = await preview(page, { subpath: true });
  await expect(page.getByRole('img', { name: 'Cinema fan cinema avatar' })).toHaveCount(2);
  await page.locator('#linkServerUser').selectOption('user-42');
  await page.locator('#linkPassword').fill('test-only-password');
  await page.getByRole('button', { name: 'Link Jellyfin account', exact: true }).click();
  await expect(page.getByRole('img', { name: 'Cinema fan avatar from Jellyfin' })).toHaveCount(2);
  await page.getByRole('button', { name: 'Unlink', exact: true }).click();
  await expect(page.getByRole('img', { name: 'Cinema fan cinema avatar' })).toHaveCount(2);
  expect(avatarRequests).toHaveLength(3);
    expect(avatarRequests.every(request => request.path === '/suggestarr/api/users/3/avatar')).toBe(true);
  expect(errors).toEqual([]);
});

test('switching accounts requests the new ID instead of reusing the signed-in user endpoint', async ({ page }) => {
  const { avatarRequests } = await preview(page, { photo: true, subpath: true });
  await expect(page.getByRole('img', { name: 'Cinema fan avatar from Jellyfin' })).toHaveCount(2);
  const originalSource = await page.locator('[role="img"] img').first().getAttribute('src');
  await page.getByRole('button', { name: 'Switch account' }).click();
  await expect(page.getByRole('img', { name: 'TV fan avatar from Jellyfin' })).toHaveCount(2);
  expect(avatarRequests.map(request => request.path)).toEqual(['/suggestarr/api/users/3/avatar', '/suggestarr/api/users/4/avatar']);
  await expect(page.locator('[role="img"] img').first()).not.toHaveAttribute('src', originalSource);
});

for (const mode of ['offline', 'broken']) {
  test(`${mode} image uses the cinema fallback and survives an account switch`, async ({ page }, testInfo) => {
    const { errors } = await preview(page, { photo: true, [mode]: true });
    await expect(page.getByRole('img', { name: 'Cinema fan cinema avatar' })).toHaveCount(2);
    await expect(page.locator('[role="img"] img')).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath('cinema-avatars.png'), fullPage: true });
    await page.getByRole('button', { name: 'Switch account' }).click();
    await expect(page.getByRole('img', { name: 'TV fan cinema avatar' })).toHaveCount(2);
    await expect(page.locator('[role="img"] img')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}
