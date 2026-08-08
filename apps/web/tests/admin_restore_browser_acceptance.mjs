/* UI-010C protected database Restore acceptance on disposable SQLite roots. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'empty', roles: ['admin', 'reader'] });
const browser = await chromium.launch({ headless: true });
async function connect(page, token) { await page.goto(fixture.origin); await page.getByRole('button', { name: 'Connect' }).click(); await page.getByLabel('Approved device Token').fill(token); await page.getByRole('button', { name: 'Validate and connect' }).click(); }
try {
  const created = await fixture.request('/backup', { method: 'POST', body: { reason: 'restore-target', tag: 'ui-010c' }, role: 'admin' });
  const target = created.payload.data.recovery_point;
  const verified = await fixture.request(`/backups/${target.identity}/verify`, { method: 'POST', body: {}, role: 'admin' });
  assert.equal(verified.payload.data.verification.verification_state, 'verified');
  const added = await fixture.request('/statuses', { method: 'POST', body: { name: 'Created After Target' }, role: 'admin' });
  assert.equal(added.status, 201);

  const reader = await browser.newPage(); await connect(reader, fixture.devices.reader.token);
  await reader.goto(`${fixture.origin}/#/admin/restore`); await reader.getByRole('heading', { name: 'Permission denied' }).waitFor(); await reader.close();

  const admin = await browser.newPage(); await connect(admin, fixture.devices.admin.token);
  await admin.goto(`${fixture.origin}/#/admin/restore`); await admin.getByRole('heading', { name: 'Database Restore' }).waitFor();
  const row = admin.getByRole('row').filter({ hasText: 'ui-010c' }); await row.getByRole('button', { name: 'Review Restore' }).click();
  await admin.getByRole('heading', { name: 'Confirm Database Restore' }).waitFor();
  await admin.getByLabel(/Type RESTORE/).fill(`RESTORE ${target.filename}`);
  await admin.getByRole('button', { name: 'Restore reviewed database' }).click();
  await admin.getByRole('heading', { name: 'Database Restore verified' }).waitFor();
  assert.equal(await admin.evaluate(() => localStorage.getItem('curator.web.deviceToken')), null);
  const statuses = await fixture.request('/statuses', { role: 'admin' });
  assert.equal((statuses.payload.data.statuses || statuses.payload.data).some(item => item.name === 'Created After Target'), false);
  const backups = await fixture.request('/backups', { role: 'admin' });
  assert.equal(backups.payload.data.items.some(item => item.reason === 'pre_restore_safety' && item.protection_state === 'protected'), true);
  await admin.close(); console.log('UI-010C protected Restore browser acceptance: OK');
} finally { await browser.close(); await fixture.stop(); }
