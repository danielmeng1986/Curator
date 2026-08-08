/* BT-039 authenticated Quarantine API and disposable filesystem contract. */
import assert from 'node:assert/strict';
import { access } from 'node:fs/promises';
import { join } from 'node:path';
import { startBrowserFixture } from './browser_fixture.mjs';

const fixture = await startBrowserFixture({ scenario: 'workflow-evidence', roles: ['admin', 'writer'] });
const relative = join('F', 'Fixture Model', 'Fixture Studio', 'Fixture Album');
const original = join(fixture.resources.archive, relative);
try {
  const denied = await fixture.request('/quarantine/preview', { method: 'POST', role: 'writer', body: {
    action: 'quarantine', repair_uuid: 'repair-ui-fixture', reason: 'isolate conflict',
  }});
  assert.equal(denied.status, 403);

  const reviewed = await fixture.request('/quarantine/preview', { method: 'POST', role: 'admin', body: {
    action: 'quarantine', repair_uuid: 'repair-ui-fixture', reason: 'isolate conflict',
  }});
  assert.equal(reviewed.status, 200); await access(join(original, 'conflict.jpg'));
  const token = reviewed.payload.data.preview.preview_token;
  const executed = await fixture.request('/quarantine/execute', { method: 'POST', role: 'admin', body: { preview_token: token } });
  assert.equal(executed.status, 200);
  const item = executed.payload.data.item;
  await access(join(fixture.resources.quarantine, item.quarantine_path, 'conflict.jpg'));
  const replay = await fixture.request('/quarantine/execute', { method: 'POST', role: 'admin', body: { preview_token: token } });
  assert.equal(replay.status, 409); assert.equal(replay.payload.error.code, 'QUARANTINE_PREVIEW_REPLAYED');

  const listing = await fixture.request('/quarantine-items', { role: 'admin' });
  assert.equal(listing.status, 200); assert.equal(listing.payload.data.items.length, 1);
  const restore = await fixture.request('/quarantine/preview', { method: 'POST', role: 'admin', body: { action: 'restore', item_uuid: item.uuid } });
  assert.equal(restore.status, 200);
  const restored = await fixture.request('/quarantine/execute', { method: 'POST', role: 'admin', body: {
    preview_token: restore.payload.data.preview.preview_token,
  }});
  assert.equal(restored.status, 200); await access(join(original, 'conflict.jpg'));
  assert.ok(restored.payload.data.item.restored_at);
  console.log('BT-039 Quarantine API contract: OK');
} finally { await fixture.stop(); }
