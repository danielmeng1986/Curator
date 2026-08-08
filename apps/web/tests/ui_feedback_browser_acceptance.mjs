/* UI-002 browser acceptance: shared feedback and interaction behavior. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto(pathToFileURL(resolve('apps/web/static/index.html')).href);
  await page.getByRole('heading', { name: 'Authorization required' }).waitFor();

  const connect = page.getByRole('button', { name: 'Connect' });
  await connect.focus();
  await connect.click();
  assert.equal(await page.getByPlaceholder('Same origin when empty').evaluate((node) => node === document.activeElement), true);
  await page.getByRole('button', { name: 'Cancel' }).click();
  assert.equal(await connect.evaluate((node) => node === document.activeElement), true, 'closing a modal restores focus');

  const presentations = await page.evaluate(() => ({
    authentication: ui.errorPresentation(new api.Error('AUTHENTICATION_REVOKED_TOKEN', 'secret', 401)).title,
    authorization: ui.errorPresentation(new api.Error('AUTHORIZATION_INSUFFICIENT_SCOPE', 'secret', 403)).title,
    validation: ui.errorPresentation(new api.Error('REQUEST_INVALID', 'Title is required.', 400)).kind,
    conflict: ui.errorPresentation(new api.Error('NEEDS_REPAIR', 'Review it.', 409)).title,
    network: ui.errorPresentation(new api.Error('NETWORK_UNAVAILABLE', 'private')).message,
    unexpected: ui.errorPresentation(new api.Error('INTERNAL_ERROR', '/private/path')).message,
  }));
  assert.deepEqual(presentations, {
    authentication: 'Authorization required',
    authorization: 'Permission denied',
    validation: 'validation',
    conflict: 'Repair review required',
    network: 'Check the Curator connection and try again. Your entered values have been retained.',
    unexpected: 'An unexpected error occurred. No success has been assumed.',
  });

  const repeated = await page.evaluate(async () => {
    let calls = 0;
    let release;
    const pending = new Promise((resolvePending) => { release = resolvePending; });
    const first = ui.runAction('browser-save', async () => { calls += 1; await pending; });
    const second = await ui.runAction('browser-save', async () => { calls += 1; });
    release();
    await first;
    return { calls, secondCode: second.error.code };
  });
  assert.deepEqual(repeated, { calls: 1, secondCode: 'CLIENT_ACTION_IN_PROGRESS' });

  console.log('UI-002 browser feedback acceptance: OK');
} finally {
  await browser.close();
}
