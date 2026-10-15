import { expect, test } from '@playwright/test';

async function openPreview(page, component, job = null, servicesProps = {}) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route(url => !['127.0.0.1', 'localhost'].includes(url.hostname), route => route.abort());
  await page.route(url => url.pathname.startsWith('/api/'), route => {
    const path = new URL(route.request().url()).pathname;
    const responses = {
      '/api/config/status': { selected_service: 'jellyfin', trakt_app_configured: true },
      '/api/jobs/default-filters': { status: 'success', defaults: { vote_average_gte: 6, vote_count_gte: 20 } },
      '/api/jobs/llm/status': { configured: false },
      '/api/jobs/lists/verify': { status: 'success', data: { name: 'Weekly favorites', provider: 'mdblist' } },
    };
    if (path === '/api/config/section/services' && route.request().method() === 'POST') {
      return route.fulfill({ json: { status: 'success' } });
    }
    return route.fulfill({ json: responses[path] ?? { status: 'success', users: [], genres: [], regions: [], servers: [], languages: [] } });
  });
  await page.route('**/list-import-preview', route => route.fulfill({
    contentType: 'text/html',
    body: `<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
      <body><div id="preview" style="padding:16px;max-width:1200px;margin:auto"></div><script type="module">
      import {createApp,h} from '/node_modules/.vite/deps/vue.js';
      import JobModal from '/src/components/settings/jobs/JobModal.vue';
      import Services from '/src/components/settings/SettingsServices.vue';
      import {useAuth,markAuthReady} from '/src/composables/useAuth.js';
      import '/src/assets/main.css';
      useAuth().currentUser.value={id:7,username:'owner',role:'admin'};
      markAuthReady();
      window.savedJob=null;
      window.savedServices=[];
      const app=createApp({render:()=>h(${component},${component === 'JobModal'
        ? `{job:${JSON.stringify(job)},onSave:value=>{window.savedJob=value;}}`
        : `{config:{SELECTED_SERVICE:'jellyfin',MDBLIST_API_KEY:'***',TRAKT_CLIENT_ID:'test-client'},...${JSON.stringify(servicesProps)},onSaveSection:value=>window.savedServices.push(value)}`})});
      app.config.globalProperties.$toast={error(){},success(){}};
      app.mount('#preview');
      </script></body></html>`,
  }));
  await page.goto('/list-import-preview');
  return errors;
}

for (const width of [1440, 900, 390]) {
  test(`Public list job creation and validation at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    const errors = await openPreview(page, 'JobModal');
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Import list Public MDBList or Trakt list' }).click();
    await page.getByLabel('Name', { exact: true }).fill('Weekly list');
    const source = page.getByTestId('public-list-source');
    await source.getByRole('button', { name: 'Select provider' }).click();
    await page.getByRole('menuitem', { name: 'MDBList', exact: true }).click();
    await page.getByLabel('List URL').fill('https://mdblist.com/lists/alice/favorites');
    await source.getByRole('button', { name: 'Verify list' }).click();
    await expect(source.getByRole('status')).toHaveText('Public list: Weekly favorites');
    await expect(page.getByText('Users to monitor')).toHaveCount(0);
    await expect(page.getByText('Pause if suggestions remain unwatched')).toHaveCount(0);
    await dialog.getByRole('button', { name: 'Both', exact: true }).click();
    await source.scrollIntoViewIfNeeded();
    expect(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await dialog.screenshot({ path: testInfo.outputPath('list-import.png') });
    await dialog.getByRole('button', { name: 'Create job', exact: true }).click();
    await expect.poll(() => page.evaluate(() => window.savedJob)).not.toBeNull();
    const saved = await page.evaluate(() => window.savedJob);
    expect(saved).toMatchObject({ job_type: 'list_import', media_type: 'both', max_results: 20, user_ids: [],
      prevent_suggestions_if_unwatched: false, filters: { list_provider: 'mdblist', list_url: 'https://mdblist.com/lists/alice/favorites' } });
    await page.route('**/api/jobs/lists/verify', route => route.fulfill({ status: 400, json: { message: 'Only public lists are supported.' } }));
    await source.getByRole('button', { name: 'Verify list' }).click();
    await expect(source.getByRole('status')).toHaveText('Only public lists are supported.');
    await page.getByLabel('List URL').fill('https://mdblist.com/lists/alice/updated');
    await expect(source.getByRole('status')).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test('MDBList connection key is saved and an unchanged key stays masked', async ({ page }) => {
  await openPreview(page, 'Services');
  const key = page.locator('#mdblistApiKey');
  await expect(key).toHaveAttribute('type', 'password');
  await expect(key).toHaveValue('***');
  await key.fill('test-key-not-real');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  expect(await page.evaluate(() => window.savedServices[0])).toMatchObject({ section: 'services', data: { MDBLIST_API_KEY: 'test-key-not-real' } });
  await page.locator('#traktClientId').fill('changed-client');
  await page.getByRole('button', { name: 'Save changes', exact: true }).click();
  expect(await page.evaluate(() => window.savedServices[1].data.MDBLIST_API_KEY)).toBe('***');
});

for (const width of [1400, 1100, 1024, 900, 390]) {
  test(`TMDB and MDBList connection cards align at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1000 });
    const errors = await openPreview(page, 'Services');
    const tmdb = page.getByTestId('tmdb-connection');
    const mdblist = page.getByTestId('mdblist-connection');
    await expect(tmdb).toBeVisible();
    await expect(mdblist).toBeVisible();
    const a = await tmdb.boundingBox();
    const b = await mdblist.boundingBox();
    const tmdbKey = await page.locator('#tmdbApiKey').boundingBox();
    const mdbKey = await page.locator('#mdblistApiKey').boundingBox();
    if (width >= 1024) {
      expect(Math.abs(a.y - b.y)).toBeLessThan(1);
      expect(Math.abs(a.height - b.height)).toBeLessThan(1);
      expect(Math.abs(a.width - b.width)).toBeLessThan(1);
      expect(Math.abs(tmdbKey.y - mdbKey.y)).toBeLessThan(1);
      expect(b.x).toBeGreaterThan(a.x + a.width);
    } else {
      expect(b.y).toBeGreaterThanOrEqual(a.y + a.height + 19);
      expect(Math.abs(a.x - b.x)).toBeLessThan(1);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('button', { name: 'Show MDBList API key', exact: true }).click();
    await expect(page.locator('#mdblistApiKey')).toHaveAttribute('type', 'text');
    await page.getByRole('button', { name: 'Hide MDBList API key', exact: true }).click();
    await expect(page.locator('#mdblistApiKey')).toHaveAttribute('type', 'password');
    await tmdb.locator('..').screenshot({ path: testInfo.outputPath('metadata-connections.png') });
    expect(errors).toEqual([]);
  });
}

