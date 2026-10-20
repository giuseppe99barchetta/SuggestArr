import { expect, test } from '@playwright/test';
import { posterFixture, titles } from './fixtures/recapPosters.js';

const watched = Array.from({ length: 6 }, (_, index) => ({
  title: titles[index % 4] + (index > 3 ? ' II' : ''),
  year: 2020 + index,
  media_type: index === 1 ? 'tv' : 'movie',
  poster_path: `/ai-search-poster-${index % 4}.svg`,
}));

async function openPreview(page, { items = watched, available = true, brokenHistory = false, userId = 7, corruptHistory = false } = {}) {
  const errors = [];
  const searches = [];
  // Stands in for the server's per-account history (newest first, five kept).
  const history = [];
  const remember = (query) => {
    const at = history.indexOf(query);
    if (at >= 0) history.splice(at, 1);
    history.unshift(query);
    history.splice(5);
  };
  page.on('pageerror', error => errors.push(error.message));
  await page.route(url => !['127.0.0.1', 'localhost'].includes(url.hostname), route => route.abort());
  await page.route('**/ai-search-poster-*.svg', route => {
    const index = Number(route.request().url().match(/poster-(\d)/)[1]);
    return route.fulfill({ contentType: 'image/svg+xml', body: posterFixture(index) });
  });
  await page.route('**/api/ai-search/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/history')) {
      const method = route.request().method();
      if (method === 'DELETE') history.splice(0);
      if (method === 'POST') [...route.request().postDataJSON().queries.slice(0, 5)].reverse().forEach(remember);
      return route.fulfill({ json: { status: 'success', history } });
    }
    if (path.endsWith('/query')) {
      searches.push(route.request().postDataJSON());
      remember(route.request().postDataJSON().query);
      return route.fulfill({ json: { status: 'success', results: [{ id: 1, title: 'A new discovery', media_type: 'movie' }] } });
    }
    if (path.endsWith('/status')) return route.fulfill({ json: { available } });
    if (path.endsWith('/inspiration')) return route.fulfill({ status: brokenHistory ? 503 : 200, json: { items } });
    return route.fulfill({ json: { status: 'success', feedback: [] } });
  });
  await page.route('**/ai-search-preview', route => route.fulfill({
    contentType: 'text/html',
    body: `<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
      <body><div id="preview" style="padding:24px;max-width:1240px;margin:auto"></div><script type="module">
      import {createApp,h} from '/node_modules/.vite/deps/vue.js';
      import {createRouter,createMemoryHistory} from '/node_modules/.vite/deps/vue-router.js';
      import AiSearchPage from '/src/components/settings/AiSearchPage.vue';
      import {useAuth,markAuthReady} from '/src/composables/useAuth.js';
      import '/src/assets/main.css';
      useAuth().currentUser.value={id:${userId},username:'viewer',role:'user'};
      markAuthReady();
      ${corruptHistory ? `localStorage.setItem('suggestarr_ai_search_history:${userId}','{broken');` : ''}
      const router=createRouter({history:createMemoryHistory(),routes:[{path:'/:tab?',name:'DashboardTab',component:AiSearchPage}]});
      const app=createApp({render:()=>h(AiSearchPage)});
      app.use(router);
      app.config.globalProperties.$toast={error(){},success(){},open(){}};
      app.mount('#preview');
      </script></body></html>`,
  }));
  await page.goto('/ai-search-preview');
  await expect(page.getByRole('heading', { name: 'AI Search', exact: true })).toBeVisible();
  return { errors, searches, history };
}

