import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { posterFixture, titles } from './fixtures/recapPosters.js';

const badgeThresholds = [10, 100, 500, 1000, 5000, 10000];

async function openJourney(page, { width = 1280, role = 'admin', total = 100, linked = true, profile = false, subpath = false, failPosters = false, missingPosters = false, nativeShare = false } = {}) {
  await page.setViewportSize({ width, height: 1000 });
  const errors = [];
  const actions = [];
  const requests = [];
  let mode = 'enabled';
  let claimed = false;
  page.on('pageerror', error => errors.push(error.message));
  const recap = {
    scope: role === 'admin' ? 'installation' : 'personal', has_linked_profiles: linked,
    total, movies: Math.ceil(total * 0.72), tv: total - Math.ceil(total * 0.72),
    first_requested_at: total ? '2025-09-01T00:00:00+00:00' : null,
    badges: [...badgeThresholds.map(threshold => ({ id: `titles_${threshold}`, kind: 'titles', threshold,
      label: { 10: 'First discoveries', 100: 'Century club', 500: 'Discovery enthusiast', 1000: 'A thousand discoveries', 5000: 'Cinema explorer', 10000: 'Discovery legend' }[threshold], unlocked: total >= threshold })),
    { id: 'one_year', kind: 'days', threshold: 365, label: 'One year of discoveries', unlocked: total > 0 }],
    next_badge: { threshold: badgeThresholds.find(n => n > total) || 10000, label: 'Discovery enthusiast' },
    preferences: { reminder_mode: mode }, posters: [], can_support: role === 'admin',
  };
  await page.route(url => url.pathname.startsWith('/api/') || url.pathname.startsWith('/suggestarr/api/'), async route => {
    const request = route.request();
    const url = new URL(request.url());
    requests.push({ method: request.method(), path: url.pathname });
    const headers = { 'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,POST,PATCH,OPTIONS' };
    if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers });
    if (url.pathname.endsWith('/recap/preferences')) {
      const action = request.postDataJSON().action;
      actions.push(action);
      mode = ({ disable: 'disabled', supported: 'supported', enable: 'enabled' })[action] || mode;
      return route.fulfill({ json: { status: 'success', data: { reminder_mode: mode } }, headers });
    }
    if (url.pathname.endsWith('/recap/prompt')) {
      const prompt = !claimed && mode === 'enabled' && total >= 100 ? { milestone: 100, scope: recap.scope, version: 1 } : null;
      claimed = true;
      return route.fulfill({ json: { status: 'success', data: { prompt } }, headers });
    }
    if (failPosters && url.searchParams.get('include_posters')) return route.fulfill({ status: 500, json: { message: 'Unavailable' }, headers });
    const posters = url.searchParams.get('include_posters') ? titles.map((title, index) => ({
      poster_path: missingPosters && index === 3 ? '/missing.jpg' : `/recap-${index}.svg`, title, rating: 9.2 - index / 10,
    })) : [];
    return route.fulfill({ json: { status: 'success', data: { ...recap, preferences: { reminder_mode: mode }, posters } }, headers });
  });
  await page.route('https://image.tmdb.org/**', route => {
    if (route.request().url().endsWith('/missing.jpg')) return route.abort();
    const index = Number(route.request().url().match(/recap-(\d)/)?.[1] || 0);
    return route.fulfill({ contentType: 'image/svg+xml', headers: { 'access-control-allow-origin': '*' }, body: posterFixture(index) });
  });
  await page.addInitScript(({ nativeShare }) => {
    Object.defineProperty(navigator, 'canShare', { value: nativeShare ? () => true : undefined, configurable: true });
    if (nativeShare) Object.defineProperty(navigator, 'share', {
      value: async data => {
        window.sharedRecap = { title: data.title, text: data.text, type: data.files[0].type, size: data.files[0].size };
      }, configurable: true,
    });
  }, { nativeShare });
  const path = subpath ? '/suggestarr/recap-preview' : '/recap-preview';
  await page.route(`**${path}`, route => route.fulfill({
    contentType: 'text/html',
    body: `<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
      <body><div id="preview" style="max-width:1100px;margin:auto;padding:16px"></div><script type="module">
      import { mountPreview } from '/e2e/fixtures/recapPreview.js';
      mountPreview(${JSON.stringify({ role, profile, subpath })});
      </script></body></html>`,
  }));
  await page.goto(path);
  return { errors, actions, requests };
}

