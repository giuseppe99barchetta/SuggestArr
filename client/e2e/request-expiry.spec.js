import { expect, test } from '@playwright/test';

const token = 'eyJhbGciOiJub25lIn0.eyJzdWIiOiIxIiwidXNlcm5hbWUiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiJ9.';

for (const width of [1440, 1280, 900, 390]) {
  test(`Seerr expiry saves, previews and declines at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    let config = { AUTH_MODE: 'enabled', REQUIRE_REQUEST_APPROVAL: false, SEER_AUTO_DECLINE_DAYS: 0, SEER_AUTO_DECLINE_DRY_RUN: true };
    const runs = [];
    const log = [];
    await page.route(url => !['127.0.0.1', 'localhost'].includes(url.hostname), route => route.abort());
    await page.addInitScript(() => {
      localStorage.setItem('suggestarr_tour_done', '1');
      localStorage.setItem('suggestarr_jobs_tour_done', '1');
    });
    await page.route('http://localhost:5000/**', route => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      const json = (body) => route.fulfill({
        json: body,
        headers: { 'access-control-allow-origin': 'http://127.0.0.1:5173', 'access-control-allow-credentials': 'true' },
      });
      if (path === '/api/auth/status') return json({ auth_setup_complete: true, app_setup_complete: true });
      if (path === '/api/auth/login' || path === '/api/auth/refresh') return json({ access_token: token });
      if (path === '/api/auth/me') return json({ id: 1, username: 'admin', role: 'admin' });
      if (path === '/api/config/status') return json({ setup_completed: true, is_complete: true });
      if (path === '/api/config/fetch') return json(config);
      if (path === '/api/config/section/advanced') {
        config = { ...config, ...request.postDataJSON() };
        return json({ status: 'success' });
      }
      if (path === '/api/automation/requests/expiry/log') return json({ status: 'success', log });
      if (path === '/api/automation/requests/expiry/run') {
        const { dry_run } = request.postDataJSON();
        runs.push(dry_run);
        log.unshift({ id: log.length + 1, seer_request_id: 42, tmdb_id: '101', media_type: 'movie',
          action: dry_run ? 'simulated' : 'declined', reason: 'Pending for more than 7 days', dry_run,
          created_at: '2026-10-15T04:30:00Z' });
        return json({ status: 'success', result: { status: 'ok', candidates: 1, simulated: dry_run ? 1 : 0,
          declined: dry_run ? 0 : 1, skipped: 0, errors: 0 } });
      }
      return json({ jobs: [], users: [], languages: [], items: [], data: [], total: 0 });
    });

    await page.goto('/login');
    await page.getByLabel('Username').fill('admin');
    await page.getByLabel('Password').fill('e2e-password');
    await page.getByRole('button', { name: 'Sign In' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.goto('/dashboard/approvals');
    const card = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Seerr pending requests', exact: true }) });
    const preview = card.getByRole('button', { name: 'Preview now' });
    const decline = card.getByRole('button', { name: 'Decline expired requests', exact: true });
    await expect(preview).toBeDisabled();
    await expect(decline).toBeDisabled();
    await expect(card.locator('details')).not.toHaveAttribute('open');
    const flow = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Approval flow', exact: true }) });
    const visibility = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Who sees what', exact: true }) });
    const [flowBox, expiryBox, visibilityBox] = await Promise.all([flow.boundingBox(), card.boundingBox(), visibility.boundingBox()]);
    if (width >= 1280) {
      expect(Math.abs(flowBox.y - expiryBox.y)).toBeLessThan(1);
      expect(Math.abs(flowBox.height - expiryBox.height)).toBeLessThan(1);
      expect(visibilityBox.y - flowBox.y - flowBox.height).toBeCloseTo(20, 0);
      const localRows = await flow.locator('button[role="switch"]').all();
      const remoteRows = [card.getByLabel('Auto-decline after (days)').locator('..').locator('..'), card.getByLabel('Preview only (dry-run)').locator('..').locator('..').locator('..')];
      for (let index = 0; index < 2; index++) {
        const [localRow, remoteRow] = await Promise.all([localRows[index].boundingBox(), remoteRows[index].boundingBox()]);
        expect(Math.abs(localRow.y - remoteRow.y)).toBeLessThan(1);
        expect(Math.abs(localRow.height - remoteRow.height)).toBeLessThan(1);
      }
    } else {
      expect(expiryBox.y - flowBox.y - flowBox.height).toBeCloseTo(20, 0);
    }
    const buttonStyle = await preview.evaluate(el => ({ height: el.offsetHeight, border: getComputedStyle(el).borderTopWidth }));
    expect(buttonStyle).toEqual({ height: 40, border: '1px' });
    await page.screenshot({ path: testInfo.outputPath('approvals-default.png'), fullPage: true });
    await card.getByLabel('Auto-decline after (days)').fill('7');
    await expect(preview).toBeDisabled();
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(preview).toBeEnabled();
    expect(config.SEER_AUTO_DECLINE_DAYS).toBe(7);
    await expect(decline).toBeDisabled();
    await preview.click();
    await expect(card.getByRole('status').filter({ hasText: '1 simulated' })).toBeVisible();
    await card.locator('summary').click();
    await expect(card.getByRole('list')).toContainText('simulated (preview)');

    await card.getByLabel('Preview only (dry-run)').uncheck();
    await page.getByRole('button', { name: 'Save changes' }).click();
    await expect(decline).toBeEnabled();
    await expect(card.getByLabel('Preview only (dry-run)')).not.toBeChecked();
    await decline.click();
    await expect(card.getByRole('status').filter({ hasText: '1 declined' })).toBeVisible();
    expect(runs).toEqual([true, false]);
    await expect(card.getByRole('list')).toContainText('declined');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await card.screenshot({ path: testInfo.outputPath('seerr-expiry.png') });
  });
}
