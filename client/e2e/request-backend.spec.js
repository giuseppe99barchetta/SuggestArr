import { expect, test } from '@playwright/test';

/** Mounts a component from the dev server on a bare page, with every /api call mocked. */
async function preview(page, { modules, mount, extraApi = {} }) {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route(url => !['127.0.0.1', 'localhost'].includes(url.hostname), route => route.abort());
  await page.route(url => url.pathname.startsWith('/api/'), route => {
    const path = new URL(route.request().url()).pathname;
    const responses = {
      '/api/config/status': { selected_service: 'jellyfin' },
      '/api/arr/test': { status: 'success' },
      '/api/arr/options': {
        status: 'success',
        profiles: [{ id: 4, name: 'HD-1080p' }, { id: 6, name: 'Any' }],
        rootFolders: [{ path: '/movies' }, { path: '/anime' }],
        tags: [{ id: 1, label: 'kids' }],
      },
      ...extraApi,
    };
    return route.fulfill({ json: responses[path] ?? { status: 'success', users: [], servers: [] } });
  });
  await page.route('**/backend-preview', route => route.fulfill({
    contentType: 'text/html',
    body: `<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
      <body><div id="preview" style="padding:16px;max-width:1200px;margin:auto"></div><script type="module">
      import {createApp,h} from '/node_modules/.vite/deps/vue.js';
      ${modules}
      import {useAuth,initializeAuthReady,markAuthReady} from '/src/composables/useAuth.js';
      import '/src/assets/main.css';
      useAuth().currentUser.value={id:7,username:'owner',role:'admin'};
      initializeAuthReady();
      markAuthReady();
      window.events=[];
      const app=createApp({render:()=>${mount}});
      app.config.globalProperties.$toast={error(){},success(){},open(){}};
      app.mount('#preview');
      </script></body></html>`,
  }));
  await page.goto('/backend-preview');
  return errors;
}

const whatsNew = (page) => preview(page, {
  modules: `import Dialog from '/src/components/WhatsNewDialog.vue';
    import {WHATS_NEW} from '/src/data/releaseNotes.js';`,
  mount: `h(Dialog,{entry:WHATS_NEW,onClose:()=>window.events.push('close')})`,
});

for (const width of [1440, 390]) {
  test(`What's new popup steps through the slides at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    const errors = await whatsNew(page);
    const dialog = page.getByRole('dialog');
    const headings = ['Choose where requests go', 'Titles added straight to your libraries', 'Know when it is ready', 'Replacements and cleanup', 'Profiles and pause, per job'];
    await expect(dialog.getByRole('button', { name: 'Back' })).toHaveCount(0);
    for (const [index, heading] of headings.entries()) {
      if (index) await dialog.getByRole('button', { name: 'Next' }).click();
      await expect(dialog.getByRole('heading', { name: heading })).toBeVisible();
      await expect(dialog.getByText(`What's new · ${index + 1} of 5`)).toBeVisible();
      await page.waitForTimeout(400); // let the slide transition finish before the screenshot
      await page.screenshot({ path: testInfo.outputPath(`whats-new-${index + 1}-${width}.png`) });
    }
    await expect(dialog.getByRole('button', { name: 'Next' })).toHaveCount(0);
    await page.keyboard.press('ArrowLeft');
    await expect(dialog.getByRole('heading', { name: 'Replacements and cleanup' })).toBeVisible();
    await dialog.getByRole('button', { name: /Go to slide 1 of 5/ }).click();
    await expect(dialog.getByRole('heading', { name: 'Choose where requests go' })).toBeVisible();
    await page.keyboard.press('Escape');
    expect(await page.evaluate(() => window.events)).toContain('close');
    expect(errors).toEqual([]);
  });
}

test("What's new links to every past release note", async ({ page }) => {
  await whatsNew(page);
  await expect(page.getByRole('dialog').getByRole('link', { name: 'All release notes' })).toHaveAttribute('href', /github\.com\/.*\/releases$/);
});

const services = (page, config) => preview(page, {
  modules: `import Services from '/src/components/settings/SettingsServices.vue';`,
  mount: `h(Services,{config:${JSON.stringify(config)},onSaveSection:value=>window.events.push(value)})`,
});

const BASE = { SELECTED_SERVICE: 'jellyfin', JELLYFIN_API_URL: 'http://jf', JELLYFIN_TOKEN: 't', TMDB_API_KEY: 'k', SEER_API_URL: 'http://seer', SEER_TOKEN: 's' };

