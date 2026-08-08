/* UI-004C browser acceptance for connection, renewal, replacement, and roles. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { setFixtureTokenState, startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true });

async function connect(page, token) {
  await page.getByRole('button', { name: /Connect|Reconnect/ }).click();
  await page.getByLabel('Approved device Token').fill(token);
  await page.getByRole('button', { name: 'Validate and connect' }).click();
}

try {
  const fixture = await startBrowserFixture({ roles: ['reader', 'writer'] });
  try {
    const page = await browser.newPage();
    await page.goto(fixture.origin);
    await connect(page, fixture.devices.writer.token);
    await page.getByRole('button', { name: /Browser fixture writer · writer/ }).waitFor();

    await page.getByRole('button', { name: /Browser fixture writer · writer/ }).click();
    await page.getByText('Scopes: read, write').waitFor();
    await page.getByText(/Expires:/).waitFor();
    await page.getByRole('button', { name: 'Request renewal' }).click();
    await page.getByText(/renewal requested/i).waitFor();
    await page.getByRole('button', { name: /Browser fixture writer · writer/ }).click();
    await page.getByText(/Renewal: Pending/).waitFor();

    const oldToken = await page.evaluate(() => localStorage.getItem('curator.web.deviceToken'));
    await page.getByLabel('Approved device Token').fill('invalid-replacement');
    await page.getByRole('button', { name: 'Validate and connect' }).click();
    await page.getByRole('alert').filter({ hasText: /Authorization required/ }).last().waitFor();
    assert.equal(await page.evaluate(() => localStorage.getItem('curator.web.deviceToken')), oldToken);

    await page.getByLabel('Approved device Token').fill(fixture.devices.reader.token);
    await page.getByRole('button', { name: 'Validate and connect' }).click();
    await page.getByRole('button', { name: /Browser fixture reader · reader/ }).waitFor();
    const importLink = page.locator('a[data-route="import"]');
    assert.equal(await importLink.isVisible(), false);
    assert.equal(await importLink.getAttribute('aria-hidden'), 'true');
    await page.evaluate(() => { location.hash = '#/import/albums'; });
    await page.getByRole('heading', { name: 'Permission denied' }).waitFor();

    await page.getByRole('button', { name: /Browser fixture reader · reader/ }).click();
    await page.getByRole('button', { name: 'Disconnect' }).click();
    assert.equal(await page.evaluate(() => localStorage.getItem('curator.web.deviceToken')), null);
    await page.getByRole('heading', { name: 'Authorization required' }).waitFor();
    await page.close();

    const revokedPage = await browser.newPage();
    await revokedPage.goto(fixture.origin);
    await connect(revokedPage, fixture.devices.writer.token);
    await revokedPage.getByRole('button', { name: /Browser fixture writer · writer/ }).waitFor();
    await setFixtureTokenState(
      fixture.resources.database, fixture.devices.writer.tokenRecord.uuid, 'revoked',
    );
    await revokedPage.reload();
    await revokedPage.getByRole('button', { name: 'Reconnect' }).waitFor();
    await revokedPage.getByRole('heading', { name: 'Authorization required' }).waitFor();
    await revokedPage.close();

    const expiredPage = await browser.newPage();
    await expiredPage.goto(fixture.origin);
    await connect(expiredPage, fixture.devices.reader.token);
    await expiredPage.getByRole('button', { name: /Browser fixture reader · reader/ }).waitFor();
    await setFixtureTokenState(
      fixture.resources.database, fixture.devices.reader.tokenRecord.uuid, 'expired',
    );
    await expiredPage.reload();
    await expiredPage.getByRole('button', { name: 'Reconnect' }).waitFor();
    await expiredPage.getByRole('heading', { name: 'Authorization required' }).waitFor();
    await expiredPage.close();
  } finally {
    await fixture.stop();
  }
  console.log('UI-004C Token lifecycle browser acceptance: OK');
} finally {
  await browser.close();
}