test('TMDB wizard keeps its standalone connection form', async ({ page }) => {
  const errors = await openPreview(page, 'Services', null, { wizardMode: true, wizardSection: 'tmdb' });
  await expect(page.locator('#tmdbApiKey')).toBeVisible();
  await expect(page.locator('#mdblistApiKey')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Test connection' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Save changes' })).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('MDBList test resets after editing and restores on navigation, reload and a new browser context', async ({ page, browser }) => {
  const errors = await openPreview(page, 'Services');
  const card = page.getByTestId('mdblist-connection');
  await expect(card.getByRole('button', { name: 'Connected', exact: true })).toBeVisible();
  await expect(card.getByText('Save your key, then verify a list in Jobs.')).toHaveCount(0);
  await page.locator('#mdblistApiKey').fill('changed-test-key');
  const button = card.getByRole('button', { name: 'Test connection', exact: true });
  await expect(button).toBeEnabled();
  let release;
  let started;
  const waiting = new Promise(resolve => { release = resolve; });
  const began = new Promise(resolve => { started = resolve; });
  await page.route('**/api/mdblist/test', async route => {
    expect(route.request().postDataJSON()).toEqual({ api_key: 'changed-test-key' });
    started();
    await waiting;
    await route.fulfill({ json: { status: 'success' } });
  });
  await button.click();
  await began;
  await expect(card.getByRole('button', { name: 'Testing…' })).toBeDisabled();
  release();
  await expect(card.getByRole('button', { name: 'Connected', exact: true })).toBeEnabled();
  await page.unroute('**/api/mdblist/test');
  await page.goto('about:blank');
  await page.goto('/list-import-preview');
  await expect(card.getByRole('button', { name: 'Connected', exact: true })).toBeVisible();
  await page.reload();
  await expect(card.getByRole('button', { name: 'Connected', exact: true })).toBeVisible();
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:5173' });
  try {
    const reopened = await context.newPage();
    await openPreview(reopened, 'Services');
    await expect(reopened.getByTestId('mdblist-connection').getByRole('button', { name: 'Connected', exact: true })).toBeVisible();
  } finally {
    await context.close();
  }
  expect(errors).toEqual([]);
});

test('MDBList failed or stale tests do not keep the card connected', async ({ page }) => {
  await openPreview(page, 'Services');
  const card = page.getByTestId('mdblist-connection');
  await expect(card.getByRole('button', { name: 'Connected', exact: true })).toBeVisible();
  await page.route('**/api/mdblist/test', route => route.fulfill({ status: 400, json: { status: 'error', message: 'Invalid key' } }));
  await card.getByRole('button', { name: 'Connected', exact: true }).click();
  await expect(card.getByRole('button', { name: 'Test connection', exact: true })).toBeEnabled();
  await expect(card.getByText('Not tested', { exact: true })).toBeVisible();
  await page.unroute('**/api/mdblist/test');
  let release;
  let started;
  const waiting = new Promise(resolve => { release = resolve; });
  const began = new Promise(resolve => { started = resolve; });
  await page.route('**/api/mdblist/test', async route => {
    started();
    await waiting;
    await route.fulfill({ json: { status: 'success' } });
  });
  await card.getByRole('button', { name: 'Test connection', exact: true }).click();
  await began;
  await page.locator('#mdblistApiKey').fill('another-test-key');
  release();
  await expect(card.getByRole('button', { name: 'Test connection', exact: true })).toBeEnabled();
  await expect(card.getByText('Connected', { exact: true })).toHaveCount(0);
  await page.locator('#mdblistApiKey').fill('');
  await expect(card.getByRole('button', { name: 'Test connection', exact: true })).toBeDisabled();
  await expect(card.getByText('Not set', { exact: true })).toBeVisible();
});