for (const width of [1280, 390]) {
  test(`journey, badges and PNG work at ${width}px`, async ({ page }, testInfo) => {
    const { errors } = await openJourney(page, { width });
    await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
    await expect(page.getByRole('heading', { name: '100 titles requested with SuggestArr' })).toBeVisible();
    await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
    await expect(page.getByRole('heading', { name: 'Your badges' })).toBeVisible();
    const downloadButton = page.getByRole('button', { name: 'Download PNG' });
    await expect(downloadButton).toBeEnabled();
    await expect(page.getByRole('button', { name: 'Share', exact: true })).toHaveCount(0);
    await expect(page.getByLabel('Show top-title covers')).toBeChecked();
    await expect(page.getByLabel('Featured covers').locator('img')).toHaveCount(4);
    const ratio = await page.locator('canvas').evaluate(canvas => canvas.getBoundingClientRect().width / canvas.getBoundingClientRect().height);
    expect(ratio).toBeCloseTo(4 / 5, 3);
    await page.screenshot({ path: testInfo.outputPath('recap-dialog.png'), fullPage: true, animations: 'disabled' });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    const downloaded = page.waitForEvent('download');
    await downloadButton.click();
    const file = await downloaded;
    const output = testInfo.outputPath('suggestarr-recap.png');
    await file.saveAs(output);
    const png = readFileSync(output);
    expect(png.readUInt32BE(16)).toBe(1080);
    expect(png.readUInt32BE(20)).toBe(1350);
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test('optional posters omit failed images and still export', async ({ page }) => {
  const { errors } = await openJourney(page, { missingPosters: true });
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await expect(page.getByText('Some covers could not be loaded. Their places use illustrated cards.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  expect(errors).toEqual([]);
});

test('poster API failure keeps the aggregate recap usable', async ({ page }) => {
  await openJourney(page, { failPosters: true });
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await expect(page.getByText('Posters could not be loaded. Your statistics are still available.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
});

test('regular users get personal badges without support prompts or mutations', async ({ page }) => {
  const { requests } = await openJourney(page, { role: 'user' });
  await expect(page.getByText('Your linked profiles')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Support SuggestArr', exact: true })).toHaveCount(0);
  expect(requests.some(request => request.method !== 'GET')).toBeFalsy();
});

test('unlinked users and zero progress show helpful empty states', async ({ page }) => {
  await openJourney(page, { role: 'user', total: 0, linked: false });
  await expect(page.getByRole('link', { name: 'Link your media account' })).toBeVisible();
  await page.getByRole('button', { name: 'Create your recap' }).click();
  await expect(page.getByRole('dialog')).toContainText('Link your Plex, Jellyfin or Emby account');
  await expect(page.getByRole('button', { name: 'Download PNG' })).toHaveCount(0);
});

test('snooze persists a preference action and removes the invitation', async ({ page }) => {
  const { actions } = await openJourney(page);
  await page.getByRole('button', { name: 'Remind me in 30 days' }).click();
  await expect(page.getByRole('heading', { name: '100 titles requested with SuggestArr' })).toHaveCount(0);
  expect(actions).toEqual(['remind_later']);
});

test('support dialog offers both providers and honors already supported', async ({ page }) => {
  const { actions } = await openJourney(page);
  await page.getByRole('button', { name: 'Support SuggestArr', exact: true }).first().click();
  await expect(page.getByRole('link', { name: 'Support on Ko-fi' })).toHaveAttribute('href', 'https://ko-fi.com/ciuse99');
  await expect(page.getByRole('link', { name: 'Buy Me a Coffee', exact: true })).toHaveAttribute('href', 'https://buymeacoffee.com/suggestarr');
  await page.getByRole('button', { name: 'I already supported', exact: true }).last().click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '100 titles requested with SuggestArr' })).toHaveCount(0);
  expect(actions).toEqual(['supported']);
});

test('profile preferences survive reload and can be re-enabled', async ({ page }) => {
  const { actions } = await openJourney(page, { profile: true });
  const select = page.getByLabel('Reminders in Home');
  await expect(select).toBeEnabled();
  await select.selectOption('disabled');
  await page.getByRole('button', { name: 'Save preferences' }).click();
  await expect(page.getByRole('button', { name: 'Save preferences' })).toBeEnabled();
  await page.reload();
  await expect(select).toHaveValue('disabled');
  await select.selectOption('enabled');
  await page.getByRole('button', { name: 'Save preferences' }).click();
  await expect(page.getByRole('button', { name: 'Save preferences' })).toBeEnabled();
  expect(actions).toEqual(['disable', 'enable']);
});

test('recap API calls honor the configured subpath', async ({ page }) => {
  const { requests } = await openJourney(page, { subpath: true });
  await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '100 titles requested with SuggestArr' })).toBeVisible();
  expect(requests.every(request => request.path.startsWith('/suggestarr/api/recap'))).toBeTruthy();
});

test('reduced-motion preference disables the badge animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openJourney(page);
  await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
  const animation = await page.locator('section[aria-labelledby="journey-title"] > div > div > span').first().evaluate(element => getComputedStyle(element).animationName);
  expect(animation).toBe('none');
});

test('native sharing receives the rendered PNG and aggregate caption', async ({ page }) => {
  const { errors } = await openJourney(page, { nativeShare: true });
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  const share = page.getByRole('button', { name: 'Share', exact: true });
  await expect(share).toBeEnabled();
  await share.click();
  const shared = await page.evaluate(() => window.sharedRecap);
  expect(shared.type).toBe('image/png');
  expect(shared.size).toBeGreaterThan(1000);
  expect(shared.text).toContain('100 titles requested with SuggestArr');
  expect(shared.text).not.toContain('admin');
  expect(errors).toEqual([]);
});

test('covers can be hidden without changing the recap aspect ratio', async ({ page }) => {
  await openJourney(page);
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await page.getByLabel('Show top-title covers').uncheck();
  await expect(page.getByLabel('Featured covers')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  expect(await page.locator('canvas').evaluate(canvas => canvas.width / canvas.height)).toBe(4 / 5);
});

test('Reddit comes first and saves an image before opening the post composer', async ({ page }) => {
  await page.context().route('https://www.reddit.com/submit*', route => route.fulfill({ contentType: 'text/html', body: '<h1>Reddit composer fixture</h1>' }));
  await openJourney(page);
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  const shortcuts = page.getByRole('dialog').locator('a');
  await expect(shortcuts.first()).toHaveText('Reddit');
  for (const platform of ['Discord', 'X', 'Bluesky']) await expect(page.getByRole('dialog').getByRole('link', { name: platform, exact: true })).toBeVisible();
  const download = page.waitForEvent('download');
  const popup = page.waitForEvent('popup');
  await page.getByRole('link', { name: 'Reddit', exact: true }).click();
  expect((await download).suggestedFilename()).toBe('suggestarr-recap.png');
  const composer = await popup;
  await composer.waitForLoadState();
  expect(new URL(composer.url()).hostname).toBe('www.reddit.com');
  expect(new URL(composer.url()).searchParams.get('type')).toBe('IMAGE');
  await expect(page.getByRole('status')).toContainText('PNG saved. Attach it to your Reddit post.');
  await composer.close();
});

test('Discord shortcut copies the PNG for the selected conversation', async ({ page }) => {
  await page.addInitScript(() => {
    navigator.clipboard.write = async items => { window.copiedImageType = items[0].types[0]; };
  });
  await page.context().route('https://discord.com/channels/@me', route => route.fulfill({ contentType: 'text/html', body: '<h1>Discord fixture</h1>' }));
  await openJourney(page);
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  const popup = page.waitForEvent('popup');
  await page.getByRole('dialog').getByRole('link', { name: 'Discord', exact: true }).click();
  const discord = await popup;
  await expect(page.getByRole('status')).toContainText('Image copied. Choose a Discord conversation');
  expect(await page.evaluate(() => window.copiedImageType)).toBe('image/png');
  await discord.close();
});

test('Discord falls back to a PNG download when clipboard access is unavailable', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true }); });
  await page.context().route('https://discord.com/channels/@me', route => route.fulfill({ contentType: 'text/html', body: '<h1>Discord fixture</h1>' }));
  const { errors } = await openJourney(page);
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  const downloaded = page.waitForEvent('download');
  const popup = page.waitForEvent('popup');
  await page.getByRole('dialog').getByRole('link', { name: 'Discord', exact: true }).click();
  expect((await downloaded).suggestedFilename()).toBe('suggestarr-recap.png');
  await expect(page.getByRole('status')).toContainText('PNG saved. Attach it to your Discord post.');
  await (await popup).close();
  expect(errors).toEqual([]);
});
