/* UI-015 role, credential-state, direct-request, and network disclosure acceptance. */
import assert from 'node:assert/strict';
import { readdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { setFixtureTokenState, startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const OPERATION_UUID = 'operation-ui-fixture';
const REPAIR_UUID = 'repair-ui-fixture';

function collection(payload) {
  const data = payload.data;
  return Array.isArray(data) ? data : (data?.items || []);
}

async function connect(page, fixture, role) {
  await page.goto(fixture.origin);
  await page.getByRole('button', { name: /Connect|Reconnect/ }).click();
  await page.getByLabel('Approved device Token').fill(fixture.devices[role].token);
  await page.getByRole('button', { name: 'Validate and connect' }).click();
  const deviceName = role === 'admin' ? 'Fixture Administrator' : `Browser fixture ${role}`;
  await page.getByRole('button', { name: new RegExp(`${deviceName} · ${role}`) }).waitFor();
  await page.getByText(/DB OK/).waitFor();
}

async function rawRequest(page, path, { method = 'GET', authorization = null, body = undefined } = {}) {
  return page.evaluate(async ({ path: requestPath, method: requestMethod, authorization: auth, body: requestBody }) => {
    const response = await fetch(requestPath, {
      method: requestMethod,
      headers: {
        ...(auth === null ? {} : { Authorization: auth }),
        ...(requestBody === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      ...(requestBody === undefined ? {} : { body: JSON.stringify(requestBody) }),
    });
    return { status: response.status, payload: await response.json() };
  }, { path, method, authorization, body });
}

function assertNoSecretFields(value, secrets = []) {
  const serialized = JSON.stringify(value);
  for (const forbidden of ['token_hash', 'registration_proof', 'bootstrap_code', 'error_details']) {
    assert.equal(serialized.includes(`"${forbidden}"`), false, `response disclosed ${forbidden}`);
  }
  for (const secret of secrets.filter(Boolean)) {
    assert.equal(serialized.includes(secret), false, 'response disclosed a fixture credential');
  }
  assert.equal(serialized.includes('/private/'), false, 'response disclosed a private absolute path');
}

const browser = await chromium.launch({ headless: true });
try {
  const authFixture = await startBrowserFixture({ scenario: 'entities', roles: ['reader', 'writer', 'admin'] });
  try {
    const page = await browser.newPage();
    await page.goto(authFixture.origin);
    await page.getByRole('heading', { name: 'Authorization required' }).waitFor();
    const albumsBefore = collection((await authFixture.request('/albums', { role: 'admin' })).payload).length;
    const statusesBefore = (await authFixture.request('/statuses', { role: 'admin' })).payload.data.statuses.length;
    const backupsBefore = (await readdir(authFixture.resources.backups)).length;

    const missing = await rawRequest(page, '/api/v1/statuses');
    assert.deepEqual([missing.status, missing.payload.error.code], [401, 'AUTHENTICATION_MISSING_TOKEN']);
    const malformed = await rawRequest(page, '/api/v1/statuses', { authorization: 'Basic malformed' });
    assert.deepEqual([malformed.status, malformed.payload.error.code], [401, 'AUTHENTICATION_MISSING_TOKEN']);
    const invalid = await rawRequest(page, '/api/v1/statuses', { authorization: 'Bearer invalid-device-token' });
    assert.equal(invalid.status, 401);
    assert.match(invalid.payload.error.code, /^AUTHENTICATION_/);
    assertNoSecretFields([missing, malformed, invalid], ['invalid-device-token']);

    const missingWrite = await rawRequest(page, '/api/v1/statuses', {
      method: 'POST', body: { name: 'Must Not Exist' },
    });
    const invalidWrite = await rawRequest(page, '/api/v1/statuses', {
      method: 'POST', authorization: 'Bearer invalid-device-token', body: { name: 'Still Must Not Exist' },
    });
    assert.equal(missingWrite.status, 401);
    assert.equal(invalidWrite.status, 401);

    await setFixtureTokenState(authFixture.resources.database, authFixture.devices.reader.tokenRecord.uuid, 'expired');
    const expired = await rawRequest(page, '/api/v1/statuses', {
      method: 'POST', authorization: `Bearer ${authFixture.devices.reader.token}`, body: { name: 'Expired Must Not Write' },
    });
    assert.deepEqual([expired.status, expired.payload.error.code], [401, 'AUTHENTICATION_EXPIRED_TOKEN']);
    await setFixtureTokenState(authFixture.resources.database, authFixture.devices.writer.tokenRecord.uuid, 'revoked');
    const revoked = await rawRequest(page, '/api/v1/statuses', {
      method: 'POST', authorization: `Bearer ${authFixture.devices.writer.token}`, body: { name: 'Revoked Must Not Write' },
    });
    assert.deepEqual([revoked.status, revoked.payload.error.code], [401, 'AUTHENTICATION_REVOKED_TOKEN']);
    assertNoSecretFields([expired, revoked], [authFixture.devices.reader.token, authFixture.devices.writer.token]);

    assert.equal((await authFixture.request('/statuses', { role: 'admin' })).payload.data.statuses.length, statusesBefore);
    assert.equal(collection((await authFixture.request('/albums', { role: 'admin' })).payload).length, albumsBefore);
    assert.equal((await readdir(authFixture.resources.backups)).length, backupsBefore);

    await page.getByRole('button', { name: /Connect|Reconnect/ }).click();
    await page.getByLabel('Approved device Token').fill('invalid-replacement');
    await page.getByRole('button', { name: 'Validate and connect' }).click();
    await page.getByRole('alert').filter({ hasText: /Authorization required/ }).last().waitFor();
    await page.waitForFunction(() => {
      const button = document.getElementById('connectionSave');
      const input = document.getElementById('deviceToken');
      return button && !button.disabled && input?.value === '';
    });
    assert.equal(await page.evaluate(() => localStorage.getItem('curator.web.deviceToken')), null);
    await page.getByLabel('Approved device Token').fill(authFixture.devices.admin.token);
    await page.getByRole('button', { name: 'Validate and connect' }).click();
    await page.getByRole('button', { name: /Fixture Administrator · admin/ }).waitFor();
    assert.equal((await rawRequest(page, '/api/v1/statuses', { authorization: `Bearer ${authFixture.devices.admin.token}` })).status, 200);
    await page.close();
  } finally { await authFixture.stop(); }

  const fixture = await startBrowserFixture({ scenario: 'workflow-evidence', roles: ['reader', 'writer', 'admin'] });
  try {
    const secrets = [fixture.devices.reader.token, fixture.devices.writer.token, fixture.devices.admin.token];

    const readerContext = await browser.newContext();
    const reader = await readerContext.newPage(); await connect(reader, fixture, 'reader');
    for (const route of ['import', 'quarantine', 'admin', 'work-dispatch', 'ai-reviews']) {
      assert.equal(await reader.locator(`[data-route="${route}"]`).isVisible(), false, `${route} visible to Reader`);
    }
    await reader.goto(`${fixture.origin}/#/import/albums`);
    await reader.getByRole('heading', { name: 'Permission denied' }).waitFor();
    await reader.goto(`${fixture.origin}/#/admin`);
    await reader.getByRole('heading', { name: 'Permission denied' }).waitFor();

    const readerOperationResponse = reader.waitForResponse(response => response.url().endsWith(`/api/v1/operations/${OPERATION_UUID}`));
    await reader.goto(`${fixture.origin}/#/operations/${OPERATION_UUID}`);
    const readerOperation = await (await readerOperationResponse).json();
    await reader.getByRole('heading', { name: 'Operation Detail' }).waitFor();
    assert.equal(Object.hasOwn(readerOperation.data.operation, 'recovery_context'), false);
    assert.equal(Object.hasOwn(readerOperation.data.operation, 'error_details'), false);
    assert.equal(await reader.getByText('Recovery context', { exact: true }).count(), 0);
    await reader.getByText('Import:', { exact: true }).waitFor();
    await reader.getByText('(detail route unavailable)', { exact: true }).waitFor();

    const readerRepairResponse = reader.waitForResponse(response => response.url().endsWith(`/api/v1/repairs/${REPAIR_UUID}`));
    await reader.goto(`${fixture.origin}/#/repairs/${REPAIR_UUID}`);
    const readerRepair = await (await readerRepairResponse).json();
    await reader.getByText('Operational path evidence is hidden for this role.').waitFor();
    assert.equal(Object.hasOwn(readerRepair.data.repair, 'expected_path'), false);
    assert.equal(Object.hasOwn(readerRepair.data.repair, 'failure_reason'), false);
    assert.deepEqual(readerRepair.data.repair.allowed_actions, []);
    assertNoSecretFields([readerOperation, readerRepair], secrets);

    const readerModelsBefore = collection((await fixture.request('/models', { role: 'admin' })).payload).length;
    const readerDenied = await reader.evaluate(async () => {
      const results = [];
      for (const [path, body] of [
        ['/models', { primary_name: 'Reader Attack' }],
        ['/backup', {}],
        ['/quarantine/preview', { action: 'quarantine', repair_uuid: 'repair-ui-fixture', reason: 'attack' }],
      ]) {
        try { await api.post(path, body); results.push(null); } catch (error) { results.push({ status: error.status, code: error.code }); }
      }
      return results;
    });
    assert.deepEqual(readerDenied.map(item => item.status), [403, 403, 403]);
    assert.equal(collection((await fixture.request('/models', { role: 'admin' })).payload).length, readerModelsBefore);
    assert.equal(collection((await fixture.request('/quarantine-items', { role: 'admin' })).payload).length, 0);

    const writerContext = await browser.newContext();
    const writer = await writerContext.newPage(); await connect(writer, fixture, 'writer');
    assert.equal(await writer.locator('[data-route="import"]').isVisible(), true);
    for (const route of ['quarantine', 'admin', 'work-dispatch', 'ai-reviews']) {
      assert.equal(await writer.locator(`[data-route="${route}"]`).isVisible(), false, `${route} visible to Writer`);
    }
    const writerOperationResponse = writer.waitForResponse(response => response.url().endsWith(`/api/v1/operations/${OPERATION_UUID}`));
    await writer.goto(`${fixture.origin}/#/operations/${OPERATION_UUID}`);
    const writerOperation = await (await writerOperationResponse).json();
    await writer.getByText('Recovery context', { exact: true }).waitFor();
    assert.equal(writerOperation.data.operation.recovery_context, 'Review the linked Repair before retrying.');
    assert.equal(Object.hasOwn(writerOperation.data.operation, 'error_details'), false);
    const writerRepairResponse = writer.waitForResponse(response => response.url().endsWith(`/api/v1/repairs/${REPAIR_UUID}`));
    await writer.goto(`${fixture.origin}/#/repairs/${REPAIR_UUID}`);
    const writerRepair = await (await writerRepairResponse).json();
    assert.equal(writerRepair.data.repair.expected_path, 'F/Fixture Model/Fixture Studio/Fixture Album');
    assert.equal(writerRepair.data.repair.suppression_candidate, undefined);
    assert.equal(writerRepair.data.repair.quarantine_candidate, undefined);
    assertNoSecretFields([writerOperation, writerRepair], secrets);
    const writerAdmin = await writer.evaluate(async () => {
      try { await api.get('/auth/admin/state'); return null; } catch (error) { return { status: error.status, code: error.code }; }
    });
    assert.deepEqual(writerAdmin, { status: 403, code: 'AUTHORIZATION_INSUFFICIENT_SCOPE' });

    const adminContext = await browser.newContext();
    const admin = await adminContext.newPage(); await connect(admin, fixture, 'admin');
    for (const route of ['import', 'quarantine', 'admin', 'work-dispatch', 'ai-reviews']) {
      assert.equal(await admin.locator(`[data-route="${route}"]`).isVisible(), true, `${route} hidden from Admin`);
    }
    const adminStateResponse = admin.waitForResponse(response => response.url().endsWith('/api/v1/auth/admin/state'));
    await admin.goto(`${fixture.origin}/#/admin/devices`);
    const adminState = await (await adminStateResponse).json();
    await admin.getByRole('heading', { name: 'Devices and Tokens' }).waitFor();
    assertNoSecretFields(adminState, secrets);
    const adminRepairResponse = admin.waitForResponse(response => response.url().endsWith(`/api/v1/repairs/${REPAIR_UUID}`));
    await admin.goto(`${fixture.origin}/#/repairs/${REPAIR_UUID}`);
    const adminRepair = await (await adminRepairResponse).json();
    assert.ok(adminRepair.data.repair.suppression_candidate);
    assert.ok(adminRepair.data.repair.quarantine_candidate);
    assertNoSecretFields(adminRepair, secrets);

    const missingOperation = await admin.evaluate(async () => {
      try { await api.get('/operations/missing-operation'); return null; }
      catch (error) { return { status: error.status, code: error.code, message: error.message }; }
    });
    assert.deepEqual({ status: missingOperation.status, code: missingOperation.code }, { status: 404, code: 'NOT_FOUND' });
    assert.equal(missingOperation.message.includes('/private/'), false);

    const allRendered = await Promise.all([reader, writer, admin].map(page => page.locator('body').innerText()));
    for (const rendered of allRendered) {
      for (const secret of secrets) assert.equal(rendered.includes(secret), false, 'rendered UI disclosed a Token');
      assert.equal(rendered.includes('token_hash'), false);
      assert.equal(rendered.includes('registration_proof'), false);
      assert.equal(rendered.includes('/private/'), false);
    }
    await adminContext.close(); await writerContext.close(); await readerContext.close();
  } finally { await fixture.stop(); }
} finally { await browser.close(); }

console.log('UI-015 full permission and disclosure browser acceptance: OK');
