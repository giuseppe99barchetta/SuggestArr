import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const storyTitles = ['Your 2026, on screen', 'Discovery, on autopilot', 'You pressed play', 'Time well watched', 'Your kind of stories', 'The titles that defined your year', 'Your year, wrapped'];

async function openPreview(page, { admin = true, journey = false, width = 1280, height = 1000, reducedMotion = true, date } = {}) {
  if (date) await page.clock.setFixedTime(new Date(date));
  await page.setViewportSize({ width, height });
  await page.emulateMedia({ reducedMotion: reducedMotion ? 'reduce' : 'no-preference' });
  const errors = [];
  const apiCalls = [];
  const remoteArtwork = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route(url => url.pathname.startsWith('/api/'), route => {
    apiCalls.push(route.request().url());
    return route.fulfill({ status: 500, json: { status: 'error' } });
  });
  await page.route('https://image.tmdb.org/**', route => { remoteArtwork.push(route.request().url()); return route.abort(); });
  await page.route('**/year-recap-preview', route => route.fulfill({
    contentType: 'text/html',
    body: `<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="preview"></div><script type="module">import { mountYearPreview } from '/e2e/fixtures/yearRecapPreview.js'; mountYearPreview(${JSON.stringify({ admin, journey })});</script></body></html>`,
  }));
  await page.goto('/year-recap-preview');
  if (!journey) await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  return { errors, apiCalls, remoteArtwork };
}

/** Open the options or share panel of the story viewer (no-op when it is already open). */
async function openPanel(page, name) {
  const toggle = page.getByRole('button', { name, exact: true });
  if (await toggle.getAttribute('aria-expanded') !== 'true') await toggle.click();
}
const openOptions = page => openPanel(page, 'Recap options');
const openShare = page => openPanel(page, 'Share this story');

async function go(page, index) {
  await page.getByRole('button', { name: `Go to story ${index + 1}: ${storyTitles[index]}`, exact: true }).click();
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  await expect(page.getByRole('heading', { name: storyTitles[index], exact: true })).toBeVisible();
}

test('all seven personal stories export distinct, complete 1080×1920 PNGs offline', async ({ page }, testInfo) => {
  const { errors, apiCalls, remoteArtwork } = await openPreview(page);
  const pngSizes = [];
  await openShare(page);
  for (let index = 0; index < 7; index += 1) {
    await go(page, index);
    await expect(page.getByRole('img')).toHaveAttribute('aria-label', /Fictional sample data for 2026/);
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download this story', exact: true }).click();
    const file = await download;
    expect(file.suggestedFilename()).toMatch(/2026-.*-preview\.png/);
    const path = testInfo.outputPath(`story-${index + 1}.png`);
    await file.saveAs(path);
    const png = readFileSync(path);
    expect(png.readUInt32BE(16)).toBe(1080);
    expect(png.readUInt32BE(20)).toBe(1920);
    pngSizes.push(png.length);
    // Every story offers the same sharing options, not only the summary.
    await expect(page.getByRole('link', { name: 'Reddit', exact: true })).toBeAttached();
  }
  expect(new Set(pngSizes).size).toBe(7);
  await expect(page.getByRole('button', { name: 'Download summary', exact: true })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('desktop-player.png'), animations: 'disabled' });
  expect(errors).toEqual([]);
  expect(apiCalls).toEqual([]);
  expect(remoteArtwork).toEqual([]);
});

