/* UI-014 full Issue, Repair, suppression, Quarantine, and item Restore acceptance. */
import assert from 'node:assert/strict';
import { access, mkdir, readdir, rename } from 'node:fs/promises';
import { constants } from 'node:fs';
import { dirname, join } from 'node:path';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const ISSUE_UUID = 'issue-ui-fixture';
const REPAIR_UUID = 'repair-ui-fixture';
const OPERATION_UUID = 'operation-ui-fixture';

async function exists(path) {
  try { await access(path, constants.F_OK); return true; } catch { return false; }
}

function collection(payload) {
  const data = payload.data;
  return Array.isArray(data) ? data : (data?.items || []);
}

async function connect(page, fixture, role) {
  await page.goto(fixture.origin);
  await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByLabel('Approved device Token').fill(fixture.devices[role].token);
  await page.getByRole('button', { name: 'Validate and connect' }).click();
  await page.getByText(/DB OK/).waitFor();
}

async function withCase(roles, run) {
  const fixture = await startBrowserFixture({ scenario: 'workflow-evidence', roles });
  const browser = await chromium.launch({ headless: true });
  try { await run({ fixture, browser }); }
  finally { await browser.close(); await fixture.stop(); }
}

async function confirmedDecision(page, name) {
  await page.getByRole('button', { name, exact: true }).click();
  await page.getByRole('button', { name: 'Apply', exact: true }).click();
}

async function promptedDecision(page, name, response) {
  const handled = page.waitForEvent('dialog').then(dialog => dialog.accept(response));
  await page.getByRole('button', { name, exact: true }).click();
  await handled;
}

await withCase(['admin', 'writer', 'reader'], async ({ fixture, browser }) => {
  const admin = await browser.newPage(); await connect(admin, fixture, 'admin');
  await admin.goto(`${fixture.origin}/#/operations/${OPERATION_UUID}`);
  await admin.getByRole('heading', { name: 'Operation Detail' }).waitFor();
  await admin.getByText('NeedsRepair', { exact: true }).waitFor();
  await admin.getByRole('link', { name: ISSUE_UUID }).click();
  await admin.getByRole('heading', { name: 'Issue Detail' }).waitFor();
  await admin.getByRole('link', { name: OPERATION_UUID }).waitFor();
  await admin.goto(`${fixture.origin}/#/operations/${OPERATION_UUID}`);
  await admin.getByRole('link', { name: REPAIR_UUID }).click();
  await admin.getByRole('heading', { name: 'Repair Detail' }).waitFor();
  await admin.getByRole('link', { name: OPERATION_UUID }).waitFor();

  await admin.goto(`${fixture.origin}/#/issues/${ISSUE_UUID}`);
  const originalIssue = (await fixture.request(`/issues/${ISSUE_UUID}`, { role: 'admin' })).payload.data.issue;
  await promptedDecision(admin, 'assign', 'Curator Admin');
  await admin.getByText(/Owner:\s*Curator Admin/).waitFor();
  const staleCode = await admin.evaluate(async ({ uuid, updatedAt }) => {
    try {
      await api.post(`/issues/${uuid}/decisions`, {
        action: 'begin_work', expected_updated_at: updatedAt,
      });
      return null;
    } catch (error) { return error.code; }
  }, { uuid: ISSUE_UUID, updatedAt: originalIssue.updated_at });
  assert.equal(staleCode, 'WORKFLOW_STALE');
  await confirmedDecision(admin, 'begin work');
  await admin.getByText('InProgress', { exact: true }).waitFor();
  await promptedDecision(admin, 'resolve', 'Affected path and Operation evidence verified.');
  await admin.getByText('Resolved', { exact: true }).waitFor();
  const issue = (await fixture.request(`/issues/${ISSUE_UUID}`, { role: 'admin' })).payload.data.issue;
  assert.equal(issue.owner, 'Curator Admin');
  assert.equal(issue.state, 'Resolved');

  const writer = await browser.newPage(); await connect(writer, fixture, 'writer');
  const denied = await fixture.request(`/issues/${ISSUE_UUID}/decisions`, {
    method: 'POST', role: 'writer', body: {
      action: 'archive', expected_updated_at: issue.updated_at,
    },
  });
  assert.equal(denied.status, 409);
  assert.equal(denied.payload.error.code, 'INVALID_TRANSITION');
  assert.equal((await fixture.request(`/issues/${ISSUE_UUID}`, { role: 'admin' })).payload.data.issue.state, 'Resolved');

  const reader = await browser.newPage(); await connect(reader, fixture, 'reader');
  await reader.goto(`${fixture.origin}/#/issues/${ISSUE_UUID}`);
  await reader.getByRole('heading', { name: 'Issue Detail' }).waitFor();
  assert.equal(await reader.locator('text=Allowed decisions').locator('..').getByRole('button').count(), 0);
  await reader.goto(`${fixture.origin}/#/repairs/${REPAIR_UUID}`);
  await reader.getByText('Operational path evidence is hidden for this role.').waitFor();
  assert.equal(await reader.getByRole('button', { name: /confirm|ignore|start|escalate/ }).count(), 0);
  await reader.close(); await writer.close(); await admin.close();
});

