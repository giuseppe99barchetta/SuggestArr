import { expect, test } from '@playwright/test';

for (const width of [390, 1280]) {
  for (const subpath of ['', '/suggestarr']) {
    test(`auth outage offers retry without opening setup (${width}, ${subpath || 'root'})`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      let available = false;
      let setupCalls = 0;
      await page.route('http://localhost:5000/**', async route => {
        const path = new URL(route.request().url()).pathname.slice(subpath.length);
        const headers = {
          'access-control-allow-origin': 'http://127.0.0.1:5173',
          'access-control-allow-credentials': 'true',
        };
        if (path === '/api/auth/setup') setupCalls += 1;
        if (path === '/api/auth/status') {
          return route.fulfill({
            status: available ? 200 : 503, headers,
            json: available
              ? { auth_setup_complete: true, app_setup_complete: true, authenticated: false }
              : { error: 'Authentication service unavailable' },
          });
        }
        const data = path === '/api/config/status' ? { setup_completed: true } : { AUTH_MODE: 'enabled' };
        return route.fulfill({ json: data, headers });
      });
      if (subpath) {
        await page.route(`**${subpath}/login`, async route => {
          const response = await route.fetch();
          const body = (await response.text()).replace('<head>', `<head><meta name="suggestarr-subpath" content="${subpath}">`);
          await route.fulfill({ response, body });
        });
      }
      await page.goto(`${subpath}/login`);
      await expect(page.getByRole('alert')).toContainText('temporarily unavailable');
      await expect(page.getByLabel('Username')).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Create Admin Account' })).toHaveCount(0);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      available = true;
      await page.getByRole('button', { name: 'Retry', exact: true }).click();
      await expect(page.getByLabel('Username')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Sign In', exact: true })).toBeVisible();
      await expect(page.getByRole('alert')).toHaveCount(0);
      expect(setupCalls).toBe(0);
    });
  }
}

for (const width of [390, 1280]) {
  test(`proxy settings preserve explicit empty trust lists (${width})`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.route(url => url.pathname.startsWith('/api/'), route => route.fulfill({ json: { languages: [] } }));
    await page.route('**/security-settings-preview', route => route.fulfill({
      contentType: 'text/html',
      body: `<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
        <body><div id="app"></div><script type="module">
        import { createApp, h } from '/node_modules/.vite/deps/vue.js';
        import SettingsAdvanced from '/src/components/settings/SettingsAdvanced.vue';
        import '/src/assets/main.css';
        const app = createApp({ render: () => h(SettingsAdvanced, {
          section: 'system', config: { AUTH_MODE: 'local_bypass', AUTH_TRUSTED_CIDRS: '192.168.0.0/16',
            AUTH_TRUSTED_PROXY_CIDRS: '10.0.0.1/32', SEER_AUTO_DECLINE_DAYS: 0 },
          onSaveSection: value => { window.savedSettings = value; }
        }) });
        app.config.globalProperties.$toast = { error: message => { throw new Error(message); } };
        app.mount('#app');
        </script></body></html>`,
    }));
    await page.goto('/security-settings-preview');
    await expect(page.locator('#authTrustedProxyCidrs')).toHaveValue('10.0.0.1/32');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.locator('#authTrustedCidrs').fill('');
    await page.locator('#authTrustedProxyCidrs').fill('');
    await page.getByRole('button', { name: 'Save changes', exact: true }).click();
    await expect.poll(() => page.evaluate(() => window.savedSettings?.data.AUTH_TRUSTED_CIDRS)).toBe('');
    expect(await page.evaluate(() => window.savedSettings.data.AUTH_TRUSTED_PROXY_CIDRS)).toBe('');
  });
}
