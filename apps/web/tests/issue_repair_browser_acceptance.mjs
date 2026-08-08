/* UI-008 focused Issue and Repair decision browser acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'workflow-evidence', roles: ['writer', 'reader', 'admin'] });
const browser = await chromium.launch({ headless: true });

async function connect(page, token) {
  await page.goto(fixture.origin); await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByLabel('Approved device Token').fill(token);
  await page.getByRole('button', { name: 'Validate and connect' }).click();
}

try {
  const writer = await browser.newPage(); await connect(writer, fixture.devices.writer.token);
  await writer.getByRole('link', { name: /Issues/ }).click();
  await writer.getByRole('heading', { name: 'Issues' }).waitFor();
  await writer.getByRole('link', { name: 'issue-ui-fixture' }).click();
  await writer.getByRole('button', { name: 'begin work' }).click();
  await writer.getByRole('button', { name: 'Apply' }).click();
  await writer.getByText('InProgress', { exact: true }).waitFor();
  assert.equal(await writer.getByRole('button', { name: 'resolve' }).count(), 0);

  await writer.goto(`${fixture.origin}/#/repairs/repair-ui-fixture`);
  await writer.getByRole('heading', { name: 'Repair Detail' }).waitFor();
  await writer.getByText('Fixture filesystem failure').waitFor();
  const confirmation = writer.waitForEvent('dialog').then(dialog => dialog.accept('Reviewed candidate and authoritative evidence.'));
  await writer.getByRole('button', { name: 'confirm' }).click();
  await confirmation;
  await writer.getByRole('button', { name: 'start' }).waitFor();

  const reader = await browser.newPage(); await connect(reader, fixture.devices.reader.token);
  await reader.goto(`${fixture.origin}/#/repairs/repair-ui-fixture`);
  await reader.getByRole('heading', { name: 'Repair Detail' }).waitFor();
  await reader.getByText('Operational path evidence is hidden for this role.').waitFor();
  assert.equal(await reader.getByRole('button', { name: /confirm|ignore|start/ }).count(), 0);

  const admin = await browser.newPage(); await connect(admin, fixture.devices.admin.token);
  await admin.goto(`${fixture.origin}/#/issues/issue-ui-fixture`);
  await admin.getByRole('button', { name: 'resolve' }).waitFor();
  await admin.goto(`${fixture.origin}/#/repairs/repair-ui-fixture`);
  await admin.getByRole('button', { name: 'Create bounded suppression' }).waitFor();

  await admin.close(); await reader.close(); await writer.close();
  console.log('UI-008 Issue and Repair browser acceptance: OK');
} finally { await browser.close(); await fixture.stop(); }
