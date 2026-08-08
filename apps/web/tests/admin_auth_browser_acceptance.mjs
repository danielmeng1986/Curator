/* UI-010A Admin registration, one-time issuance, and revocation acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'empty', roles: ['admin', 'writer', 'reader'], pendingRegistrations: [{
  device_name: 'Pending Browser Writer', device_identity: 'pending-browser-writer', requested_role: 'writer', requested_scopes: ['read','write'],
}] });
const browser = await chromium.launch({ headless: true });
async function connect(page, token) { await page.goto(fixture.origin); await page.getByRole('button', { name: 'Connect' }).click(); await page.getByLabel('Approved device Token').fill(token); await page.getByRole('button', { name: 'Validate and connect' }).click(); }
try {
  const reader = await browser.newPage(); await connect(reader, fixture.devices.reader.token);
  await reader.goto(`${fixture.origin}/#/admin/devices`); await reader.getByRole('heading', { name: 'Permission denied' }).waitFor(); await reader.close();

  const admin = await browser.newPage(); await connect(admin, fixture.devices.admin.token);
  await admin.goto(`${fixture.origin}/#/admin/devices`); await admin.getByRole('heading', { name: 'Devices and Tokens' }).waitFor();
  await admin.getByText('Pending Browser Writer').waitFor();
  await admin.getByRole('button', { name: 'Approve', exact: true }).click();
  await admin.getByRole('heading', { name: 'Device Token issued once' }).waitFor();
  const issued = await admin.locator('#adminIssuedToken').textContent(); assert.ok(issued.length > 20);
  await admin.getByRole('button', { name: 'I stored it securely' }).click();
  await admin.getByText('Pending Browser Writer').waitFor();
  assert.equal((await admin.locator('body').innerText()).includes(issued), false);

  const state = await fixture.request('/auth/admin/state', { role: 'admin' });
  const writerToken = state.payload.data.tokens.find(item => item.registration_uuid === fixture.devices.writer.registration.uuid);
  const row = admin.getByRole('row').filter({ hasText: writerToken.uuid });
  await row.getByRole('button', { name: 'Revoke' }).click();
  await admin.getByLabel(/Type/).fill('REVOKE'); await admin.getByRole('button', { name: 'Execute reviewed action' }).click();
  await admin.getByText('Token revoked').waitFor();
  const revoked = await fixture.request('/auth/admin/state', { role: 'admin' });
  assert.ok(revoked.payload.data.tokens.find(item => item.uuid === writerToken.uuid).revoked_at);
  assert.equal(JSON.stringify(revoked.payload).includes(issued), false);

  const adminToken = revoked.payload.data.tokens.find(item => item.scopes.includes('admin') && !item.revoked_at);
  const adminRow = admin.getByRole('row').filter({ hasText: adminToken.uuid });
  await adminRow.getByRole('button', { name: 'Revoke' }).click();
  await admin.getByLabel(/Type/).fill('REVOKE'); await admin.getByRole('button', { name: 'Execute reviewed action' }).click();
  await admin.getByRole('alert').filter({ hasText: /final usable Admin Token/i }).last().waitFor();
  const protectedState = await fixture.request('/auth/admin/state', { role: 'admin' });
  assert.equal(protectedState.payload.data.tokens.find(item => item.uuid === adminToken.uuid).revoked_at, null);
  await admin.close(); console.log('UI-010A authentication administration browser acceptance: OK');
} finally { await browser.close(); await fixture.stop(); }