test('Connections: choosing Radarr & Sonarr swaps Seer for the direct-delivery card and saves the profiles', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1200, height: 1000 });
  const errors = await services(page, BASE);
  await expect(page.getByText('Jellyseerr / Overseerr', { exact: true })).toBeVisible();
  const choice = page.getByTestId('request-backend-choice');
  await expect(choice.getByRole('radio', { name: /^Seer/ })).toHaveAttribute('aria-checked', 'true');

  await choice.getByRole('radio', { name: /Radarr & Sonarr/ }).click();
  await expect(page.getByText('Jellyseerr / Overseerr', { exact: true })).toHaveCount(0);
  const arr = page.getByTestId('arr-connection');
  await arr.getByLabel('Radarr URL', { exact: true }).fill('http://radarr:7878');
  await arr.getByLabel('Radarr API key', { exact: true }).fill('radarr-key');
  await arr.getByRole('button', { name: 'Test Radarr' }).click();

  const profiles = page.getByTestId('radarr-profiles');
  await expect(profiles).toBeVisible();
  await profiles.getByLabel('Radarr Default quality profile').selectOption('4');
  await profiles.getByLabel('Radarr Default root folder').selectOption('/movies');
  await profiles.getByLabel('Radarr Anime root folder').selectOption('/anime');
  await page.screenshot({ path: testInfo.outputPath('connections-arr.png'), fullPage: true });

  await page.getByRole('button', { name: 'Save changes' }).click();
  const saved = (await page.evaluate(() => window.events))[0].data;
  expect(saved.REQUEST_BACKEND).toBe('arr');
  expect(saved.RADARR_API_URL).toBe('http://radarr:7878');
  expect(saved.ARR_PROFILE_CONFIG).toEqual({
    default_movie: { profileId: 4, rootFolder: '/movies' },
    anime_movie: { rootFolder: '/anime' },
  });
  expect(errors).toEqual([]);
});

test('Connections: "Both" keeps Seer required and offers no profile pickers', async ({ page }) => {
  const errors = await services(page, { ...BASE, REQUEST_BACKEND: 'both', RADARR_API_URL: 'http://radarr:7878', RADARR_TOKEN: 'k' });
  await expect(page.getByText('Jellyseerr / Overseerr', { exact: true })).toBeVisible();
  await expect(page.getByTestId('arr-connection')).toBeVisible();
  await expect(page.getByTestId('radarr-profiles')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('Connections: with Seer only, Radarr & Sonarr is an optional extra for the library check', async ({ page }) => {
  await services(page, BASE);
  await expect(page.getByText('Optional extras')).toBeVisible();
  await expect(page.getByTestId('arr-connection').getByText('Skip titles already in your Radarr or Sonarr')).toBeVisible();
});

const SEER_JOB_PROFILE = { serverId: 0, profileId: 7, rootFolder: '/seer', is4k: false };
const jobModal = (page, job) => preview(page, {
  modules: `import JobModal from '/src/components/settings/jobs/JobModal.vue';`,
  mount: `h(JobModal,{job:${JSON.stringify(job)},requestBackend:'arr',onSave:value=>{window.savedJob=value;}})`,
  extraApi: { '/api/jobs/genres/movie': { status: 'success', genres: [] }, '/api/jobs/genres/tv': { status: 'success', genres: [] },
    '/api/jobs/watch-regions': { status: 'success', regions: [] }, '/api/jobs/languages': { status: 'success', languages: [] } },
});
const arrJob = { id: 5, name: 'Weekly', job_type: 'discover', media_type: 'movie', max_results: 5,
  delivery_mode: 'automatic', request_profiles: { movie: SEER_JOB_PROFILE, tv: {} } };

test('Job dialog: direct delivery picks a Radarr profile per job', async ({ page }, testInfo) => {
  const errors = await jobModal(page, arrJob);
  const dialog = page.getByRole('dialog');
  const overrides = dialog.getByRole('button', { name: /Radarr \/ Sonarr overrides/ });
  await expect(overrides).toContainText('Using the default quality profile, root folder and tags from Services.');
  await overrides.click();
  const profiles = page.getByTestId('job-arr-profiles');
  await profiles.getByRole('combobox', { name: /Quality profile/ }).selectOption({ label: 'HD-1080p' });
  await profiles.getByRole('combobox', { name: /Root folder/ }).selectOption('/movies');
  await profiles.getByLabel('kids').check();
  await expect(overrides).toContainText('Custom Radarr profile.');
  await dialog.getByText('Radarr/Sonarr still has downloads in the queue').click();
  await profiles.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('job-arr-profiles.png') });
  await dialog.getByRole('button', { name: 'Save job' }).click();
  await expect.poll(() => page.evaluate(() => window.savedJob?.request_profiles)).toEqual({
    movie: { profileId: 4, rootFolder: '/movies', tags: [1] }, tv: {} });
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => window.savedJob.pause_if_pending_requests)).toBe(true);
});

test('Job dialog: direct delivery keeps an untouched Seer profile as stored', async ({ page }) => {
  await jobModal(page, arrJob);
  await page.getByRole('dialog').getByRole('button', { name: 'Save job' }).click();
  await expect.poll(() => page.evaluate(() => window.savedJob?.request_profiles)).toEqual({ movie: SEER_JOB_PROFILE, tv: {} });
});

test('Job dialog: a Radarr profile without a root folder cannot be saved', async ({ page }) => {
  await jobModal(page, { ...arrJob, request_profiles: { movie: {}, tv: {} } });
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: /Radarr \/ Sonarr overrides/ }).click();
  const profiles = page.getByTestId('job-arr-profiles');
  await profiles.getByRole('combobox', { name: /Quality profile/ }).selectOption({ label: 'HD-1080p' });
  await expect(dialog.getByText('Choose a root folder for the Radarr/Sonarr profile')).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Save job' })).toBeDisabled();
  await profiles.getByRole('combobox', { name: /Root folder/ }).selectOption('/anime');
  await dialog.getByRole('button', { name: 'Save job' }).click();
  await expect.poll(() => page.evaluate(() => window.savedJob?.request_profiles)).toEqual({
    movie: { profileId: 4, rootFolder: '/anime' }, tv: {} });
});