for (const width of [390, 320]) {
  test(`player fits mobile at ${width}px and preserves the story aspect ratio`, async ({ page }, testInfo) => {
    const { errors } = await openPreview(page, { width, height: width === 320 ? 640 : 844 });
    const box = await page.getByRole('img').boundingBox();
    expect(box.width / box.height).toBeCloseTo(9 / 16, 3);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.getByRole('button', { name: 'Next story', exact: true }).click();
    await expect(page.getByRole('heading', { name: storyTitles[1], exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('mobile-player.png'), animations: 'disabled' });
    await go(page, 6);
    await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeAttached();
    expect(await page.getByRole('dialog').evaluate(dialog => dialog.scrollWidth <= dialog.clientWidth + 1)).toBeTruthy();
    expect(errors).toEqual([]);
  });
}

for (const [width, height] of [[1080, 900], [1280, 720], [844, 480], [320, 568]]) {
  test(`complete story and controls stay inside the viewport at ${width}×${height}`, async ({ page }, testInfo) => {
    await openPreview(page, { width, height });
    const canvas = await page.getByRole('img').boundingBox();
    const previous = await page.getByRole('button', { name: 'Previous story', exact: true }).boundingBox();
    const next = await page.getByRole('button', { name: 'Next story', exact: true }).boundingBox();
    expect(canvas.width / canvas.height).toBeCloseTo(9 / 16, 3);
    for (const box of [canvas, previous, next]) {
      expect(box.y).toBeGreaterThanOrEqual(0);
      expect(box.y + box.height).toBeLessThanOrEqual(height);
      expect(box.x + box.width).toBeLessThanOrEqual(width);
    }
    expect(canvas.y + canvas.height).toBeLessThan(previous.y);
    await page.screenshot({ path: testInfo.outputPath('complete-player.png'), animations: 'disabled' });
  });
}

function recordedFixture(year = 2026, scope = 'personal', playback = false) {
  const monthly = Array.from({ length: 12 }, (_, i) => ({ month: `M${i + 1}`, label: `Month ${i + 1}`, requests: i === 4 ? 7 : 0, minutes: null }));
  return { year, isDemo: false, scope, isYearToDate: true, allowedScopes: ['personal', 'server'], availableYears: [2026, 2025],
    hasLinkedProfiles: true, provider: 'jellyfin', providerLabel: 'Jellyfin', activeUsers: playback ? 1 : null,
    requested: { total: 7, movies: 5, series: 2 }, watched: playback ? { movies: 2, episodes: 6, series: 1 } : null,
    watchMinutes: null, watchStatus: playback ? 'partial' : 'not_loaded', watchNote: playback ? 'Jellyfin last-played snapshot. Actual watch time unavailable.' : 'Watch activity has not been loaded.',
    monthly, peakMonth: monthly[4], genres: [{ label: 'Drama', percent: 100 }], genreCoverage: 3,
    titles: [{ title: 'A recorded title', detail: 'Movie · 2026', poster_path: '/missing-test-cover.jpg' }] };
}

test('real yearly activity loads watch data automatically and follows scope and year changes', async ({ page }, testInfo) => {
  const { errors } = await openPreview(page);
  const calls = [];
  await page.route('**/api/recap/year?*', route => {
    const url = new URL(route.request().url());
    calls.push(Object.fromEntries(url.searchParams));
    return route.fulfill({ json: { status: 'success', data: recordedFixture(Number(url.searchParams.get('year')), url.searchParams.get('scope'), url.searchParams.get('include_playback') === 'true') } });
  });
  await openOptions(page);
  await page.getByLabel('Data source').selectOption('real');
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  // Watch activity comes with the recap; there is no manual loading step.
  expect(calls[0].include_playback).toBe('true');
  await expect(page.getByRole('button', { name: /watch activity/ })).toHaveCount(0);
  await page.getByRole('button', { name: /Go to story 2:/ }).click();
  await expect(page.getByRole('img')).toHaveAttribute('aria-label', /7 titles first recorded this year: 5 movies and 2 TV series/);
  await expect(page.getByRole('status')).toContainText('Some covers could not be loaded');
  await page.getByRole('button', { name: /Go to story 3:/ }).click();
  await expect(page.getByRole('img')).toHaveAttribute('aria-label', /2 movies, 6 episodes and 1 TV series/);
  await page.getByRole('button', { name: /Go to story 4:/ }).click();
  await expect(page.getByRole('img')).toHaveAttribute('aria-label', /7 recorded title requests across twelve months/);
  await page.getByLabel('Year', { exact: true }).selectOption('2025');
  await expect(page.getByRole('heading', { name: 'Your 2025, on screen', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  await page.getByLabel('Recap scope').selectOption('server');
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  expect(calls.at(-1).scope).toBe('server');
  await page.getByRole('button', { name: /Go to story 7:/ }).click();
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download this story', exact: true }).click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toBe('suggestarr-2025-summary-recorded.png');
  await file.saveAs(testInfo.outputPath('recorded-summary.png'));
  await openShare(page);
  const caption = new URL(await page.getByRole('link', { name: 'X', exact: true }).getAttribute('href')).searchParams.get('text');
  expect(caption).toContain('7 recorded titles');
  expect(caption).not.toContain('Sample');
  expect(errors).toEqual([]);
});

test('missing profiles and empty years never substitute sample statistics', async ({ page }) => {
  await openPreview(page, { admin: false });
  await page.route('**/api/recap/year?*', route => {
    const data = recordedFixture();
    Object.assign(data, { hasLinkedProfiles: false, allowedScopes: ['personal'], requested: { total: 0, movies: 0, series: 0 }, genres: [], titles: [], genreCoverage: 0 });
    data.monthly.forEach(month => { month.requests = 0; });
    return route.fulfill({ json: { status: 'success', data } });
  });
  await openOptions(page);
  await page.getByLabel('Data source').selectOption('real');
  await expect(page.getByRole('link', { name: 'Link your media account', exact: true })).toBeVisible();
  await expect(page.getByLabel('Recap scope')).toHaveCount(0);
  for (let index = 0; index < 7; index += 1) {
    await page.getByRole('button', { name: new RegExp(`Go to story ${index + 1}:`) }).click();
    await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
    await expect(page.getByRole('img')).not.toHaveAttribute('aria-label', /Fictional|248|314 hours/);
  }
});

test('annual API respects the configured subpath', async ({ page }) => {
  await openPreview(page);
  await page.evaluate(async () => {
    const { setApiBase } = await import('/e2e/fixtures/yearRecapPreview.js');
    setApiBase('/suggestarr');
  });
  let requested = false;
  await page.route('**/suggestarr/api/recap/year?*', route => {
    requested = true;
    return route.fulfill({ json: { status: 'success', data: recordedFixture() } });
  });
  await openOptions(page);
  await page.getByLabel('Data source').selectOption('real');
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  expect(requested).toBeTruthy();
});

test('admin scope and provider changes reset the story and update the sample numbers', async ({ page }) => {
  await openPreview(page);
  await go(page, 2);
  await openOptions(page);
  await page.getByLabel('Media server').selectOption('plex');
  await expect(page.getByRole('heading', { name: storyTitles[0], exact: true })).toBeVisible();
  await page.getByLabel('Recap scope').selectOption('server');
  await go(page, 1);
  await expect(page.getByRole('img')).toHaveAttribute('aria-label', /1240 titles requested: 880 movies and 360 TV series/);
  await go(page, 2);
  await expect(page.getByRole('img')).toHaveAttribute('aria-label', /410 movies, 2050 episodes and 170 TV series watched on Plex/);
  await go(page, 3);
  await expect(page.getByRole('img')).toHaveAttribute('aria-label', /1571 hours and 40 minutes/);
});

test('regular users have a personal preview without a server-scope selector', async ({ page }) => {
  const { apiCalls } = await openPreview(page, { admin: false });
  await openOptions(page);
  await expect(page.getByLabel('Recap scope')).toHaveCount(0);
  await openOptions(page);
  await page.getByLabel('Media server').selectOption('plex');
  await go(page, 1);
  await expect(page.getByRole('img')).toHaveAttribute('aria-label', /248 titles requested/);
  expect(apiCalls).toEqual([]);
});

test('every story renders in all four provider and scope combinations', async ({ page }) => {
  const { errors, apiCalls } = await openPreview(page);
  for (const provider of ['jellyfin', 'plex']) {
    for (const scope of ['personal', 'server']) {
      await openOptions(page);
      await page.getByLabel('Media server').selectOption(provider);
      await page.getByLabel('Recap scope').selectOption(scope);
      for (let index = 0; index < 7; index += 1) {
        await go(page, index);
        expect(await page.getByRole('img').evaluate(canvas => canvas.width / canvas.height)).toBe(9 / 16);
      }
    }
  }
  expect(errors).toEqual([]);
  expect(apiCalls).toEqual([]);
});

test('Home opens the preview even when recap API and linked profiles are unavailable', async ({ page }) => {
  const { apiCalls, remoteArtwork } = await openPreview(page, { journey: true, admin: false, date: '2026-12-20T12:00:00Z' });
  await page.getByRole('button', { name: 'Year recap', exact: true }).click();
  await openOptions(page);
  await page.getByLabel('Data source').selectOption('demo');
  const initialCalls = apiCalls.length;
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  await go(page, 3);
  expect(apiCalls.length).toBe(initialCalls);
  expect(remoteArtwork).toEqual([]);
  // Escape closes the open options panel first, then the viewer.
  await page.keyboard.press('Escape');
  await expect(page.getByRole('complementary', { name: 'Recap options' })).toHaveCount(0);
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

for (const admin of [true, false]) {
  test(`development Home keeps annual recap available outside its season for ${admin ? 'admins' : 'users'}`, async ({ page }) => {
    await openPreview(page, { journey: true, admin, date: '2026-10-19T12:00:00Z' });
    await expect(page.getByText('Your journey could not be loaded.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Year recap', exact: true })).toBeVisible();
    await page.clock.setFixedTime(new Date('2026-12-14T12:00:00Z'));
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(page.getByRole('button', { name: 'Year recap', exact: true })).toBeVisible();
    await page.clock.setFixedTime(new Date('2026-12-15T12:00:00Z'));
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(page.getByRole('button', { name: 'Year recap', exact: true })).toBeVisible();
    await page.clock.setFixedTime(new Date('2027-02-01T12:00:00Z'));
    await page.evaluate(() => window.dispatchEvent(new Event('focus')));
    await expect(page.getByRole('button', { name: 'Year recap', exact: true })).toBeVisible();
  });
}

test('January opens the previous year and development keeps the recap open after the season ends', async ({ page }) => {
  await openPreview(page, { journey: true, date: '2027-01-31T12:00:00Z' });
  let requestedYear;
  await page.route('**/api/recap/year?*', route => {
    requestedYear = new URL(route.request().url()).searchParams.get('year');
    return route.fulfill({ json: { status: 'success', data: recordedFixture(2026) } });
  });
  await page.getByRole('button', { name: 'Year recap', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  expect(requestedYear).toBe('2026');
  await expect(page.getByRole('heading', { name: '2026 Year recap', exact: true })).toBeVisible();
  await page.clock.setFixedTime(new Date('2027-02-01T12:00:00Z'));
  await page.evaluate(() => window.dispatchEvent(new Event('focus')));
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Year recap', exact: true })).toBeVisible();
});

test('keyboard navigation and reduced-motion playback work without animation', async ({ page }) => {
  await openPreview(page);
  await expect(page.getByRole('button', { name: 'Play stories', exact: true })).toBeVisible();
  await page.getByRole('img').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('heading', { name: storyTitles[1], exact: true })).toBeVisible();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByRole('heading', { name: storyTitles[0], exact: true })).toBeVisible();
  await page.keyboard.press('Space');
  await expect(page.getByRole('button', { name: 'Pause stories', exact: true })).toBeVisible();
  await page.keyboard.press('Space');
  await expect(page.getByRole('button', { name: 'Play stories', exact: true })).toBeVisible();
  expect(await page.getByRole('img').evaluate(canvas => canvas.getAnimations().length)).toBe(0);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('swipes navigate horizontally and ignore vertical scrolling gestures', async ({ page }) => {
  await openPreview(page, { width: 390, height: 844 });
  async function swipe(dx, dy) {
    await page.getByRole('img').evaluate((canvas, { dx, dy }) => {
      const touch = (x, y) => new Touch({ identifier: 1, target: canvas, clientX: x, clientY: y });
      canvas.dispatchEvent(new TouchEvent('touchstart', { bubbles: true, changedTouches: [touch(220, 200)] }));
      canvas.dispatchEvent(new TouchEvent('touchend', { bubbles: true, changedTouches: [touch(220 + dx, 200 + dy)] }));
    }, { dx, dy });
  }
  await swipe(-120, 5);
  await expect(page.getByRole('heading', { name: storyTitles[1], exact: true })).toBeVisible();
  await swipe(10, -180);
  await expect(page.getByRole('heading', { name: storyTitles[1], exact: true })).toBeVisible();
  await swipe(120, 5);
  await expect(page.getByRole('heading', { name: storyTitles[0], exact: true })).toBeVisible();
});

test('autoplay advances after eight seconds, pauses, resumes and holds the last story', async ({ page }) => {
  await page.clock.install();
  await openPreview(page, { reducedMotion: false });
  await page.clock.runFor(8100);
  await expect(page.getByRole('heading', { name: storyTitles[1], exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Pause stories', exact: true }).click();
  await page.clock.runFor(12000);
  await expect(page.getByRole('heading', { name: storyTitles[1], exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Play stories', exact: true }).click();
  await page.clock.runFor(8100);
  await expect(page.getByRole('heading', { name: storyTitles[2], exact: true })).toBeVisible();
  await go(page, 6);
  await page.clock.runFor(20000);
  await expect(page.getByRole('heading', { name: storyTitles[6], exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Next story', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Play stories', exact: true })).toBeVisible();
});

test('hidden tabs, lost focus and downloads pause playback', async ({ page }) => {
  await openPreview(page, { reducedMotion: false });
  await page.evaluate(() => window.dispatchEvent(new Event('blur')));
  await expect(page.getByRole('button', { name: 'Play stories', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Play stories', exact: true }).click();
  await page.evaluate(() => {
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
  });
  await expect(page.getByRole('button', { name: 'Play stories', exact: true })).toBeVisible();
  await page.evaluate(() => { Object.defineProperty(document, 'hidden', { value: false, configurable: true }); });
  await page.getByRole('button', { name: 'Play stories', exact: true }).click();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download this story', exact: true }).click();
  await downloaded;
  await expect(page.getByRole('button', { name: 'Play stories', exact: true })).toBeVisible();
});

test('summary Reddit shortcut exports a clearly marked demo and opens only a composer', async ({ page }) => {
  await page.context().route('https://www.reddit.com/submit*', route => route.fulfill({ contentType: 'text/html', body: 'Composer fixture' }));
  await openPreview(page);
  await go(page, 6);
  await openShare(page);
  const link = page.getByRole('link', { name: 'Reddit', exact: true });
  expect(new URL(await link.getAttribute('href')).searchParams.get('title')).toContain('Preview · Sample data');
  const popup = page.waitForEvent('popup');
  const download = page.waitForEvent('download');
  await link.click();
  expect((await download).suggestedFilename()).toBe('suggestarr-2026-summary-preview.png');
  const composer = await popup;
  await composer.waitForLoadState();
  expect(new URL(composer.url()).hostname).toBe('www.reddit.com');
  await composer.close();
});

test('native sharing and clipboard preserve PNG type, year and sample-data disclosure', async ({ page }) => {
  await page.clock.install();
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'canShare', { value: () => true, configurable: true });
    Object.defineProperty(navigator, 'share', { value: async data => { window.sharedYear = { title: data.title, text: data.text, name: data.files[0].name, type: data.files[0].type }; }, configurable: true });
    navigator.clipboard.write = async items => { window.copiedYearType = items[0].types[0]; };
    navigator.clipboard.writeText = async text => { window.copiedYearCaption = text; };
  });
  await openPreview(page);
  await openShare(page);
  await page.getByRole('button', { name: 'Share', exact: true }).click();
  const share = await page.evaluate(() => window.sharedYear);
  expect(share.text).toContain('Preview / Sample data');
  expect(share.name).toBe('suggestarr-2026-intro-preview.png');
  expect(share.type).toBe('image/png');
  await page.getByRole('button', { name: 'Copy image', exact: true }).click();
  expect(await page.evaluate(() => window.copiedYearType)).toBe('image/png');
  await page.getByRole('button', { name: 'Copy caption', exact: true }).click();
  expect(await page.evaluate(() => window.copiedYearCaption)).toContain('Preview / Sample data');
  await expect(page.getByRole('button', { name: 'Copied!', exact: true })).toHaveCount(2);
  await page.clock.fastForward(2600);
  await expect(page.getByRole('button', { name: 'Copy image', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Copy caption', exact: true })).toBeVisible();
});

test('tapping the story navigates by side and holding pauses autoplay', async ({ page }) => {
  await page.clock.install();
  await openPreview(page, { reducedMotion: false });
  const frame = page.getByRole('img');
  const box = await frame.boundingBox();
  await page.mouse.click(box.x + box.width * 0.8, box.y + box.height / 2);
  await expect(page.getByRole('heading', { name: storyTitles[1], exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  await page.mouse.click(box.x + box.width * 0.1, box.y + box.height / 2);
  await expect(page.getByRole('heading', { name: storyTitles[0], exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Download this story', exact: true })).toBeEnabled();
  await page.mouse.move(box.x + box.width * 0.8, box.y + box.height / 2);
  await page.mouse.down();
  await page.clock.runFor(10000);
  await expect(page.getByRole('heading', { name: storyTitles[0], exact: true })).toBeVisible();
  await page.mouse.up();
  // Releasing a hold resumes playback instead of skipping ahead.
  await expect(page.getByRole('heading', { name: storyTitles[0], exact: true })).toBeVisible();
  await page.clock.runFor(8100);
  await expect(page.getByRole('heading', { name: storyTitles[1], exact: true })).toBeVisible();
});

test('captions can be edited per story and feed the composers', async ({ page }) => {
  await openPreview(page);
  await openShare(page);
  const caption = page.getByLabel('Caption');
  await expect(caption).toHaveValue(/Preview \/ Sample data/);
  await caption.fill('Our server year in one picture');
  expect(new URL(await page.getByRole('link', { name: 'X', exact: true }).getAttribute('href')).searchParams.get('text')).toBe('Our server year in one picture');
  await go(page, 1);
  await expect(caption).toHaveValue(/Discovery, on autopilot/);
});
