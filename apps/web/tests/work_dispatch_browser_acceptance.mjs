/* UI-011F Album-exclusive Work Dispatch browser acceptance. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const require=createRequire(import.meta.url); const {chromium}=require('playwright');
const fixture=await startBrowserFixture({scenario:'future-ai-workspace',roles:['admin','writer']});
const browser=await chromium.launch({headless:true});

async function connect(page,token){
  await page.goto(fixture.origin); await page.getByRole('button',{name:'Connect'}).click();
  await page.getByLabel('Approved device Token').fill(token); await page.getByRole('button',{name:'Validate and connect'}).click();
  await page.getByText(/DB OK/).waitFor();
}
async function createConfiguration(name,modelFile){
  const response=await fixture.request('/ai-model-configurations',{method:'POST',role:'admin',body:{
    name,model_identifier:name.toLowerCase().replaceAll(' ','-'),model_file:modelFile,
    vision_prompt_version:'v1',writer_prompt_version:'w1',sample_count:8,context_size:4096,
    threads:8,gpu_layers:20,max_tokens:800,temperature:0.2,image_max_tokens:384,
  }});
  assert.equal(response.status,201); return response.payload.data.configuration;
}

try{
  const configA=await createConfiguration('Fixture Balanced','balanced.gguf');
  const configB=await createConfiguration('Fixture Fast','fast.gguf');
  const before=(await fixture.request('/albums',{role:'admin'})).payload.data.map(item=>[item.id,item.status_id]);

  const denied=await browser.newPage(); await connect(denied,fixture.devices.writer.token);
  await denied.goto(`${fixture.origin}/#/work-dispatch`); await denied.getByRole('heading',{name:'Permission denied'}).waitFor();
  assert.equal(await denied.getByRole('link',{name:/AI Work Dispatch/}).isVisible(),false); await denied.close();

  const page=await browser.newPage(); await connect(page,fixture.devices.admin.token);
  await page.goto(`${fixture.origin}/#/work-dispatch`);await page.getByText('No Open AI Workspace exists.').waitFor();
  await page.getByRole('button',{name:'Select current page'}).click();assert.equal(await page.getByRole('button',{name:'Preview dispatch'}).isDisabled(),true);
  await page.getByRole('link',{name:'Create Workspace'}).click();await page.getByRole('heading',{name:'AI Workspaces'}).waitFor();
  await page.getByRole('button',{name:'+ New Workspace',exact:true}).click();await page.getByLabel('Workspace title').fill('Browser Dispatch Workspace');
  await page.getByRole('button',{name:'Create Workspace',exact:true}).click();await page.getByText('AI Workspace created.').waitFor();await page.getByRole('link',{name:'Browser Dispatch Workspace'}).waitFor();
  const workspace=(await fixture.request('/ai-workspaces',{role:'admin'})).payload.data.items[0];assert.equal(workspace.lifecycle_state,'Open');
  await page.getByRole('link',{name:/AI Work Dispatch/}).click(); await page.getByRole('heading',{name:'Album Work Dispatch'}).waitFor();
  await page.getByText('balanced.gguf',{exact:true}).waitFor();
  await page.getByText(/context 4096 · max 800 tokens · image 384 · temp 0.2 · 8 threads · 20 GPU layers/).first().waitFor();
  await page.locator('[data-dispatch-album="1"]').check(); await page.getByLabel(/Fixture Balanced/).check();
  await page.getByRole('button',{name:'Preview dispatch'}).click(); await page.getByRole('heading',{name:'Confirm Album Work Dispatch'}).waitFor();

  const competingPreview=await fixture.request('/work-dispatch/preview',{method:'POST',role:'admin',body:{worker_kind:'album_name_analysis',workspace_uuid:workspace.uuid,configuration_uuids:[configA.uuid],album_ids:[1]}});
  const competingExecution=await fixture.request('/work-dispatch/execute',{method:'POST',role:'admin',body:{preview_token:competingPreview.payload.data.preview.preview_token}});
  assert.equal(competingExecution.status,200); const competingGroup=competingExecution.payload.data.result.groups[0].group_uuid;
  await page.getByLabel('I reviewed this zero-write preview.').check(); await page.getByRole('button',{name:'Dispatch reviewed Albums'}).click();
  await page.getByText(/The action conflicts with current state/).waitFor();
  await page.getByRole('button',{name:'Cancel'}).click();
  await page.locator('#dispatchWorkerKind').selectOption('fixture_metadata_worker');
  await page.getByText('Fixture Album',{exact:true}).waitFor({state:'detached'});
  assert.equal(await page.locator('[data-dispatch-album="1"]').count(),0,'active reservation must hide the Album across Worker kinds');
  await page.locator('#dispatchWorkerKind').selectOption('album_name_analysis');
  const cancelledCompeting=await fixture.request(`/work-dispatch/groups/${competingGroup}/cancel`,{method:'POST',role:'admin',body:{expected_version:1,reason:'Complete race scenario'}});
  assert.equal(cancelledCompeting.status,200);

  await page.reload(); await page.getByRole('heading',{name:'Album Work Dispatch'}).waitFor();
  await page.getByRole('button',{name:'Select current page'}).click();
  await page.getByLabel(/Fixture Balanced/).check(); await page.getByLabel(/Fixture Fast/).check();
  await page.getByRole('button',{name:'Preview dispatch'}).click(); await page.getByText('6',{exact:true}).waitFor();
  await page.getByLabel('I reviewed this zero-write preview.').check(); await page.getByRole('button',{name:'Dispatch reviewed Albums'}).click();
  await page.getByText('Dispatched 3 Album Group(s). Album Status was unchanged.').waitFor();
  await page.getByRole('button',{name:'Worker Queue'}).click();
  const active=await fixture.request('/work-dispatch/groups?view=active',{role:'admin'});
  assert.equal(active.payload.data.length,3); assert.equal(active.payload.data.every(item=>item.item_count===2),true);
  assert.equal(active.payload.data.every(item=>item.items.length===2),true);
  await page.getByText('Waiting for Worker').first().waitFor();
  await page.getByText('Fixture Balanced').first().waitFor();
  await page.getByText('Fixture Fast').first().waitFor();
  await page.getByText(/Auto refresh on/).waitFor();
  assert.equal(await page.getByRole('button',{name:'Previous'}).count(),2,'pagination must be available above and below long content');
  assert.equal(await page.getByRole('button',{name:'First'}).count(),2);assert.equal(await page.getByRole('button',{name:'Last'}).count(),2);
  assert.equal(await page.getByLabel('Go to page').count(),2);assert.equal(await page.getByRole('button',{name:'Go',exact:true}).count(),2);

  const claim=await fixture.request('/ai-work-items/claim',{method:'POST',role:'writer',body:{worker_kinds:['album_name_analysis'],lease_seconds:300,wait_seconds:0}});
  assert.equal(claim.status,200);const failedItem=claim.payload.data.item;
  const failed=await fixture.request(`/ai-work-items/${failedItem.uuid}/fail`,{method:'POST',role:'writer',body:{error_code:'EVIDENCE_SAMPLE_INSUFFICIENT',message:'Album contains fewer usable images than the configured sample count.'}});
  assert.equal(failed.status,200);
  const failedGroup=active.payload.data.find(group=>group.items.some(item=>item.item_uuid===failedItem.uuid));assert.ok(failedGroup);
  await page.goto(`${fixture.origin}/#/work-dispatch/groups/${failedGroup.uuid}`);await page.getByText('Album contains fewer usable images than the configured sample count.').waitFor();
  await page.getByRole('button',{name:'Cancel',exact:true}).click();await page.getByRole('heading',{name:'Cancel failed Work Item?'}).waitFor();
  await page.getByRole('button',{name:'Cancel Work Item'}).click();await page.getByText(/Work Item cancelled. The Album remains reserved/).waitFor();
  assert.equal(await page.getByText('Cancelled',{exact:true}).count(),1);
  await page.getByText(/The Album is still reserved/).waitFor();

  for(const group of active.payload.data){
    const detail=await fixture.request(`/work-dispatch/groups/${group.uuid}`,{role:'admin'});
    for(const item of detail.payload.data.group.items){if(item.run_state==='Pending'||item.run_state==='Failed'){
      const cancelled=await fixture.request(`/ai-work-items/${item.item_uuid}/cancel`,{method:'POST',role:'admin',body:{expected_version:item.version}});assert.equal(cancelled.status,200);
    }}
  }
  await page.goto(`${fixture.origin}/#/work-dispatch`);await page.getByRole('button',{name:'Closure',exact:true}).click();
  await page.getByText('Cancelled',{exact:true}).first().waitFor();
  const closure=await fixture.request('/work-dispatch/groups?view=closure',{role:'admin'});assert.equal(closure.payload.data.length,3);
  const review=await fixture.request('/work-dispatch/groups?view=review',{role:'admin'});assert.equal(review.payload.data.length,0);
  const after=(await fixture.request('/albums',{role:'admin'})).payload.data.map(item=>[item.id,item.status_id]); assert.deepEqual(after,before);

  for(const group of active.payload.data){
    await page.goto(`${fixture.origin}/#/work-dispatch/groups/${group.uuid}`); await page.getByRole('heading',{name:'Dispatch Group'}).waitFor();
    assert.equal(await page.getByRole('columnheader',{name:'Current stage'}).isVisible(),true);
    page.once('dialog',dialog=>dialog.accept('Browser acceptance terminal cancellation'));
    const cancel=page.getByRole('button',{name:'Cancel Group',exact:true});if(await cancel.count())await cancel.click();else await page.getByRole('button',{name:'Release Group',exact:true}).click();await page.getByText('Released').waitFor();
  }
  await page.goto(`${fixture.origin}/#/work-dispatch`); await page.getByRole('heading',{name:'Album Work Dispatch'}).waitFor();
  assert.equal(await page.locator('[data-dispatch-album]').count(),3);
  await page.getByRole('button',{name:'History'}).click();
  const history=await fixture.request('/work-dispatch/groups?view=history',{role:'admin'});
  assert.equal(history.payload.data.length,4); assert.equal(history.payload.data.every(item=>item.group_state==='Released'),true);
  await browser.close(); console.log('UI-011F Work Dispatch browser acceptance: OK');
}finally{if(browser.isConnected())await browser.close();await fixture.stop();}
