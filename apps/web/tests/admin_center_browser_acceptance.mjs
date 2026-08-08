/* UI-010 Administrator Center shell and authorization browser acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'workflow-evidence', roles: ['admin', 'writer', 'reader'] });
const browser = await chromium.launch({ headless: true });
async function connect(page, token) {
  await page.goto(fixture.origin); await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByLabel('Approved device Token').fill(token); await page.getByRole('button', { name: 'Validate and connect' }).click();
}
try {
  for (const role of ['writer', 'reader']) {
    const page = await browser.newPage(); const protectedRequests = [];
    page.on('request', request => { if (/\/(backups|quarantine-items|operations)/.test(request.url())) protectedRequests.push(request.url()); });
    await connect(page, fixture.devices[role].token); protectedRequests.length = 0;
    assert.equal(await page.getByRole('link', { name: /Administrator Center/ }).count(), 0);
    await page.goto(`${fixture.origin}/#/admin`); await page.getByRole('heading', { name: 'Permission denied' }).waitFor();
    assert.deepEqual(protectedRequests, [], `${role} direct route must not fetch protected Admin data`); await page.close();
  }
  const admin = await browser.newPage(); await connect(admin, fixture.devices.admin.token);
  await admin.getByRole('link', { name: /Administrator Center/ }).click();
  await admin.getByRole('heading', { name: 'Administrator Center' }).waitFor();
  await admin.locator('.card .form-section-title', { hasText: 'Devices and Tokens' }).waitFor();
  await admin.locator('.card .form-section-title', { hasText: 'Repair Quarantine' }).waitFor();
  assert.equal((await admin.locator('body').innerText()).includes(fixture.devices.admin.token), false);
  assert.equal(await admin.getByRole('button', { name: 'Not available yet' }).count(), 3);
  await admin.close(); console.log('UI-010 Administrator Center browser acceptance: OK');
} finally { await browser.close(); await fixture.stop(); }
