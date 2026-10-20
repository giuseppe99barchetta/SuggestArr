import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { posterFixture, titles } from './fixtures/recapPosters.js';

const badgeThresholds = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000];
const badgeLabels = { 10: 'First discoveries', 50: 'Half-century', 100: 'Century club', 250: 'Film buff', 500: 'Discovery enthusiast',
  1000: 'A thousand discoveries', 2500: 'Marathon curator', 5000: 'Cinema explorer', 10000: 'Discovery legend' };
const unlockDate = index => `2026-10-${String(index + 1).padStart(2, '0')}T12:00:00+00:00`;

/** Badges as the API returns them: each title badge was unlocked after the anniversary. */
function recapBadges(total, { watched = null } = {}) {
  const badges = badgeThresholds.map((threshold, i) => ({ id: `titles_${threshold}`, kind: 'titles', threshold,
    label: badgeLabels[threshold], description: `Request ${threshold.toLocaleString('en-US')} titles`,
    progress: Math.min(total, threshold), unlocked: total >= threshold, unlocked_at: total >= threshold ? unlockDate(i) : null }));
  if (watched != null) badges.push({ id: 'watched_1', kind: 'watched', threshold: 1, label: 'First pick watched',
    description: 'Watch a title SuggestArr requested', progress: Math.min(watched, 1), unlocked: watched >= 1,
    unlocked_at: watched >= 1 ? '2026-10-15T12:00:00+00:00' : null });
  badges.push({ id: 'one_year', kind: 'days', threshold: 365, label: 'One year of discoveries',
    description: 'One year since your first recorded request', progress: total ? 365 : 0, unlocked: total > 0,
    unlocked_at: total ? '2026-09-01T00:00:00+00:00' : null, unlocks_at: total ? '2026-09-01T00:00:00+00:00' : null });
  return badges;
}

const supportPrompt = page => page.getByRole('complementary', { name: 'Enjoying the discoveries?' });
const openSharePanel = page => page.getByRole('button', { name: 'Share recap' }).click();

