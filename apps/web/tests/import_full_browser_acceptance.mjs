/* UI-013 full Import workflow and filesystem browser acceptance. */
import assert from 'node:assert/strict';
import { access, mkdir, readdir, writeFile } from 'node:fs/promises';
import { constants } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

async function exists(path) {
  try { await access(path, constants.F_OK); return true; } catch { return false; }
}

function collection(payload) {
  const data = payload.data;
  return Array.isArray(data) ? data : (data?.items || []);
}

async function sourceFolder(fixture, name, filename = 'cover.jpg') {
  const path = join(fixture.resources.source, name);
  await mkdir(path, { recursive: true });
  await writeFile(join(path, filename), `fixture:${name}`, 'utf8');
  return path;
}

async function connect(page, fixture) {
  await page.goto(fixture.origin);
  await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByLabel('Approved device Token').fill(fixture.devices.writer.token);
  await page.getByRole('button', { name: 'Validate and connect' }).click();
  await page.getByRole('link', { name: /Import/ }).click();
  await page.getByRole('heading', { name: 'Import Albums' }).waitFor();
}

async function compose(page, action, paths) {
  await page.getByLabel('Import Action (applies to this batch)').selectOption(action);
  for (const path of paths) {
    await page.getByLabel('Source Path (full path to folder)').fill(path);
    await page.getByRole('button', { name: '+ Add to Batch' }).click();
  }
  await page.getByRole('button', { name: 'Preview →' }).click();
  await page.getByText(`Preview Summary — ${action}`).waitFor();
}

async function confirmAndExecute(page, action) {
  await page.getByRole('button', { name: /Confirm selected/ }).click();
  await page.getByRole('button', { name: new RegExp(`Execute reviewed ${action}`) }).click();
  await page.getByText('Import Results').waitFor();
}

async function withCase(run) {
  const fixture = await startBrowserFixture({ scenario: 'filesystem', roles: ['writer'] });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  try {
    await connect(page, fixture);
    await run({ fixture, page });
  } finally {
    await page.close();
    await browser.close();
    await fixture.stop();
  }
}

await withCase(async ({ fixture, page }) => {
  const source = join(fixture.resources.source, 'Fixture Model in Fixture Album');
  const albumsBefore = collection((await fixture.request('/albums')).payload).length;
  const operationsBefore = collection((await fixture.request('/operations')).payload).length;
  const backupsBefore = (await readdir(fixture.resources.backups)).length;
  await compose(page, 'COPY', [source]);
  assert.equal(collection((await fixture.request('/albums')).payload).length, albumsBefore);
  assert.equal(collection((await fixture.request('/operations')).payload).length, operationsBefore);
  assert.equal((await readdir(fixture.resources.backups)).length, backupsBefore);
  assert.equal(await exists(join(source, 'cover.jpg')), true);
  await confirmAndExecute(page, 'COPY');
  await page.getByText('Succeeded', { exact: true }).waitFor();
  const album = collection((await fixture.request('/albums')).payload)[0];
  const albumDetail = (await fixture.request(`/albums/${album.id}`)).payload.data;
  const albumModels = albumDetail.models;
  assert.equal(albumModels.length, 1);
  assert.equal(albumModels[0].model_name, 'Fixture Model');
  assert.equal(await exists(join(source, 'cover.jpg')), true);
  assert.equal(await exists(join(fixture.resources.archive, album.path, 'cover.jpg')), true);
  assert.equal(collection((await fixture.request('/operations')).payload).length, operationsBefore + 1);
  assert.ok((await readdir(fixture.resources.backups)).length > backupsBefore);
  await page.getByRole('link', { name: 'View Operation' }).click();
  await page.getByRole('heading', { name: 'Operation Detail' }).waitFor();
  await page.getByText('Succeeded', { exact: true }).waitFor();
});

await withCase(async ({ fixture, page }) => {
  const source = await sourceFolder(fixture, 'Move Model in Move Album');
  await compose(page, 'MOVE', [source]);
  await confirmAndExecute(page, 'MOVE');
  const album = collection((await fixture.request('/albums')).payload)[0];
  assert.equal(await exists(source), false);
  assert.equal(await exists(join(fixture.resources.archive, album.path, 'cover.jpg')), true);
  await page.getByText('MOVE', { exact: true }).waitFor();
});

await withCase(async ({ fixture, page }) => {
  const source = await sourceFolder(fixture, 'Database Model in Database Album');
  await compose(page, 'DATABASE_ONLY', [source]);
  await confirmAndExecute(page, 'DATABASE_ONLY');
  const album = collection((await fixture.request('/albums')).payload)[0];
  assert.equal(await exists(join(source, 'cover.jpg')), true);
  assert.equal(await exists(join(fixture.resources.archive, album.path)), false);
  await page.getByText('DATABASE_ONLY', { exact: true }).waitFor();
});

await withCase(async ({ fixture, page }) => {
  const source = await sourceFolder(fixture, 'Duplicate Model in Duplicate Album');
  await compose(page, 'COPY', [source, source]);
  assert.equal(await page.getByText(/Multiple items in this import batch/).count(), 2);
  assert.equal(await page.getByRole('button', { name: /Confirm selected/ }).count(), 0);
  assert.equal(collection((await fixture.request('/albums')).payload).length, 0);
});

