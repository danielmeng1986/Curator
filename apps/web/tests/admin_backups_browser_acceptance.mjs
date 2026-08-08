/* UI-010B recovery-point administration acceptance on disposable roots. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'empty', roles: ['admin', 'reader'] });
const browser = await chromium.launch({ headless: true });
async function connect(page, token) { await page.goto(fixture.origin); await page.getByRole('button', { name: 'Connect' }).click(); await page.getByLabel('Approved device Token').fill(token); await page.getByRole('button', { name: 'Validate and connect' }).click(); }
try {
  const reader = await browser.newPage(); await connect(reader, fixture.devices.reader.token);
  await reader.goto(`${fixture.origin}/#/admin/backups`); await reader.getByRole('heading', { name: 'Permission denied' }).waitFor(); await reader.close();

  const admin = await browser.newPage(); await connect(admin, fixture.devices.admin.token);
  await admin.goto(`${fixture.origin}/#/admin/backups`); await admin.getByRole('heading', { name: 'Backups and Snapshots' }).waitFor();
  await admin.getByRole('button', { name: 'Create recovery point' }).click();
  await admin.getByLabel('Tag (optional)').fill('ui-010b'); await admin.getByRole('button', { name: 'Create', exact: true }).click();
  await admin.getByText('Recovery point created').waitFor();
  const row = admin.getByRole('row').filter({ hasText: 'ui-010b' }); await row.waitFor();
  assert.equal((await admin.locator('body').innerText()).includes(fixture.resources.backups), false);
  await row.getByRole('button', { name: 'Verify' }).click(); await admin.getByText('Recovery point verified').waitFor();
  await admin.getByRole('button', { name: 'Review retention cleanup' }).click();
  await admin.getByText(/0 expired, unprotected/).waitFor();
  await admin.getByRole('button', { name: 'Cancel' }).click();
  const catalog = await fixture.request('/backups', { role: 'admin' });
  assert.equal(JSON.stringify(catalog.payload).includes(fixture.resources.backups), false);
  await admin.close(); console.log('UI-010B backup administration browser acceptance: OK');
} finally { await browser.close(); await fixture.stop(); }