async function openJourney(page, { width = 1280, role = 'admin', total = 100, linked = true, profile = false, subpath = false, failPosters = false, missingPosters = false, nativeShare = false, watched = null } = {}) {
  await page.setViewportSize({ width, height: 1000 });
  const errors = [];
  const actions = [];
  const requests = [];
  let mode = 'enabled';
  let claimed = false;
  const nextThreshold = badgeThresholds.find(threshold => threshold > total);
  page.on('pageerror', error => errors.push(error.message));
  const recap = {
    scope: role === 'admin' ? 'installation' : 'personal', has_linked_profiles: linked,
    total, movies: Math.ceil(total * 0.72), tv: total - Math.ceil(total * 0.72),
    first_requested_at: total ? '2025-09-01T00:00:00+00:00' : null,
    badges: recapBadges(total, { watched }),
    watch_tracking: watched != null, watched, hit_rate: watched != null && total ? Math.round(watched * 100 / total) : null,
    streak: watched != null ? { current: 2, longest: 3 } : null,
    next_badge: nextThreshold ? { id: `titles_${nextThreshold}`, threshold: nextThreshold, label: badgeLabels[nextThreshold] } : null,
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
    if (url.pathname.endsWith('/recap/watch-sync')) return route.fulfill({ json: { status: 'success', data: { status: 'ok', matched: 0 } }, headers });
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

for (const width of [1280, 768, 390, 320]) {
  test(`support invitation and dialog stay usable at ${width}px`, async ({ page }, testInfo) => {
    const { errors } = await openJourney(page, { width, total: 597 });
    await page.setViewportSize({ width, height: width <= 390 ? 640 : 900 });
    const journey = page.getByRole('region', { name: 'Your SuggestArr journey' });
    await expect(journey.getByText('597', { exact: true })).toHaveCount(0);
    await expect(journey.getByText('500', { exact: true })).toBeVisible();
    await expect(journey.getByText('Discovery enthusiast', { exact: true })).toBeVisible();
    await expect(journey.getByRole('button', { name: 'Create your recap', exact: true })).toHaveCount(1);
    await expect(journey.getByRole('button', { name: 'Remind me in 30 days' })).toBeHidden();
    await page.screenshot({ path: testInfo.outputPath('journey-panel.png'), fullPage: true, animations: 'disabled' });
    await supportPrompt(page).getByRole('button', { name: 'Support SuggestArr', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Support SuggestArr' });
    await expect(dialog.getByRole('link', { name: 'Support on Ko-fi' })).toBeVisible();
    await expect(dialog.getByRole('link', { name: 'Buy Me a Coffee', exact: true })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'I already supported' })).toBeHidden();
    await page.screenshot({ path: testInfo.outputPath('support-dialog.png'), animations: 'disabled' });
    const layout = await dialog.evaluate(element => {
      const bounds = element.getBoundingClientRect();
      return { left: bounds.left, right: bounds.right, overflow: element.scrollWidth > element.clientWidth };
    });
    expect(layout.left).toBeGreaterThanOrEqual(0);
    expect(layout.right).toBeLessThanOrEqual(width);
    expect(layout.overflow).toBeFalsy();
    await dialog.getByRole('button', { name: 'Reminder options' }).focus();
    await page.keyboard.press('Enter');
    await expect(dialog.getByRole('button', { name: 'I already supported' })).toBeVisible();
    await expect(dialog.getByRole('button', { name: "Don't show these reminders" })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(supportPrompt(page).getByRole('button', { name: 'Support SuggestArr', exact: true })).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    expect(errors).toEqual([]);
  });
}

for (const width of [1280, 390]) {
  test(`journey, badges and PNG work at ${width}px`, async ({ page }, testInfo) => {
    const { errors } = await openJourney(page, { width });
    await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
    await expect(supportPrompt(page)).toContainText('100 titles requested');
    await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
    await expect(page.getByRole('heading', { name: 'Your badges' })).toBeHidden();
    const downloadButton = page.getByRole('button', { name: 'Download PNG' });
    await expect(downloadButton).toBeEnabled();
    await expect(page.getByRole('button', { name: 'Share', exact: true })).toHaveCount(0);
    await expect(page.getByLabel('Show top-title covers')).toBeChecked();
    await expect(page.getByRole('img', { name: /100 titles requested with SuggestArr/ })).toBeVisible();
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

for (const { width, height } of [{ width: 1280, height: 720 }, { width: 768, height: 720 }, { width: 390, height: 640 }, { width: 320, height: 568 }, { width: 844, height: 480 }]) {
  test(`recap fits the viewport with preview and actions together at ${width}x${height}`, async ({ page }, testInfo) => {
    const { errors } = await openJourney(page, { width, total: 597 });
    await page.setViewportSize({ width, height });
    await expect(page.getByText('403 more titles to unlock')).toBeVisible();
    await page.getByRole('button', { name: 'Create your recap', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Your SuggestArr recap' });
    const download = dialog.getByRole('button', { name: 'Download PNG' });
    await expect(download).toBeEnabled();
    await expect(dialog.getByRole('tab')).toHaveCount(0);
    // A full-viewport player like the year recap: the image leads, controls sit below it.
    const bounds = await dialog.boundingBox();
    expect(bounds.width).toBeCloseTo(width, 0);
    expect(bounds.height).toBeCloseTo(height, 0);
    await page.screenshot({ path: testInfo.outputPath('recap-preview.png'), animations: 'disabled' });
    const image = await page.locator('canvas').boundingBox();
    const button = await download.boundingBox();
    expect(image.y).toBeGreaterThanOrEqual(0);
    expect(image.x).toBeGreaterThanOrEqual(0);
    expect(image.x + image.width).toBeLessThanOrEqual(width);
    expect(image.y + image.height).toBeLessThan(button.y);
    expect(image.width / image.height).toBeCloseTo(4 / 5, 2);
    expect(button.y + button.height).toBeLessThanOrEqual(height);
    await openSharePanel(page);
    await expect(dialog.getByRole('link', { name: 'Reddit', exact: true })).toBeVisible();
    await expect(dialog.getByLabel('Caption')).toBeAttached();
    await page.screenshot({ path: testInfo.outputPath('recap-share.png'), animations: 'disabled' });
    await page.keyboard.press('Escape');
    await expect(dialog.getByRole('complementary', { name: 'Share' })).toHaveCount(0);
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Badges · 6 / 10 unlocked' }).click();
    await expect(page.getByRole('dialog', { name: 'Your badges' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByLabel('Show top-title covers')).toBeChecked();
    await page.screenshot({ path: testInfo.outputPath('recap-badges.png'), animations: 'disabled' });
    const overflow = await dialog.evaluate(element => {
      const body = element.querySelector(':scope > div');
      return { outer: element.scrollHeight - element.clientHeight, body: body.scrollHeight - body.clientHeight, horizontal: element.scrollWidth - element.clientWidth };
    });
    expect(overflow.outer).toBeLessThanOrEqual(1);
    expect(overflow.body).toBeLessThanOrEqual(1);
    expect(overflow.horizontal).toBeLessThanOrEqual(1);
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
  await expect(page.getByRole('region', { name: 'Your SuggestArr journey' }).getByRole('button', { name: 'Support SuggestArr', exact: true })).toHaveCount(0);
  await page.locator('footer').getByRole('button', { name: 'Support SuggestArr', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Support SuggestArr' }).getByRole('link', { name: 'Support on Ko-fi' })).toBeVisible();
  await expect(page.getByRole('dialog').getByText('Reminder options')).toHaveCount(0);
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
  await supportPrompt(page).getByRole('button', { name: 'Reminder options' }).click();
  await page.getByRole('menuitem', { name: 'Remind me in 30 days' }).click();
  await expect(supportPrompt(page)).toHaveCount(0);
  expect(actions).toEqual(['remind_later']);
});

test('support dialog offers both providers and honors already supported', async ({ page }) => {
  const { actions } = await openJourney(page);
  await page.getByRole('button', { name: 'Support SuggestArr', exact: true }).first().click();
  await expect(page.getByRole('link', { name: 'Support on Ko-fi' })).toHaveAttribute('href', 'https://ko-fi.com/ciuse99');
  await expect(page.getByRole('link', { name: 'Buy Me a Coffee', exact: true })).toHaveAttribute('href', 'https://buymeacoffee.com/suggestarr');
  await page.getByRole('dialog').getByRole('button', { name: 'Reminder options' }).click();
  await page.getByRole('button', { name: 'I already supported', exact: true }).last().click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(supportPrompt(page)).toHaveCount(0);
  expect(actions).toEqual(['supported']);
});

test('dismissing the invitation preserves the journey and recap action', async ({ page }, testInfo) => {
  const { actions } = await openJourney(page, { total: 597 });
  await supportPrompt(page).getByRole('button', { name: 'Not now' }).click();
  await expect(supportPrompt(page)).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create your recap' })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('journey-without-reminder.png'), animations: 'disabled' });
  expect(actions).toEqual(['dismiss']);
});

test('support preference errors keep the dialog open and allow retry', async ({ page }) => {
  const { actions } = await openJourney(page);
  await page.getByRole('button', { name: 'Support SuggestArr', exact: true }).first().click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Reminder options' }).click();
  await page.route('**/api/recap/preferences', route => route.fulfill({ status: 500, json: { status: 'error' } }), { times: 1 });
  await dialog.getByRole('button', { name: "Don't show these reminders" }).click();
  await expect(dialog.getByRole('alert')).toContainText('Unable to save your preferences');
  await expect(dialog.getByRole('button', { name: "Don't show these reminders" })).toBeEnabled();
  await dialog.getByRole('button', { name: "Don't show these reminders" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(supportPrompt(page)).toHaveCount(0);
  expect(actions).toEqual(['disable']);
});

test('profile preferences survive reload and can be re-enabled', async ({ page }) => {
  const { actions } = await openJourney(page, { profile: true });
  const disabled = page.getByRole('radio', { name: 'Off', exact: true });
  const enabled = page.getByRole('radio', { name: 'Occasional', exact: true });
  await expect(enabled).toBeChecked();
  await disabled.check({ force: true });
  await expect.poll(() => actions).toEqual(['disable']);
  await page.reload();
  await expect(disabled).toBeChecked();
  await enabled.check({ force: true });
  await expect.poll(() => actions).toEqual(['disable', 'enable']);
  expect(actions).toEqual(['disable', 'enable']);
});

test('recap API calls honor the configured subpath', async ({ page }) => {
  const { requests } = await openJourney(page, { subpath: true });
  await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
  await expect(supportPrompt(page)).toContainText('100 titles requested');
  expect(requests.every(request => request.path.startsWith('/suggestarr/api/recap'))).toBeTruthy();
});

test('journey respects reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openJourney(page);
  await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
  const animations = await page.getByRole('region', { name: 'Your SuggestArr journey' }).evaluate(element => element.getAnimations({ subtree: true }).filter(animation => animation.playState === 'running').length);
  expect(animations).toBe(0);
});

test('native sharing receives the rendered PNG and aggregate caption', async ({ page }) => {
  const { errors } = await openJourney(page, { nativeShare: true });
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await openSharePanel(page);
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
  const original = await page.locator('canvas').evaluate(canvas => canvas.toDataURL());
  await page.getByLabel('Show top-title covers').uncheck();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  expect(await page.locator('canvas').evaluate(canvas => canvas.toDataURL())).not.toBe(original);
  await expect(page.getByLabel('Show top-title covers')).not.toBeChecked();
  expect(await page.locator('canvas').evaluate(canvas => canvas.width / canvas.height)).toBe(4 / 5);
});

test('Reddit comes first and saves an image before opening the post composer', async ({ page }) => {
  await page.addInitScript(() => { navigator.clipboard.write = async items => { window.copiedImageType = items[0].types[0]; }; });
  await page.context().route('https://www.reddit.com/submit*', route => route.fulfill({ contentType: 'text/html', body: '<h1>Reddit composer fixture</h1>' }));
  await openJourney(page);
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await openSharePanel(page);
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
  await expect(page.getByRole('status')).toContainText('PNG also saved for upload.');
  expect(await page.evaluate(() => window.copiedImageType)).toBe('image/png');
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
  await openSharePanel(page);
  const popup = page.waitForEvent('popup');
  await page.getByRole('dialog').getByRole('link', { name: 'Discord', exact: true }).click();
  const discord = await popup;
  await expect(page.getByRole('status')).toContainText('Image copied. Paste it into your Discord conversation.');
  expect(await page.evaluate(() => window.copiedImageType)).toBe('image/png');
  await discord.close();
});

test('Discord falls back to a PNG download when clipboard access is unavailable', async ({ page }) => {
  await page.addInitScript(() => { Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true }); });
  await page.context().route('https://discord.com/channels/@me', route => route.fulfill({ contentType: 'text/html', body: '<h1>Discord fixture</h1>' }));
  const { errors } = await openJourney(page);
  await page.getByRole('button', { name: 'Create your recap', exact: true }).first().click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await openSharePanel(page);
  const downloaded = page.waitForEvent('download');
  const popup = page.waitForEvent('popup');
  await page.getByRole('dialog').getByRole('link', { name: 'Discord', exact: true }).click();
  expect((await downloaded).suggestedFilename()).toBe('suggestarr-recap.png');
  await expect(page.getByRole('status')).toContainText('PNG saved. Attach it to your Discord post.');
  await (await popup).close();
  expect(errors).toEqual([]);
});

test('copy image confirms on its button and resets without shifting the preview', async ({ page }) => {
  await page.clock.install();
  await page.addInitScript(() => { navigator.clipboard.write = async items => { window.copiedImageType = items[0].types[0]; }; });
  await openJourney(page);
  await page.getByRole('button', { name: 'Create your recap', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Your SuggestArr recap' });
  await expect(dialog.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await openSharePanel(page);
  const before = await dialog.boundingBox();
  await dialog.getByRole('button', { name: 'Copy image', exact: true }).click();
  await expect(dialog.getByRole('button', { name: 'Copied!', exact: true })).toBeVisible();
  await expect(dialog.getByText('Image copied. Paste it into your post or Discord conversation.')).toHaveCount(0);
  expect((await dialog.boundingBox()).height).toBeCloseTo(before.height, 0);
  expect(await page.evaluate(() => window.copiedImageType)).toBe('image/png');
  await page.clock.fastForward(2600);
  await expect(dialog.getByRole('button', { name: 'Copy image', exact: true })).toBeVisible();
});

for (const platform of [{ name: 'X', url: 'https://twitter.com/intent/tweet*' }, { name: 'Bluesky', url: 'https://bsky.app/intent/compose*' }]) {
  test(`${platform.name} carries the PNG in the clipboard without overwriting it with text`, async ({ page }) => {
    await page.addInitScript(() => {
      navigator.clipboard.write = async items => { window.copiedImageType = items[0].types[0]; };
      navigator.clipboard.writeText = async () => { window.textOverwroteImage = true; };
    });
    await page.context().route(platform.url, route => route.fulfill({ contentType: 'text/html', body: 'Composer fixture' }));
    await openJourney(page);
    await page.getByRole('button', { name: 'Create your recap', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
    await openSharePanel(page);
      const popup = page.waitForEvent('popup');
    await page.getByRole('link', { name: platform.name, exact: true }).click();
    const composer = await popup;
    await expect(page.getByRole('status')).toContainText(`Paste it into your ${platform.name} post.`);
    expect(await page.evaluate(() => window.copiedImageType)).toBe('image/png');
    expect(await page.evaluate(() => window.textOverwroteImage)).toBeUndefined();
    await composer.close();
  });
}

test('denied image clipboard downloads a PNG and sharing feedback expires', async ({ page }) => {
  await page.clock.install();
  await page.addInitScript(() => { navigator.clipboard.write = async () => { throw new DOMException('Denied', 'NotAllowedError'); }; });
  await page.context().route('https://discord.com/channels/@me', route => route.fulfill({ contentType: 'text/html', body: 'Discord fixture' }));
  await openJourney(page);
  await page.getByRole('button', { name: 'Create your recap', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await openSharePanel(page);
  const popup = page.waitForEvent('popup');
  const download = page.waitForEvent('download');
  await page.getByRole('dialog').getByRole('link', { name: 'Discord', exact: true }).click();
  const composer = await popup;
  expect((await download).suggestedFilename()).toBe('suggestarr-recap.png');
  await expect(page.getByRole('status')).toContainText('PNG saved. Attach it to your Discord post.');
  await page.clock.fastForward(5100);
  await expect(page.getByRole('status')).toHaveCount(0);
  await composer.close();
});

test('the badge collection opens from the recap and Home with up next, details and sharing', async ({ page }, testInfo) => {
  await openJourney(page, { total: 597 });
  await page.getByRole('button', { name: 'Create your recap', exact: true }).click();
  const recapDialog = page.getByRole('dialog', { name: 'Your SuggestArr recap' });
  await recapDialog.getByRole('button', { name: /Badges · 6 \/ 10 unlocked/ }).click();
  const badges = page.getByRole('dialog', { name: 'Your badges' });
  await expect(badges.getByText('6 of 10 unlocked')).toBeVisible();
  await expect(badges.getByText('Latest badge')).toBeVisible();
  // Up next leads with the closest locked badge.
  const upNext = badges.getByRole('region', { name: 'Up next' });
  await expect(upNext.getByRole('listitem')).toHaveCount(3);
  await expect(upNext.getByRole('listitem').first()).toContainText('A thousand discoveries');
  await expect(upNext.getByRole('listitem').first()).toContainText('403 more titles to go');
  await expect(badges.getByRole('list', { name: 'Titles requested' }).getByRole('listitem')).toHaveCount(9);
  await expect(badges.getByRole('heading', { name: 'Anniversaries' })).toBeVisible();
  await expect(badges.getByText('Connect Plex or Jellyfin to unlock badges for the suggestions you actually watch.')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('badge-gallery.png'), animations: 'disabled' });
  // A locked badge expands what is still missing; tiles stay compact.
  await badges.getByRole('button', { name: 'Cinema explorer, locked' }).click();
  await expect(badges.getByRole('region', { name: 'Cinema explorer details' })).toContainText('Request 5,000 titles · 4,403 more titles to go');
  await badges.getByRole('button', { name: 'Cinema explorer, locked' }).click();
  await expect(badges.getByRole('region', { name: 'Cinema explorer details' })).toHaveCount(0);
  // An earned badge opens its shareable view without confetti.
  await badges.getByRole('button', { name: 'Century club, unlocked' }).click();
  const earned = page.getByRole('dialog', { name: 'Badge unlocked' });
  await expect(earned.getByRole('heading', { name: 'Century club' })).toBeVisible();
  await expect(earned.getByText('Congratulations!')).toHaveCount(0);
  await expect(earned.getByRole('button', { name: 'See all your badges' })).toHaveCount(0);
  await earned.getByRole('button', { name: 'Share badge' }).click();
  await expect(earned.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await page.keyboard.press('Escape');
  await expect(earned).toHaveCount(0);
  await expect(badges).toBeVisible();
  await page.keyboard.press('Escape');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('button', { name: 'Open your badges' }).click();
  await expect(page.getByRole('dialog', { name: 'Your badges' })).toBeVisible();
});

test('edited captions feed the composers and can be reset', async ({ page }) => {
  await openJourney(page);
  await page.getByRole('button', { name: 'Create your recap', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Your SuggestArr recap' });
  await openSharePanel(page);
  const caption = dialog.getByLabel('Caption');
  await expect(caption).toHaveValue(/100 titles requested with SuggestArr/);
  await caption.fill('My own words about SuggestArr');
  const text = async name => new URL(await dialog.getByRole('link', { name, exact: true }).getAttribute('href')).searchParams.get('text');
  expect(await text('X')).toBe('My own words about SuggestArr');
  expect(await text('Bluesky')).toBe('My own words about SuggestArr');
  await caption.fill('x'.repeat(301));
  await expect(dialog.getByText('Too long for Bluesky · 301 / 300')).toBeVisible();
  await dialog.getByRole('button', { name: 'Reset', exact: true }).click();
  await expect(caption).toHaveValue(/100 titles requested with SuggestArr/);
  await expect(dialog.getByRole('button', { name: 'Reset', exact: true })).toHaveCount(0);
});

test('native sharing failure saves the image while cancelling leaves the dialog alone', async ({ page }) => {
  await openJourney(page, { nativeShare: true });
  await page.getByRole('button', { name: 'Create your recap', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await openSharePanel(page);
  const downloads = [];
  page.on('download', file => downloads.push(file.suggestedFilename()));
  await page.evaluate(() => { Object.defineProperty(navigator, 'share', { value: async () => { throw new DOMException('Cancelled', 'AbortError'); }, configurable: true }); });
  await page.getByRole('button', { name: 'Share', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Share', exact: true })).toBeEnabled();
  expect(downloads).toEqual([]);
  await expect(page.getByRole('status')).toHaveCount(0);
  await page.evaluate(() => { Object.defineProperty(navigator, 'share', { value: async () => { throw new DOMException('Unsupported', 'DataError'); }, configurable: true }); });
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Share', exact: true }).click();
  expect((await download).suggestedFilename()).toBe('suggestarr-recap.png');
  await expect(page.getByRole('status')).toContainText('PNG saved so you can attach it.');
});

test('a newly unlocked badge opens a celebration with confetti, sharing and support', async ({ page }, testInfo) => {
  const { errors, requests } = await openJourney(page, { total: 597, watched: 120 });
  await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
  // The first visit stored every badge as seen; pretend two were unlocked since then.
  await page.evaluate(() => {
    const key = Object.keys(localStorage).find(name => name.startsWith('suggestarr-recap-seen-badges:'));
    localStorage.setItem(key, JSON.stringify(['titles_10', 'titles_50', 'titles_100', 'titles_250', 'one_year']));
  });
  await page.reload();
  const dialog = page.getByRole('dialog', { name: 'Badge unlocked' });
  await expect(dialog).toBeVisible();
  // The most recent unlock leads; the other new badge can be selected.
  await expect(dialog.getByRole('heading', { name: 'First pick watched' })).toBeVisible();
  await expect(dialog.getByText('2 new badges since your last visit')).toBeVisible();
  await expect(dialog.locator('canvas[aria-hidden="true"]')).toHaveCount(1);
  await page.waitForTimeout(900);
  await page.screenshot({ path: testInfo.outputPath('badge-celebration.png') });
  // Sharing stays one click away so the badge leads the dialog.
  await expect(dialog.getByRole('button', { name: 'Download PNG' })).toHaveCount(0);
  await dialog.getByRole('button', { name: 'Share badge' }).click();
  await expect(dialog.getByRole('button', { name: 'Download PNG' })).toBeEnabled();
  await expect(dialog.getByRole('img', { name: 'First pick watched badge image' })).toBeVisible();
  await expect(dialog.getByLabel('Caption')).toHaveValue(/Badge unlocked on SuggestArr: First pick watched/);
  await page.screenshot({ path: testInfo.outputPath('badge-celebration-share.png'), animations: 'disabled' });
  await dialog.getByRole('button', { name: 'Discovery enthusiast' }).click();
  await expect(dialog.getByRole('heading', { name: 'Discovery enthusiast' })).toBeVisible();
  await expect(dialog.getByLabel('Caption')).toHaveValue(/Discovery enthusiast — Request 500 titles/);
  await dialog.getByRole('button', { name: 'Support SuggestArr' }).click();
  await expect(page.getByRole('dialog', { name: 'Support SuggestArr' }).getByRole('link', { name: 'Support on Ko-fi' })).toBeVisible();
  await page.keyboard.press('Escape');
  await page.reload();
  // Seen badges do not celebrate again.
  await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Badge unlocked' })).toHaveCount(0);
  const journey = page.getByRole('region', { name: 'Your SuggestArr journey' });
  await expect(journey.getByText('20% of picks watched')).toBeVisible();
  await expect(journey.getByText('2-month watch streak')).toBeVisible();
  await expect(journey.getByText('First pick watched', { exact: true })).toBeVisible();
  expect(requests.filter(request => request.path.endsWith('/recap/watch-sync')).length).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});

test('the first visit records existing badges without a celebration', async ({ page }) => {
  await openJourney(page, { total: 597 });
  await expect(page.getByRole('heading', { name: 'Your SuggestArr journey' })).toBeVisible();
  await expect(page.getByRole('dialog', { name: 'Badge unlocked' })).toHaveCount(0);
  const seen = await page.evaluate(() => Object.entries(localStorage).find(([name]) => name.startsWith('suggestarr-recap-seen-badges:')));
  expect(seen[0]).toMatch(/:installation$/);
  expect(JSON.parse(seen[1])).toHaveLength(6);
});
