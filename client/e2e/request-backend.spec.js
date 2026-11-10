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
      import {useAuth,markAuthReady} from '/src/composables/useAuth.js';
      import '/src/assets/main.css';
      useAuth().currentUser.value={id:7,username:'owner',role:'admin'};
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
    import {RELEASE_NOTES} from '/src/data/releaseNotes.js';`,
  mount: `h(Dialog,{entries:RELEASE_NOTES,availableTabs:['services'],showAllLink:true,
    onClose:()=>window.events.push('close'),onNavigate:t=>window.events.push('navigate:'+t),onAllNotes:()=>window.events.push('all')})`,
});

for (const width of [1440, 390]) {
  test(`What's new popup steps through the slides at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 800 });
    const errors = await whatsNew(page);
    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: 'Choose where requests go' })).toBeVisible();
    await expect(dialog.getByText("What's new · 1 of 4")).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Back' })).toHaveCount(0);
    await expect(dialog.locator('[data-testid=whats-new-slide] svg')).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath(`whats-new-1-${width}.png`) });

    await dialog.getByRole('button', { name: 'Next' }).click();
    await expect(dialog.getByRole('heading', { name: 'Titles added straight to your libraries' })).toBeVisible();
    await expect(dialog.getByText('What it means for you')).toBeVisible();
    await dialog.getByRole('button', { name: 'Back' }).click();
    await expect(dialog.getByRole('heading', { name: 'Choose where requests go' })).toBeVisible();

    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await expect(dialog.getByRole('heading', { name: 'Profiles, folders and anime' })).toBeVisible();
    await page.keyboard.press('ArrowLeft');
    await expect(dialog.getByRole('heading', { name: 'Titles added straight to your libraries' })).toBeVisible();

    await dialog.getByRole('button', { name: /Go to slide 4 of 4/ }).click();
    await expect(dialog.getByRole('heading', { name: 'What is not available without Seer' })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Next' })).toHaveCount(0);
    await page.screenshot({ path: testInfo.outputPath(`whats-new-4-${width}.png`) });
    await dialog.getByRole('button', { name: 'Done' }).click();
    expect(await page.evaluate(() => window.events)).toContain('close');
    expect(errors).toEqual([]);
  });
}

test("What's new slide buttons open the settings tab and the full changelog stays reachable", async ({ page }) => {
  await whatsNew(page);
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Open Connections' }).click();
  await dialog.getByRole('link', { name: 'All release notes' }).click();
  expect(await page.evaluate(() => window.events)).toEqual(['navigate:services', 'all']);
});

test("What's new hides a slide button whose tab the viewer cannot open", async ({ page }) => {
  await preview(page, {
    modules: `import Dialog from '/src/components/WhatsNewDialog.vue';
      import {RELEASE_NOTES} from '/src/data/releaseNotes.js';`,
    mount: `h(Dialog,{entries:RELEASE_NOTES,availableTabs:[]})`,
  });
  await expect(page.getByRole('button', { name: 'Open Connections' })).toHaveCount(0);
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

test("What's new offers a chooser once there are several release notes", async ({ page }) => {
  await preview(page, {
    modules: `import Dialog from '/src/components/WhatsNewDialog.vue';
      import {RELEASE_NOTES} from '/src/data/releaseNotes.js';
      const older={id:'older',title:'An older release',slides:[{icon:'choice.svg',tone:'good',heading:'Older heading',changes:'c',impact:'i'}]};`,
    mount: `h(Dialog,{entries:[RELEASE_NOTES[0],older],availableTabs:[]})`,
  });
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('heading', { name: 'Choose where requests go' })).toBeVisible();
  await dialog.getByLabel('Release notes').selectOption('older');
  await expect(dialog.getByRole('heading', { name: 'Older heading' })).toBeVisible();
  await expect(dialog.getByText("What's new · 1 of 1")).toBeVisible();
});