await withCase(['writer'], async ({ fixture, browser }) => {
  const page = await browser.newPage(); await connect(page, fixture, 'writer');
  await page.goto(`${fixture.origin}/#/repairs/${REPAIR_UUID}`);
  await page.getByRole('heading', { name: 'Repair Detail' }).waitFor();
  await confirmedDecision(page, 'escalate');
  await page.getByText('ManualConflict', { exact: true }).waitFor();
  const current = (await fixture.request(`/repairs/${REPAIR_UUID}`, { role: 'writer' })).payload.data.repair;
  const operationsBefore = collection((await fixture.request('/operations', { role: 'writer' })).payload).length;
  const bypassCode = await page.evaluate(async ({ uuid, updatedAt }) => {
    try {
      await api.post(`/repairs/${uuid}/decisions`, { action: 'start', expected_updated_at: updatedAt });
      return null;
    } catch (error) { return error.code; }
  }, { uuid: REPAIR_UUID, updatedAt: current.updated_at });
  assert.equal(bypassCode, 'INVALID_TRANSITION');
  assert.equal((await fixture.request(`/repairs/${REPAIR_UUID}`, { role: 'writer' })).payload.data.repair.state, 'ManualConflict');
  assert.equal(collection((await fixture.request('/operations', { role: 'writer' })).payload).length, operationsBefore);

  await promptedDecision(page, 'confirm', 'Manually reviewed source, destination, and conflict.');
  await confirmedDecision(page, 'start');
  await page.getByText('Repairing', { exact: true }).waitFor();
  await confirmedDecision(page, 'complete action');
  await page.getByText('PendingVerification', { exact: true }).waitFor();
  await promptedDecision(page, 'verify failed', 'Canonical destination still differs.');
  await page.getByText('NeedsRepair', { exact: true }).waitFor();
  await confirmedDecision(page, 'start');
  await confirmedDecision(page, 'complete action');
  await promptedDecision(page, 'verify passed', 'Canonical path and intact files verified.');
  await page.getByText('Resolved', { exact: true }).waitFor();
  const repair = (await fixture.request(`/repairs/${REPAIR_UUID}`, { role: 'writer' })).payload.data.repair;
  assert.equal(repair.state, 'Resolved');
  assert.equal(repair.verification_result, 'Canonical path and intact files verified.');
  await page.close();
});

await withCase(['writer'], async ({ fixture, browser }) => {
  const page = await browser.newPage(); await connect(page, fixture, 'writer');
  await page.goto(`${fixture.origin}/#/repairs/${REPAIR_UUID}`);
  await page.getByRole('heading', { name: 'Repair Detail' }).waitFor();
  await confirmedDecision(page, 'ignore');
  await page.getByText('Ignored', { exact: true }).waitFor();
  const repair = (await fixture.request(`/repairs/${REPAIR_UUID}`, { role: 'writer' })).payload.data.repair;
  assert.equal(repair.state, 'Ignored');
  assert.deepEqual(repair.allowed_actions, []);
  await page.close();
});

await withCase(['admin', 'writer'], async ({ fixture, browser }) => {
  const writerRepair = (await fixture.request(`/repairs/${REPAIR_UUID}`, { role: 'writer' })).payload.data.repair;
  const denied = await fixture.request('/repair-suppressions', {
    method: 'POST', role: 'writer', body: {
      fingerprint: 'writer-cannot-suppress', scope_path: writerRepair.expected_path,
      reason: 'Not authorized', expires_at: new Date(Date.now() + 86400000).toISOString(),
    },
  });
  assert.equal(denied.status, 403);
  const admin = await browser.newPage(); await connect(admin, fixture, 'admin');
  await admin.goto(`${fixture.origin}/#/repairs/${REPAIR_UUID}`);
  let promptIndex = 0;
  admin.on('dialog', async dialog => {
    const answers = ['Reviewed exception during migration.', '2'];
    await dialog.accept(answers[promptIndex++]);
  });
  await admin.getByRole('button', { name: 'Create bounded suppression' }).click();
  await admin.getByText('Bounded suppression created').waitFor();
  const suppressions = collection((await fixture.request('/repair-suppressions', { role: 'admin' })).payload);
  assert.equal(suppressions.length, 1);
  assert.equal(suppressions[0].scope_path, writerRepair.expected_path);
  const suppressionOperations = collection((await fixture.request('/operations?operation_type=repair_suppression_create', { role: 'admin' })).payload);
  assert.equal(suppressionOperations.length, 1);
  assert.equal(suppressionOperations[0].status, 'Succeeded');
  await admin.close();
});

