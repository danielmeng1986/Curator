/* UI-006 focused Import preview/execute browser acceptance. */
import assert from 'node:assert/strict';
import { access } from 'node:fs/promises';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const fixture = await startBrowserFixture({ scenario: 'filesystem', roles: ['writer'] });
const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage();
  await page.goto(fixture.origin);
  await page.getByRole('button', { name: 'Connect' }).click();
  await page.getByLabel('Approved device Token').fill(fixture.devices.writer.token);
  await page.getByRole('button', { name: 'Validate and connect' }).click();
  await page.getByRole('link', { name: /Import/ }).click();
  await page.getByRole('heading', { name: 'Import Albums' }).waitFor();

  const sourceAlbum = join(fixture.resources.source, 'Fixture Model in Fixture Album');
  await page.getByLabel('Import Action (applies to this batch)').selectOption('COPY');
  await page.getByLabel('Source Path (full path to folder)').fill(sourceAlbum);
  await page.getByRole('button', { name: '+ Add to Batch' }).click();
  await page.getByRole('button', { name: 'Preview →' }).click();

  await page.getByText('Preview Summary — COPY').waitFor();
  await page.getByText('Fixture Studio/Fixture Album').waitFor();
  await page.getByText('Preview does not change the database or filesystem.', { exact: false }).waitFor();
  assert.equal((await fixture.request('/albums', { role: 'writer' })).payload.data.length, 0);
  await access(join(sourceAlbum, 'cover.jpg'));

  await page.getByRole('button', { name: /Confirm selected/ }).click();
  await page.getByText('Copy source files to the archive and preserve the source folder.').waitFor();
  await page.getByRole('button', { name: /Execute reviewed COPY/ }).click();
  await page.getByText('Import Results').waitFor();
  await page.getByText('Succeeded', { exact: true }).waitFor();
  await page.getByRole('link', { name: 'View Operation' }).waitFor();

  await access(join(sourceAlbum, 'cover.jpg'));
  const albums = await fixture.request('/albums', { role: 'writer' });
  assert.equal(albums.payload.data.length, 1);
  assert.equal(albums.payload.data[0].title, 'Fixture Album');
  await access(join(fixture.resources.archive, albums.payload.data[0].path, 'cover.jpg'));

  await page.close();
  console.log('UI-006 Import browser acceptance: OK');
} finally {
  await browser.close();
  await fixture.stop();
}
