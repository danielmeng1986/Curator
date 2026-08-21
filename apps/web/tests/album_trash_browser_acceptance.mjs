/* UI-037 disposable Album move-to-Trash browser and filesystem acceptance. */
import assert from 'node:assert/strict';
import { access, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require=createRequire(import.meta.url);
const { chromium }=require('playwright');
const fixture=await startBrowserFixture({scenario:'digital-asset-trash',roles:['writer','reader','admin']});
const browser=await chromium.launch({headless:true});

async function connect(page,token){
  await page.goto(fixture.origin);
  await page.getByRole('button',{name:'Connect'}).click();
  await page.getByLabel('Approved device Token').fill(token);
  await page.getByRole('button',{name:'Validate and connect'}).click();
}

try {
  const reader=await browser.newPage();
  await connect(reader,fixture.devices.reader.token);
  await reader.goto(`${fixture.origin}/#/albums/1`);
  await reader.getByRole('heading',{name:'Fixture Album'}).waitFor();
  await reader.getByText(/Read-only access/).waitFor();
  assert.equal(await reader.getByRole('button',{name:'Move to Trash'}).count(),0);
  const denied=await fixture.request('/albums/1/trash/preview',{method:'POST',body:{},role:'reader'});
  assert.equal(denied.status,403);
  await reader.close();

  const writer=await browser.newPage();
  await connect(writer,fixture.devices.writer.token);
  await writer.goto(`${fixture.origin}/#/albums/2`);
  await writer.getByRole('heading',{name:'Blocked Album'}).waitFor();
  await writer.getByText(/active AI Work reservation/).waitFor();
  const blockedButton=writer.getByRole('button',{name:'Move to Trash'});
  assert.equal(await blockedButton.isDisabled(),true);
  assert.equal((await fixture.request('/albums/2/trash-readiness',{role:'writer'})).payload.data.readiness.can_trash,false);
  await access(join(fixture.resources.archive,'Fixture Studio','Blocked Album','blocked.jpg'));

  await writer.goto(`${fixture.origin}/#/albums/1`);
  await writer.getByRole('heading',{name:'Fixture Album'}).waitFor();
  await writer.getByRole('button',{name:'Move to Trash'}).click();
  await writer.getByRole('heading',{name:'Move Album to Digital Asset Trash?'}).waitFor();
  await writer.getByRole('button',{name:'Cancel'}).click();
  await writer.getByRole('heading',{name:'Move Album to Digital Asset Trash?'}).waitFor({state:'detached'});
  await access(join(fixture.resources.archive,'Fixture Studio','Fixture Album','cover.jpg'));

  const stalePreview=await fixture.request('/albums/1/trash/preview',{method:'POST',body:{},role:'writer'});
  const coverPath=join(fixture.resources.archive,'Fixture Studio','Fixture Album','cover.jpg');
  await writeFile(coverPath,Buffer.from('changed-after-preview'));
  const staleExecute=await fixture.request('/albums/trash/execute',{method:'POST',body:{preview_token:stalePreview.payload.data.preview.preview_token},role:'writer'});
  assert.equal(staleExecute.status,409);
  assert.equal(staleExecute.payload.error.code,'ASSET_SCOPE_CHANGED');
  await writeFile(coverPath,Buffer.from('cover'));

  await writer.getByRole('button',{name:'Move to Trash'}).click();
  await writer.getByRole('heading',{name:'Move Album to Digital Asset Trash?'}).waitFor();
  await writer.getByText('3',{exact:true}).first().waitFor();
  await writer.getByText(/This is not database deletion/).waitFor();
  assert.equal(await writer.getByRole('button',{name:'Move reviewed Album to Trash'}).isDisabled(),true);
  await writer.getByLabel(/I understand that the saved Album/).check();
  await writer.getByRole('button',{name:'Move reviewed Album to Trash'}).click();
  await writer.getByRole('heading',{name:/Albums/}).waitFor();
  await writer.getByText(/Album moved to Trash\. Operation/).waitFor();
  assert.equal(await writer.getByText('Fixture Album',{exact:true}).count(),0);

  const albums=await fixture.request('/albums?limit=100',{role:'writer'});
  assert.equal(albums.payload.data.some(item=>item.title==='Fixture Album'),false);
  const hidden=await fixture.request('/albums/1',{role:'writer'});
  assert.equal(hidden.status,404);
  await assert.rejects(access(join(fixture.resources.archive,'Fixture Studio','Fixture Album')));
  const trash=await fixture.request('/admin/digital-asset-trash',{role:'admin'});
  assert.equal(trash.status,200);
  const item=trash.payload.data.items.find(candidate=>candidate.album_id===1);
  assert.ok(item,'Admin Trash must contain the moved Album');
  await access(join(fixture.resources.trash,item.trash_relative_path,'cover.jpg'));
  await access(join(fixture.resources.trash,item.trash_relative_path,'photo-2.jpg'));
  await access(join(fixture.resources.trash,item.trash_relative_path,'photo-3.jpg'));
  await writer.close();
  console.log('UI-037 Album Trash browser acceptance: OK');
} finally {
  await browser.close();
  await fixture.stop();
}
