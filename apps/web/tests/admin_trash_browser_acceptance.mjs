/* UI-010E disposable Administrator restore and permanent purge acceptance. */
import assert from 'node:assert/strict';
import { access } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require=createRequire(import.meta.url); const { chromium }=require('playwright');

async function connect(page,fixture){
  await page.goto(fixture.origin); await page.getByRole('button',{name:'Connect'}).click();
  await page.getByLabel('Approved device Token').fill(fixture.devices.admin.token);
  await page.getByRole('button',{name:'Validate and connect'}).click();
}

async function trashAlbum(fixture){
  const preview=await fixture.request('/albums/1/trash/preview',{method:'POST',body:{},role:'writer'});
  const executed=await fixture.request('/albums/trash/execute',{method:'POST',body:{preview_token:preview.payload.data.preview.preview_token},role:'writer'});
  return executed.payload.data.result.trash_uuid;
}

const browser=await chromium.launch({headless:true});
try {
  const restoreFixture=await startBrowserFixture({scenario:'digital-asset-trash',roles:['writer','admin']});
  try {
    const trashUuid=await trashAlbum(restoreFixture); const admin=await browser.newPage(); await connect(admin,restoreFixture);
    await admin.goto(`${restoreFixture.origin}/#/admin/trash/${trashUuid}`);
    await admin.getByRole('heading',{name:'Fixture Album'}).waitFor();
    await admin.getByText('TRASHED',{exact:true}).first().waitFor();
    await admin.getByRole('button',{name:'Review restore'}).click();
    await admin.getByRole('heading',{name:'Restore Album assets?'}).waitFor();
    await admin.getByRole('button',{name:'Execute reviewed restore'}).click();
    await admin.getByText(/Album assets restored/).waitFor();
    await access(join(restoreFixture.resources.archive,'Fixture Studio','Fixture Album','cover.jpg'));
    const current=await restoreFixture.request('/admin/digital-asset-trash',{role:'admin'});
    assert.equal(current.payload.data.items.length,0);
    await admin.close();
  } finally { await restoreFixture.stop(); }

  const purgeFixture=await startBrowserFixture({scenario:'digital-asset-trash',roles:['writer','admin']});
  try {
    const trashUuid=await trashAlbum(purgeFixture);
    execFileSync('/usr/bin/sqlite3',[purgeFixture.resources.database,"UPDATE digital_asset_trash_item SET retention_until='2000-01-01T00:00:00+00:00';"]);
    const admin=await browser.newPage(); await connect(admin,purgeFixture);
    await admin.goto(`${purgeFixture.origin}/#/admin/trash/${trashUuid}`);
    await admin.getByRole('button',{name:'Review permanent purge'}).click();
    await admin.getByRole('heading',{name:'Permanently purge Album assets'}).waitFor();
    await admin.getByLabel(/Type/).fill('PURGE Fixture Album');
    await admin.getByRole('button',{name:'Execute reviewed action'}).click();
    await admin.getByText(/Digital assets permanently purged/).waitFor();
    await admin.getByText('DELETED',{exact:true}).waitFor();
    await assert.rejects(access(join(purgeFixture.resources.trash,'albums',trashUuid)));
    const history=await purgeFixture.request(`/admin/digital-asset-trash/${trashUuid}`,{role:'admin'});
    assert.equal(history.payload.data.item.assets_available,false);
    assert.ok(history.payload.data.item.purge_operation_uuid);
    assert.equal(history.payload.data.item.allowed_actions.includes('restore'),false);
    await admin.close();
  } finally { await purgeFixture.stop(); }
  console.log('UI-010E Administrator Trash restore/purge browser acceptance: OK');
} finally { await browser.close(); }
