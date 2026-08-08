/* UI-009 Admin-only Repair Quarantine browser/filesystem acceptance. */
import assert from 'node:assert/strict';
import { access } from 'node:fs/promises';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'workflow-evidence', roles: ['admin', 'writer'] });
const browser = await chromium.launch({ headless: true });
const original = join(fixture.resources.archive, 'F', 'Fixture Model', 'Fixture Studio', 'Fixture Album');

async function connect(page, token) {
  await page.goto(fixture.origin); await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByLabel('Approved device Token').fill(token); await page.getByRole('button', { name: 'Validate and connect' }).click();
}

try {
  const writer = await browser.newPage(); await connect(writer, fixture.devices.writer.token);
  assert.equal(await writer.getByRole('link', { name: /Repair Quarantine/ }).count(), 0);
  await writer.goto(`${fixture.origin}/#/quarantine`);
  await writer.getByRole('heading', { name: 'Permission denied' }).waitFor();

  const admin = await browser.newPage(); await connect(admin, fixture.devices.admin.token);
  await admin.goto(`${fixture.origin}/#/repairs/repair-ui-fixture`);
  await admin.getByRole('button', { name: 'Review Quarantine move' }).waitFor();
  const reasonDialog = admin.waitForEvent('dialog').then(dialog => dialog.accept('Isolate fixture conflict for review.'));
  await admin.getByRole('button', { name: 'Review Quarantine move' }).click(); await reasonDialog;
  await admin.getByRole('heading', { name: 'Confirm quarantine preview' }).waitFor();
  await admin.getByText('this does not resolve the Issue', { exact: false }).waitFor();
  await access(join(original, 'conflict.jpg'));
  await admin.getByRole('button', { name: 'Execute reviewed quarantine' }).click();
  await admin.getByRole('heading', { name: 'Quarantine Item' }).waitFor();
  await admin.getByText('conflict.jpg', { exact: true }).waitFor();
  const item = (await fixture.request('/quarantine-items', { role: 'admin' })).payload.data.items[0];
  await access(join(fixture.resources.quarantine, item.quarantine_path, 'conflict.jpg'));

  await admin.getByRole('button', { name: 'Review restore to original path' }).click();
  await admin.getByRole('heading', { name: 'Confirm restore preview' }).waitFor();
  await admin.getByRole('button', { name: 'Execute reviewed restore' }).click();
  await admin.getByText('Restored', { exact: true }).waitFor();
  await access(join(original, 'conflict.jpg'));
  assert.ok((await fixture.request(`/quarantine-items/${item.uuid}`, { role: 'admin' })).payload.data.item.restored_at);

  await admin.close(); await writer.close();
  console.log('UI-009 Repair Quarantine browser acceptance: OK');
} finally { await browser.close(); await fixture.stop(); }
