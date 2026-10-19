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
      '/api/jobs': { status: 'success', jobs: [] },
      '/api/jobs/history': { status: 'success', history: [] },
      '/api/jobs/queue-status': { status: 'success', total_pending: 0 },
      '/api/jobs/lists/import': { status: 'success', data: null },
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
      import Jobs from '/src/components/settings/SettingsJobs.vue';
      import {useAuth,markAuthReady} from '/src/composables/useAuth.js';
      import '/src/assets/main.css';
      useAuth().currentUser.value={id:7,username:'owner',role:'admin'};
      markAuthReady();
      localStorage.setItem('suggestarr_jobs_tour_done','1');
      window.savedJob=null;
      window.savedServices=[];
      const app=createApp({render:()=>h(${component},${component === 'JobModal'
        ? `{job:${JSON.stringify(job)},...${JSON.stringify(servicesProps)},onSave:value=>{window.savedJob=value;}}`
        : `{config:{SELECTED_SERVICE:'jellyfin',MDBLIST_API_KEY:'***',TRAKT_CLIENT_ID:'test-client'},...${JSON.stringify(servicesProps)},onSaveSection:value=>window.savedServices.push(value)}`})});
      app.config.globalProperties.$toast={error(){},success(){},open(){}};
      app.mount('#preview');
      </script></body></html>`,
  }));
  await page.goto('/list-import-preview');
  return errors;
}

const shots = 'C:/Users/peppe/AppData/Local/Temp/claude/c--Users-peppe-VsProjects-SuggestArr/39c920cc-c403-4224-a5f9-d309b30856db/scratchpad/shots';

test('tmp job modal screenshots', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const job = { id: 3, name: 'Weekly recs', job_type: 'recommendation', media_type: 'both', max_results: 20, filters: {}, user_ids: [], delivery_mode: 'inherit', schedule_type: 'preset', schedule_value: 'weekly' };
  const errors = await openPreview(page, 'JobModal', job, { requestApprovalDefault: true, approvalPauseDefault: false });
  const dialog = page.getByRole('dialog');
  const body = dialog.locator('form > div > div.overflow-y-auto');
  await page.waitForTimeout(600);
  await dialog.screenshot({ path: `${shots}/rec-1.png` });
  for (const [i, id] of ['filters', 'schedule', 'requests'].entries()) {
    await dialog.getByRole('button', { name: new RegExp(`^${i + 2} `) }).click();
    await page.waitForTimeout(700);
    await dialog.screenshot({ path: `${shots}/rec-${id}.png` });
  }
  await dialog.locator('[data-section="requests"] button[aria-label="More information"]').first().hover();
  await page.waitForTimeout(200);
  await page.screenshot({ path: `${shots}/tooltip.png` });
  expect(errors).toEqual([]);
});

test('tmp discover new job', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const errors = await openPreview(page, 'JobModal');
  const dialog = page.getByRole('dialog');
  await page.waitForTimeout(600);
  await dialog.getByRole('button', { name: /^2 / }).click();
  await page.waitForTimeout(700);
  await dialog.screenshot({ path: `${shots}/disc-filters.png` });
  expect(errors).toEqual([]);
});