await withCase(['admin', 'writer'], async ({ fixture, browser }) => {
  const original = join(fixture.resources.archive, 'F', 'Fixture Model', 'Fixture Studio', 'Fixture Album');
  const quarantinedFile = item => join(fixture.resources.quarantine, item.quarantine_path, 'conflict.jpg');
  const writer = await browser.newPage(); await connect(writer, fixture, 'writer');
  assert.equal(await writer.getByRole('link', { name: /Repair Quarantine/ }).count(), 0);
  const directDenied = await fixture.request('/quarantine/preview', {
    method: 'POST', role: 'writer', body: { action: 'quarantine', repair_uuid: REPAIR_UUID, reason: 'Denied' },
  });
  assert.equal(directDenied.status, 403);
  await writer.close();

  const admin = await browser.newPage(); await connect(admin, fixture, 'admin');
  await admin.goto(`${fixture.origin}/#/repairs/${REPAIR_UUID}`);
  const operationsBefore = collection((await fixture.request('/operations', { role: 'admin' })).payload).length;
  let dialog = admin.waitForEvent('dialog').then(item => item.accept('Cancel preserves the source.'));
  await admin.getByRole('button', { name: 'Review Quarantine move' }).click(); await dialog;
  await admin.getByRole('heading', { name: 'Confirm quarantine preview' }).waitFor();
  await admin.getByRole('button', { name: 'Cancel' }).click();
  assert.equal(await exists(join(original, 'conflict.jpg')), true);
  assert.equal(collection((await fixture.request('/quarantine-items', { role: 'admin' })).payload).length, 0);
  assert.equal(collection((await fixture.request('/operations', { role: 'admin' })).payload).length, operationsBefore);

  dialog = admin.waitForEvent('dialog').then(item => item.accept('Isolate intact conflict for review.'));
  await admin.getByRole('button', { name: 'Review Quarantine move' }).click(); await dialog;
  await admin.getByRole('heading', { name: 'Confirm quarantine preview' }).waitFor();
  const quarantineToken = await admin.evaluate(() => QuarantinePage._previewToken);
  await admin.getByRole('button', { name: 'Execute reviewed quarantine' }).click();
  await admin.getByRole('heading', { name: 'Quarantine Item' }).waitFor();
  const item = collection((await fixture.request('/quarantine-items', { role: 'admin' })).payload)[0];
  assert.equal(await exists(original), false);
  assert.equal(await exists(quarantinedFile(item)), true);
  assert.match(item.inventory, /conflict\.jpg/);
  const quarantineReplay = await admin.evaluate(async token => {
    try { await api.post('/quarantine/execute', { preview_token: token }); return null; }
    catch (error) { return error.code; }
  }, quarantineToken);
  assert.equal(quarantineReplay, 'QUARANTINE_PREVIEW_REPLAYED');
  await admin.getByRole('link', { name: item.operation_uuid }).click();
  await admin.getByRole('heading', { name: 'Operation Detail' }).waitFor();
  await admin.getByText('Succeeded', { exact: true }).waitFor();
  await admin.goto(`${fixture.origin}/#/quarantine/${item.uuid}`);

  const backupsBefore = (await readdir(fixture.resources.backups)).length;
  await admin.getByRole('button', { name: 'Review restore to original path' }).click();
  await admin.getByRole('heading', { name: 'Confirm restore preview' }).waitFor();
  await mkdir(original, { recursive: true });
  await admin.getByRole('button', { name: 'Execute reviewed restore' }).click();
  await admin.getByText(/restore destination changed after preview/i).waitFor();
  assert.equal(await exists(quarantinedFile(item)), true);
  assert.equal((await fixture.request(`/quarantine-items/${item.uuid}`, { role: 'admin' })).payload.data.item.restored_at, null);
  assert.equal((await readdir(fixture.resources.backups)).length, backupsBefore);

  const collisionHolding = join(dirname(original), 'Fixture Album collision holding');
  await rename(original, collisionHolding);
  await admin.getByRole('button', { name: 'Cancel' }).click();
  await admin.getByRole('button', { name: 'Review restore to original path' }).click();
  await admin.getByRole('heading', { name: 'Confirm restore preview' }).waitFor();
  const restoreToken = await admin.evaluate(() => QuarantinePage._previewToken);
  await admin.getByRole('button', { name: 'Execute reviewed restore' }).click();
  await admin.getByText('Restored', { exact: true }).waitFor();
  assert.equal(await exists(join(original, 'conflict.jpg')), true);
  assert.equal(await exists(quarantinedFile(item)), false);
  assert.ok((await readdir(fixture.resources.backups)).length > backupsBefore);
  const restored = (await fixture.request(`/quarantine-items/${item.uuid}`, { role: 'admin' })).payload.data.item;
  assert.ok(restored.restored_at);
  assert.ok(restored.restore_operation_uuid);
  const restoreReplay = await admin.evaluate(async token => {
    try { await api.post('/quarantine/execute', { preview_token: token }); return null; }
    catch (error) { return error.code; }
  }, restoreToken);
  assert.equal(restoreReplay, 'QUARANTINE_PREVIEW_REPLAYED');
  await admin.getByRole('link', { name: restored.restore_operation_uuid }).click();
  await admin.getByRole('heading', { name: 'Operation Detail' }).waitFor();
  await admin.getByText('Succeeded', { exact: true }).waitFor();
  await admin.close();
});

console.log('UI-014 full Repair and Quarantine browser acceptance: OK');
