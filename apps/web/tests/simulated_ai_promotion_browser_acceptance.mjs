/* UI-029 deterministic dispatch → simulated Worker → Review → Promotion drill. */
import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { createRequire } from 'node:module';
import { startBrowserFixture } from './browser_fixture.mjs';

const execFileAsync=promisify(execFile);const require=createRequire(import.meta.url);const {chromium}=require('playwright');
const fixture=await startBrowserFixture({scenario:'future-ai-workspace',roles:['admin','writer']});
const browser=await chromium.launch({headless:true});
const chosenName='Simulated Golden Morning';
async function connect(page){await page.goto(fixture.origin);await page.getByRole('button',{name:'Connect'}).click();await page.getByLabel('Approved device Token').fill(fixture.devices.admin.token);await page.getByRole('button',{name:'Validate and connect'}).click();await page.getByText(/DB OK/).waitFor();}

try{
  const configuration=await fixture.request('/ai-model-configurations',{method:'POST',role:'admin',body:{name:'No-model Workflow Fixture',model_identifier:'deterministic-fixture',model_file:'not-invoked.gguf',vision_prompt_version:'fixture-v1',writer_prompt_version:'fixture-w1',sample_count:8,context_size:4096,threads:1,gpu_layers:0,max_tokens:128,temperature:0,image_max_tokens:64}});
  assert.equal(configuration.status,201);const config=configuration.payload.data.configuration;
  const workspaceResponse=await fixture.request('/ai-workspaces',{method:'POST',role:'admin',body:{title:'No-model Promotion Drill'}});const workspace=workspaceResponse.payload.data.workspace;

  const page=await browser.newPage();await connect(page);await page.getByRole('link',{name:/AI Work Dispatch/}).click();
  await page.locator('[data-dispatch-album="1"]').check();await page.getByLabel(/No-model Workflow Fixture/).check();await page.getByRole('button',{name:'Preview dispatch'}).click();
  await page.getByLabel('I reviewed this zero-write preview.').check();await page.getByRole('button',{name:'Dispatch reviewed Albums'}).click();await page.getByText('Dispatched 1 Album Group(s). Album Status was unchanged.').waitFor();
  const groups=await fixture.request('/work-dispatch/groups?view=active',{role:'admin'});assert.equal(groups.payload.data.length,1);const group=groups.payload.data[0];const detail=await fixture.request(`/work-dispatch/groups/${group.uuid}`,{role:'admin'});const itemUuid=detail.payload.data.group.items[0].item_uuid;

  const manifest=await fixture.request(`/ai-work-items/${itemUuid}/evidence-manifest`,{method:'POST',role:'admin',body:{}});assert.equal(manifest.status,201);
  const claim=await fixture.request('/ai-work-items/claim',{method:'POST',role:'writer',body:{worker_kinds:['album_name_analysis'],lease_seconds:300}});assert.equal(claim.payload.data.item.uuid,itemUuid);
  const vision=await fixture.request(`/ai-work-items/${itemUuid}/results/vision`,{method:'POST',role:'writer',body:{schema_version:'curator://album-analysis/vision/v1',payload:{scene:'Deterministic fixture scene',people:{minimum:1,maximum:1},location_environment:'Studio',subjects:['fixture'],objects:['camera'],actions:['standing'],confidence:1,warnings:[]}}});assert.equal(vision.status,200);
  const writer=await fixture.request(`/ai-work-items/${itemUuid}/results/writer`,{method:'POST',role:'writer',body:{schema_version:'curator://album-analysis/writer/v1',payload:{album_summary:'Deterministic workflow-only result.',description:'No model was invoked.',suggested_names:[chosenName,'Simulated Silver Light','Simulated Quiet Studio','Simulated Portrait Study','Simulated Still Moment','Simulated Studio Memory']}}});assert.equal(writer.status,200);

  await page.goto(`${fixture.origin}/#/ai-work-items/${itemUuid}/review`);await page.getByRole('button',{name:'Begin review'}).click();await page.getByLabel(chosenName).check();await page.getByRole('button',{name:'Approve selection'}).click();await page.getByText('Approved',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Review Promotion'}).click();await page.getByLabel('I confirm this Album name and Status change.').check();await page.getByRole('button',{name:'Confirm & Rename'}).click();await page.getByText('Album name Promotion completed.').waitFor();

  const {stdout}=await execFileAsync('python3',['apps/web/tests/fixture_ai_promotion_state.py','--database',fixture.resources.database,'--album-id','1']);const durable=JSON.parse(stdout);
  assert.deepEqual(durable.album,{id:1,title:chosenName,status_name:'NAME_GENERATED'});assert.equal(durable.promotions,1);assert.equal(durable.promotion_operations,1);assert.equal(durable.approved_reviews,1);assert.equal(durable.result_stages,2);assert.equal(durable.reservations,1);
  await page.close();console.log('UI-029 simulated AI Promotion workflow drill: OK (no model invoked)');
}finally{await browser.close();await fixture.stop();}
