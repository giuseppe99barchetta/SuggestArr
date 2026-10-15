import { expect, test } from '@playwright/test';

const token = 'eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.';

for (const width of [1440, 900, 390]) {
  test(`Rejected request replacement settings and actions at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    let config = { AUTH_MODE: 'enabled', REQUIRE_REQUEST_APPROVAL: false, REPLACE_REJECTED_REQUESTS: false };
    let runs = 0;
    let failRun = false;
    let failLog = false;
    let failSave = false;
    const errors = [];
    const log = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route(url => !['127.0.0.1', 'localhost'].includes(url.hostname), route => route.abort());
    await page.addInitScript(() => {
      localStorage.setItem('suggestarr_tour_done', '1');
      localStorage.setItem('suggestarr_jobs_tour_done', '1');
    });
    await page.route('http://localhost:5000/**', route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      const json = (body, status = 200) => route.fulfill({ status, json: body,
        headers: { 'access-control-allow-origin': 'http://127.0.0.1:5173', 'access-control-allow-credentials': 'true' } });
      if (path === '/api/auth/status') return json({ auth_setup_complete: true, app_setup_complete: true });
      if (path === '/api/auth/login' || path === '/api/auth/refresh') return json({ access_token: token });
      if (path === '/api/auth/me') return json({ id: 1, username: 'admin', role: 'admin' });
      if (path === '/api/config/status') return json({ setup_completed: true, is_complete: true });
      if (path === '/api/config/fetch') return json(config);
      if (path === '/api/config/section/advanced') {
        if (failSave) return json({ message: 'Save failed' }, 500);
        config = { ...config, ...request.postDataJSON() };
        return json({ status: 'success' });
      }
      if (path === '/api/automation/requests/expiry/log') return json({ log: [] });
      if (path === '/api/automation/requests/replacements/log') {
        return failLog ? json({ message: 'Decision log unavailable' }, 500) : json({ log });
      }
      if (path === '/api/automation/requests/replacements/run') {
        runs++;
        if (failRun) return json({ message: 'A request check is already running' }, 409);
        log.unshift({ delivery_id: 1, seer_request_id: 42, tmdb_id: '101', media_type: 'movie',
          status: 'queued', reason: 'Alternative queued', replacement_delivery_id: 2,
          checked_at: '2026-10-15T11:00:00Z' });
        return json({ status: 'success', result: { status: 'ok', checked: 1, queued: 1,
          pending: 0, exhausted: 0, ignored: 0, errors: 0 } });
      }
      return json({ jobs: [], users: [], languages: [], items: [], data: [], total: 0 });
    });
    await page.goto('/login');
    await page.getByLabel('Username').fill('admin');
    await page.getByLabel('Password').fill('e2e-password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.goto('/dashboard/approvals');
    const card = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Replace rejected requests', exact: true }) });
    const toggle = card.getByLabel('Generate an alternative after rejection');
    const check = card.getByRole('button', { name: 'Check rejections now' });
    const save = page.getByRole('button', { name: 'Save changes' });
    await expect(toggle).not.toBeChecked();
    await expect(check).toBeDisabled();
    await toggle.check();
    await expect(check).toBeDisabled();
    await save.click();
    await expect(check).toBeEnabled();
    expect(config.REPLACE_REJECTED_REQUESTS).toBe(true);
    await check.click();
    await expect(card.getByRole('status')).toContainText('Alternatives queued: 1');
    expect(await check.evaluate(el => ({ height: el.offsetHeight, border: getComputedStyle(el).borderTopWidth }))).toEqual({ height: 40, border: '1px' });
    expect(runs).toBe(1);
    await card.locator('summary').click();
    await expect(card.getByRole('list')).toContainText('Alternative #2');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await expect(page.getByText('Settings saved successfully!', { exact: true })).toBeHidden();
    await card.screenshot({ path: testInfo.outputPath('request-replacements.png') });
    failRun = true;
    await check.click();
    await expect(card.getByRole('alert').filter({ hasText: 'A request check is already running' })).toBeVisible();
    await expect(check).toBeEnabled();
    failLog = true;
    await card.getByRole('button', { name: 'Refresh', exact: true }).click();
    await expect(card.getByRole('alert').filter({ hasText: 'Decision log unavailable' })).toBeVisible();
    await toggle.uncheck();
    failSave = true;
    await save.click();
    await expect(save).toBeEnabled();
    await expect(check).toBeDisabled();
    expect(config.REPLACE_REJECTED_REQUESTS).toBe(true);
    failSave = false;
    await save.click();
    await expect(save).toBeDisabled();
    await expect(check).toBeDisabled();
    expect(config.REPLACE_REJECTED_REQUESTS).toBe(false);
    expect(errors).toEqual([]);
  });
}