for (const width of [1440, 900, 390]) {
  test(`Search starters and personal posters at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 1100 });
    const { errors, searches } = await openPreview(page);
    const input = page.getByRole('textbox', { name: 'What do you want to watch?' });
    await expect(page.getByRole('button', { name: 'Find more like AFTERLIGHT', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Feel-good', exact: false }).click();
    await expect(input).toHaveValue(/uplifting/);
    await expect(input).toBeFocused();
    expect(searches).toHaveLength(0);
    await page.getByRole('button', { name: 'Find more like AFTERLIGHT', exact: true }).click();
    await expect(input).toHaveValue(/Something like "AFTERLIGHT" \(2021\)/);
    await expect(page.getByRole('radio', { name: 'TV shows' })).toHaveAttribute('aria-checked', 'true');
    expect(searches).toHaveLength(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await input.fill('A thoughtful mystery with a hopeful ending');
    await page.screenshot({ path: testInfo.outputPath('ai-search-inspiration.png'), fullPage: true });
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await expect(page.getByRole('heading', { name: '1 match', exact: true })).toBeVisible();
    expect(searches).toHaveLength(1);
    expect(searches[0]).toMatchObject({ query: 'A thoughtful mystery with a hopeful ending', media_type: 'tv' });
    await expect(page.getByRole('heading', { name: 'Set the mood' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Explore search ideas' }).click();
    await expect(page.getByRole('heading', { name: 'Recent searches' })).toBeVisible();
    await page.reload();
    await page.getByRole('button', { name: 'A thoughtful mystery with a hopeful ending', exact: true }).click();
    await expect(input).toHaveValue('A thoughtful mystery with a hopeful ending');
    expect(searches).toHaveLength(1);
    await page.getByRole('button', { name: 'Clear recent searches' }).click();
    await expect(page.getByRole('heading', { name: 'Recent searches' })).toHaveCount(0);
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Recent searches' })).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test('Empty history offers Profile, malformed recents do not break the page', async ({ page }) => {
  const { errors } = await openPreview(page, { items: [], corruptHistory: true });
  await expect(page.getByText('Your favourites belong here')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open profile' })).toHaveAttribute('href', '/profile');
  await page.getByRole('button', { name: 'A good mystery', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeEnabled();
  expect(errors).toEqual([]);
});

test('History failure can be retried and never blocks searching', async ({ page }) => {
  await openPreview(page, { brokenHistory: true });
  await expect(page.getByText('Your watch history is taking a break')).toBeVisible();
  await page.getByRole('button', { name: 'Adrenaline', exact: false }).click();
  await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeEnabled();
  await page.route('**/api/ai-search/inspiration', route => route.fulfill({ json: { items: watched } }));
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Find more like AFTERLIGHT', exact: true })).toBeVisible();
});

test('Searches kept in this browser move to the account once, other accounts stay untouched', async ({ page }) => {
  await page.addInitScript(() => {
    if (sessionStorage.getItem('seeded')) return;
    sessionStorage.setItem('seeded', '1');
    localStorage.setItem('suggestarr_ai_search_history:8', JSON.stringify(['Another account query']));
    localStorage.setItem('suggestarr_ai_search_history:7', JSON.stringify(Array.from({ length: 8 }, (_, i) => `My query ${i}`)));
  });
  const { history } = await openPreview(page);
  await expect(page.getByRole('button', { name: 'Another account query', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: /^My query/ })).toHaveCount(5);
  await expect(page.getByRole('button', { name: /^My query/ }).first()).toHaveText(/My query 0/);
  expect(history).toEqual(['My query 0', 'My query 1', 'My query 2', 'My query 3', 'My query 4']);
  expect(await page.evaluate(() => localStorage.getItem('suggestarr_ai_search_history:7'))).toBeNull();
  await page.getByRole('button', { name: 'Clear recent searches' }).click();
  expect(history).toEqual([]);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('suggestarr_ai_search_history:8')))).toEqual(['Another account query']);
});

test('Unconfigured AI retains setup guidance and disables search', async ({ page }) => {
  const { searches } = await openPreview(page, { available: false });
  await expect(page.getByRole('link', { name: 'Set up AI provider' })).toBeVisible();
  await expect(page.getByRole('textbox')).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeDisabled();
  await expect(page.getByRole('heading', { name: 'Set the mood' })).toHaveCount(0);
  expect(searches).toHaveLength(0);
});
