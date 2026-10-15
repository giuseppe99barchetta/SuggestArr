import { expect, test } from '@playwright/test';

async function openPreview(page, component, job = null) {
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
        : `{config:{SELECTED_SERVICE:'jellyfin',MDBLIST_API_KEY:'***',TRAKT_CLIENT_ID:'test-client'},onSaveSection:value=>window.savedServices.push(value)}`})});
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