await withCase(async ({ fixture, page }) => {
  const source = await sourceFolder(fixture, 'Collision Model in Collision Album');
  const item = {
    source_path: source,
    folder_name: 'Collision Model in Collision Album',
    studio_name: 'Fixture Studio',
    model_name: null,
    album_name: null,
  };
  const probe = await fixture.request('/import/preview', {
    method: 'POST', body: { items: [item], import_action: 'COPY' },
  });
  assert.equal(probe.status, 200);
  const expectedPath = probe.payload.data.preview.items[0].expected_path;
  await mkdir(join(fixture.resources.archive, expectedPath), { recursive: true });
  const operationsBefore = collection((await fixture.request('/operations')).payload).length;
  await compose(page, 'COPY', [source]);
  await page.getByText(/target filesystem path already exists/i).waitFor();
  assert.equal(await page.getByRole('button', { name: /Confirm selected/ }).count(), 0);
  assert.equal(collection((await fixture.request('/albums')).payload).length, 0);
  assert.equal(collection((await fixture.request('/operations')).payload).length, operationsBefore);
});

await withCase(async ({ fixture, page }) => {
  const source = await sourceFolder(fixture, 'Cancel Model in Cancel Album');
  const operationsBefore = collection((await fixture.request('/operations')).payload).length;
  await compose(page, 'COPY', [source]);
  await page.getByRole('button', { name: '← Back' }).click();
  await page.getByText('Import settings').waitFor();
  assert.equal(collection((await fixture.request('/albums')).payload).length, 0);
  assert.equal(collection((await fixture.request('/operations')).payload).length, operationsBefore);
  assert.equal(await exists(join(source, 'cover.jpg')), true);
});

await withCase(async ({ fixture, page }) => {
  const source = await sourceFolder(fixture, 'Stale Model in Stale Album');
  const operationsBefore = collection((await fixture.request('/operations')).payload).length;
  await compose(page, 'COPY', [source]);
  await page.getByRole('button', { name: /Confirm selected/ }).click();
  await writeFile(join(source, 'changed.jpg'), 'changed after preview', 'utf8');
  await page.getByRole('button', { name: /Execute reviewed COPY/ }).click();
  await page.getByText(/source changed after preview/i).waitFor();
  assert.equal(collection((await fixture.request('/albums')).payload).length, 0);
  assert.equal(collection((await fixture.request('/operations')).payload).length, operationsBefore);
  assert.equal(await exists(join(source, 'changed.jpg')), true);
});

await withCase(async ({ fixture, page }) => {
  const source = await sourceFolder(fixture, 'Replay Model in Replay Album');
  await compose(page, 'DATABASE_ONLY', [source]);
  await page.getByRole('button', { name: /Confirm selected/ }).click();
  const outcomes = await page.evaluate(async () => {
    const token = ImportPage._previewToken;
    return Promise.allSettled([
      api.post('/import/execute', { preview_token: token }),
      api.post('/import/execute', { preview_token: token }),
    ]).then(results => results.map(result => ({
      status: result.status,
      code: result.status === 'rejected' ? result.reason.code : null,
    })));
  });
  assert.deepEqual(outcomes.map(item => item.status).sort(), ['fulfilled', 'rejected']);
  assert.equal(outcomes.find(item => item.status === 'rejected').code, 'CLIENT_ACTION_IN_PROGRESS');
  const replayCode = await page.evaluate(async () => {
    try {
      await api.post('/import/execute', { preview_token: ImportPage._previewToken });
      return null;
    } catch (error) {
      return error.code;
    }
  });
  assert.equal(replayCode, 'IMPORT_PREVIEW_REPLAYED');
  assert.equal(collection((await fixture.request('/albums')).payload).length, 1);
  const imports = collection((await fixture.request('/operations?operation_type=import')).payload);
  assert.equal(imports.length, 1);
});

await withCase(async ({ fixture, page }) => {
  const good = await sourceFolder(fixture, 'Good Model in Good Album');
  const failing = await sourceFolder(fixture, 'Fail After Preview Model in Repair Album');
  await compose(page, 'COPY', [good, failing]);
  await confirmAndExecute(page, 'COPY');
  await page.getByText('Succeeded', { exact: true }).waitFor();
  await page.getByText('NeedsRepair', { exact: true }).waitFor();
  await page.getByText(/filesystem work needs repair/i).waitFor();
  const albums = collection((await fixture.request('/albums')).payload);
  assert.equal(albums.length, 2);
  const goodAlbum = albums.find(album => album.title === 'Good Album');
  const repairAlbum = albums.find(album => album.title === 'Repair Album');
  assert.equal(await exists(join(fixture.resources.archive, goodAlbum.path, 'cover.jpg')), true);
  assert.equal(await exists(join(fixture.resources.archive, repairAlbum.path, 'cover.jpg')), false);
  assert.equal(await exists(join(failing, 'cover.jpg')), true);
  const imports = collection((await fixture.request('/operations?status=NeedsRepair')).payload);
  assert.equal(imports.length, 1);
  assert.equal(imports[0].status, 'NeedsRepair');
});

console.log('UI-013 full Import browser acceptance: OK');
