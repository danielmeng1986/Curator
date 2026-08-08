import assert from 'node:assert/strict';
import { access, mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { SCENARIOS, startBrowserFixture } from './browser_fixture.mjs';

assert.equal(SCENARIOS['future-ai-workspace'].readiness, 'Blocked by Specification');
await assert.rejects(
  startBrowserFixture({ scenario: 'future-ai-workspace' }),
  /UI-011A\/B/,
);

const artifactDir = await mkdtemp(join(tmpdir(), 'curator-browser-artifact-test-'));
const roots = [];
try {
  for (let run = 0; run < 2; run += 1) {
    const fixture = await startBrowserFixture({
      scenario: 'entities',
      roles: ['reader', 'writer', 'admin'],
      artifactDir,
    });
    roots.push(fixture.root);
    try {
      const readerAlbums = await fixture.request('/albums', { role: 'reader' });
      assert.equal(readerAlbums.status, 200);
      assert.equal(readerAlbums.payload.data.length, 1);
      const denied = await fixture.request('/albums', {
        method: 'POST', body: { title: 'Rejected' }, role: 'reader',
      });
      assert.equal(denied.status, 403);
      assert.equal((await fixture.request('/albums', { role: 'writer' })).payload.data.length, 1);

      const artifact = await fixture.writeFailureArtifact(
        `redaction-${run}.txt`,
        `token=${fixture.devices.admin.token}`,
      );
      const artifactText = await readFile(artifact, 'utf8');
      assert.equal(artifactText.includes(fixture.devices.admin.token), false);
      assert.equal(artifactText, 'token=[REDACTED]');
    } finally {
      await fixture.stop();
    }
  }
  assert.notEqual(roots[0], roots[1], 'clean runs must use unique roots');

  const evidence = await startBrowserFixture({ scenario: 'workflow-evidence', roles: ['reader'] });
  try {
    const operations = await evidence.request('/operations', { role: 'reader' });
    assert.equal(operations.status, 200);
    assert.equal(operations.payload.data.items.some((item) => item.uuid === 'operation-ui-fixture'), true);
  } finally {
    await evidence.stop();
  }

  const filesystem = await startBrowserFixture({ scenario: 'filesystem', roles: ['writer'] });
  try {
    await access(join(filesystem.resources.source, 'Fixture Model in Fixture Album', 'cover.jpg'));
    for (const name of ['archive', 'snapshots', 'quarantine', 'backups', 'logs', 'outputs']) {
      await access(filesystem.resources[name]);
    }
  } finally {
    await filesystem.stop();
  }
  console.log('UI-003 browser fixture contract: OK');
} finally {
  await rm(artifactDir, { recursive: true, force: true });
}
