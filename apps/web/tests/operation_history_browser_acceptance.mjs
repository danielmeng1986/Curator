/* UI-007 focused role-sensitive Operation history browser acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'workflow-evidence', roles: ['writer', 'reader'] });
const browser = await chromium.launch({ headless: true });

async function connect(page, token) {
  await page.goto(fixture.origin);
  await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByLabel('Approved device Token').fill(token);
  await page.getByRole('button', { name: 'Validate and connect' }).click();
}

try {
  const writer = await browser.newPage();
  await connect(writer, fixture.devices.writer.token);
  await writer.getByRole('link', { name: /Operations/ }).click();
  await writer.getByRole('heading', { name: 'Operations' }).waitFor();
  await writer.getByLabel('Status').selectOption('NeedsRepair');
  await writer.getByLabel('Operation type').fill('import');
  await writer.getByRole('button', { name: 'Filter' }).click();
  assert.match(writer.url(), /status=NeedsRepair/);
  await writer.getByRole('link', { name: 'operation-ui-fixture' }).click();
  await writer.getByRole('heading', { name: 'Operation Detail' }).waitFor();
  await writer.getByText('Fixture import requires review.').waitFor();
  await writer.getByRole('link', { name: 'issue-ui-fixture' }).waitFor();
  await writer.getByRole('link', { name: 'repair-ui-fixture' }).waitFor();
  await writer.getByText('Recovery context', { exact: true }).waitFor();
  await writer.getByText('Review the linked Repair before retrying.').waitFor();

  const reader = await browser.newPage();
  await connect(reader, fixture.devices.reader.token);
  await reader.goto(`${fixture.origin}/#/operations/operation-ui-fixture`);
  await reader.getByRole('heading', { name: 'Operation Detail' }).waitFor();
  assert.equal(await reader.getByText('Recovery context', { exact: true }).count(), 0);
  assert.equal((await reader.locator('body').innerText()).includes('/private/'), false);

  await reader.close();
  await writer.close();
  console.log('UI-007 Operation history browser acceptance: OK');
} finally {
  await browser.close();
  await fixture.stop();
}
