/* UI-005 focused entity-management browser acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'entities', roles: ['writer', 'reader'] });
const browser = await chromium.launch({ headless: true });

async function connect(page, token) {
  await page.goto(fixture.origin);
  await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByLabel('Approved device Token').fill(token);
  await page.getByRole('button', { name: 'Validate and connect' }).click();
}

try {
  const page = await browser.newPage();
  await connect(page, fixture.devices.writer.token);
  await page.getByRole('link', { name: /Albums/ }).click();
  await page.getByRole('heading', { name: /Albums/ }).waitFor();
  await page.getByRole('searchbox', { name: 'Search…', exact: true }).fill('Fixture');
  await page.getByRole('button', { name: 'Filter' }).click();
  assert.match(page.url(), /q=Fixture/);
  await page.getByText('Fixture Album', { exact: true }).click();
  await page.getByRole('heading', { name: 'Fixture Album' }).waitFor();
  await page.waitForTimeout(500);
  await page.getByRole('heading', { name: 'Fixture Album' }).waitFor();
  assert.equal(await page.getByRole('heading', { name: /Photos/ }).count(), 0);
  assert.equal(await page.getByRole('button', { name: 'Delete Album' }).count(), 0);
  await page.getByText('Digital Asset Lifecycle', { exact: true }).waitFor();

  await page.getByRole('button', { name: '+ Add Model' }).click();
  await page.getByRole('button', { name: 'Create Model' }).click();
  await page.locator('#mNewPrimaryName').fill('Inline Browser Model');
  await page.getByRole('button', { name: 'Add', exact: true }).click();
  await page.getByText('Inline Browser Model').waitFor();
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByText('Album saved').waitFor();
  const detail = await fixture.request('/albums/1', { role: 'writer' });
  assert.equal(detail.payload.data.models.some((item) => item.model_name === 'Inline Browser Model'), true);

  await page.getByRole('link', { name: /Albums/ }).click();
  await page.getByLabel('Select Fixture Album').check();
  await page.getByRole('button', { name: 'Batch edit selected' }).click();
  await page.locator('#batchField').selectOption('rating');
  await page.locator('#batchValue').fill('4');
  await page.getByRole('button', { name: 'Review changes' }).click();
  await page.getByText('1 eligible').waitFor();
  await page.getByRole('button', { name: 'Execute reviewed batch' }).click();
  await page.getByText('Updated 1 Albums').waitFor();
  const updated = await fixture.request('/albums/1', { role: 'writer' });
  assert.equal(updated.payload.data.album.rating, 4);

  const reader = await browser.newPage();
  await connect(reader, fixture.devices.reader.token);
  await reader.getByRole('link', { name: /Albums/ }).click();
  assert.equal(await reader.getByRole('button', { name: '+ New Album' }).isVisible(), false);
  await reader.close();
  await page.close();
  console.log('UI-005 entity management browser acceptance: OK');
} finally {
  await browser.close();
  await fixture.stop();
}
