/* UI-012 complete permanent-entity browser acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdtemp, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { startBrowserFixture } from './browser_fixture.mjs';

const require=createRequire(import.meta.url);const {chromium}=require('playwright');
const artifactDir=await mkdtemp(join(tmpdir(),'curator-ui-012-'));
const fixture=await startBrowserFixture({scenario:'entities',roles:['writer','reader'],artifactDir});
const browser=await chromium.launch({headless:true});
let completed=false;
async function connect(page,token){await page.goto(fixture.origin);await page.getByRole('button',{name:'Connect'}).click();await page.getByLabel('Approved device Token').fill(token);await page.getByRole('button',{name:'Validate and connect'}).click();await page.getByText(/DB OK/).waitFor();}
async function api(path,options={}){return fixture.request(path,{role:options.role||'writer',method:options.method||'GET',body:options.body});}
async function byName(path,key,name){const result=await api(`${path}?q=${encodeURIComponent(name)}&limit=100`);return (result.payload.data||[]).find(item=>(item[key]||'')===name);}

try{
  const page=await browser.newPage();await connect(page,fixture.devices.writer.token);

  await page.getByRole('link',{name:/Studios/}).click();await page.getByRole('button',{name:'+ New Studio'}).click();
  await page.locator('#fName').fill('Browser Studio');await page.locator('#fScope').selectOption('p+v');await page.locator('#fWebsite').fill('https://studio.example.invalid');await page.locator('#fDescription').fill('Created through UI-012');await page.getByRole('button',{name:'Save'}).click();await page.getByText('Studio created').waitFor();
  let studio=await byName('/studios','name','Browser Studio');assert.ok(studio);await page.reload();await page.getByRole('heading',{name:'Browser Studio'}).waitFor();
  await page.locator('#fDescription').fill('Persisted Studio edit');await page.getByRole('button',{name:'Save'}).click();await page.getByText('Studio saved').waitFor();assert.equal((await api(`/studios/${studio.id}`)).payload.data.studio.description,'Persisted Studio edit');

  await page.getByRole('link',{name:/Models/}).click();await page.getByRole('button',{name:'+ New Model'}).click();
  await page.locator('#fDisplayName').fill('Browser Model');await page.locator('#fPrimaryName').fill('Browser Model');await page.locator('#fCountry').fill('DE');await page.getByRole('button',{name:'Save'}).click();await page.getByText('Model created').waitFor();
  let model=await byName('/models','primary_name','Browser Model');assert.ok(model);await page.reload();await page.getByRole('heading',{name:'Browser Model'}).waitFor();
  await page.locator('#fDescription').fill('Persisted Model edit');await page.getByRole('button',{name:'Save'}).click();await page.getByText('Model saved').waitFor();assert.equal((await api(`/models/${model.id}`)).payload.data.model.description,'Persisted Model edit');

  await page.getByRole('link',{name:/Statuses/}).click();await page.getByRole('button',{name:'+ New Status'}).click();await page.locator('#sName').fill('BROWSER_REVIEWED');await page.locator('#sDesc').fill('Browser-created status');await page.getByRole('button',{name:'Create'}).click();await page.getByText('Status created').waitFor();
  let statuses=(await api('/statuses')).payload.data.statuses;let status=statuses.find(item=>item.name==='BROWSER_REVIEWED');assert.ok(status);
  const statusRow=page.getByRole('row',{name:/BROWSER_REVIEWED/});await statusRow.getByRole('button',{name:'Edit'}).click();await page.locator('#sDesc').fill('Persisted Status edit');await page.getByRole('button',{name:'Save'}).click();await page.getByText('Status saved').waitFor();

  await page.getByRole('link',{name:/Albums/}).click();await page.getByRole('button',{name:'+ New Album'}).click();await page.locator('#fTitle').fill('Browser Related Release');
  await page.locator('#fStudio').selectOption(String(studio.id));await page.locator('#fStatus').selectOption(String(status.id));await page.locator('#fCaptureDate').fill('2026-07-12');await page.locator('#fPublishDate').fill('2026-08-01');await page.locator('#fRating').fill('5');
  await page.getByRole('button',{name:'+ Add Model'}).click();await page.locator('#mModelId').selectOption(String(model.id));await page.locator('#mRole').fill('primary');await page.getByRole('button',{name:'Add',exact:true}).click();
  const relationSection=page.locator('.form-section',{hasText:'Belongs to / Related Releases'});await relationSection.getByRole('button',{name:'+ Add Relation'}).click();await page.locator('#rAlbumId').selectOption('1');await page.getByRole('button',{name:'Cancel'}).click();assert.equal((await api('/albums/1')).payload.data.relations.length,0);
  await relationSection.getByRole('button',{name:'+ Add Relation'}).click();await page.locator('#rAlbumId').selectOption('1');await page.locator('#rRemarks').fill('Alternate release');await page.getByRole('button',{name:'Add',exact:true}).click();
  await page.getByRole('button',{name:'Save'}).click();await page.getByText('Album created').waitFor();let album=await byName('/albums','title','Browser Related Release');assert.ok(album);await page.reload();await page.getByRole('heading',{name:'Browser Related Release'}).waitFor();
  let detail=(await api(`/albums/${album.id}`)).payload.data;assert.equal(detail.models.length,1);assert.equal(detail.relations.length,1);assert.equal(detail.relations[0].relation_type,'BELONGS_TO');assert.equal(detail.album.rating,5);
  assert.equal(await page.getByRole('heading',{name:/Photos/}).count(),0);assert.equal(await page.getByRole('button',{name:'Delete Album'}).count(),0);assert.equal(await page.locator('#rAlbumId').count(),0);

  await page.locator('#modelsSection').getByRole('button',{name:'×'}).click();await page.locator('#relationsSection').getByRole('button',{name:'×'}).click();await page.getByRole('button',{name:'Save'}).click();await page.getByText('Album saved').waitFor();detail=(await api(`/albums/${album.id}`)).payload.data;assert.equal(detail.models.length,0);assert.equal(detail.relations.length,0);
  await page.reload();await page.getByRole('button',{name:'+ Add Model'}).click();await page.locator('#mModelId').selectOption(String(model.id));await page.getByRole('button',{name:'Add',exact:true}).click();await relationSection.getByRole('button',{name:'+ Add Relation'}).click();
  assert.equal(await page.locator(`#rAlbumId option[value="${album.id}"]`).count(),0,'self relationship must not be selectable');await page.locator('#rAlbumId').selectOption('1');await page.getByRole('button',{name:'Add',exact:true}).click();
  await page.getByRole('button',{name:'+ Add Model'}).click();await page.locator('#mModelId').selectOption(String(model.id));await page.getByRole('button',{name:'Add',exact:true}).click();await page.getByText('This Model is already linked').waitFor();await page.getByRole('button',{name:'Cancel'}).click();
  await relationSection.getByRole('button',{name:'+ Add Relation'}).click();await page.locator('#rAlbumId').selectOption('1');await page.getByRole('button',{name:'Add',exact:true}).click();await page.getByText('This Album relationship already exists').waitFor();await page.getByRole('button',{name:'Cancel'}).click();
  const relationshipSave=page.waitForResponse(response=>response.url().endsWith(`/api/v1/albums/${album.id}`)&&response.request().method()==='PUT');await page.getByRole('button',{name:'Save'}).click();assert.equal((await relationshipSave).status(),200);
  detail=(await api(`/albums/${album.id}`)).payload.data;assert.equal(detail.models.length,1);assert.equal(detail.relations.length,1);

  await page.goto(`${fixture.origin}/#/models/${model.id}`);await page.getByRole('button',{name:'Delete Model'}).click();await page.getByRole('button',{name:'Confirm'}).click();await page.getByText(/The action conflicts with current state/).waitFor();assert.ok(await byName('/models','primary_name','Browser Model'));
  await page.goto(`${fixture.origin}/#/studios/${studio.id}`);await page.getByRole('button',{name:'Delete Studio'}).click();await page.getByRole('button',{name:'Confirm'}).click();await page.getByText(/The action conflicts with current state/).waitFor();assert.ok(await byName('/studios','name','Browser Studio'));
  statuses=(await api('/statuses')).payload.data.statuses;status=statuses.find(item=>item.name==='BROWSER_REVIEWED');assert.equal(status.album_count,1);
  await page.goto(`${fixture.origin}/#/statuses`);const usedStatus=page.getByRole('row',{name:/BROWSER_REVIEWED/});assert.equal(await usedStatus.getByRole('button',{name:'Delete'}).isDisabled(),true);

  await page.goto(`${fixture.origin}/#/models/new`);await page.locator('#fDisplayName').fill('Retained Invalid Draft');await page.getByRole('button',{name:'Save'}).click();await page.getByText('Primary name is required').waitFor();assert.equal(await page.locator('#fDisplayName').inputValue(),'Retained Invalid Draft');
  for(let index=1;index<=51;index+=1){const created=await api('/studios',{method:'POST',body:{name:`Pagination Studio ${String(index).padStart(2,'0')}`,media_scope:'p'}});assert.equal(created.status,201);}
  await page.goto(`${fixture.origin}/#/studios`);await page.locator('.page-info').waitFor();assert.match(await page.locator('.page-info').textContent(),/53 total/);await page.getByRole('button',{name:'Next →'}).click();await page.getByText(/Page 2 \/ 2/).waitFor();

  const reader=await browser.newPage();await connect(reader,fixture.devices.reader.token);await reader.getByRole('link',{name:/Albums/}).click();await reader.getByRole('heading',{name:/Albums/}).waitFor();assert.equal(await reader.getByRole('button',{name:'+ New Album'}).isVisible(),false);
  const beforeDenied=(await api('/albums?limit=100')).payload.data.length;const denied=await api('/albums',{role:'reader',method:'POST',body:{title:'Reader Rejected Album'}});assert.equal(denied.status,403);assert.equal((await api('/albums?limit=100')).payload.data.length,beforeDenied);await reader.close();

  await page.close();completed=true;console.log('UI-012 permanent entity browser acceptance: OK');
}catch(error){await fixture.writeFailureArtifact('ui-012-failure.txt',`${error.stack||error}`);throw error;}
finally{await browser.close();await fixture.stop();if(completed)await rm(artifactDir,{recursive:true,force:true});}
