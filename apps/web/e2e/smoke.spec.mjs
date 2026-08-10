import { test, expect } from '@playwright/test';
import { startBrowserFixture } from '../tests/browser_fixture.mjs';

test('Writer connects and opens permanent Album management', async ({ page }) => {
  const fixture = await startBrowserFixture({ scenario: 'entities', roles: ['writer'] });
  const browserErrors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') browserErrors.push(`console: ${message.text()}`);
  });
  page.on('pageerror', (error) => browserErrors.push(`page: ${error.message}`));
  page.on('requestfailed', (request) => {
    browserErrors.push(`request: ${request.method()} ${request.url()} ${request.failure()?.errorText || ''}`);
  });

  try {
    await page.goto(fixture.origin);
    await expect(page.getByRole('heading', { name: 'Authorization required' })).toBeVisible();
    await page.getByRole('button', { name: 'Connect' }).click();
    await page.getByPlaceholder('Same origin when empty').fill(fixture.origin);
    await page.getByLabel('Approved device Token').fill(fixture.devices.writer.token);
    await page.getByRole('button', { name: 'Validate and connect' }).click();
    await expect(page.getByText(/DB OK/)).toBeVisible();

    await page.getByRole('link', { name: /Albums/ }).click();
    await expect(page.getByRole('heading', { name: 'Albums' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'New Album' })).toBeVisible();
    expect(browserErrors).toEqual([]);
  } catch (error) {
    await test.info().attach('sanitized-browser-errors', {
      body: Buffer.from(fixture.sanitize(browserErrors.join('\n') || String(error))),
      contentType: 'text/plain',
    });
    throw error;
  } finally {
    await fixture.stop();
  }
});
