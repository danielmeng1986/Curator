/* UI-019/UI-020/UI-021 multi-browser UI-only device enrollment acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url); const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'empty', roles: ['admin'] });
const browser = await chromium.launch({ headless: true });

async function connect(page, token) {
  await page.goto(fixture.origin);
  await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByLabel('Approved device Token').fill(token);
  await page.getByRole('button', { name: 'Validate and connect' }).click();
  await page.getByText(/DB OK/).waitFor();
}

try {
  const adminContext = await browser.newContext(); const admin = await adminContext.newPage();
  await connect(admin, fixture.devices.admin.token);
  await admin.goto(`${fixture.origin}/#/admin/devices`);
  await admin.getByRole('button', { name: 'Generate Registration Proof' }).click();
  await admin.getByRole('button', { name: 'Generate', exact: true }).click();
  await admin.getByRole('heading', { name: 'Registration Proof shown once' }).waitFor();
  const proof = await admin.locator('#issuedRegistrationProof').textContent(); assert.ok(proof.length > 32);
  await admin.getByRole('button', { name: 'I stored it securely' }).click();

  const requesterContext = await browser.newContext(); const requester = await requesterContext.newPage();
  await requester.goto(fixture.origin);
  await requester.getByRole('button', { name: 'Connect' }).click();
  await requester.getByRole('button', { name: 'Request device access' }).click();
  await requester.getByLabel('Device name').fill('Chrome Writer');
  await requester.getByLabel('Requested role').selectOption('writer');
  await requester.getByLabel('Registration Proof').fill(proof);
  await requester.getByRole('button', { name: 'Request access' }).click();
  await requester.getByRole('heading', { name: 'Waiting for Administrator approval' }).waitFor();

  await admin.reload(); await admin.getByText('Chrome Writer').waitFor();
  await admin.getByRole('row').filter({ hasText: 'Chrome Writer' }).getByRole('button', { name: 'Approve' }).click();
  await admin.getByText('Device approved. The requesting browser can now connect.').waitFor();

  await requester.getByRole('button', { name: 'Check status' }).click();
  await requester.getByText('Device approved and connected as writer.').waitFor();
  await requester.getByRole('button', { name: /Chrome Writer · writer/ }).waitFor();
  const state = await fixture.request('/auth/admin/state', { role: 'admin' });
  const registration = state.payload.data.registrations.find(item => item.device_name === 'Chrome Writer');
  assert.equal(registration.approved_role, 'writer');
  assert.deepEqual(registration.approved_scopes, ['read', 'write']);
  assert.equal(JSON.stringify(state.payload).includes(proof), false);
  assert.equal(JSON.stringify(state.payload).includes('candidate_token_hash'), false);
  assert.equal(JSON.stringify(state.payload).includes('enrollment_proof_hash'), false);
  await requesterContext.close(); await adminContext.close();
  console.log('UI-021 multi-browser device enrollment acceptance: OK');
} finally { await browser.close(); await fixture.stop(); }
