/* UI-011D AI Workspace review and Promotion browser acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require=createRequire(import.meta.url); const {chromium}=require('playwright');
const fixture=await startBrowserFixture({scenario:'future-ai-workspace',roles:['admin','writer']});
const browser=await chromium.launch({headless:true});
const admin=options=>fixture.request(options.path,{method:options.method||'GET',body:options.body,role:'admin'});

async function connect(page){await page.goto(fixture.origin);await page.getByRole('button',{name:'Connect'}).click();await page.getByLabel('Approved device Token').fill(fixture.devices.admin.token);await page.getByRole('button',{name:'Validate and connect'}).click();await page.getByText(/DB OK/).waitFor();}
async function configuration(){const response=await admin({path:'/ai-model-configurations',method:'POST',body:{name:'Review Fixture Configuration',model_identifier:'review-fixture',model_file:'review.gguf',vision_prompt_version:'v1',writer_prompt_version:'w1',sample_count:8,context_size:4096,threads:8,gpu_layers:20,max_tokens:800,temperature:0.2,image_max_tokens:384}});assert.equal(response.status,201);return response.payload.data.configuration;}
async function submitResult(itemUuid,index){
  const manifest=await admin({path:`/ai-work-items/${itemUuid}/evidence-manifest`,method:'POST',body:{}});assert.equal(manifest.status,201);assert.equal(manifest.payload.data.manifest.evidence.length,8);
  const claim=await fixture.request('/ai-work-items/claim',{method:'POST',role:'writer',body:{worker_kinds:['album_name_analysis'],lease_seconds:300}});assert.equal(claim.payload.data.item.uuid,itemUuid);
  const vision=await fixture.request(`/ai-work-items/${itemUuid}/results/vision`,{method:'POST',role:'writer',body:{schema_version:'curator://album-analysis/vision/v1',payload:{scene:`Curated outdoor scene ${index}`,people:{minimum:2,maximum:4},location_environment:'Forest lakeside',subjects:['friends'],objects:['trees'],actions:['walking'],confidence:0.91,warnings:[]}}});assert.equal(vision.status,200);
  const names=['Golden Forest Morning','Quiet Lakeside Walk','Summer Friends Journey','Gentle Woodland Light','Memories Beside Water','Together Through Nature'];
  const writer=await fixture.request(`/ai-work-items/${itemUuid}/results/writer`,{method:'POST',role:'writer',body:{schema_version:'curator://album-analysis/writer/v1',payload:{album_summary:`Friends explore a forest lakeside ${index}.`,description:'A calm outdoor journey with friends among trees and water.',suggested_names:names}}});assert.equal(writer.status,200);return names;
}
async function openReview(page,itemUuid){await page.goto(`${fixture.origin}/#/ai-work-items/${itemUuid}/review`);await page.locator('h1.page-title').waitFor();}
async function releaseGroup(page,groupUuid){await page.goto(`${fixture.origin}/#/work-dispatch/groups/${groupUuid}`);await page.getByRole('heading',{name:'Dispatch Group'}).waitFor();page.once('dialog',dialog=>dialog.accept('All review obligations are terminal'));await page.getByRole('button',{name:'release',exact:true}).click();await page.getByText('Released').waitFor();}

try{
  const config=await configuration();const workspaceResponse=await admin({path:'/ai-workspaces',method:'POST',body:{title:'Browser Review Workspace'}});const workspace=workspaceResponse.payload.data.workspace;
  const preview=await admin({path:'/work-dispatch/preview',method:'POST',body:{worker_kind:'album_name_analysis',workspace_uuid:workspace.uuid,configuration_uuids:[config.uuid],album_ids:[1,2,3]}});
  const executed=await admin({path:'/work-dispatch/execute',method:'POST',body:{preview_token:preview.payload.data.preview.preview_token}});const groups=executed.payload.data.result.groups;
  const items=groups.map(group=>group.work_item_uuids[0]);const recommendations=[];for(let index=0;index<items.length;index+=1)recommendations.push(await submitResult(items[index],index+1));

  const page=await browser.newPage();await connect(page);await page.getByRole('link',{name:/AI Review/}).click();await page.getByRole('heading',{name:'AI Review Queue'}).waitFor();assert.equal(await page.getByRole('link',{name:'Review details'}).count(),3);

  await openReview(page,items[0]);await page.getByText('AI analysis · immutable').waitFor();await page.getByText('Human review · editable draft').waitFor();await page.getByText('System evidence and provenance').waitFor();assert.equal(await page.locator('.evidence-card').count(),8);
  await page.getByRole('button',{name:'Begin review'}).click();await page.getByRole('button',{name:'Approve selection'}).waitFor();
  await page.getByLabel('Final Album name').fill('invalid name');await page.getByLabel('Selection source').selectOption('HumanRevision');await page.getByRole('button',{name:'Approve selection'}).click();await page.getByText(/Check the highlighted information/).waitFor();assert.equal(await page.getByLabel('Final Album name').inputValue(),'invalid name');
  await page.getByLabel('Final Album name').fill('Golden Forest Morning');await page.getByRole('button',{name:'Approve selection'}).click();await page.getByText('Approved',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Review Promotion'}).click();await page.getByRole('heading',{name:'Confirm Album Name Promotion'}).waitFor();await page.getByLabel('I confirm this Album name and Status change.').check();await page.getByRole('button',{name:'Confirm & Rename'}).click();await page.getByText('Album name Promotion completed.').waitFor();
  await page.getByRole('button',{name:'Next review'}).click();await page.waitForFunction(()=>document.querySelector('h1.page-title')?.textContent!=='Golden Forest Morning');assert.notEqual(await page.locator('h1.page-title').textContent(),'Golden Forest Morning');
  const promotedAlbum=await admin({path:'/albums/1'});assert.equal(promotedAlbum.payload.data.album.title,'Golden Forest Morning');assert.equal(promotedAlbum.payload.data.album.status_name,'NAME_GENERATED');
  const promotionHistory=await admin({path:`/ai-work-items/${items[0]}/promotion`});assert.equal(promotionHistory.payload.data.promotion_history.items.length,1);

  await openReview(page,items[1]);await page.getByRole('button',{name:'Begin review'}).click();await page.getByLabel('Administrator evaluation').fill('Retain this local stale draft');await page.getByLabel(/Reason/).fill('The proposed naming is not suitable');
  page.once('dialog',dialog=>dialog.accept());await page.reload();await page.getByLabel('Administrator evaluation').waitFor();assert.equal(await page.getByLabel('Administrator evaluation').inputValue(),'Retain this local stale draft');
  const initialRebase=page.getByRole('button',{name:'Keep text and rebase'});if(await initialRebase.count())await initialRebase.click();
  const concurrent=await admin({path:`/ai-work-items/${items[1]}/review/decision`,method:'POST',body:{expected_version:2,action:'reject',reason:'Concurrent administrator rejection'}});assert.equal(concurrent.status,200);
  await page.getByRole('button',{name:'Reject',exact:true}).click();await page.getByText(/The action conflicts with current state/).waitFor();assert.equal(await page.getByLabel('Administrator evaluation').inputValue(),'Retain this local stale draft');
  page.once('dialog',dialog=>dialog.accept());await page.reload();await page.getByText(/local draft predates the current Backend review state/).waitFor();assert.equal(await page.getByLabel('Administrator evaluation').inputValue(),'Retain this local stale draft');await page.getByRole('button',{name:'Discard local draft'}).click();
  const rejectedAlbum=await admin({path:'/albums/2'});assert.equal(rejectedAlbum.payload.data.album.title,'AI Fixture Album 2');assert.equal(rejectedAlbum.payload.data.album.status_name,'TEMPORARY');

  await openReview(page,items[2]);await page.getByRole('button',{name:'Begin review'}).click();await page.getByLabel(/Reason/).fill('Use a different sample and retry');await page.getByRole('button',{name:'Request rework'}).click();await page.getByText('ReworkRequested',{exact:true}).waitFor();
  const rework=await admin({path:`/ai-work-items/${items[2]}/review`});const successor=rework.payload.data.review.successor_work_item_uuid;assert.ok(successor);
  const cancelled=await admin({path:`/ai-work-items/${successor}/cancel`,method:'POST',body:{expected_version:1}});assert.equal(cancelled.status,200);

  for(const group of groups)await releaseGroup(page,group.group_uuid);
  await page.goto(`${fixture.origin}/#/ai-workspaces/${workspace.uuid}`);await page.getByRole('heading',{name:'Browser Review Workspace'}).waitFor();
  page.once('dialog',dialog=>dialog.accept('Completed browser review acceptance'));await page.getByRole('button',{name:'Close Workspace'}).click();await page.getByText('Closed',{exact:true}).waitFor();
  page.once('dialog',dialog=>dialog.accept('Archive completed audit record'));await page.getByRole('button',{name:'Archive Workspace'}).click();await page.getByText('Archived',{exact:true}).waitFor();
  await openReview(page,items[0]);assert.equal(await page.getByRole('button',{name:/Begin review|Approve selection|Reject|Request rework|Review Promotion/}).count(),0);assert.equal(await page.locator('.evidence-card').count(),8);
  const retired=await admin({path:'/workspace/albums'});assert.equal(retired.status,410);
  const operations=await admin({path:'/operations?operation_type=workspace_promotion'});assert.equal(operations.payload.data.length,1);
  await browser.close();console.log('UI-011D Workspace review browser acceptance: OK');
}finally{if(browser.isConnected())await browser.close();await fixture.stop();}
