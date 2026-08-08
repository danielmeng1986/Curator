/* Browser acceptance smoke gate: only disposable Backend state is used. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'empty', roles: ['writer'] });
try {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto(fixture.origin);
  await page.getByRole('heading', { name:'Authorization required' }).waitFor();
  await page.getByRole('button', { name:'Connect' }).click();
  await page.getByPlaceholder('Same origin when empty').fill(fixture.origin);
  await page.getByPlaceholder('Required').fill(fixture.devices.writer.token);
  await page.getByRole('button', { name:'Save' }).click();
  await page.getByText(/DB OK/).waitFor();
  await page.getByRole('link', { name:/Albums/ }).click();
  await page.getByRole('heading', { name:'Albums' }).waitFor();

  const before = (await fixture.request('/albums', { role: 'writer' })).payload.data.length;
  const denied = await fixture.request('/backup', { method: 'POST', body: {}, role: 'writer' });
  assert.equal(denied.status, 403);
  const after = (await fixture.request('/albums', { role: 'writer' })).payload.data.length;
  assert.equal(after, before, 'rejected administrative action has no business side effect');
  await browser.close();
  console.log('browser workflow acceptance: ok');
} finally {
  await fixture.stop();
}
