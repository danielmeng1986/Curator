/* UI-004B browser acceptance for one-time loopback administrator bootstrap. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { access, readFile } from 'node:fs/promises';
import { createBootstrapCode, startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

async function logsDoNotContain(fixture, secrets) {
  for (const filename of ['changes.log', 'backup.log', 'rollback.log']) {
    const path = `${fixture.resources.logs}/${filename}`;
    try { await access(path); } catch { continue; }
    const text = await readFile(path, 'utf8');
    for (const secret of secrets) assert.equal(text.includes(secret), false, `${filename} leaked a secret`);
  }
}

const browser = await chromium.launch({ headless: true });
try {
  const lockedFixture = await startBrowserFixture({ roles: [], bootstrapAdmin: false });
  try {
    const code = await createBootstrapCode(lockedFixture.resources.database);
    const page = await browser.newPage();
    await page.goto(lockedFixture.origin);
    await page.getByRole('button', { name: 'Initialize administrator' }).click();
    for (let attempt = 0; attempt < 5; attempt += 1) {
      await page.getByLabel('Bootstrap Code').fill(`wrong-${attempt}`);
      await page.getByRole('button', { name: 'Initialize', exact: true }).click();
      await page.getByLabel('Bootstrap Code').waitFor();
    }
    await page.getByLabel('Bootstrap Code').fill(code);
    await page.getByRole('button', { name: 'Initialize', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: /invalid or locked/i }).last().waitFor();
    assert.equal(await page.evaluate(() => localStorage.getItem('curator.web.deviceToken')), null);
    await logsDoNotContain(lockedFixture, [code]);
    await page.close();
  } finally {
    await lockedFixture.stop();
  }

  const fixture = await startBrowserFixture({ roles: [], bootstrapAdmin: false });
  try {
    const code = await createBootstrapCode(fixture.resources.database);
    const page = await browser.newPage();
    await page.goto(fixture.origin);
    await page.getByRole('button', { name: 'Initialize administrator' }).click();
    await page.getByLabel('Administrator device name').fill('Browser Administrator');
    await page.getByLabel('Bootstrap Code').fill(code);
    await page.getByRole('button', { name: 'Initialize', exact: true }).click();
    await page.getByRole('heading', { name: 'Administrator initialized' }).waitFor();
    const token = await page.locator('#issuedAdminToken').textContent();
    assert.ok(token);
    assert.equal(await page.evaluate(() => localStorage.getItem('curator.web.deviceToken')), token);
    assert.equal(await page.getByRole('button', { name: 'Continue' }).isDisabled(), true);

    // Simulate interruption before acknowledgement: the Token was stored first.
    await page.reload();
    await page.getByText(/DB OK/).waitFor();
    const replay = await fetch(`${fixture.origin}/api/auth/bootstrap/complete`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, device_name: 'Replay', device_identity: 'replay' }),
    });
    assert.equal(replay.status, 409);
    const status = await (await fetch(`${fixture.origin}/api/auth/bootstrap/status`)).json();
    assert.equal(status.data.bootstrap.initialized, true);
    assert.equal(status.data.bootstrap.code_available, false);
    await logsDoNotContain(fixture, [code, token]);
    await page.close();
  } finally {
    await fixture.stop();
  }
  console.log('UI-004B administrator bootstrap browser acceptance: OK');
} finally {
  await browser.close();
}
